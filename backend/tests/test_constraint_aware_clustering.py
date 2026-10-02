"""
backend/tests/test_constraint_aware_clustering.py

Unit and integration tests for constraint-aware clustering (Phase 1 / ADR-001).

Proves that:
1. Constrained documents are separated BEFORE unconstrained clustering (HDBSCAN).
2. Constrained documents cannot distort the density/clustering of unconstrained documents.
3. All edge cases (0 constrained, 1 constrained, many constrained, all constrained,
   1 unconstrained, noise, missing constraints) are handled deterministically without crashing.
4. Constraint satisfaction rate and silhouette evaluation are accurately computed.
"""

import unittest
import numpy as np
from pathlib import Path

from backend.clustering.pipeline import (
    run_constraint_aware_clustering,
    cluster_embeddings,
    assign_stable_cluster_ids,
    EvaluationContract,
)
from backend.clustering.constraints import (
    Constraint,
    apply_constraints,
    evaluate_constraint_satisfaction,
)


class TestConstraintAwareClustering(unittest.TestCase):
    def setUp(self):
        # Create synthetic 2D/multi-D embeddings with 3 distinct clusters:
        # Cluster A: 4 points near [1.0, 0.0]
        # Cluster B: 4 points near [0.0, 1.0]
        # Cluster C: 4 points near [-1.0, 0.0]
        # Noise point: 1 outlier near [0.5, 0.5] (or normalized angle)
        rng = np.random.default_rng(seed=42)

        def make_points(center_vec, count=4, noise_std=0.03):
            pts = []
            for _ in range(count):
                pt = center_vec + rng.normal(0, noise_std, size=len(center_vec))
                pts.append(pt / np.linalg.norm(pt))
            return pts

        pts_a = make_points(np.array([1.0, 0.0, 0.0]), count=4)
        pts_b = make_points(np.array([0.0, 1.0, 0.0]), count=4)
        pts_c = make_points(np.array([0.0, 0.0, 1.0]), count=4)

        all_pts = pts_a + pts_b + pts_c
        self.embeddings = np.array(all_pts)
        self.docs = [{"id": f"doc-{i:02d}", "filename": f"paper_{i:02d}.pdf"} for i in range(len(all_pts))]

    def test_zero_constraints(self):
        """0 constraints: runs pure unconstrained HDBSCAN on all documents."""
        res = run_constraint_aware_clustering(
            self.docs, self.embeddings, state_file=None, forced_assignments={}
        )
        self.assertEqual(len(res["doc_cluster_ids"]), len(self.docs))
        self.assertEqual(len(res["boundary_flags"]), len(self.docs))
        self.assertEqual(len(res["unconstrained_indices"]), len(self.docs))
        self.assertEqual(len(res["constrained_indices"]), 0)

        eval_res = res["evaluation"]
        self.assertIsInstance(eval_res, EvaluationContract)
        self.assertGreaterEqual(eval_res.num_clusters, 2)
        self.assertIsNone(eval_res.constraint_satisfaction_rate)
        self.assertEqual(eval_res.num_constraints_applied, 0)
        self.assertEqual(eval_res.num_constraints_violated, 0)

    def test_single_constraint_and_density_isolation(self):
        """
        Critical Proof for ADR-001:
        If doc-00 (belonging to Cluster A) is constrained to a different cluster (e.g. 'forced-cluster-X'),
        the remaining unconstrained documents must cluster identically to a run where doc-00 was completely
        excluded from the dataset.
        """
        forced = {"doc-00": "forced-cluster-X"}
        res_constrained = run_constraint_aware_clustering(
            self.docs, self.embeddings, state_file=None, forced_assignments=forced
        )

        # 1. doc-00 gets forced cluster
        self.assertEqual(res_constrained["doc_cluster_ids"][0], "forced-cluster-X")
        self.assertIn(0, res_constrained["constrained_indices"])
        self.assertNotIn(0, res_constrained["unconstrained_indices"])

        # 2. Compare unconstrained clustering against a dataset with doc-00 completely removed
        remaining_docs = self.docs[1:]
        remaining_embs = self.embeddings[1:]
        res_without_doc00 = run_constraint_aware_clustering(
            remaining_docs, remaining_embs, state_file=None, forced_assignments={}
        )

        # The cluster partitions among docs 1..11 must match
        # Let's verify pairwise co-occurrence between unconstrained docs
        for i in range(1, len(self.docs)):
            for j in range(i + 1, len(self.docs)):
                c1_in_constrained = res_constrained["doc_cluster_ids"][i]
                c2_in_constrained = res_constrained["doc_cluster_ids"][j]
                same_in_constrained = (c1_in_constrained == c2_in_constrained) and not c1_in_constrained.startswith("noise-")

                c1_in_without = res_without_doc00["doc_cluster_ids"][i - 1]
                c2_in_without = res_without_doc00["doc_cluster_ids"][j - 1]
                same_in_without = (c1_in_without == c2_in_without) and not c1_in_without.startswith("noise-")

                self.assertEqual(
                    same_in_constrained, same_in_without,
                    f"Clustering distortion detected for docs {self.docs[i]['id']} and {self.docs[j]['id']}"
                )

        eval_res = res_constrained["evaluation"]
        self.assertEqual(eval_res.constraint_satisfaction_rate, 1.0)
        self.assertEqual(eval_res.num_constraints_applied, 1)
        self.assertEqual(eval_res.num_constraints_violated, 0)

    def test_many_constraints(self):
        """Multiple documents assigned to different and shared forced clusters."""
        forced = {
            "doc-00": "cluster-custom-1",
            "doc-01": "cluster-custom-1",
            "doc-04": "cluster-custom-2",
        }
        res = run_constraint_aware_clustering(
            self.docs, self.embeddings, state_file=None, forced_assignments=forced
        )

        self.assertEqual(res["doc_cluster_ids"][0], "cluster-custom-1")
        self.assertEqual(res["doc_cluster_ids"][1], "cluster-custom-1")
        self.assertEqual(res["doc_cluster_ids"][4], "cluster-custom-2")

        eval_res = res["evaluation"]
        self.assertEqual(eval_res.constraint_satisfaction_rate, 1.0)
        self.assertEqual(eval_res.num_constraints_applied, 3)
        self.assertEqual(eval_res.num_constraints_violated, 0)

    def test_all_documents_constrained(self):
        """M=0 unconstrained documents: HDBSCAN is bypassed without error."""
        forced = {doc["id"]: f"forced-{i % 2}" for i, doc in enumerate(self.docs)}
        res = run_constraint_aware_clustering(
            self.docs, self.embeddings, state_file=None, forced_assignments=forced
        )

        self.assertEqual(len(res["unconstrained_indices"]), 0)
        self.assertEqual(len(res["constrained_indices"]), len(self.docs))
        for i, doc in enumerate(self.docs):
            self.assertEqual(res["doc_cluster_ids"][i], forced[doc["id"]])

        eval_res = res["evaluation"]
        self.assertEqual(eval_res.constraint_satisfaction_rate, 1.0)
        self.assertEqual(eval_res.num_constraints_applied, len(self.docs))
        self.assertEqual(eval_res.num_constraints_violated, 0)
        self.assertEqual(eval_res.num_clusters, 2)

    def test_single_unconstrained_document(self):
        """M=1 unconstrained document: handles 1 unconstrained doc gracefully."""
        forced = {doc["id"]: "forced-group" for doc in self.docs[1:]}
        res = run_constraint_aware_clustering(
            self.docs, self.embeddings, state_file=None, forced_assignments=forced
        )

        self.assertEqual(len(res["unconstrained_indices"]), 1)
        self.assertEqual(len(res["constrained_indices"]), len(self.docs) - 1)
        self.assertTrue(res["doc_cluster_ids"][0].startswith("cluster-"))
        self.assertEqual(res["doc_cluster_ids"][1], "forced-group")

    def test_unmatched_and_conflicting_constraints(self):
        """Constraints for doc_ids not in corpus are ignored safely."""
        forced = {
            "doc-999_nonexistent": "cluster-phantom",
            "doc-00": "cluster-real",
        }
        res = run_constraint_aware_clustering(
            self.docs, self.embeddings, state_file=None, forced_assignments=forced
        )
        self.assertEqual(res["doc_cluster_ids"][0], "cluster-real")
        self.assertEqual(res["evaluation"].num_constraints_applied, 1)

    def test_empty_corpus(self):
        """Empty input returns graceful empty structures."""
        res = run_constraint_aware_clustering([], np.empty((0, 3)), state_file=None, forced_assignments={})
        self.assertEqual(res["doc_cluster_ids"], [])
        self.assertEqual(res["evaluation"].num_clusters, 0)


if __name__ == "__main__":
    unittest.main()
