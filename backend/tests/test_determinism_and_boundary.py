"""
tests/test_determinism_and_boundary.py

Standalone verification script for:
  1. compute_home_positions() determinism (order-independent, stable across phases)
  2. compute_boundary_flags() edge case: assigned cluster NOT in cosine top-2

Run with:
    python -m backend.tests.test_determinism_and_boundary
"""
import sys
import math
import numpy as np
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.layout.physics import compute_home_positions, CANVAS_WIDTH, CANVAS_HEIGHT
from backend.clustering.pipeline import compute_boundary_flags


def _check(condition: bool, name: str) -> bool:
    status = "[PASS]" if condition else "[FAIL]"
    print(f"  {status}  {name}")
    return condition


# ---------------------------------------------------------------------------
# 1. Determinism of compute_home_positions()
# ---------------------------------------------------------------------------
def test_home_positions_determinism():
    print("\n=== 1. compute_home_positions() determinism ===")
    ok = True

    # --- 1a. Order-independence ---
    # Same cluster IDs in different input orders must produce identical results.
    ids = ["cluster-zz1111", "cluster-aa2222", "cluster-mm3333"]
    p_fwd  = compute_home_positions(ids)
    p_rev  = compute_home_positions(list(reversed(ids)))
    p_shuf = compute_home_positions([ids[1], ids[2], ids[0]])

    for cid in ids:
        same_rev  = math.isclose(p_fwd[cid][0], p_rev[cid][0])  and math.isclose(p_fwd[cid][1], p_rev[cid][1])
        same_shuf = math.isclose(p_fwd[cid][0], p_shuf[cid][0]) and math.isclose(p_fwd[cid][1], p_shuf[cid][1])
        ok &= _check(same_rev,  f"  1a. reversed order -> same pos for {cid}")
        ok &= _check(same_shuf, f"  1a. shuffled order -> same pos for {cid}")

    # --- 1b. Idempotence ---
    # Calling twice with the same list must return byte-identical results.
    p_a = compute_home_positions(ids)
    p_b = compute_home_positions(ids)
    for cid in ids:
        ok &= _check(p_a[cid] == p_b[cid], f"  1b. idempotent double-call for {cid}")

    # --- 1c. Cross-phase identity (THE KEY INVARIANT) ---
    # When going from N clusters to N+1 clusters (one new cluster added),
    # every surviving cluster's home position must be IDENTICAL — not merely
    # internally consistent — before and after.
    #
    # Under the old rank-indexed scheme (angle = 2pi*k/N) this test FAILS
    # because adding a 4th cluster shifts k for every cluster whose sorted
    # position comes after the newcomer.  Under the hash-derived scheme this
    # test PASSES because each cluster's angle depends only on its own UUID.
    print("\n  1c. Cross-phase identity: 3 clusters -> 4 clusters (1 new)")

    cluster_a = "cluster-alpha-1111"
    cluster_b = "cluster-beta-2222"
    cluster_c = "cluster-gamma-3333"
    cluster_new = "cluster-delta-9999"   # added in "Phase 2"

    p1_ids = [cluster_a, cluster_b, cluster_c]
    p2_ids = [cluster_a, cluster_b, cluster_c, cluster_new]   # one new entry

    p1_homes = compute_home_positions(p1_ids)
    p2_homes = compute_home_positions(p2_ids)

    for cid in p1_ids:
        pos_before = p1_homes[cid]
        pos_after  = p2_homes[cid]
        identical = (pos_before == pos_after)
        ok &= _check(
            identical,
            f"  1c. {cid} pos unchanged after adding {cluster_new}: "
            f"before={pos_before}, after={pos_after}"
        )

    # New cluster must have a position
    ok &= _check(cluster_new in p2_homes, f"  1c. new cluster has a home in Phase2")

    # Positions of ALL 4 clusters must be distinct (no collisions at this scale)
    all_pos = list(p2_homes.values())
    distinct = len(set(all_pos)) == len(all_pos)
    ok &= _check(distinct, "  1c. all 4 cluster positions are distinct (no hash collisions)")

    return ok


# ---------------------------------------------------------------------------
# 2. compute_boundary_flags() edge case: assigned cluster not in top-2
# ---------------------------------------------------------------------------
def test_boundary_edge_case():
    """
    Construct embeddings where a document's HDBSCAN-assigned cluster is
    neither the closest nor the second-closest centroid by cosine similarity.

    Setup (all unit vectors in 2D for clarity):
      - Cluster 0 centroid: angle 0°   → (1, 0)
      - Cluster 1 centroid: angle 90°  → (0, 1)
      - Cluster 2 centroid: angle 180° → (-1, 0)

      - doc_a: assigned to cluster 0, angle 5° → very close to cluster 0
               → NOT a boundary doc (gap >> BOUNDARY_MARGIN)
      - doc_b: assigned to cluster 2 (angle 170°), but cosine-closest clusters
               are 2 then 1 — assigned IS in top-2, normal case.
      - doc_c: assigned to cluster 0 (label=0), but its embedding is very close
               to cluster 1's direction (angle 88°).  So cosine top-2 are
               cluster 1 and cluster 0 → assigned IS in top-2 (normal case,
               boundary flag depends on gap).
      - doc_edge: assigned to cluster 0 (label=0), but its embedding points
                  toward cluster 2's direction (angle 182°).  Cosine top-2 are
                  cluster 2 and cluster 1 — cluster 0 is NOT in top-2.
                  → edge-case branch fires.
                  The assigned_sim (cluster 0) ≈ cos(182°) ≈ -0.9994.
                  The best other cluster sim (cluster 2) ≈ cos(2°) ≈ 0.9994.
                  Gap = assigned_sim − other_sim ≈ -1.999 << BOUNDARY_MARGIN=0.05.
                  → (assigned_sim - other_sim) < BOUNDARY_MARGIN → True → IS boundary.
    """
    print("\n=== 2. compute_boundary_flags() edge-case ===")

    def unit(angle_deg: float) -> np.ndarray:
        a = math.radians(angle_deg)
        return np.array([math.cos(a), math.sin(a)])

    centers = {
        0: unit(0),    # (1, 0)
        1: unit(90),   # (0, 1)
        2: unit(180),  # (-1, 0)
    }

    # Embeddings: each is a unit vector
    embeddings = np.array([
        unit(5),    # doc_a: assigned 0, very close to cluster 0
        unit(170),  # doc_b: assigned 2, close to cluster 2 (normal in-top-2)
        unit(88),   # doc_c: assigned 0, close to cluster 1 (normal in-top-2)
        unit(182),  # doc_edge: assigned 0, but pointing at cluster 2 — EDGE CASE
    ])
    labels = np.array([0, 2, 0, 0])

    flags = [f[0] for f in compute_boundary_flags(embeddings, labels, centers)]

    ok = True

    # doc_a: assigned cluster 0, cos_sim ≈ cos(5°)≈0.996, next best cluster 1 sim≈cos(85°)≈0.087
    # gap ≈ 0.909 >> 0.05 → not boundary
    ok &= _check(flags[0] == False, "doc_a (angle 5°, assigned 0): not boundary (large gap to cluster 1)")

    # doc_b: assigned cluster 2, cos_sim≈cos(10°)≈0.985, next best cluster 1 sim≈cos(80°)≈0.174
    # gap >> 0.05 → not boundary
    ok &= _check(flags[1] == False, "doc_b (angle 170°, assigned 2): not boundary (large gap)")

    # doc_c: assigned 0, angle 88°. Top-2 by cosine: cluster 1 (cos 2°≈1.0), cluster 0 (cos 88°≈0.035)
    # gap = 1.0 - 0.035 ≈ 0.965 >> 0.05 → not boundary
    ok &= _check(flags[2] == False, "doc_c (angle 88°, assigned 0): not boundary (assigned in top-2, large gap)")

    # doc_edge: assigned 0, angle 182°. Cosine similarities:
    #   cluster 0: cos(182°)≈-0.9994
    #   cluster 1: cos(92°)≈-0.035
    #   cluster 2: cos(2°)≈0.9994
    # Top-2 by cosine: cluster 2 (0.9994), cluster 1 (-0.035)
    # Assigned cluster 0 is NOT in top-2 → EDGE CASE BRANCH
    # assigned_sim = -0.9994, other_sim = 0.9994 (cluster 2)
    # (assigned_sim - other_sim) = -1.999 < BOUNDARY_MARGIN=0.05 → boundary = True
    ok &= _check(flags[3] == True, "doc_edge (angle 182°, assigned 0): IS boundary (edge-case branch fires)")

    # Also confirm it doesn't crash with only 1 cluster
    flags_single = [f[0] for f in compute_boundary_flags(embeddings[:1], np.array([0]), {0: unit(0)})]
    ok &= _check(flags_single == [False], "single cluster -> no boundary flags (no crash)")

    # Confirm it doesn't crash with noise labels
    flags_noise = [f[0] for f in compute_boundary_flags(embeddings[:2], np.array([-1, -1]), {})]
    ok &= _check(flags_noise == [False, False], "all noise labels -> no boundary flags (no crash)")

    return ok


if __name__ == "__main__":
    all_ok = True
    all_ok &= test_home_positions_determinism()
    all_ok &= test_boundary_edge_case()

    print("\n" + "=" * 60)
    if all_ok:
        print("  ALL CHECKS PASSED")
    else:
        print("  ONE OR MORE CHECKS FAILED")
        sys.exit(1)
