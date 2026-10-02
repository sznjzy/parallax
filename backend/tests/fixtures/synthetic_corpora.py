"""
backend/tests/fixtures/synthetic_corpora.py

Reusable synthetic evaluation fixtures for Parallax testing foundation (Phase 3).
Provides deterministic embeddings, document structures, and ground-truth groupings.
"""

import math
from dataclasses import dataclass
from typing import List, Tuple, Dict
import numpy as np


@dataclass
class SyntheticCorpus:
    docs: List[Dict[str, str]]
    embeddings: np.ndarray
    ground_truth_labels: np.ndarray
    cluster_names: List[str]


def make_clustered_corpus(
    n_clusters: int = 3,
    docs_per_cluster: int = 4,
    dim: int = 768,
    noise_count: int = 0,
    seed: int = 42,
    noise_std: float = 0.05,
) -> SyntheticCorpus:
    """
    Generate a synthetic document corpus with well-separated hyperspherical clusters.
    """
    rng = np.random.default_rng(seed=seed)

    # Generate n_clusters orthogonal or well-separated base vectors
    base_vectors = []
    for _ in range(n_clusters):
        v = rng.normal(0, 1.0, size=dim)
        v /= np.linalg.norm(v)
        base_vectors.append(v)

    docs = []
    embeddings = []
    ground_truth = []
    cluster_names = [f"topic_{i}" for i in range(n_clusters)]

    doc_counter = 0
    for c_idx, base_vec in enumerate(base_vectors):
        for _ in range(docs_per_cluster):
            doc_id = f"doc-{doc_counter:03d}"
            filename = f"paper_{doc_counter:03d}.pdf"

            noise = rng.normal(0, noise_std, size=dim)
            vec = base_vec + noise
            vec /= np.linalg.norm(vec)

            docs.append({"id": doc_id, "filename": filename})
            embeddings.append(vec)
            ground_truth.append(c_idx)
            doc_counter += 1

    # Add noise points if requested
    for _ in range(noise_count):
        doc_id = f"doc-{doc_counter:03d}"
        filename = f"paper_{doc_counter:03d}.pdf"
        noise_vec = rng.normal(0, 1.0, size=dim)
        noise_vec /= np.linalg.norm(noise_vec)

        docs.append({"id": doc_id, "filename": filename})
        embeddings.append(noise_vec)
        ground_truth.append(-1)
        doc_counter += 1

    return SyntheticCorpus(
        docs=docs,
        embeddings=np.array(embeddings),
        ground_truth_labels=np.array(ground_truth),
        cluster_names=cluster_names,
    )


def make_boundary_corpus(dim: int = 768, seed: int = 42) -> SyntheticCorpus:
    """
    Generate a corpus with two clear clusters (-25° and +25°) and one document deliberately
    placed at 0° (bisector) so it sits within the 0.05 boundary threshold of both clusters.
    """
    rng = np.random.default_rng(seed=seed)

    # Centers at -25° and +25°
    c1_base = np.zeros(dim)
    c1_base[0] = math.cos(math.radians(-25.0))
    c1_base[1] = math.sin(math.radians(-25.0))

    c2_base = np.zeros(dim)
    c2_base[0] = math.cos(math.radians(25.0))
    c2_base[1] = math.sin(math.radians(25.0))

    docs = []
    embeddings = []
    ground_truth = []

    # Cluster 1 members (8 docs)
    for i in range(8):
        v = c1_base + rng.normal(0, 0.02, size=dim)
        v /= np.linalg.norm(v)
        docs.append({"id": f"doc-c1-{i}", "filename": f"c1_{i}.pdf"})
        embeddings.append(v)
        ground_truth.append(0)

    # Cluster 2 members (8 docs)
    for i in range(8):
        v = c2_base + rng.normal(0, 0.02, size=dim)
        v /= np.linalg.norm(v)
        docs.append({"id": f"doc-c2-{i}", "filename": f"c2_{i}.pdf"})
        embeddings.append(v)
        ground_truth.append(1)

    # Boundary document at 0° (bisector)
    boundary_vec = np.zeros(dim)
    boundary_vec[0] = 1.0

    docs.append({"id": "doc-boundary-01", "filename": "boundary_doc.pdf"})
    embeddings.append(boundary_vec)
    ground_truth.append(0)

    return SyntheticCorpus(
        docs=docs,
        embeddings=np.array(embeddings),
        ground_truth_labels=np.array(ground_truth),
        cluster_names=["topic_A", "topic_B"],
    )
