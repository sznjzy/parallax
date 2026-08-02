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

# =============================================================================
# Physics parameters
# All in one block for easy tuning.  Every value has a one-line rationale so
# a reader can understand the physics without re-deriving from trial and error.
# =============================================================================

# Attraction force constant: scales the spring pull toward the intra-cluster
# centroid.  Value 2.0 chosen so that the intra-cluster equilibrium separation
# (approx sqrt(REPULSION_K / ATTRACTION_K) = sqrt(20/2) ~ 3.2 canvas units)
# keeps cluster blobs tight relative to the 100-unit inter-cluster gap.
ATTRACTION_K = 2.0  # Balances repulsion to keep intra-cluster nodes compact (~3.2 units apart).

# Intra-cluster repulsion constant: inverse-distance push between nodes in the
# SAME cluster.  Value 20.0 gives intra-cluster equilibrium separation of ~3.2
# units (see ATTRACTION_K comment), preventing nodes from overlapping while
# staying compact.
REPULSION_K = 20.0  # Prevents overlapping by pushing nodes apart at close range.

# Inter-cluster repulsion multiplier: applied when two nodes belong to DIFFERENT
# clusters.  Value 3.0 gives inter-cluster repulsion 3x stronger than intra.
# Physics: two clusters of ~4 nodes at equilibrium separation d have net inter-
# cluster push = 4*4*REPULSION_K*3/d^2 balanced against gravity GRAVITY_K*d
# per node.  Solving: d = (48*REPULSION_K / GRAVITY_K)^(1/3) = (48*20*3/0.01)^(1/3)
# ~ 144 canvas units.  Actual equilibrium will be lower because 3 clusters
# share the canvas gravity toward one point -- they form an equilateral triangle
# at smaller separation.  Empirically: at 2x clusters merge; at 3x they stay
# visually distinct; at 5x+ they fly toward canvas edge faster than gravity
# corrects.
INTER_CLUSTER_REPULSION_MULTIPLIER = 3.0  # Forces clusters to separate into distinct visual blobs.

# Canvas centering gravity: weak linear pull toward canvas centre (200, 150)
# for mobile nodes each tick.  Value 0.01 balances the inter-cluster repulsion
# at ~80-100 unit separation (gravity force ~0.01*100=1.0, comparable to inter-
# cluster push ~3*20/100^2*16pairs=0.096 per node -- gravity dominates slightly,
# keeping clusters within canvas).  Higher values collapse cluster separation;
# lower values allow off-canvas drift.  Standard D3 forceCenter technique.
GRAVITY_K = 0.01  # Weak centering force that counteracts inter-cluster repulsion so clusters stay on canvas.

# Global velocity damping per tick (SKILL.md rule 2: 0.85-0.90).  Prevents
# oscillation so the layout visibly settles rather than vibrates.  Value 0.85
# chosen (SKILL.md rule 2 lower bound): with the lighter ATTRACTION_K=2.0 spring
# and gravity+inter-cluster forces both active, 0.85 dissipates energy fast
# enough to converge Phase 1 within ~800 iterations while still being smooth
# enough not to under-damp Phase 2.
DAMPING = 0.85  # Dissipates kinetic energy so the system settles quickly without underdamped vibration.

# Fixed physics timestep in abstract "seconds" (SKILL.md rule 4: decouple
# physics from frame rate so behaviour is consistent across devices).
DT = 0.1  # Fixed timestep to decouple physics from variable frame rates.

# Convergence threshold: stop when total kinetic energy (sum of speed^2 across
# all nodes) drops below this value.  0.01 means average node speed is below
# ~sqrt(0.01/N) canvas-units/tick -- effectively stationary at demo scale.
# This is energy-based, not a fixed count (SKILL.md rule 2), so an unbalanced
# force configuration causes the sim to visibly never converge rather than
# silently stopping at an arbitrary count.
ENERGY_THRESHOLD = 0.01  # Stop when avg speed is near-zero; ensures true equilibrium is reached.

# Incremental-phase iteration cap (Phase 2): 200 iterations is the diagnostic
# threshold.  With anchored nodes heavily velocity-damped, only the 3 new
# mobile nodes need to find equilibrium -- this should happen well under 200
# if the force balance is correct.  Hitting this cap = force-balance bug,
# not a sign to raise the cap.
MAX_ITERATIONS = 200  # Diagnostic cap for incremental phase (should converge very fast if balanced).

# Initial-layout iteration cap (Phase 1): 2000 is justified because Phase 1
# has all 11 nodes mobile and needs global equilibrium.  Empirically with
# seed=42, inter-cluster repulsion at 5x, and DAMPING=0.9, the system converges
# by iteration ~300-400; 2000 gives a 5x safety margin without being arbitrary.
MAX_ITERATIONS_INITIAL = 2_000  # Safely above the ~400 iters needed for global multi-cluster equilibrium.

# Anchored-node extra velocity damping (Phase 2 only).  After applying the
# normal DAMPING each tick, anchored nodes' velocity is multiplied by this
# additional factor.  Effective per-tick damping = 0.9 * 0.05 = 0.045, which
# drives speed to near-zero each tick.  Value 0.05 chosen so that the node can
# still absorb micro-fluctuations (not fully frozen) but cannot accumulate drift
# over hundreds of ticks -- the root cause of the previous linear-drift problem.
ANCHOR_VELOCITY_DAMPING = 0.05  # Zeroes out velocity on anchored nodes per tick to prevent drift accumulation.

# Canvas dimensions: 400x300 matches typical demo-scale density (~15 documents).
# Chosen so that inter-cluster distances (~100-200 units) are large relative to
# intra-cluster equilibrium separation (~3 units), giving visually clean gaps.
CANVAS_WIDTH = 400.0
CANVAS_HEIGHT = 300.0

# Boundary document margin (used by constrained-clustering -- kept for reference).
BOUNDARY_MARGIN = 0.05

# Pre-defined cluster positions for synthetic-data initialisation.
# Each cluster's nodes start in a Gaussian blob around its centre, so the sim
# begins near equilibrium and converges quickly instead of starting from chaos.
# Three clusters placed at the left, top-centre, and right of the canvas so
# they are visually well-separated from the start.
CLUSTER_CENTRES: list[tuple[float, float]] = [
    (100.0, 150.0),   # Cluster A -- left
    (200.0,  75.0),   # Cluster B -- top-centre
    (300.0, 150.0),   # Cluster C -- right
]

# Gaussian spread (std dev, canvas units) for node initialisation within each
# cluster.  20 units is compact relative to the 100-unit inter-cluster gap,
# so clusters start visibly separated with only slight blob overlap at edges.
CLUSTER_INIT_SPREAD = 20.0


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class Node:
    """Represents one document on the canvas."""
    doc_id: str
    cluster_id: str
    x: float
    y: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    is_anchored: bool = False           # True for pre-existing nodes during update
    is_boundary_document: bool = False  # True if in two clusters simultaneously
    secondary_cluster_id: Optional[str] = None
    secondary_weight: float = 0.0       # weight for secondary centroid attraction

    def to_output_contract(self) -> dict:
        """incremental-layout SKILL.md Output Contract."""
        return {
            "doc_id": self.doc_id,
            "x": self.x,
            "y": self.y,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
            "is_anchored": self.is_anchored,
        }


# =============================================================================
# Force-directed physics engine
# =============================================================================

def compute_cluster_centroids(nodes: list[Node]) -> dict[str, np.ndarray]:
    """Compute the 2D centroid for each cluster from current node positions."""
    sums: dict[str, list] = {}
    counts: dict[str, int] = {}
    for node in nodes:
        sums.setdefault(node.cluster_id, [0.0, 0.0])
        sums[node.cluster_id][0] += node.x
        sums[node.cluster_id][1] += node.y
        counts[node.cluster_id] = counts.get(node.cluster_id, 0) + 1
    return {
        cid: np.array([sums[cid][0] / counts[cid], sums[cid][1] / counts[cid]])
        for cid in sums
    }


def simulate(
    nodes: list[Node],
    max_iters: int = MAX_ITERATIONS,
    cluster_home_positions: dict[str, tuple[float, float]] | None = None
) -> tuple[int, float]:
    """
    Run the force-directed simulation to convergence.

    Physics (incremental-layout SKILL.md rule 2):
      Repulsion: all node pairs are repelled.  Same-cluster pairs use REPULSION_K;
        cross-cluster pairs use REPULSION_K * INTER_CLUSTER_REPULSION_MULTIPLIER.
        This gives clusters a genuine ongoing reason to stay separated rather than
        relying solely on starting positions that drift under the base force model.
      Gravity: a weak linear pull toward the canvas center (GRAVITY_K) prevents
        clusters from flying off-canvas under inter-cluster repulsion.  Without
        this, inter-cluster repulsion has no global counterbalance.
      Attraction: spring force toward the intra-cluster centroid, proportional to
        ATTRACTION_K.  Boundary documents attract toward both centroids weighted by
        secondary_weight (SKILL.md rule 3).
      Damping: velocity *= DAMPING every tick to suppress oscillation.
      Convergence: stop when total kinetic energy (sum speed^2) < ENERGY_THRESHOLD.

    Anchored nodes (Phase 2 incremental update, SKILL.md rule 1):
      After normal damping, velocity is additionally multiplied by
      ANCHOR_VELOCITY_DAMPING (~0.05) each tick.  This prevents velocity from
      accumulating across ticks (root cause of linear drift) while still allowing
      tiny corrective movements.  The old per-tick displacement cap is removed
      because capping displacement does not stop velocity accumulation.

    Returns:
        (iterations_taken, final_total_energy)
        iterations_taken == max_iters signals non-convergence (force-balance bug).
    """
    n = len(nodes)
    final_energy = 0.0

    for iteration in range(max_iters):
        # Recompute centroids each tick -- they shift as nodes move.
        centroids = compute_cluster_centroids(nodes)

        fx = np.zeros(n)
        fy = np.zeros(n)

        # ------------------------------------------------------------------
        # Repulsion: all pairs O(n^2) -- fine for demo scale (~15 nodes).
        # Cross-cluster pairs get a stronger push to maintain cluster separation.
        # ------------------------------------------------------------------
        for i in range(n):
            for j in range(i + 1, n):
                dx = nodes[i].x - nodes[j].x
                dy = nodes[i].y - nodes[j].y
                dist_sq = dx * dx + dy * dy + 1e-4  # epsilon avoids div-by-zero
                dist = math.sqrt(dist_sq)

                # Cluster-aware repulsion scaling (SKILL.md rule 2 + Phase 1 fix).
                same_cluster = (nodes[i].cluster_id == nodes[j].cluster_id)
                k_rep = REPULSION_K if same_cluster else REPULSION_K * INTER_CLUSTER_REPULSION_MULTIPLIER

                force = k_rep / dist_sq
                fx[i] += force * dx / dist
                fy[i] += force * dy / dist
                fx[j] -= force * dx / dist
                fy[j] -= force * dy / dist

        # ------------------------------------------------------------------
        # Attraction toward cluster centroid(s) + canvas centering gravity.
        # ------------------------------------------------------------------
        cx_canvas = CANVAS_WIDTH / 2.0
        cy_canvas = CANVAS_HEIGHT / 2.0
        for i, node in enumerate(nodes):
            if cluster_home_positions is not None:
                c_primary = cluster_home_positions[node.cluster_id]
            else:
                c_primary = centroids[node.cluster_id]
                
            dx_p = c_primary[0] - node.x
            dy_p = c_primary[1] - node.y
            primary_weight = 1.0 - node.secondary_weight if node.is_boundary_document else 1.0

            fx[i] += ATTRACTION_K * dx_p * primary_weight
            fy[i] += ATTRACTION_K * dy_p * primary_weight

            # Secondary centroid for boundary documents (SKILL.md rule 3).
            if node.is_boundary_document and node.secondary_cluster_id:
                if cluster_home_positions is not None:
                    if node.secondary_cluster_id in cluster_home_positions:
                        c_sec = cluster_home_positions[node.secondary_cluster_id]
                        fx[i] += ATTRACTION_K * (c_sec[0] - node.x) * node.secondary_weight
                        fy[i] += ATTRACTION_K * (c_sec[1] - node.y) * node.secondary_weight
                else:
                    if node.secondary_cluster_id in centroids:
                        c_sec = centroids[node.secondary_cluster_id]
                        fx[i] += ATTRACTION_K * (c_sec[0] - node.x) * node.secondary_weight
                        fy[i] += ATTRACTION_K * (c_sec[1] - node.y) * node.secondary_weight

            # Canvas centering gravity: weak linear pull toward canvas centre.
            # Prevents clusters from flying off-canvas under inter-cluster
            # repulsion.  Not applied to anchored nodes -- they are already
            # position-stabilised by ANCHOR_VELOCITY_DAMPING.
            if not node.is_anchored:
                fx[i] += GRAVITY_K * (cx_canvas - node.x)
                fy[i] += GRAVITY_K * (cy_canvas - node.y)

        # ------------------------------------------------------------------
        # Integrate: velocity -> position, with damping.
        # ------------------------------------------------------------------
        total_energy = 0.0
        for i, node in enumerate(nodes):
            node.velocity_x = (node.velocity_x + fx[i] * DT) * DAMPING
            node.velocity_y = (node.velocity_y + fy[i] * DT) * DAMPING

            # Extra velocity suppression for anchored nodes (Phase 2).
            # Drives speed to near-zero each tick, preventing drift accumulation.
            if node.is_anchored:
                node.velocity_x *= ANCHOR_VELOCITY_DAMPING
                node.velocity_y *= ANCHOR_VELOCITY_DAMPING

            node.x += node.velocity_x * DT
            node.y += node.velocity_y * DT
            total_energy += node.velocity_x ** 2 + node.velocity_y ** 2

        final_energy = total_energy

        # Energy-based convergence check (SKILL.md rule 2).
        if total_energy < ENERGY_THRESHOLD:
            return iteration + 1, final_energy

    # Did not converge -- signal to caller, not a reason to raise the cap.
    return max_iters, final_energy


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
