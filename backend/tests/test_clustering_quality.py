"""
backend/tests/test_clustering_quality.py

Tests for unconstrained clustering quality, fallback mechanics, and boundary detection (Phase 3).
"""

import unittest
import numpy as np

from backend.clustering.pipeline import (
    cluster_embeddings,
    compute_boundary_flags,
    compute_evaluation,
    EvaluationContract,
    BOUNDARY_MARGIN,
)
from backend.tests.fixtures.synthetic_corpora import (
    make_clustered_corpus,
    make_boundary_corpus,
)


class TestClusteringQuality(unittest.TestCase):
    def test_well_separated_clustering_quality(self):
        """Well-separated synthetic clusters should achieve high silhouette score."""
        corpus = make_clustered_corpus(n_clusters=3, docs_per_cluster=5, dim=64, noise_std=0.02, seed=42)
        labels, centers = cluster_embeddings(corpus.embeddings)

        unique_labels = set(l for l in labels if l != -1)
        self.assertEqual(len(unique_labels), 3, "HDBSCAN should discover all 3 distinct clusters")

        eval_contract = compute_evaluation(corpus.embeddings, labels)
        self.assertIsNotNone(eval_contract)
        self.assertIsNotNone(eval_contract.silhouette_score)
        self.assertGreater(eval_contract.silhouette_score, 0.50, "Well-separated clusters should have SS > 0.5")

    def test_kmeans_fallback_on_degenerate_clusters(self):
        """When points are uniformly distributed and HDBSCAN marks everything as noise, KMeans takes over."""
        rng = np.random.default_rng(seed=123)
        # Uniform points on sphere that lack dense cores
        uniform_points = rng.normal(0, 1.0, size=(12, 16))
        norms = np.linalg.norm(uniform_points, axis=1, keepdims=True)
        uniform_points /= norms

        labels, centers = cluster_embeddings(uniform_points)
        unique_labels = set(l for l in labels if l != -1)

        self.assertGreaterEqual(len(unique_labels), 2, "Fallback should ensure at least 2 clusters for N=12")
        self.assertEqual(len(centers), len(unique_labels))

    def test_boundary_document_detection(self):
        """Verify boundary document is flagged when cosine distance gap to second-closest centroid < BOUNDARY_MARGIN."""
        corpus = make_boundary_corpus(dim=32, seed=42)
        labels, centers = cluster_embeddings(corpus.embeddings)

        boundary_flags = compute_boundary_flags(corpus.embeddings, labels, centers)

        # The last document is the bisector between c1 and c2
        is_b, sec_lbl, sec_weight = boundary_flags[-1]
        self.assertTrue(is_b, "Equidistant bisector document must be flagged as a boundary document")
        self.assertIsNotNone(sec_lbl, "Boundary document must have a secondary cluster assigned")
        self.assertGreater(sec_weight, 0.40, "Secondary weight for equidistant document should be ~0.5")

    def test_tiny_corpora_edge_cases(self):
        """Verify 0, 1, and 2 document corpora do not crash and produce valid outputs."""
        # 0 docs
        l0, c0 = cluster_embeddings(np.empty((0, 8)))
        self.assertEqual(len(l0), 0)
        self.assertEqual(len(c0), 0)

        # 1 doc
        l1, c1 = cluster_embeddings(np.array([[1.0, 0.0, 0.0]]))
        self.assertEqual(len(l1), 1)
        self.assertEqual(l1[0], 0)
        self.assertEqual(len(c1), 1)

        # 2 docs
        l2, c2 = cluster_embeddings(np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]))
        self.assertEqual(len(l2), 2)


if __name__ == "__main__":
    unittest.main()
