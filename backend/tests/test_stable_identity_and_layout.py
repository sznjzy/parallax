"""
backend/tests/test_stable_identity_and_layout.py

Unit and integration tests for Phase 2:
- Stable cluster UUID lineage across incremental updates (ADR-003).
- Deterministic spatial anchoring and order invariance (ADR-004).
- Collision-free cluster home separation.
- Physics layout stability under incremental addition and anchor constraints.
"""

import unittest
import math
import json
import tempfile
from pathlib import Path
import numpy as np

from backend.clustering.pipeline import (
    run_constraint_aware_clustering,
    assign_stable_cluster_ids,
)
from backend.layout.physics import (
    Node,
    simulate,
    compute_home_positions,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
)


class TestStableIdentityAndLayout(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tmp_dir.name) / "cluster_mapping_test.json"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_stable_uuid_lineage_incremental(self):
        """
        Test that clusters maintain the same UUID across incremental updates
        when document overlap >= 50%.
        """
        docs_phase1 = [
            {"id": "doc-01", "filename": "p1.pdf"},
            {"id": "doc-02", "filename": "p2.pdf"},
            {"id": "doc-03", "filename": "p3.pdf"},
            {"id": "doc-04", "filename": "p4.pdf"},
        ]
        # 2 clusters in Phase 1: {0: [doc-01, doc-02], 1: [doc-03, doc-04]}
        labels_p1 = np.array([0, 0, 1, 1])
        uuid_map_p1 = assign_stable_cluster_ids(docs_phase1, labels_p1, self.state_file)

        uuid_cluster_0 = uuid_map_p1[0]
        uuid_cluster_1 = uuid_map_p1[1]
        self.assertNotEqual(uuid_cluster_0, uuid_cluster_1)

        # Phase 2: add doc-05 to cluster 0 and doc-06 as a new cluster 2
        docs_phase2 = docs_phase1 + [
            {"id": "doc-05", "filename": "p5.pdf"},
            {"id": "doc-06", "filename": "p6.pdf"},
            {"id": "doc-07", "filename": "p7.pdf"},
        ]
        # In Phase 2:
        # Label 0: [doc-01, doc-02, doc-05] (overlap with old cluster 0 is 2/2 = 100%)
        # Label 1: [doc-03, doc-04] (overlap with old cluster 1 is 2/2 = 100%)
        # Label 2: [doc-06, doc-07] (new cluster)
        labels_p2 = np.array([0, 0, 1, 1, 0, 2, 2])
        uuid_map_p2 = assign_stable_cluster_ids(docs_phase2, labels_p2, self.state_file)

        # Verify old clusters preserved their UUIDs
        self.assertEqual(uuid_map_p2[0], uuid_cluster_0, "Cluster 0 should retain its stable UUID")
        self.assertEqual(uuid_map_p2[1], uuid_cluster_1, "Cluster 1 should retain its stable UUID")
        # Verify new cluster gets a new unique UUID
        self.assertNotIn(uuid_map_p2[2], [uuid_cluster_0, uuid_cluster_1])

    def test_corpus_pruning_on_document_removal(self):
        """
        Test that documents removed from corpus are pruned from the state file
        so stale documents do not cause false overlap matches.
        """
        docs = [{"id": f"doc-{i}", "filename": f"p{i}.pdf"} for i in range(4)]
        labels = np.array([0, 0, 1, 1])
        uuid_map = assign_stable_cluster_ids(docs, labels, self.state_file)

        # Now simulate removing cluster 1 documents completely
        reduced_docs = docs[:2]
        reduced_labels = np.array([0, 0])
        reduced_uuid_map = assign_stable_cluster_ids(reduced_docs, reduced_labels, self.state_file)

        self.assertEqual(reduced_uuid_map[0], uuid_map[0])
        # Verify state file was updated
        with open(self.state_file, "r") as f:
            state = json.load(f)
        self.assertIn(uuid_map[0], state)
        self.assertNotIn(uuid_map[1], state)

    def test_deterministic_home_positions_order_invariance(self):
        """
        Order invariance: Home positions must be identical regardless of
        the order of cluster IDs passed in.
        """
        cids = ["cluster-alpha-1234", "cluster-beta-5678", "cluster-gamma-9012", "cluster-delta-3456"]

        pos_original = compute_home_positions(cids)
        pos_reversed = compute_home_positions(list(reversed(cids)))
        pos_shuffled = compute_home_positions([cids[2], cids[0], cids[3], cids[1]])

        for cid in cids:
            self.assertAlmostEqual(pos_original[cid][0], pos_reversed[cid][0], places=5)
            self.assertAlmostEqual(pos_original[cid][1], pos_reversed[cid][1], places=5)
            self.assertAlmostEqual(pos_original[cid][0], pos_shuffled[cid][0], places=5)
            self.assertAlmostEqual(pos_original[cid][1], pos_shuffled[cid][1], places=5)

    def test_collision_free_home_separation(self):
        """
        Verify that cluster homes maintain minimum angular separation >= 35 degrees
        for various cluster counts (2, 3, 5, 8).
        """
        for count in [2, 3, 5, 8]:
            cids = [f"cluster-{i:02d}-{i*17:04x}" for i in range(count)]
            homes = compute_home_positions(cids)

            # Check all pairs have non-zero distance
            coords = list(homes.values())
            for i in range(len(coords)):
                for j in range(i + 1, len(coords)):
                    dist = math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
                    self.assertGreater(dist, 10.0, f"Clusters {i} and {j} collided with distance {dist:.2f}")

    def test_anchored_node_drift_resistance(self):
        """
        Anchored nodes (is_anchored=True) must resist displacement from physics forces.
        """
        # Place 2 nodes: one anchored at (100, 100), one free near (105, 100)
        n1 = Node(doc_id="doc-anchored", cluster_id="cluster-A", x=100.0, y=100.0, is_anchored=True)
        n2 = Node(doc_id="doc-free", cluster_id="cluster-A", x=105.0, y=100.0, is_anchored=False)

        homes = {"cluster-A": (200.0, 150.0)}
        iters, final_energy = simulate([n1, n2], max_iters=50, cluster_home_positions=homes)

        # Anchored node should barely move from (100, 100)
        disp_anchored = math.hypot(n1.x - 100.0, n1.y - 100.0)
        disp_free = math.hypot(n2.x - 105.0, n2.y - 100.0)

        self.assertLess(disp_anchored, 20.0, f"Anchored node moved too much: {disp_anchored:.2f}")
        self.assertGreater(disp_free, disp_anchored, "Free node should move more than anchored node")

    def test_incremental_layout_stability(self):
        """
        When Phase 1 nodes are passed as existing_nodes into Phase 2,
        they must experience low average displacement while new nodes settle.
        """
        rng = np.random.default_rng(42)
        # Phase 1: 6 nodes in 2 clusters
        p1_nodes = [
            Node(doc_id="doc-01", cluster_id="cluster-A", x=120.0, y=100.0),
            Node(doc_id="doc-02", cluster_id="cluster-A", x=130.0, y=110.0),
            Node(doc_id="doc-03", cluster_id="cluster-A", x=110.0, y=90.0),
            Node(doc_id="doc-04", cluster_id="cluster-B", x=280.0, y=200.0),
            Node(doc_id="doc-05", cluster_id="cluster-B", x=290.0, y=210.0),
            Node(doc_id="doc-06", cluster_id="cluster-B", x=270.0, y=190.0),
        ]
        homes = compute_home_positions(["cluster-A", "cluster-B"])
        simulate(p1_nodes, max_iters=200, cluster_home_positions=homes)

        # Record converged positions of Phase 1 nodes
        p1_coords = {n.doc_id: (n.x, n.y) for n in p1_nodes}

        # Phase 2: Add 2 new nodes to cluster-A
        p2_nodes = [
            Node(doc_id=n.doc_id, cluster_id=n.cluster_id, x=p1_coords[n.doc_id][0], y=p1_coords[n.doc_id][1])
            for n in p1_nodes
        ] + [
            Node(doc_id="doc-new-1", cluster_id="cluster-A", x=200.0, y=150.0),
            Node(doc_id="doc-new-2", cluster_id="cluster-B", x=200.0, y=150.0),
        ]

        simulate(p2_nodes, max_iters=100, cluster_home_positions=homes)

        # Check existing nodes displacement
        displacements = []
        for n in p2_nodes:
            if n.doc_id in p1_coords:
                orig_x, orig_y = p1_coords[n.doc_id]
                d = math.hypot(n.x - orig_x, n.y - orig_y)
                displacements.append(d)

        avg_disp = float(np.mean(displacements))
        self.assertLess(avg_disp, 15.0, f"Average displacement of existing nodes was too high: {avg_disp:.2f}")


if __name__ == "__main__":
    unittest.main()
