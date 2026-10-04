"""
backend/evaluation/eval_scalability.py

Optional Scalability Benchmark:
Measures pipeline stages across controlled synthetic corpus sizes (N = 34, 50, 100, 250, 500).
Reports mean ± standard deviation over 5 repetitions for each stage.
"""

import time
import numpy as np
from sklearn.cluster import KMeans

from backend.clustering.pipeline import cluster_embeddings
from backend.layout.physics import Node, simulate, compute_home_positions
from backend.tests.fixtures.synthetic_corpora import make_clustered_corpus


def benchmark_stage(func, repetitions=5) -> tuple[float, float]:
    """Execute func repetitions times and return (mean_ms, std_ms)."""
    times = []
    for _ in range(repetitions):
        t0 = time.perf_counter()
        func()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)
    return float(np.mean(times)), float(np.std(times))


def run_scalability_benchmark(sizes=(34, 50, 100, 250, 500), repetitions=5) -> dict:
    """Run scalability benchmark across corpus sizes."""
    print("--- Running Scalability Benchmark (Controlled Synthetic Embeddings) ---")
    results = {}

    for N in sizes:
        # Determine k proportionally: k = max(2, int(sqrt(N)))
        k = max(2, int(np.sqrt(N)))
        docs_per_c = max(2, N // k)
        noise_cnt = max(0, N - (k * docs_per_c))

        corpus = make_clustered_corpus(
            n_clusters=k,
            docs_per_cluster=docs_per_c,
            dim=768,
            noise_count=noise_cnt,
            seed=42,
        )
        X = corpus.embeddings[:N]

        # 1. HDBSCAN
        mean_hdb, std_hdb = benchmark_stage(lambda: cluster_embeddings(X), repetitions)

        # 2. KMeans (oracle k)
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        mean_km, std_km = benchmark_stage(lambda: km.fit_predict(X), repetitions)

        # Cluster labels for layout
        labels, _ = cluster_embeddings(X)
        cids = [f"cluster-{lbl}" if lbl != -1 else f"noise-{idx}" for idx, lbl in enumerate(labels)]
        unique_cids = sorted(list(set(cids)))
        homes = compute_home_positions(unique_cids)

        # 3. Physics Simulation (80 iterations)
        def run_physics():
            nodes = [
                Node(
                    doc_id=f"doc-{i}",
                    cluster_id=cids[i],
                    x=homes.get(cids[i], (200.0, 150.0))[0] + float(np.random.normal(0, 3)),
                    y=homes.get(cids[i], (200.0, 150.0))[1] + float(np.random.normal(0, 3)),
                )
                for i in range(len(X))
            ]
            simulate(nodes, max_iters=80, cluster_home_positions=homes)

        mean_phys, std_phys = benchmark_stage(run_physics, repetitions)

        # 4. Semantic Search Dot-Product & Heap Ranking (N chunks)
        q_vec = np.random.normal(0, 1.0, size=768)
        q_vec /= np.linalg.norm(q_vec)

        def run_search_dot():
            sims = np.dot(X, q_vec)
            top_k_idx = np.argsort(sims)[::-1][:10]
            return top_k_idx

        mean_search, std_search = benchmark_stage(run_search_dot, repetitions)

        results[f"N_{N}"] = {
            "document_count": N,
            "cluster_count_k": k,
            "repetitions": repetitions,
            "HDBSCAN_latency_ms": f"{mean_hdb:.2f} ± {std_hdb:.2f}",
            "KMeans_latency_ms": f"{mean_km:.2f} ± {std_km:.2f}",
            "physics_layout_latency_ms": f"{mean_phys:.2f} ± {std_phys:.2f}",
            "search_dotproduct_latency_ms": f"{mean_search:.3f} ± {std_search:.3f}",
            "raw": {
                "hdbscan_mean": round(mean_hdb, 2),
                "hdbscan_std": round(std_hdb, 2),
                "kmeans_mean": round(mean_km, 2),
                "kmeans_std": round(std_km, 2),
                "physics_mean": round(mean_phys, 2),
                "physics_std": round(std_phys, 2),
                "search_mean": round(mean_search, 3),
                "search_std": round(std_search, 3),
            }
        }

    return {
        "experiment": "Controlled_Scalability_Benchmark",
        "tested_sizes": list(sizes),
        "results": results,
    }


if __name__ == "__main__":
    res = run_scalability_benchmark()
    import json
    print(json.dumps(res, indent=2))
