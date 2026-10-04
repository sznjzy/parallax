"""
backend/evaluation/eval_incremental_e3.py

Experiment E3: Incremental Stability Evaluation.
Evaluates cluster identity preservation (ADR-003) and spatial layout stability (ADR-004)
across explicit multi-stage additions on the real 34-paper research corpus.
"""

import math
import tempfile
import numpy as np
from pathlib import Path

from backend.clustering.pipeline import (
    run_constraint_aware_clustering,
    assign_stable_cluster_ids,
)
from backend.layout.physics import (
    Node,
    simulate,
    compute_home_positions,
)
from backend.embeddings.embedding_cache import get_cached_embedding


# Explicitly documented stage split
STAGE_0_DOCS = [
    "paper1.pdf", "paper2.pdf", "paper4.pdf", "paper5.pdf", "paper6.pdf",
    "paper7.pdf", "paper8.pdf", "paper9.pdf", "paper10.pdf", "paper11.pdf",
    "paper15.pdf", "paper17.pdf", "paper18.pdf", "paper19.pdf", "paper20.pdf",
    "paper23.pdf", "paper24.pdf", "paper25.pdf", "paper29.pdf", "paper30.pdf"
]

STAGE_1_ADDITIONS = [
    "paper3.pdf", "paper12.pdf", "paper13.pdf", "paper14.pdf", "paper16.pdf",
    "paper31.pdf", "paper32.pdf"
]

STAGE_2_ADDITIONS = [
    "paper21.pdf", "paper22.pdf", "paper26.pdf", "paper27.pdf", "paper28.pdf",
    "paper33.pdf", "paper34.pdf"
]


def load_corpus_slice(filenames: list[str]) -> tuple[list[dict], np.ndarray]:
    docs_dir = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs"
    docs = []
    embeddings = []
    for fn in filenames:
        p = docs_dir / fn
        vec = get_cached_embedding(p)
        if vec is not None:
            docs.append({"id": f"doc-{fn}", "filename": fn})
            embeddings.append(vec)
        else:
            raise FileNotFoundError(f"Missing cached embedding for {fn}")
    return docs, np.array(embeddings)


def run_e3_incremental_evaluation() -> dict:
    """Run incremental multi-stage stability evaluation across Stage 0 -> Stage 1 -> Stage 2."""
    print("--- Running Experiment E3: Incremental Stability Evaluation ---")

    tmp_dir = tempfile.TemporaryDirectory(prefix="parallax_eval_e3_")
    state_file = Path(tmp_dir.name) / "cluster_mapping.json"

    # ==========================================
    # STAGE 0 (N0 = 20)
    # ==========================================
    docs_s0, X_s0 = load_corpus_slice(STAGE_0_DOCS)
    res_s0 = run_constraint_aware_clustering(docs_s0, X_s0, state_file=state_file)
    cids_s0 = res_s0["doc_cluster_ids"]
    unique_cids_s0 = sorted(list(set(cids_s0)))

    # Compute initial physics layout
    homes_s0 = compute_home_positions(unique_cids_s0)
    nodes_s0 = []
    for i, d in enumerate(docs_s0):
        cid = cids_s0[i]
        hx, hy = homes_s0.get(cid, (200.0, 150.0))
        nodes_s0.append(Node(
            doc_id=d["id"],
            cluster_id=cid,
            x=hx + float(np.random.normal(0, 5)),
            y=hy + float(np.random.normal(0, 5)),
        ))
    simulate(nodes_s0, max_iters=150, cluster_home_positions=homes_s0)
    pos_s0 = {n.doc_id: (n.x, n.y) for n in nodes_s0}
    cluster_map_s0 = {d["id"]: cids_s0[i] for i, d in enumerate(docs_s0)}

    # ==========================================
    # STAGE 1 (N1 = 27, +7 docs)
    # ==========================================
    stage_1_docs = STAGE_0_DOCS + STAGE_1_ADDITIONS
    docs_s1, X_s1 = load_corpus_slice(stage_1_docs)
    res_s1 = run_constraint_aware_clustering(docs_s1, X_s1, state_file=state_file)
    cids_s1 = res_s1["doc_cluster_ids"]
    unique_cids_s1 = sorted(list(set(cids_s1)))

    homes_s1 = compute_home_positions(unique_cids_s1)
    # Initialize nodes: existing nodes retain previous coordinates, new nodes start near home
    nodes_s1 = []
    for i, d in enumerate(docs_s1):
        cid = cids_s1[i]
        if d["id"] in pos_s0:
            init_x, init_y = pos_s0[d["id"]]
        else:
            hx, hy = homes_s1.get(cid, (200.0, 150.0))
            init_x = hx + float(np.random.normal(0, 5))
            init_y = hy + float(np.random.normal(0, 5))
        nodes_s1.append(Node(doc_id=d["id"], cluster_id=cid, x=init_x, y=init_y))

    simulate(nodes_s1, max_iters=100, cluster_home_positions=homes_s1)
    pos_s1 = {n.doc_id: (n.x, n.y) for n in nodes_s1}
    cluster_map_s1 = {d["id"]: cids_s1[i] for i, d in enumerate(docs_s1)}

    # Measure Stage 0 -> Stage 1 metrics
    s0_displacements = [
        math.hypot(pos_s1[doc_id][0] - pos_s0[doc_id][0], pos_s1[doc_id][1] - pos_s0[doc_id][1])
        for doc_id in pos_s0
    ]
    reassigned_s1 = sum(1 for doc_id in cluster_map_s0 if cluster_map_s1[doc_id] != cluster_map_s0[doc_id])
    drr_s1 = float(reassigned_s1 / len(cluster_map_s0))

    preserved_clusters_s1 = len(set(unique_cids_s0) & set(unique_cids_s1))
    new_clusters_s1 = len(set(unique_cids_s1) - set(unique_cids_s0))
    lpr_s1 = float(preserved_clusters_s1 / len(unique_cids_s0)) if len(unique_cids_s0) > 0 else 1.0

    # ==========================================
    # STAGE 2 (N2 = 34, +7 docs)
    # ==========================================
    stage_2_docs = stage_1_docs + STAGE_2_ADDITIONS
    docs_s2, X_s2 = load_corpus_slice(stage_2_docs)
    res_s2 = run_constraint_aware_clustering(docs_s2, X_s2, state_file=state_file)
    cids_s2 = res_s2["doc_cluster_ids"]
    unique_cids_s2 = sorted(list(set(cids_s2)))

    homes_s2 = compute_home_positions(unique_cids_s2)
    nodes_s2 = []
    for i, d in enumerate(docs_s2):
        cid = cids_s2[i]
        if d["id"] in pos_s1:
            init_x, init_y = pos_s1[d["id"]]
        else:
            hx, hy = homes_s2.get(cid, (200.0, 150.0))
            init_x = hx + float(np.random.normal(0, 5))
            init_y = hy + float(np.random.normal(0, 5))
        nodes_s2.append(Node(doc_id=d["id"], cluster_id=cid, x=init_x, y=init_y))

    simulate(nodes_s2, max_iters=100, cluster_home_positions=homes_s2)
    pos_s2 = {n.doc_id: (n.x, n.y) for n in nodes_s2}
    cluster_map_s2 = {d["id"]: cids_s2[i] for i, d in enumerate(docs_s2)}

    # Measure Stage 1 -> Stage 2 metrics
    s1_displacements = [
        math.hypot(pos_s2[doc_id][0] - pos_s1[doc_id][0], pos_s2[doc_id][1] - pos_s1[doc_id][1])
        for doc_id in pos_s1
    ]
    reassigned_s2 = sum(1 for doc_id in cluster_map_s1 if cluster_map_s2[doc_id] != cluster_map_s1[doc_id])
    drr_s2 = float(reassigned_s2 / len(cluster_map_s1))

    preserved_clusters_s2 = len(set(unique_cids_s1) & set(unique_cids_s2))
    new_clusters_s2 = len(set(unique_cids_s2) - set(unique_cids_s1))
    lpr_s2 = float(preserved_clusters_s2 / len(unique_cids_s1)) if len(unique_cids_s1) > 0 else 1.0

    tmp_dir.cleanup()

    return {
        "experiment": "E3_Incremental_Stability",
        "stage_splits": {
            "stage_0_initial_count": len(STAGE_0_DOCS),
            "stage_1_added_count": len(STAGE_1_ADDITIONS),
            "stage_2_added_count": len(STAGE_2_ADDITIONS),
            "total_corpus_count": len(stage_2_docs),
        },
        "Stage_0_Initial": {
            "document_count": len(STAGE_0_DOCS),
            "cluster_count": len(unique_cids_s0),
            "cluster_ids": unique_cids_s0,
        },
        "Stage_0_to_Stage_1_Transition": {
            "initial_docs": len(STAGE_0_DOCS),
            "added_docs": len(STAGE_1_ADDITIONS),
            "cluster_lineage_preservation_rate": round(lpr_s1, 4),
            "document_reassignment_rate": round(drr_s1, 4),
            "preserved_cluster_count": preserved_clusters_s1,
            "new_cluster_count": new_clusters_s1,
            "mean_spatial_displacement": round(float(np.mean(s0_displacements)), 2),
            "median_spatial_displacement": round(float(np.median(s0_displacements)), 2),
            "max_spatial_displacement": round(float(np.max(s0_displacements)), 2),
        },
        "Stage_1_to_Stage_2_Transition": {
            "initial_docs": len(stage_1_docs),
            "added_docs": len(STAGE_2_ADDITIONS),
            "cluster_lineage_preservation_rate": round(lpr_s2, 4),
            "document_reassignment_rate": round(drr_s2, 4),
            "preserved_cluster_count": preserved_clusters_s2,
            "new_cluster_count": new_clusters_s2,
            "mean_spatial_displacement": round(float(np.mean(s1_displacements)), 2),
            "median_spatial_displacement": round(float(np.median(s1_displacements)), 2),
            "max_spatial_displacement": round(float(np.max(s1_displacements)), 2),
        },
    }


if __name__ == "__main__":
    res = run_e3_incremental_evaluation()
    import json
    print(json.dumps(res, indent=2))
