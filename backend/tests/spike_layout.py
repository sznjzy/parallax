"""
backend/tests/spike_layout.py
------------------------------------------------------------------------------
Spike B -- Validate incremental layout stability.

PURPOSE
-------
Prove that existing nodes do NOT jump significantly when new documents are
added to the canvas -- the "persistent spatial memory" guarantee that is one
of the three core technical claims in the project evaluation plan.

This spike uses SYNTHETIC data only (no real embeddings needed).  It exercises
the physics engine and anchoring logic so we can read the evaluation numbers
before building any UI.

USAGE
-----
    python -m backend.tests.spike_layout
  or:
    python backend/tests/spike_layout.py

SKILL FOLLOWED
--------------
  incremental-layout -- physics parameters, convergence threshold,
                         anchoring rules, output + evaluation contracts.

OUTPUT CONTRACT per node (incremental-layout SKILL.md Output Contract)
----------------------------------------------------------------------
{ doc_id, x, y, velocity_x, velocity_y, is_anchored }

EVALUATION CONTRACT (incremental-layout SKILL.md Evaluation Contract)
---------------------------------------------------------------------
{
  "update_id": "string",
  "avg_displacement_existing_nodes": float,
  "max_displacement_existing_nodes": float,
  "convergence_iterations": int,
  "convergence_time_ms": float
}

ANCHORING APPROACH (structural fix -- not a magnitude problem)
--------------------------------------------------------------
The old approach capped per-tick displacement for anchored nodes, which still
allowed drift to accumulate linearly over thousands of ticks.  The correct fix
is to heavily damp anchored-node velocity toward zero each tick so they can
settle slightly (absorbing force-balance fluctuations) but cannot accumulate
meaningful drift over the full simulation.

CONVERGENCE DIAGNOSTIC (rule: lower cap first)
----------------------------------------------
MAX_ITERATIONS is intentionally low (200) for the incremental phase.  If the
simulation cannot converge within 200 well-tuned iterations, the force balance
is still wrong -- fix the physics, don't raise the cap.  Phase 1 (initial
layout with no anchors) uses a separate, larger cap MAX_ITERATIONS_INITIAL.
"""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import numpy as np

from backend.layout.physics import (
    ATTRACTION_K,
    REPULSION_K,
    INTER_CLUSTER_REPULSION_MULTIPLIER,
    GRAVITY_K,
    DAMPING,
    DT,
    ENERGY_THRESHOLD,
    MAX_ITERATIONS,
    MAX_ITERATIONS_INITIAL,
    ANCHOR_VELOCITY_DAMPING,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    BOUNDARY_MARGIN,
    CLUSTER_CENTRES,
    CLUSTER_INIT_SPREAD,
    Node,
    compute_cluster_centroids,
    simulate
)


# =============================================================================
# Spike helpers
# =============================================================================

def make_synthetic_nodes(
    n: int,
    cluster_id: str,
    rng: np.random.Generator,
    centre_index: int,
    is_anchored: bool = False,
) -> list[Node]:
    """
    Create n nodes for a single cluster, initialised as a Gaussian blob
    around CLUSTER_CENTRES[centre_index].

    Signature change from prior version: cluster_id is now a scalar (not a
    list) and centre_index selects the CLUSTER_CENTRES entry directly.  The
    old version accepted cluster_ids: list[str] with a cluster_index_offset
    that collapsed to index 0 for single-cluster batches, causing all three
    clusters to initialise at the same CLUSTER_CENTRES entry.
    """
    cx, cy = CLUSTER_CENTRES[centre_index % len(CLUSTER_CENTRES)]
    nodes = []
    for _ in range(n):
        node = Node(
            doc_id=str(uuid.uuid4()),
            cluster_id=cluster_id,
            x=float(cx + rng.normal(0, CLUSTER_INIT_SPREAD)),
            y=float(cy + rng.normal(0, CLUSTER_INIT_SPREAD)),
            is_anchored=is_anchored,
        )
        nodes.append(node)
    return nodes


def snapshot_positions(nodes: list[Node]) -> dict[str, tuple[float, float]]:
    """Record {doc_id: (x, y)} to measure displacement after update."""
    return {node.doc_id: (node.x, node.y) for node in nodes}


def compute_displacement_metrics(
    before: dict[str, tuple[float, float]],
    after_nodes: list[Node],
) -> tuple[float, float]:
    """
    Returns (avg_displacement, max_displacement) for nodes present in both
    'before' and 'after_nodes' -- i.e., the pre-existing anchored nodes.
    """
    displacements = []
    for node in after_nodes:
        if node.doc_id in before:
            x0, y0 = before[node.doc_id]
            displacements.append(math.sqrt((node.x - x0) ** 2 + (node.y - y0) ** 2))
    if not displacements:
        return 0.0, 0.0
    return float(np.mean(displacements)), float(np.max(displacements))


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    rng = np.random.default_rng(seed=42)  # fixed seed for reproducibility

    print("\nParallax -- Spike B: Incremental Layout Stability Validation")
    print("=" * 65)
    print(f"\n  [CONFIG] ATTRACTION_K={ATTRACTION_K}")
    print(f"  [CONFIG] REPULSION_K={REPULSION_K}  (intra-cluster)")
    print(f"  [CONFIG] INTER_CLUSTER_REPULSION_MULTIPLIER={INTER_CLUSTER_REPULSION_MULTIPLIER}")
    print(f"  [CONFIG] GRAVITY_K={GRAVITY_K}")
    print(f"  [CONFIG] DAMPING={DAMPING}  DT={DT}  ENERGY_THRESHOLD={ENERGY_THRESHOLD}")
    print(f"  [CONFIG] ANCHOR_VELOCITY_DAMPING={ANCHOR_VELOCITY_DAMPING}")
    print(f"  [CONFIG] MAX_ITERATIONS_INITIAL={MAX_ITERATIONS_INITIAL}  "
          f"MAX_ITERATIONS(incremental)={MAX_ITERATIONS}")

    # =========================================================================
    # Phase 1: Initial layout -- 11 nodes across 3 clusters
    # =========================================================================
    print("\nPhase 1: Initial layout -- 10 nodes + 1 boundary, 3 clusters")
    print("-" * 50)

    cluster_a = str(uuid.uuid4())
    cluster_b = str(uuid.uuid4())
    cluster_c = str(uuid.uuid4())

    # Each cluster's nodes are initialised near their designated CLUSTER_CENTRES
    # entry.  centre_index is passed explicitly -- no ambiguous offset logic.
    initial_nodes: list[Node] = []
    initial_nodes += make_synthetic_nodes(4, cluster_a, rng, centre_index=0)
    initial_nodes += make_synthetic_nodes(3, cluster_b, rng, centre_index=1)
    initial_nodes += make_synthetic_nodes(3, cluster_c, rng, centre_index=2)

    # Boundary document: sits between clusters A and B (SKILL.md rule 3).
    cx_boundary = (CLUSTER_CENTRES[0][0] + CLUSTER_CENTRES[1][0]) / 2
    cy_boundary = (CLUSTER_CENTRES[0][1] + CLUSTER_CENTRES[1][1]) / 2
    boundary_node = Node(
        doc_id=str(uuid.uuid4()),
        cluster_id=cluster_a,
        x=cx_boundary + float(rng.normal(0, 10)),
        y=cy_boundary + float(rng.normal(0, 10)),
        is_boundary_document=True,
        secondary_cluster_id=cluster_b,
        secondary_weight=0.4,  # 60% toward A, 40% toward B
    )
    initial_nodes.append(boundary_node)

    print(f"  Nodes: {len(initial_nodes)} total "
          f"(Cluster A: 4 + 1 boundary, B: 3, C: 3)")
    print(f"  Running initial simulation...")

    t_start = time.perf_counter()
    cluster_homes = {
        cluster_a: CLUSTER_CENTRES[0],
        cluster_b: CLUSTER_CENTRES[1],
        cluster_c: CLUSTER_CENTRES[2],
    }
    iters_initial, energy_initial = simulate(
        initial_nodes,
        max_iters=MAX_ITERATIONS_INITIAL,
        cluster_home_positions=cluster_homes
    )
    t_ms_initial = (time.perf_counter() - t_start) * 1000

    converged_initial = iters_initial < MAX_ITERATIONS_INITIAL

    if converged_initial:
        print(f"  [PASS] CONVERGED in {iters_initial} iters "
              f"({t_ms_initial:.1f} ms)  final energy={energy_initial:.6f}")
    else:
        print(f"  [FAIL] DID NOT CONVERGE in {iters_initial} iters "
              f"({t_ms_initial:.1f} ms)  residual energy={energy_initial:.6f}")
        print()
        print("  [FORCE-BALANCE FAILURE] Phase 1 did not converge.")
        print("  Fix INTER_CLUSTER_REPULSION_MULTIPLIER or ATTRACTION_K.")
        print()

    # Cluster centroids after Phase 1 (sanity check for separation).
    centroids_p1 = compute_cluster_centroids(initial_nodes)
    print(f"  Cluster centroids after Phase 1:")
    for i, (cid, centroid) in enumerate(centroids_p1.items()):
        label = ["A", "B", "C"][i] if i < 3 else str(i)
        print(f"    Cluster {label}: x={centroid[0]:.1f}  y={centroid[1]:.1f}")
        
    c_a, c_b, c_c = centroids_p1[cluster_a], centroids_p1[cluster_b], centroids_p1[cluster_c]
    sep_ab = math.sqrt((c_a[0]-c_b[0])**2 + (c_a[1]-c_b[1])**2)
    sep_bc = math.sqrt((c_b[0]-c_c[0])**2 + (c_b[1]-c_c[1])**2)
    sep_ac = math.sqrt((c_a[0]-c_c[0])**2 + (c_a[1]-c_c[1])**2)
    print(f"  Pairwise Separation:")
    print(f"    A-B: {sep_ab:.1f}  |  B-C: {sep_bc:.1f}  |  A-C: {sep_ac:.1f}")
    
    print(f"  Boundary node: x={boundary_node.x:.1f}  y={boundary_node.y:.1f}")

    # =========================================================================
    # Phase 2: Incremental update -- add 3 new mobile nodes
    # =========================================================================
    print("\nPhase 2: Incremental update -- adding 3 new nodes")
    print("-" * 50)

    positions_before = snapshot_positions(initial_nodes)

    # Anchor ALL existing nodes (SKILL.md rule 1).
    for node in initial_nodes:
        node.is_anchored = True

    # New nodes: one per cluster, each placed near its cluster's centre so they
    # start close to their target equilibrium rather than from a random position.
    new_nodes: list[Node] = []
    new_nodes += make_synthetic_nodes(1, cluster_a, rng, centre_index=0)
    new_nodes += make_synthetic_nodes(1, cluster_b, rng, centre_index=1)
    new_nodes += make_synthetic_nodes(1, cluster_c, rng, centre_index=2)

    all_nodes = initial_nodes + new_nodes
    print(f"  Total nodes: {len(all_nodes)}  "
          f"(anchored: {len(initial_nodes)}  mobile: {len(new_nodes)})")
    print(f"  Running incremental simulation...")

    t_start = time.perf_counter()
    iters_incremental, energy_incremental = simulate(
        all_nodes,
        max_iters=MAX_ITERATIONS,
        cluster_home_positions=cluster_homes
    )
    t_ms_incremental = (time.perf_counter() - t_start) * 1000

    converged_incremental = iters_incremental < MAX_ITERATIONS

    if converged_incremental:
        print(f"  [PASS] CONVERGED in {iters_incremental} iters "
              f"({t_ms_incremental:.1f} ms)  final energy={energy_incremental:.6f}")
    else:
        print(f"  [FAIL] DID NOT CONVERGE in {iters_incremental} iters "
              f"({t_ms_incremental:.1f} ms)  residual energy={energy_incremental:.6f}")
        print()
        print("  [FORCE-BALANCE FAILURE] Incremental phase did not converge.")
        print("  With anchored nodes heavily damped, the 3 mobile nodes should")
        print("  always converge quickly.  Check ATTRACTION_K / REPULSION_K.")
        print()

    avg_disp, max_disp = compute_displacement_metrics(positions_before, all_nodes)

    # =========================================================================
    # Evaluation contract (incremental-layout SKILL.md Evaluation Contract)
    # =========================================================================
    eval_result = {
        "update_id": str(uuid.uuid4()),
        "avg_displacement_existing_nodes": avg_disp,
        "max_displacement_existing_nodes": max_disp,
        "convergence_iterations": iters_incremental,
        "convergence_time_ms": t_ms_incremental,
    }

    print()
    print("=" * 65)
    print("  EVALUATION CONTRACT  (incremental-layout SKILL.md)")
    print("=" * 65)
    print(json.dumps(eval_result, indent=4))

    # Output contract sample
    print()
    print("-" * 65)
    print("  OUTPUT CONTRACT sample (first 5 nodes, existing/anchored):")
    print("-" * 65)
    for node in all_nodes[:5]:
        print(json.dumps(node.to_output_contract(), indent=4))

    # =========================================================================
    # Final summary -- both phases side by side (for report / screenshot)
    # =========================================================================
    print()
    print("=" * 65)
    print("  FINAL SUMMARY")
    print("=" * 65)
    print()
    print("  Phase 1 -- Initial layout (no anchors, all nodes mobile)")
    p1_status = "[PASS]" if converged_initial else "[FAIL]"
    print(f"    Status          : {p1_status}")
    print(f"    Iterations used : {iters_initial} / {MAX_ITERATIONS_INITIAL}")
    print(f"    Final energy    : {energy_initial:.6f}")
    print(f"    Time            : {t_ms_initial:.1f} ms")
    print(f"    Separation      : A-B {sep_ab:.1f}, B-C {sep_bc:.1f}, A-C {sep_ac:.1f}")
    print()
    print("  Phase 2 -- Incremental update (existing nodes anchored)")
    p2_status = "[PASS]" if converged_incremental and avg_disp < 5.0 else "[FAIL]"
    print(f"    Status          : {p2_status}")
    print(f"    Iterations used : {iters_incremental} / {MAX_ITERATIONS}")
    print(f"    Final energy    : {energy_incremental:.6f}")
    print(f"    Time            : {t_ms_incremental:.1f} ms")
    print(f"    Avg displacement: {avg_disp:.4f} canvas units")
    print(f"    Max displacement: {max_disp:.4f} canvas units")
    print()

    if converged_initial and converged_incremental and avg_disp < 5.0:
        print("  [PASS] Both phases pass -- layout is stable and convergent.")
        print("    Phase 1: clusters form and separate correctly.")
        print("    Phase 2: existing nodes hold position during incremental update.")
    else:
        failures = []
        if not converged_initial:
            failures.append("Phase 1 did not converge")
        if not converged_incremental:
            failures.append("Phase 2 did not converge")
        if avg_disp >= 5.0:
            failures.append(f"Phase 2 displacement too high ({avg_disp:.2f} units)")
        print("  [FAIL] Issues: " + "; ".join(failures))

    print()


if __name__ == "__main__":
    main()
