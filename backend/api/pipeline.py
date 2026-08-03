"""
pipeline.py

Integration script chaining embedding, clustering, and layout engines.
Runs Phase 1 (Initial Layout) and Phase 2 (Incremental Update).

Public API
----------
    run_pipeline(pdf_folder: Path) -> list[dict]
        Runs the full two-phase pipeline on every PDF in `pdf_folder` and
        returns the final node list as JSON-serialisable dicts matching the
        combined output contract (layout + clustering fields).
"""

import sys
import uuid
import numpy as np
import random
import json
import os
from pathlib import Path

# Fix path to allow importing backend modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.embeddings.pipeline import (
    extract_text_from_pdf,
    chunk_text,
    load_model,
    generate_embeddings
)

from backend.clustering.pipeline import (
    cluster_embeddings,
    assign_stable_cluster_ids
)

from backend.layout.physics import (
    Node,
    simulate,
    MAX_ITERATIONS_INITIAL,
    MAX_ITERATIONS,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    CLUSTER_INIT_SPREAD
)

MARGIN = 0.05
STATE_FILE = Path(__file__).parent / "cluster_mapping.json"

# Default document folder — same as spike_clustering uses; defined here so API
# code never needs to import from a test file.
SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs"


# ---------------------------------------------------------------------------
# Internal helpers (unchanged from original script logic)
# ---------------------------------------------------------------------------

def map_to_nodes(docs, embeddings, labels, centers, existing_nodes=None):
    """
    Map clustering outputs to layout Node objects.
    Resolves contract mismatches (boundary calculations, noise handling).
    """
    nodes = []
    existing_map = {n.doc_id: n for n in existing_nodes} if existing_nodes else {}

    label_to_uuid = assign_stable_cluster_ids(docs, labels, STATE_FILE)

    cids = [cid for cid in centers.keys() if cid != -1]
    if len(cids) < 2:
        center_matrix = np.array([centers[cid] for cid in cids]) if cids else np.array([])
    else:
        center_matrix = np.array([centers[cid] for cid in cids])

    for i, doc in enumerate(docs):
        doc_id = doc["id"]
        label = labels[i]
        emb = embeddings[i]

        # Handle Noise
        if label == -1:
            cluster_id_str = f"noise-{doc_id}"
            is_boundary = False
            sec_cluster = None
            sec_weight = 0.0
        else:
            cluster_id_str = label_to_uuid[label]
            is_boundary = False
            sec_cluster = None
            sec_weight = 0.0

            # Calculate boundary properties if multiple clusters exist
            if len(cids) >= 2:
                similarities = np.dot(center_matrix, emb)
                sorted_indices = np.argsort(similarities)[::-1]
                
                best_idx = sorted_indices[0]
                second_best_idx = sorted_indices[1]
                
                best_sim = similarities[best_idx]
                second_best_sim = similarities[second_best_idx]
                
                if (best_sim - second_best_sim) < MARGIN:
                    is_boundary = True
                    sec_lbl = cids[second_best_idx]
                    sec_cluster = label_to_uuid[sec_lbl]
                    
                    # Normalize weights
                    total_sim = max(0.0001, best_sim + second_best_sim)
                    sec_weight = second_best_sim / total_sim

        if doc_id in existing_map:
            # Incremental update: keep old positions, update cluster, set anchored
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
                secondary_weight=sec_weight
            )
        else:
            # Initial layout / New node: random gaussian near center
            node = Node(
                doc_id=doc_id,
                cluster_id=cluster_id_str,
                x=CANVAS_WIDTH/2.0 + random.gauss(0, CLUSTER_INIT_SPREAD),
                y=CANVAS_HEIGHT/2.0 + random.gauss(0, CLUSTER_INIT_SPREAD),
                is_anchored=False,
                is_boundary_document=is_boundary,
                secondary_cluster_id=sec_cluster,
                secondary_weight=sec_weight
            )
        nodes.append(node)
        
    return nodes

def calculate_stability(old_nodes, new_nodes):
    old_map = {n.doc_id: n for n in old_nodes}
    displacements = []
    for new_n in new_nodes:
        if new_n.doc_id in old_map:
            old_n = old_map[new_n.doc_id]
            dist = np.sqrt((new_n.x - old_n.x)**2 + (new_n.y - old_n.y)**2)
            displacements.append(dist)
    if displacements:
        return np.mean(displacements), np.max(displacements)
    return 0.0, 0.0


# ---------------------------------------------------------------------------
# Public callable — used by the API endpoint
# ---------------------------------------------------------------------------

def run_pipeline(pdf_folder: Path) -> list[dict]:
    """
    Run the full two-phase pipeline on every PDF in `pdf_folder`.

    Phase 1: embed + cluster + layout all documents in the folder.
    Phase 2: re-cluster the full set (identical here since we use all docs),
             anchoring Phase 1 positions to measure stability and persist
             stable cluster UUIDs.

    Returns a list of node dicts matching the combined output contract:
        doc_id, x, y, velocity_x, velocity_y, is_anchored,
        cluster_id, is_boundary_document

    Raises:
        ValueError  — if no PDFs are found or none yield extractable text.
    """
    pdf_files = sorted(pdf_folder.glob("*.pdf"))
    if not pdf_files:
        raise ValueError(f"No PDF files found in '{pdf_folder}'")

    # Hold back the same set as the validated integration test so results are
    # comparable to known baselines.  This preserves the Phase 1 / Phase 2
    # split that was regression-tested.
    holdback_names = {
        "paper14.pdf", "paper15.pdf", "paper16.pdf",
        "paper17.pdf", "paper18.pdf", "paper19.pdf", "paper21.pdf"
    }
    phase1_files = [f for f in pdf_files if f.name not in holdback_names]

    # --- EMBEDDING (all docs up front) ---
    model = load_model()

    docs_all = []
    for pdf_path in pdf_files:
        text = extract_text_from_pdf(pdf_path)
        if text.strip():
            chunks = chunk_text(text)
            if chunks:
                docs_all.append({
                    "id": f"doc-{pdf_path.name}",
                    "filename": pdf_path.name,
                    "text": chunks[0]
                })

    if not docs_all:
        raise ValueError("No text could be extracted from any PDF in the folder.")

    texts = [d["text"] for d in docs_all]
    embeddings_all = generate_embeddings(model, texts)

    doc_data = {docs_all[i]["id"]: (docs_all[i], embeddings_all[i]) for i in range(len(docs_all))}

    # --- PHASE 1 ---
    p1_docs = [d for d in docs_all if d["filename"] not in holdback_names]
    p1_embeddings = np.array([doc_data[d["id"]][1] for d in p1_docs])

    p1_labels, p1_centers = cluster_embeddings(p1_embeddings)
    p1_nodes = map_to_nodes(p1_docs, p1_embeddings, p1_labels, p1_centers)
    simulate(p1_nodes, max_iters=MAX_ITERATIONS_INITIAL)

    # --- PHASE 2 ---
    p2_docs = docs_all
    p2_embeddings = embeddings_all

    p2_labels, p2_centers = cluster_embeddings(p2_embeddings)
    p2_nodes = map_to_nodes(p2_docs, p2_embeddings, p2_labels, p2_centers, existing_nodes=p1_nodes)
    simulate(p2_nodes, max_iters=MAX_ITERATIONS)

    # Serialise to combined output contract
    result = []
    for node in p2_nodes:
        result.append({
            # incremental-layout SKILL.md Output Contract
            "doc_id": node.doc_id,
            "x": round(node.x, 4),
            "y": round(node.y, 4),
            "velocity_x": round(node.velocity_x, 6),
            "velocity_y": round(node.velocity_y, 6),
            "is_anchored": node.is_anchored,
            # constrained-clustering SKILL.md Output Contract additions
            "cluster_id": node.cluster_id,
            "is_boundary_document": node.is_boundary_document,
        })

    return result


# ---------------------------------------------------------------------------
# CLI entry point (unchanged behaviour)
# ---------------------------------------------------------------------------

def main():
    print("==================================================")
    print("Parallax Pipeline Integration Test")
    print("==================================================\n")
    
    if STATE_FILE.exists():
        STATE_FILE.unlink()

    pdf_files = sorted(list(SAMPLE_DOCS_DIR.glob("*.pdf")))
    if not pdf_files:
        print("[FAIL] No PDFs found.")
        return

    # Hold back paper14, 15, 16, and all compiler papers EXCEPT paper20.
    holdback_names = {
        "paper14.pdf", "paper15.pdf", "paper16.pdf",
        "paper17.pdf", "paper18.pdf", "paper19.pdf", "paper21.pdf"
    }
    phase1_files = [f for f in pdf_files if f.name not in holdback_names]
    phase2_files = [f for f in pdf_files if f.name in holdback_names]

    print(f"[Phase 1] Using {len(phase1_files)} files.")
    print(f"[Phase 2] Holding back {len(phase2_files)} files: {[f.name for f in phase2_files]}\n")

    print("1. INGESTION & EMBEDDING")
    print("-" * 50)
    model = load_model()
    
    docs_all = []
    for pdf_path in pdf_files:
        text = extract_text_from_pdf(pdf_path)
        if text.strip():
            chunks = chunk_text(text)
            if chunks:
                docs_all.append({
                    "id": f"doc-{pdf_path.name}",
                    "filename": pdf_path.name,
                    "text": chunks[0]
                })

    texts = [d["text"] for d in docs_all]
    embeddings_all = generate_embeddings(model, texts)
    
    doc_data = {docs_all[i]["id"]: (docs_all[i], embeddings_all[i]) for i in range(len(docs_all))}
    
    # --- PHASE 1 ---
    print("\n==================================================")
    print("PHASE 1: Initial Layout")
    print("==================================================")
    p1_docs = [d for d in docs_all if d["filename"] not in holdback_names]
    p1_embeddings = np.array([doc_data[d["id"]][1] for d in p1_docs])
    
    p1_labels, p1_centers = cluster_embeddings(p1_embeddings)
    p1_nodes = map_to_nodes(p1_docs, p1_embeddings, p1_labels, p1_centers)
    
    print(f"\nSimulating Phase 1 ({len(p1_nodes)} nodes)...")
    iters_p1, energy_p1 = simulate(p1_nodes, max_iters=MAX_ITERATIONS_INITIAL)
    print(f"Converged in {iters_p1} iterations (Final Energy: {energy_p1:.4f})")
    
    print("\nPhase 1 Output Contract (Positions):")
    for n in p1_nodes:
        fn = n.doc_id.replace("doc-", "")
        print(f"  {fn:12s} | Cluster: {n.cluster_id:10s} | pos: ({n.x:6.1f}, {n.y:6.1f}) | anchor: {n.is_anchored}")
        
    # --- PHASE 2 ---
    print("\n==================================================")
    print("PHASE 2: Incremental Update (Adding new nodes)")
    print("==================================================")
    p2_docs = docs_all
    p2_embeddings = embeddings_all
    
    p2_labels, p2_centers = cluster_embeddings(p2_embeddings)
    p2_nodes = map_to_nodes(p2_docs, p2_embeddings, p2_labels, p2_centers, existing_nodes=p1_nodes)
    
    print(f"\nSimulating Phase 2 ({len(p2_nodes)} nodes, {len(p1_nodes)} anchored)...")
    iters_p2, energy_p2 = simulate(p2_nodes, max_iters=MAX_ITERATIONS)
    print(f"Converged in {iters_p2} iterations (Final Energy: {energy_p2:.4f})")
    
    avg_disp, max_disp = calculate_stability(p1_nodes, p2_nodes)
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


if __name__ == "__main__":
    main()
