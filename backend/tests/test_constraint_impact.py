"""
backend/tests/test_constraint_impact.py

Tests assessing the impact of constraints on clustering, centroid shifts, and evaluation metrics (Phase 3).
"""

import unittest
import numpy as np

from backend.clustering.pipeline import run_constraint_aware_clustering
from backend.clustering.constraints import (
    Constraint,
    evaluate_constraint_satisfaction,
)
from backend.tests.fixtures.synthetic_corpora import make_clustered_corpus


class TestConstraintImpact(unittest.TestCase):
    def setUp(self):
        self.corpus = make_clustered_corpus(n_clusters=3, docs_per_cluster=4, dim=32, seed=42)

    def test_unconstrained_baseline_vs_constrained(self):
        """Quantify and verify the impact when a document is manually reassigned."""
        # 1. Unconstrained run
        res_unconstrained = run_constraint_aware_clustering(
            self.corpus.docs, self.corpus.embeddings, state_file=None, forced_assignments={}
        )
        orig_c0_id = res_unconstrained["doc_cluster_ids"][0]
        orig_c1_id = res_unconstrained["doc_cluster_ids"][4]
        self.assertNotEqual(orig_c0_id, orig_c1_id)

        # 2. Force doc-00 into doc-04's cluster
        forced = {self.corpus.docs[0]["id"]: orig_c1_id}
        res_constrained = run_constraint_aware_clustering(
            self.corpus.docs, self.corpus.embeddings, state_file=None, forced_assignments=forced
        )

        # Verify forced cluster assignment
        self.assertEqual(res_constrained["doc_cluster_ids"][0], orig_c1_id)

        # Verify constraint satisfaction
        eval_contract = res_constrained["evaluation"]
        self.assertEqual(eval_contract.constraint_satisfaction_rate, 1.0)
        self.assertEqual(eval_contract.num_constraints_applied, 1)
        self.assertEqual(eval_contract.num_constraints_violated, 0)

    def test_multiple_competing_constraints(self):
        """Verify multiple constraints applied across several clusters."""
        target_cluster_1 = "custom-cluster-alpha"
        target_cluster_2 = "custom-cluster-beta"

        forced = {
            self.corpus.docs[0]["id"]: target_cluster_1,
            self.corpus.docs[1]["id"]: target_cluster_1,
            self.corpus.docs[4]["id"]: target_cluster_2,
            self.corpus.docs[5]["id"]: target_cluster_2,
        }

        res = run_constraint_aware_clustering(
            self.corpus.docs, self.corpus.embeddings, state_file=None, forced_assignments=forced
        )

        self.assertEqual(res["doc_cluster_ids"][0], target_cluster_1)
        self.assertEqual(res["doc_cluster_ids"][1], target_cluster_1)
        self.assertEqual(res["doc_cluster_ids"][4], target_cluster_2)
        self.assertEqual(res["doc_cluster_ids"][5], target_cluster_2)

        # Centroids for custom clusters must be computed
        self.assertIn(target_cluster_1, res["cluster_centers"])
        self.assertIn(target_cluster_2, res["cluster_centers"])

        eval_c = res["evaluation"]
        self.assertEqual(eval_c.constraint_satisfaction_rate, 1.0)
        self.assertEqual(eval_c.num_constraints_applied, 4)
        self.assertEqual(eval_c.num_constraints_violated, 0)

    def test_evaluate_constraint_satisfaction_metric(self):
        """Test exact calculation of constraint satisfaction rate when violations occur."""
        nodes = [
            {"doc_id": "doc-01", "cluster_id": "cluster-A"},
            {"doc_id": "doc-02", "cluster_id": "cluster-B"},  # Violated
            {"doc_id": "doc-03", "cluster_id": "cluster-A"},
        ]
        forced = {
            "doc-01": "cluster-A",
            "doc-02": "cluster-A",  # forced to A, but node is in B
            "doc-03": "cluster-A",
        }

        rate, applied, violated = evaluate_constraint_satisfaction(nodes, forced)
        self.assertEqual(applied, 3)
        self.assertEqual(violated, 1)
        self.assertAlmostEqual(rate, 2.0 / 3.0, places=4)


if __name__ == "__main__":
    unittest.main()
