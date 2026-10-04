"""
backend/evaluation/eval_clustering_e1.py

Experiment E1: Clustering Quality Benchmark.
Compares HDBSCAN (production default) vs KMeans (oracle-k) vs Agglomerative Clustering (oracle-k)
on synthetic ground-truth corpora and the real 34-paper research corpus.
"""

import time
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import (
    silhouette_score,
    davies_bouldin_score,
    calinski_harabasz_score,
    adjusted_rand_score,
    normalized_mutual_info_score,
)

from backend.clustering.pipeline import cluster_embeddings
from backend.tests.fixtures.synthetic_corpora import make_clustered_corpus
from backend.embeddings.embedding_cache import get_cached_embedding


def evaluate_cluster_metrics(embeddings: np.ndarray, labels: np.ndarray, true_labels: np.ndarray | None = None) -> dict:
    """
    Compute internal and external clustering metrics separating non-noise from noise points.
    """
    valid_idx = np.where(labels != -1)[0]
    noise_count = int(np.sum(labels == -1))
    noise_ratio = float(noise_count / len(labels)) if len(labels) > 0 else 0.0
    num_clusters = len(set(labels[valid_idx])) if len(valid_idx) > 0 else 0

    sil = None
    dbi = None
    ch = None

    if num_clusters >= 2 and len(valid_idx) >= 3:
        try:
            sil = float(silhouette_score(embeddings[valid_idx], labels[valid_idx], metric="cosine"))
        except Exception:
            sil = None
        try:
            dbi = float(davies_bouldin_score(embeddings[valid_idx], labels[valid_idx]))
        except Exception:
            dbi = None
        try:
            ch = float(calinski_harabasz_score(embeddings[valid_idx], labels[valid_idx]))
        except Exception:
            ch = None

    ari = None
    nmi = None
    if true_labels is not None:
        try:
            ari = float(adjusted_rand_score(true_labels, labels))
            nmi = float(normalized_mutual_info_score(true_labels, labels))
        except Exception:
            ari = None
            nmi = None

    return {
        "num_clusters": num_clusters,
        "noise_count": noise_count,
        "noise_ratio": noise_ratio,
        "silhouette_score": sil,
        "davies_bouldin_index": dbi,
        "calinski_harabasz_index": ch,
        "adjusted_rand_index": ari,
        "normalized_mutual_info": nmi,
    }


def run_e1_synthetic_oracle_benchmark(k_values=(2, 3, 4, 5, 8), docs_per_cluster=8, noise_count=4, seed=42) -> dict:
    """
    Controlled Oracle-k benchmark on synthetic corpora with ground truth.
    """
    results = {}

    for k in k_values:
        corpus = make_clustered_corpus(
            n_clusters=k,
            docs_per_cluster=docs_per_cluster,
            dim=768,
            noise_count=noise_count,
            noise_std=0.04,
            seed=seed,
        )
        X = corpus.embeddings
        y_true = corpus.ground_truth_labels

        # 1. Production HDBSCAN (autonomous k)
        t0 = time.perf_counter()
        hdb_labels, _ = cluster_embeddings(X)
        t_hdb = (time.perf_counter() - t0) * 1000.0
        hdb_metrics = evaluate_cluster_metrics(X, hdb_labels, y_true)
        hdb_metrics["runtime_ms"] = round(t_hdb, 2)

        # Injected noise recall (points with true_label == -1)
        if noise_count > 0:
            true_noise_mask = (y_true == -1)
            pred_noise_mask = (hdb_labels == -1)
            tp_noise = np.sum(true_noise_mask & pred_noise_mask)
            hdb_metrics["injected_noise_precision"] = float(tp_noise / np.sum(pred_noise_mask)) if np.sum(pred_noise_mask) > 0 else 0.0
            hdb_metrics["injected_noise_recall"] = float(tp_noise / np.sum(true_noise_mask))
        else:
            hdb_metrics["injected_noise_precision"] = 1.0
            hdb_metrics["injected_noise_recall"] = 1.0

        # 2. KMeans with Oracle k
        t0 = time.perf_counter()
        km = KMeans(n_clusters=k, random_state=seed, n_init=10)
        km_labels = km.fit_predict(X)
        t_km = (time.perf_counter() - t0) * 1000.0
        km_metrics = evaluate_cluster_metrics(X, km_labels, y_true)
        km_metrics["runtime_ms"] = round(t_km, 2)
        km_metrics["injected_noise_precision"] = 0.0
        km_metrics["injected_noise_recall"] = 0.0

        # 3. Agglomerative with Oracle k
        t0 = time.perf_counter()
        agg = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average")
        agg_labels = agg.fit_predict(X)
        t_agg = (time.perf_counter() - t0) * 1000.0
        agg_metrics = evaluate_cluster_metrics(X, agg_labels, y_true)
        agg_metrics["runtime_ms"] = round(t_agg, 2)
        agg_metrics["injected_noise_precision"] = 0.0
        agg_metrics["injected_noise_recall"] = 0.0

        results[f"k_{k}"] = {
            "ground_truth_k": k,
            "total_docs": len(X),
            "injected_noise_docs": noise_count,
            "HDBSCAN": hdb_metrics,
            "KMeans_oracle_k": km_metrics,
            "Agglomerative_oracle_k": agg_metrics,
        }

    return results


def run_e1_real_corpus_benchmark() -> dict:
    """
    Benchmark algorithms on the real 34-paper research corpus.
    """
    docs_dir = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs"
    pdf_paths = sorted(docs_dir.glob("paper*.pdf"), key=lambda p: int(p.stem.replace("paper", "")))

    embeddings = []
    valid_pdfs = []
    for p in pdf_paths:
        vec = get_cached_embedding(p)
        if vec is not None:
            embeddings.append(vec)
            valid_pdfs.append(p.name)

    if len(embeddings) == 0:
        return {"error": "No cached embeddings found for sample_docs"}

    X = np.array(embeddings)

    # 1. HDBSCAN
    t0 = time.perf_counter()
    hdb_labels, _ = cluster_embeddings(X)
    t_hdb = (time.perf_counter() - t0) * 1000.0
    hdb_metrics = evaluate_cluster_metrics(X, hdb_labels)
    hdb_metrics["runtime_ms"] = round(t_hdb, 2)

    # 2. KMeans across k in [2..8]
    km_results = {}
    for k in range(2, 9):
        t0 = time.perf_counter()
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km_lbls = km.fit_predict(X)
        t_km = (time.perf_counter() - t0) * 1000.0
        m = evaluate_cluster_metrics(X, km_lbls)
        m["runtime_ms"] = round(t_km, 2)
        km_results[f"k_{k}"] = m

    # 3. Agglomerative across k in [2..8]
    agg_results = {}
    for k in range(2, 9):
        t0 = time.perf_counter()
        agg = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average")
        agg_lbls = agg.fit_predict(X)
        t_agg = (time.perf_counter() - t0) * 1000.0
        m = evaluate_cluster_metrics(X, agg_lbls)
        m["runtime_ms"] = round(t_agg, 2)
        agg_results[f"k_{k}"] = m

    return {
        "total_documents": len(X),
        "HDBSCAN_production": hdb_metrics,
        "KMeans_comparison": km_results,
        "Agglomerative_comparison": agg_results,
    }


def run_e1_evaluation() -> dict:
    """Run full E1 clustering evaluation suite."""
    print("--- Running Experiment E1: Clustering Quality Benchmark ---")
    synthetic_res = run_e1_synthetic_oracle_benchmark()
    real_res = run_e1_real_corpus_benchmark()
    return {
        "experiment": "E1_Clustering_Quality",
        "synthetic_oracle_k": synthetic_res,
        "real_34_paper_corpus": real_res,
    }


if __name__ == "__main__":
    res = run_e1_evaluation()
    import json
    print(json.dumps(res, indent=2))
