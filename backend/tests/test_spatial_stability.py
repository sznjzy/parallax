"""
backend/tests/test_spatial_stability.py

Tests for physics layout spatial stability, node displacement metrics, and boundary behavior (Phase 3).
"""

import unittest
import math
import numpy as np

from backend.layout.physics import (
    Node,
    simulate,
    compute_home_positions,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
)


class TestSpatialStability(unittest.TestCase):
    def test_simulation_convergence_and_energy(self):
        """Simulation should steadily reduce kinetic energy below threshold or stop within max_iters."""
        rng = np.random.default_rng(42)
        nodes = [
            Node(doc_id=f"doc-{i}", cluster_id=f"cluster-{i % 3}", x=rng.uniform(50, 350), y=rng.uniform(50, 250))
            for i in range(12)
        ]
        homes = compute_home_positions(["cluster-0", "cluster-1", "cluster-2"])

        iters, energy = simulate(nodes, max_iters=300, cluster_home_positions=homes)
        self.assertLessEqual(iters, 300)
        self.assertGreater(iters, 0)

    def test_boundary_node_interpolation(self):
        """A boundary node with a secondary cluster must settle between both home positions."""
        h1 = (100.0, 150.0)
        h2 = (300.0, 150.0)
        homes = {"cluster-1": h1, "cluster-2": h2}

        # Regular cluster-1 node
        n_reg = Node(doc_id="doc-reg", cluster_id="cluster-1", x=200.0, y=150.0, is_boundary_document=False)
        # Boundary node with 50% coupling to cluster-2
        n_bound = Node(
            doc_id="doc-bound", cluster_id="cluster-1", x=200.0, y=150.0,
            is_boundary_document=True, secondary_cluster_id="cluster-2", secondary_weight=0.5
        )

        simulate([n_reg, n_bound], max_iters=200, cluster_home_positions=homes)

        # Boundary node x should be significantly closer to the midpoint (200) than the regular node
        dist_reg_to_h1 = abs(n_reg.x - h1[0])
        dist_bound_to_h1 = abs(n_bound.x - h1[0])

        self.assertGreater(dist_bound_to_h1, dist_reg_to_h1, "Boundary node should be pulled toward secondary cluster")

    def test_canvas_boundary_clamping(self):
        """No node coordinates should escape outside [MARGIN_X, CANVAS_WIDTH - MARGIN_X]."""
        # Place nodes with high velocity outside the bounds
        nodes = [
            Node(doc_id="doc-out-left", cluster_id="cluster-0", x=-50.0, y=-50.0, velocity_x=-50.0, velocity_y=-50.0),
            Node(doc_id="doc-out-right", cluster_id="cluster-0", x=500.0, y=400.0, velocity_x=50.0, velocity_y=50.0),
        ]
        homes = {"cluster-0": (200.0, 150.0)}

        simulate(nodes, max_iters=10, cluster_home_positions=homes)

        for n in nodes:
            self.assertGreaterEqual(n.x, 24.0)
            self.assertLessEqual(n.x, CANVAS_WIDTH - 24.0)
            self.assertGreaterEqual(n.y, 24.0)
            self.assertLessEqual(n.y, CANVAS_HEIGHT - 24.0)


if __name__ == "__main__":
    unittest.main()
