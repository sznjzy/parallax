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

from backend.clustering.pipeline import (
    BOUNDARY_MARGIN,
    cluster_embeddings,
    assign_stable_cluster_ids,
    compute_boundary_flags,
    compute_evaluation,
    ClusteringOutput,
    EvaluationContract,
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
    labels: np.ndarray,
    centers: dict,
    boundary_flags: list[bool],
    label_to_uuid: dict,
    existing_nodes: list[Node] | None,
    rng: np.random.Generator,
) -> list[Node]:
    """
    Map clustering outputs to layout Node objects.

    Uses the canonical compute_boundary_flags() result (pre-computed by the
    caller) so there is exactly one implementation of boundary-detection logic.
    Secondary cluster and weight are derived from the same cosine-similarity
    computation used by compute_boundary_flags().
    """
    nodes: list[Node] = []
    existing_map = {n.doc_id: n for n in existing_nodes} if existing_nodes else {}

    cids = [cid for cid in centers.keys() if cid != -1]
    center_matrix = np.array([centers[cid] for cid in cids]) if len(cids) >= 2 else None

    for i, doc in enumerate(docs):
        doc_id = doc["id"]
        label = labels[i]
        emb = embeddings[i]
        is_boundary = boundary_flags[i]

        # --- Cluster ID and secondary cluster ---
        if label == -1:
            cluster_id_str = f"noise-{doc_id}"
            sec_cluster: str | None = None
            sec_weight = 0.0
            is_boundary = False
        else:
            cluster_id_str = label_to_uuid[label]
            is_boundary, sec_lbl, sec_weight = boundary_flags[i]
            sec_cluster = label_to_uuid.get(sec_lbl) if sec_lbl is not None else None

        # --- Position ---
        if doc_id in existing_map:
            # Incremental update: keep old positions, update cluster, set anchored.
            old_node = existing_map[doc_id]
            node = Node(
                doc_id=doc_id,
                cluster_id=cluster_id_str,
                x=old_node.x,
                y=old_node.y,
                velocity_x=0.0,
                velocity_y=0.0,
                is_anchored=True,
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
                is_anchored=False,
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
) -> tuple[list[Node], tuple[int, float], np.ndarray]:
    """
    Cluster + layout one phase. Returns (nodes_after_sim, (iters, energy), labels).
    """
    labels, centers = cluster_embeddings(embeddings)
    boundary_flags = compute_boundary_flags(embeddings, labels, centers)
    label_to_uuid = assign_stable_cluster_ids(docs, labels, STATE_FILE)

    nodes = _map_to_nodes(
        docs, embeddings, labels, centers, boundary_flags,
        label_to_uuid, existing_nodes, rng,
    )

    # Wire compute_home_positions into simulate() — the validated stable mode.
    cluster_ids_in_phase = list({n.cluster_id for n in nodes})
    home_positions = compute_home_positions(cluster_ids_in_phase)
    # Noise nodes (cluster_id like "noise-<doc_id>") won't be in home_positions;
    # fall back to canvas centre for those.
    for n in nodes:
        if n.cluster_id not in home_positions:
            home_positions[n.cluster_id] = (CANVAS_WIDTH / 2.0, CANVAS_HEIGHT / 2.0)

    iters, energy = simulate(nodes, max_iters=max_iters, cluster_home_positions=home_positions)
    return nodes, (iters, energy), labels


# ---------------------------------------------------------------------------
# Public callable — used by the API endpoint
# ---------------------------------------------------------------------------

def _ingest_corpus(
    pdf_files: list[Path], model: Any, is_live_api: bool = True
) -> tuple[list[dict], list[np.ndarray], list[dict], dict[str, list[np.ndarray]]]:
    """
    Ingest PDFs into embedded chunks.
    Shared by both run_pipeline() and main() stress test.
    """
    docs_all: list[dict] = []
    embeddings_list: list[np.ndarray] = []
    per_chunk_store: dict[str, list[np.ndarray]] = {}
    skipped: list[dict] = []

    for pdf_path in pdf_files:
        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            skipped.append({"filename": pdf_path.name, "reason": "PDF parse failed or empty"})
            logger.warning("Skipping %s: no text extracted", pdf_path.name)
            continue

        chunks = chunk_text(text)
        if not chunks:
            skipped.append({"filename": pdf_path.name, "reason": "No text chunks after chunking"})
            continue

        doc_id = f"doc-{pdf_path.name}"
        canvas_vec, chunk_vecs = embed_document_chunks(model, chunks)

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

    return docs_all, embeddings_list, skipped, per_chunk_store


def run_pipeline(pdf_folder: Path, seed: int = 42) -> dict:
    """
    Run the full single-pass pipeline on every PDF in ``pdf_folder``.

    Does a straightforward single clustering pass over all PDFs present —
    no hardcoded holdback split.  Dropping different PDFs into the folder
    behaves exactly as a caller would expect.

    Returns a dict with three keys:
        "nodes"             : list[dict] — layout + clustering output contract
        "evaluation"        : dict | None — EvaluationContract for this run
        "skipped_documents" : list[dict] — PDFs that could not be parsed

    Raises:
        ValueError — if no PDFs are found or none yield extractable text.
    """
    rng = np.random.default_rng(seed=seed)

    pdf_files = sorted(pdf_folder.glob("*.pdf"))
    if not pdf_files:
        raise ValueError(f"No PDF files found in '{pdf_folder}'")

    # --- EMBEDDING (all docs up front) ---
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

    # --- SINGLE-PASS CLUSTER + LAYOUT ---
    logger.info("Clustering %d documents...", len(docs_all))
    
    nodes, (iters, energy), labels = _run_phase(
        docs_all, embeddings_all, rng, existing_nodes=None, max_iters=MAX_ITERATIONS_INITIAL
    )
    
    logger.info("Layout converged in %d iterations (energy=%.4f)", iters, energy)

    # --- EVALUATION ---
    evaluation = compute_evaluation(embeddings_all, labels)

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
            # constraint_satisfaction_rate is None until manual-correction /
            # constraint-storage is implemented (see PROGRESS.md Next Steps).
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

    This does NOT call run_pipeline() because it needs to inspect intermediate
    state (p1_nodes positions before Phase 2 overwrites them).  The live API
    endpoint uses run_pipeline() instead.
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

    p1_nodes, (iters_p1, energy_p1), p1_labels = _run_phase(
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

    p2_nodes, (iters_p2, energy_p2), p2_labels = _run_phase(
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
    p2_eval = compute_evaluation(p2_embeddings, p2_labels)
    if p2_eval:
        print(f"\nPhase 2 Evaluation:")
        print(f"  Silhouette score: {p2_eval.silhouette_score:.4f}")
        print(f"  Num clusters:     {p2_eval.num_clusters}")


if __name__ == "__main__":
    main()
