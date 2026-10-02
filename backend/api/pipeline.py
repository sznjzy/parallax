"""
pipeline.py

Integration script chaining embedding, clustering, and layout engines.

Public API
----------
    run_pipeline(pdf_folder: Path, seed: int = 42) -> dict
        Runs the full single-pass pipeline on every PDF in `pdf_folder` and
        returns a dict with three sibling keys:
            {
                "nodes":             list[dict],   # layout + clustering output contract
                "evaluation":        dict | None,  # EvaluationContract (clustering)
                "skipped_documents": list[dict]    # PDFs that failed to parse
            }

    main()
        CLI entry point — runs the two-phase Phase 1 / Phase 2 stress-test
        (papers held back for Phase 2, then added incrementally) on
        data/sample_docs/.  This is the demo / regression-test path; the live
        API endpoint calls run_pipeline() instead.

Output contract (per node):
    doc_id, x, y, velocity_x, velocity_y, is_anchored,   <- incremental-layout
    cluster_id, is_boundary_document                       <- constrained-clustering
"""

import logging
import sys
import uuid
import numpy as np
import json
from typing import Any
from pathlib import Path

logger = logging.getLogger(__name__)

from backend.embeddings.pipeline import (
    extract_text_from_pdf,
    chunk_text,
    embed_document_chunks,
    load_model,
    generate_embeddings,
    EmbeddingOutput,
    MODEL_NAME,
)
from backend.embeddings.embedding_cache import (
    get_cached_embedding,
    save_cached_embedding,
    is_cached,
)

from backend.clustering.pipeline import (
    BOUNDARY_MARGIN,
    cluster_embeddings,
    assign_stable_cluster_ids,
    compute_boundary_flags,
    compute_evaluation,
    run_constraint_aware_clustering,
    ClusteringOutput,
    EvaluationContract,
)
from backend.clustering.constraints import (
    apply_constraints,
    evaluate_constraint_satisfaction,
)

from backend.layout.physics import (
    Node,
    simulate,
    compute_home_positions,
    MAX_ITERATIONS_INITIAL,
    MAX_ITERATIONS,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    CLUSTER_INIT_SPREAD,
)

STATE_FILE = Path(__file__).parent / "cluster_mapping.json"

# Default document folder — same as spike_clustering uses; defined here so API
# code never needs to import from a test file.
SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _map_to_nodes(
    docs: list[dict],
    embeddings: np.ndarray,
    doc_cluster_ids: list[str],
    boundary_flags: list[tuple[bool, str | None, float]],
    existing_nodes: list[Node] | None,
    rng: np.random.Generator,
    forced_assignments: dict[str, str] | None = None,
) -> list[Node]:
    """
    Map clustering outputs to layout Node objects.
    """
    nodes: list[Node] = []
    existing_map = {n.doc_id: n for n in existing_nodes} if existing_nodes else {}

    for i, doc in enumerate(docs):
        doc_id = doc["id"]
        cluster_id_str = doc_cluster_ids[i]
        is_constrained = bool(forced_assignments and doc_id in forced_assignments)
        is_boundary, sec_cluster, sec_weight = boundary_flags[i]

        if doc_id in existing_map:
            # Incremental update: keep old positions, update cluster.
            old_node = existing_map[doc_id]
            node = Node(
                doc_id=doc_id,
                cluster_id=cluster_id_str,
                x=old_node.x,
                y=old_node.y,
                velocity_x=0.0,
                velocity_y=0.0,
                is_anchored=is_constrained,
                is_boundary_document=is_boundary,
                secondary_cluster_id=sec_cluster,
                secondary_weight=sec_weight,
            )
        else:
            # New node: random Gaussian near canvas centre.
            node = Node(
                doc_id=doc_id,
                cluster_id=cluster_id_str,
                x=CANVAS_WIDTH / 2.0 + float(rng.normal(0, CLUSTER_INIT_SPREAD)),
                y=CANVAS_HEIGHT / 2.0 + float(rng.normal(0, CLUSTER_INIT_SPREAD)),
                is_anchored=is_constrained,
                is_boundary_document=is_boundary,
                secondary_cluster_id=sec_cluster,
                secondary_weight=sec_weight,
            )
        nodes.append(node)

    return nodes


def _calculate_stability(
    old_nodes: list[Node], new_nodes: list[Node]
) -> tuple[float, float]:
    old_map = {n.doc_id: n for n in old_nodes}
    displacements = []
    for new_n in new_nodes:
        if new_n.doc_id in old_map:
            old_n = old_map[new_n.doc_id]
            dist = np.sqrt((new_n.x - old_n.x) ** 2 + (new_n.y - old_n.y) ** 2)
            displacements.append(dist)
    if displacements:
        return float(np.mean(displacements)), float(np.max(displacements))
    return 0.0, 0.0


def _run_phase(
    docs: list[dict],
    embeddings: np.ndarray,
    rng: np.random.Generator,
    existing_nodes: list[Node] | None,
    max_iters: int,
    forced_assignments: dict[str, str] | None = None,
) -> tuple[list[Node], tuple[int, float], dict]:
    """
    Cluster + layout one phase using true constraint-aware clustering.
    Returns: (nodes_after_sim, (iters, energy), clustering_result).
    """
    clustering_res = run_constraint_aware_clustering(
        docs, embeddings, state_file=STATE_FILE, forced_assignments=forced_assignments
    )
    doc_cluster_ids = clustering_res["doc_cluster_ids"]
    boundary_flags = clustering_res["boundary_flags"]

    nodes = _map_to_nodes(
        docs, embeddings, doc_cluster_ids, boundary_flags,
        existing_nodes, rng,
        forced_assignments=forced_assignments,
    )

    # Wire compute_home_positions into simulate() — the validated stable mode.
    cluster_ids_in_phase = list({n.cluster_id for n in nodes})
    home_positions = compute_home_positions(cluster_ids_in_phase)
    for n in nodes:
        if n.cluster_id not in home_positions:
            home_positions[n.cluster_id] = (CANVAS_WIDTH / 2.0, CANVAS_HEIGHT / 2.0)

    iters, energy = simulate(nodes, max_iters=max_iters, cluster_home_positions=home_positions)
    return nodes, (iters, energy), clustering_res


# ---------------------------------------------------------------------------
# Public callable — used by the API endpoint
# ---------------------------------------------------------------------------

def _ingest_corpus(
    pdf_files: list[Path], model: Any, is_live_api: bool = True
) -> tuple[list[dict], list[np.ndarray], list[dict], dict[str, list[np.ndarray]]]:
    """
    Ingest PDFs into embedded chunks, using the disk cache where possible.

    Cache behaviour:
        - If a .npy cache entry exists for this exact PDF (keyed by SHA-256),
          the stored canvas vector is loaded directly — no model inference.
        - Otherwise the document is embedded and the result is saved to cache.

    Shared by both run_pipeline() and main() stress test.
    """
    docs_all: list[dict] = []
    embeddings_list: list[np.ndarray] = []
    per_chunk_store: dict[str, list[np.ndarray]] = {}
    skipped: list[dict] = []

    cached_count = 0
    embed_count = 0

    for pdf_path in pdf_files:
        doc_id = f"doc-{pdf_path.name}"

        # ── Try cache first ───────────────────────────────────────────
        cached_vec = get_cached_embedding(pdf_path)
        if cached_vec is not None:
            docs_all.append({"id": doc_id, "filename": pdf_path.name})
            embeddings_list.append(cached_vec)
            cached_count += 1
            logger.debug("Cache HIT  %s", pdf_path.name)
            continue

        # ── Cache miss — extract text and embed ───────────────────────
        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            skipped.append({"filename": pdf_path.name, "reason": "PDF parse failed or empty"})
            logger.warning("Skipping %s: no text extracted", pdf_path.name)
            continue

        chunks = chunk_text(text)
        if not chunks:
            skipped.append({"filename": pdf_path.name, "reason": "No text chunks after chunking"})
            continue

        canvas_vec, chunk_vecs = embed_document_chunks(model, chunks)

        # Persist to cache for next run
        save_cached_embedding(pdf_path, canvas_vec)
        embed_count += 1

        doc_dict = {"id": doc_id, "filename": pdf_path.name}
        if is_live_api:
            # EmbeddingOutput typed contract
            doc_dict["embedding_output"] = EmbeddingOutput(
                doc_id=doc_id,
                embedding=canvas_vec.tolist(),
                model_name=MODEL_NAME,
                normalized=True,
                source_type="pdf",
            )
            per_chunk_store[doc_id] = chunk_vecs

        docs_all.append(doc_dict)
        embeddings_list.append(canvas_vec)
        logger.debug("Embedded %s (%d chunks)", pdf_path.name, len(chunks))

    logger.info(
        "Ingestion complete: %d cached, %d newly embedded, %d skipped",
        cached_count, embed_count, len(skipped),
    )
    return docs_all, embeddings_list, skipped, per_chunk_store


def run_pipeline(
    pdf_folder: Path,
    seed: int = 42,
    doc_filter: set[str] | None = None,
) -> dict:
    """
    Run the full single-pass pipeline on PDFs in ``pdf_folder``.

    Parameters
    ----------
    pdf_folder : Path
        Folder containing .pdf files.
    seed : int
        RNG seed for reproducible layout.
    doc_filter : set[str] | None
        If provided, only the filenames in this set are processed.
        e.g. {"paper1.pdf", "paper3.pdf"}.  If None, all PDFs are run.

    Returns a dict with three keys:
        "nodes"             : list[dict] — layout + clustering output contract
        "evaluation"        : dict | None — EvaluationContract for this run
        "skipped_documents" : list[dict] — PDFs that could not be parsed

    Raises:
        ValueError — if no PDFs are found or none yield extractable text.
    """
    rng = np.random.default_rng(seed=seed)

    all_pdf_files = sorted(pdf_folder.glob("*.pdf"))
    if not all_pdf_files:
        raise ValueError(f"No PDF files found in '{pdf_folder}'")

    # Apply optional document filter
    if doc_filter:
        pdf_files = [f for f in all_pdf_files if f.name in doc_filter]
        if not pdf_files:
            raise ValueError(
                f"None of the requested documents were found in '{pdf_folder}'. "
                f"Requested: {sorted(doc_filter)}"
            )
        logger.info("doc_filter active: running %d/%d PDFs", len(pdf_files), len(all_pdf_files))
    else:
        pdf_files = all_pdf_files

    # --- EMBEDDING (with cache) ---
    logger.info("Loading embedding model...")
    model = load_model()

    docs_all, embeddings_list, skipped, per_chunk_store = _ingest_corpus(
        pdf_files, model, is_live_api=True
    )

    if not docs_all:
        raise ValueError(
            "No text could be extracted from any PDF in the folder. "
            f"Skipped: {[s['filename'] for s in skipped]}"
        )

    embeddings_all = np.array(embeddings_list)

    # Apply active user constraints
    unconstrained_docs, unconstrained_indices, forced_assignments = apply_constraints(
        docs_all, embeddings_list
    )

    # --- SINGLE-PASS CONSTRAINT-AWARE CLUSTER + LAYOUT ---
    logger.info("Clustering %d documents (%d constrained)...", len(docs_all), len(forced_assignments))
    
    nodes, (iters, energy), clustering_res = _run_phase(
        docs_all, embeddings_all, rng, existing_nodes=None, max_iters=MAX_ITERATIONS_INITIAL,
        forced_assignments=forced_assignments,
    )
    
    logger.info("Layout converged in %d iterations (energy=%.4f)", iters, energy)

    evaluation = clustering_res["evaluation"]

    # --- SERIALISE ---
    result_nodes = []
    for node in nodes:
        result_nodes.append({
            # incremental-layout SKILL.md Output Contract
            "doc_id": node.doc_id,
            "x": round(node.x, 4),
            "y": round(node.y, 4),
            "velocity_x": round(node.velocity_x, 6),
            "velocity_y": round(node.velocity_y, 6),
            "is_anchored": bool(node.is_anchored),
            # constrained-clustering SKILL.md Output Contract additions
            "cluster_id": node.cluster_id,
            "is_boundary_document": bool(node.is_boundary_document),
        })

    eval_dict: dict | None = None
    if evaluation is not None:
        eval_dict = {
            "silhouette_score": evaluation.silhouette_score,
            "num_clusters": evaluation.num_clusters,
            "constraint_satisfaction_rate": evaluation.constraint_satisfaction_rate,
            "num_constraints_applied": evaluation.num_constraints_applied,
            "num_constraints_violated": evaluation.num_constraints_violated,
        }

    return {
        "nodes": result_nodes,
        "evaluation": eval_dict,
        "skipped_documents": skipped,
    }


# ---------------------------------------------------------------------------
# CLI / demo entry point — Phase 1 / Phase 2 stress-test
# ---------------------------------------------------------------------------

def main():
    """
    CLI stress-test: runs the Phase 1 / Phase 2 holdback experiment that was
    used to validate stability in PROGRESS.md.
    """
    logging.basicConfig(level=logging.WARNING)  # suppress library noise in CLI output
    print("==================================================")
    print("Parallax Pipeline — Phase 1 / Phase 2 Stress Test")
    print("==================================================\n")

    if STATE_FILE.exists():
        STATE_FILE.unlink()

    rng = np.random.default_rng(seed=42)

    pdf_files = sorted(list(SAMPLE_DOCS_DIR.glob("*.pdf")))
    if not pdf_files:
        print("[FAIL] No PDFs found.")
        return

    # Hold back the same set as the validated integration test.
    holdback_names = {
        "paper14.pdf", "paper15.pdf", "paper16.pdf",
        "paper17.pdf", "paper18.pdf", "paper19.pdf", "paper21.pdf",
    }
    phase2_files_names = {f.name for f in pdf_files if f.name in holdback_names}

    print(f"[Phase 1] {len(pdf_files) - len(phase2_files_names)} files.")
    print(f"[Phase 2] Holding back {len(phase2_files_names)}: {sorted(phase2_files_names)}\n")

    print("1. INGESTION & EMBEDDING")
    print("-" * 50)
    model = load_model()

    docs_all, embeddings_list, _, _ = _ingest_corpus(
        pdf_files, model, is_live_api=False
    )

    embeddings_all = np.array(embeddings_list)
    doc_data = {docs_all[i]["id"]: embeddings_list[i] for i in range(len(docs_all))}

    # --- PHASE 1 ---
    print("\n==================================================")
    print("PHASE 1: Initial Layout")
    print("==================================================")
    p1_docs = [d for d in docs_all if d["filename"] not in holdback_names]
    p1_embeddings = np.array([doc_data[d["id"]] for d in p1_docs])

    p1_nodes, (iters_p1, energy_p1), p1_res = _run_phase(
        p1_docs, p1_embeddings, rng, existing_nodes=None, max_iters=MAX_ITERATIONS_INITIAL
    )

    print(f"\nSimulating Phase 1 ({len(p1_nodes)} nodes)...")
    print(f"Converged in {iters_p1} iterations (Final Energy: {energy_p1:.4f})")

    print("\nPhase 1 Output Contract (Positions):")
    for n in p1_nodes:
        fn = n.doc_id.replace("doc-", "")
        print(f"  {fn:12s} | Cluster: {n.cluster_id:10s} | pos: ({n.x:6.1f}, {n.y:6.1f}) | boundary: {n.is_boundary_document}")

    # --- PHASE 2 ---
    print("\n==================================================")
    print("PHASE 2: Incremental Update (Adding new nodes)")
    print("==================================================")
    p2_docs = docs_all
    p2_embeddings = embeddings_all

    p2_nodes, (iters_p2, energy_p2), p2_res = _run_phase(
        p2_docs, p2_embeddings, rng, existing_nodes=p1_nodes, max_iters=MAX_ITERATIONS
    )

    print(f"\nSimulating Phase 2 ({len(p2_nodes)} nodes, {len(p1_nodes)} anchored)...")
    print(f"Converged in {iters_p2} iterations (Final Energy: {energy_p2:.4f})")

    avg_disp, max_disp = _calculate_stability(p1_nodes, p2_nodes)
    print(f"\nStability Metrics:")
    print(f"  Avg existing node displacement: {avg_disp:.4f} units")
    print(f"  Max existing node displacement: {max_disp:.4f} units")

    print("\nPhase 2 Output Contract (Final Positions):")
    for n in p2_nodes:
        fn = n.doc_id.replace("doc-", "")
        is_new = fn in holdback_names
        marker = "[NEW]" if is_new else ""
        boundary = "[BOUNDARY]" if n.is_boundary_document else ""
        print(f"  {fn:12s} {marker:5s} {boundary:10s} | Cluster: {n.cluster_id:10s} | pos: ({n.x:6.1f}, {n.y:6.1f})")

    # Evaluation
    p2_eval = p2_res["evaluation"]
    if p2_eval:
        print(f"\nPhase 2 Evaluation:")
        if p2_eval.silhouette_score is not None:
            print(f"  Silhouette score: {p2_eval.silhouette_score:.4f}")
        else:
            print(f"  Silhouette score: None")
        print(f"  Num clusters:     {p2_eval.num_clusters}")


if __name__ == "__main__":
    main()
