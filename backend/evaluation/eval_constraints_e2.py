"""
backend/evaluation/eval_constraints_e2.py

Experiment E2: Constraint Effectiveness Evaluation.
Evaluates Parallax's production Constraint-Aware Clustering (ADR-001) using run_constraint_aware_clustering().
Measures Constraint Satisfaction Rate, stability on unconstrained nodes (ARI), centroid shifts, and silhouette impact.
"""

import numpy as np
from pathlib import Path
from sklearn.metrics import adjusted_rand_score

from backend.clustering.pipeline import (
    run_constraint_aware_clustering,
    compute_evaluation,
)
from backend.tests.fixtures.synthetic_corpora import make_clustered_corpus
from backend.embeddings.embedding_cache import get_cached_embedding


def cosine_distance(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine distance (1 - cos_sim) between two vectors."""
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    return float(1.0 - (np.dot(v1, v2) / (n1 * n2)))


def run_e2_synthetic_evaluation(seed=42) -> dict:
    """
    Evaluate constraints on synthetic corpus with known baseline cluster structure.
    """
    corpus = make_clustered_corpus(n_clusters=3, docs_per_cluster=6, dim=768, noise_count=3, seed=seed)
    docs = corpus.docs
    embeddings = corpus.embeddings

    # Condition A: Unconstrained baseline
    base_res = run_constraint_aware_clustering(docs, embeddings, state_file=None, forced_assignments={})
    base_cids = base_res["doc_cluster_ids"]
    base_eval = base_res["evaluation"]
    base_centers = base_res["cluster_centers"]

    unique_real_cids = sorted(list(set(cid for cid in base_cids if not cid.startswith("noise-"))))
    target_c0 = unique_real_cids[0]
    target_c1 = unique_real_cids[1] if len(unique_real_cids) > 1 else target_c0

    # Condition B: Single Constraint (Move doc-00 into cluster 1)
    doc0_id = docs[0]["id"]
    forced_b = {doc0_id: target_c1}
    res_b = run_constraint_aware_clustering(docs, embeddings, state_file=None, forced_assignments=forced_b)
    eval_b = res_b["evaluation"]

    # Non-constrained ARI
    unconstrained_mask_b = [d["id"] not in forced_b for d in docs]
    base_unconstrained_b = [base_cids[i] for i, m in enumerate(unconstrained_mask_b) if m]
    res_unconstrained_b = [res_b["doc_cluster_ids"][i] for i, m in enumerate(unconstrained_mask_b) if m]
    ari_b = float(adjusted_rand_score(base_unconstrained_b, res_unconstrained_b))

    # Centroid displacement for target cluster
    disp_b = cosine_distance(base_centers[target_c1], res_b["cluster_centers"][target_c1]) if target_c1 in base_centers and target_c1 in res_b["cluster_centers"] else 0.0

    # Condition C: Multiple Constraints (Move 3 documents)
    doc1_id = docs[1]["id"]
    doc2_id = docs[2]["id"]
    forced_c = {
        doc0_id: target_c1,
        doc1_id: target_c1,
        doc2_id: target_c1,
    }
    res_c = run_constraint_aware_clustering(docs, embeddings, state_file=None, forced_assignments=forced_c)
    eval_c = res_c["evaluation"]

    unconstrained_mask_c = [d["id"] not in forced_c for d in docs]
    base_unconstrained_c = [base_cids[i] for i, m in enumerate(unconstrained_mask_c) if m]
    res_unconstrained_c = [res_c["doc_cluster_ids"][i] for i, m in enumerate(unconstrained_mask_c) if m]
    ari_c = float(adjusted_rand_score(base_unconstrained_c, res_unconstrained_c))
    disp_c = cosine_distance(base_centers[target_c1], res_c["cluster_centers"][target_c1]) if target_c1 in base_centers and target_c1 in res_c["cluster_centers"] else 0.0

    # Condition D: Outlier Integration (Force noise point doc-18 into target_c0)
    noise_doc_id = docs[-1]["id"]
    forced_d = {noise_doc_id: target_c0}
    res_d = run_constraint_aware_clustering(docs, embeddings, state_file=None, forced_assignments=forced_d)
    eval_d = res_d["evaluation"]
    unconstrained_mask_d = [d["id"] not in forced_d for d in docs]
    base_unconstrained_d = [base_cids[i] for i, m in enumerate(unconstrained_mask_d) if m]
    res_unconstrained_d = [res_d["doc_cluster_ids"][i] for i, m in enumerate(unconstrained_mask_d) if m]
    ari_d = float(adjusted_rand_score(base_unconstrained_d, res_unconstrained_d))
    disp_d = cosine_distance(base_centers[target_c0], res_d["cluster_centers"][target_c0]) if target_c0 in base_centers and target_c0 in res_d["cluster_centers"] else 0.0

    noise_cnt_a = sum(1 for cid in base_cids if str(cid).startswith("noise-") or cid == -1)

    return {
        "dataset": "synthetic_clustered (N=21, k=3 + 3 noise)",
        "Condition_A_Unconstrained": {
            "num_clusters": base_eval.num_clusters,
            "noise_count": noise_cnt_a,
            "silhouette_score": round(base_eval.silhouette_score, 4) if base_eval.silhouette_score else None,
            "constraint_satisfaction_rate": base_eval.constraint_satisfaction_rate,
        },
        "Condition_B_SingleConstraint": {
            "constraints_applied": eval_b.num_constraints_applied,
            "constraint_satisfaction_rate": eval_b.constraint_satisfaction_rate,
            "unconstrained_ari_stability": round(ari_b, 4),
            "target_centroid_displacement_cosine": round(disp_b, 6),
            "silhouette_delta": round((eval_b.silhouette_score - base_eval.silhouette_score), 4) if (eval_b.silhouette_score and base_eval.silhouette_score) else None,
        },
        "Condition_C_MultipleConstraints": {
            "constraints_applied": eval_c.num_constraints_applied,
            "constraint_satisfaction_rate": eval_c.constraint_satisfaction_rate,
            "unconstrained_ari_stability": round(ari_c, 4),
            "target_centroid_displacement_cosine": round(disp_c, 6),
            "silhouette_delta": round((eval_c.silhouette_score - base_eval.silhouette_score), 4) if (eval_c.silhouette_score and base_eval.silhouette_score) else None,
        },
        "Condition_D_OutlierIntegration": {
            "constraints_applied": eval_d.num_constraints_applied,
            "constraint_satisfaction_rate": eval_d.constraint_satisfaction_rate,
            "unconstrained_ari_stability": round(ari_d, 4),
            "target_centroid_displacement_cosine": round(disp_d, 6),
            "silhouette_delta": round((eval_d.silhouette_score - base_eval.silhouette_score), 4) if (eval_d.silhouette_score and base_eval.silhouette_score) else None,
        },
    }


def run_e2_real_corpus_evaluation() -> dict:
    """
    Evaluate constraints on the real 34-paper research corpus.
    """
    docs_dir = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs"
    pdf_paths = sorted(docs_dir.glob("paper*.pdf"), key=lambda p: int(p.stem.replace("paper", "")))

    docs = []
    embeddings = []
    for p in pdf_paths:
        vec = get_cached_embedding(p)
        if vec is not None:
            docs.append({"id": f"doc-{p.name}", "filename": p.name})
            embeddings.append(vec)

    X = np.array(embeddings)

    # Condition A: Unconstrained baseline
    base_res = run_constraint_aware_clustering(docs, X, state_file=None, forced_assignments={})
    base_cids = base_res["doc_cluster_ids"]
    base_eval = base_res["evaluation"]
    base_centers = base_res["cluster_centers"]

    unique_real = sorted(list(set(cid for cid in base_cids if not cid.startswith("noise-"))))
    c0 = unique_real[0]
    c1 = unique_real[1] if len(unique_real) > 1 else c0

    # Condition B: Single Constraint (Move paper1.pdf to cluster c1)
    forced_b = {"doc-paper1.pdf": c1}
    res_b = run_constraint_aware_clustering(docs, X, state_file=None, forced_assignments=forced_b)
    eval_b = res_b["evaluation"]
    unconstrained_mask_b = [d["id"] not in forced_b for d in docs]
    base_unconstrained_b = [base_cids[i] for i, m in enumerate(unconstrained_mask_b) if m]
    res_unconstrained_b = [res_b["doc_cluster_ids"][i] for i, m in enumerate(unconstrained_mask_b) if m]
    ari_b = float(adjusted_rand_score(base_unconstrained_b, res_unconstrained_b))
    disp_b = cosine_distance(base_centers[c1], res_b["cluster_centers"][c1]) if c1 in base_centers and c1 in res_b["cluster_centers"] else 0.0

    # Condition C: Multiple Constraints (Move paper1, paper2, paper4 to c1)
    forced_c = {"doc-paper1.pdf": c1, "doc-paper2.pdf": c1, "doc-paper4.pdf": c1}
    res_c = run_constraint_aware_clustering(docs, X, state_file=None, forced_assignments=forced_c)
    eval_c = res_c["evaluation"]
    unconstrained_mask_c = [d["id"] not in forced_c for d in docs]
    base_unconstrained_c = [base_cids[i] for i, m in enumerate(unconstrained_mask_c) if m]
    res_unconstrained_c = [res_c["doc_cluster_ids"][i] for i, m in enumerate(unconstrained_mask_c) if m]
    ari_c = float(adjusted_rand_score(base_unconstrained_c, res_unconstrained_c))
    disp_c = cosine_distance(base_centers[c1], res_c["cluster_centers"][c1]) if c1 in base_centers and c1 in res_c["cluster_centers"] else 0.0

    # Condition D: Outlier Integration (Force culinary paper34.pdf into c0)
    forced_d = {"doc-paper34.pdf": c0}
    res_d = run_constraint_aware_clustering(docs, X, state_file=None, forced_assignments=forced_d)
    eval_d = res_d["evaluation"]
    unconstrained_mask_d = [d["id"] not in forced_d for d in docs]
    base_unconstrained_d = [base_cids[i] for i, m in enumerate(unconstrained_mask_d) if m]
    res_unconstrained_d = [res_d["doc_cluster_ids"][i] for i, m in enumerate(unconstrained_mask_d) if m]
    ari_d = float(adjusted_rand_score(base_unconstrained_d, res_unconstrained_d))
    disp_d = cosine_distance(base_centers[c0], res_d["cluster_centers"][c0]) if c0 in base_centers and c0 in res_d["cluster_centers"] else 0.0

    noise_cnt_real = sum(1 for cid in base_cids if str(cid).startswith("noise-") or cid == -1)

    return {
        "dataset": "real_34_paper_corpus",
        "Condition_A_Unconstrained": {
            "num_clusters": base_eval.num_clusters,
            "noise_count": noise_cnt_real,
            "silhouette_score": round(base_eval.silhouette_score, 4) if base_eval.silhouette_score else None,
            "constraint_satisfaction_rate": base_eval.constraint_satisfaction_rate,
        },
        "Condition_B_SingleConstraint": {
            "constraints_applied": eval_b.num_constraints_applied,
            "constraint_satisfaction_rate": eval_b.constraint_satisfaction_rate,
            "unconstrained_ari_stability": round(ari_b, 4),
            "target_centroid_displacement_cosine": round(disp_b, 6),
            "silhouette_delta": round((eval_b.silhouette_score - base_eval.silhouette_score), 4) if (eval_b.silhouette_score and base_eval.silhouette_score) else None,
        },
        "Condition_C_MultipleConstraints": {
            "constraints_applied": eval_c.num_constraints_applied,
            "constraint_satisfaction_rate": eval_c.constraint_satisfaction_rate,
            "unconstrained_ari_stability": round(ari_c, 4),
            "target_centroid_displacement_cosine": round(disp_c, 6),
            "silhouette_delta": round((eval_c.silhouette_score - base_eval.silhouette_score), 4) if (eval_c.silhouette_score and base_eval.silhouette_score) else None,
        },
        "Condition_D_OutlierIntegration": {
            "constraints_applied": eval_d.num_constraints_applied,
            "constraint_satisfaction_rate": eval_d.constraint_satisfaction_rate,
            "unconstrained_ari_stability": round(ari_d, 4),
            "target_centroid_displacement_cosine": round(disp_d, 6),
            "silhouette_delta": round((eval_d.silhouette_score - base_eval.silhouette_score), 4) if (eval_d.silhouette_score and base_eval.silhouette_score) else None,
        },
    }


def run_e2_evaluation() -> dict:
    """Run full E2 constraint effectiveness evaluation."""
    print("--- Running Experiment E2: Constraint Effectiveness Evaluation ---")
    synthetic_res = run_e2_synthetic_evaluation()
    real_res = run_e2_real_corpus_evaluation()
    return {
        "experiment": "E2_Constraint_Effectiveness",
        "synthetic_evaluation": synthetic_res,
        "real_34_paper_corpus": real_res,
    }


if __name__ == "__main__":
    res = run_e2_evaluation()
    import json
    print(json.dumps(res, indent=2))
