import hashlib
import math
from dataclasses import dataclass
from typing import Optional
import numpy as np

ATTRACTION_K = 0.5
REPULSION_K = 4000.0
INTER_CLUSTER_REPULSION_MULTIPLIER = 3.0
GRAVITY_K = 0.01
DAMPING = 0.85
DT = 0.1
ENERGY_THRESHOLD = 0.01
MAX_ITERATIONS = 200
MAX_ITERATIONS_INITIAL = 2_000
ANCHOR_VELOCITY_DAMPING = 0.05

# Canvas dimensions are sized for the current demo corpus (~10-25 documents).
# At this scale a 400×300 canvas gives comfortable visual separation between
# clusters without requiring scroll or zoom in the frontend.  If corpus size
# grows significantly (>50 docs) consider scaling proportionally.
CANVAS_WIDTH = 400.0
CANVAS_HEIGHT = 300.0

CLUSTER_INIT_SPREAD = 20.0


def compute_home_positions(
    cluster_ids: list[str],
) -> dict[str, tuple[float, float]]:
    """
    Deterministically generate home (x, y) positions for an arbitrary number
    of clusters, keyed by cluster ID string.

    Stability guarantee
    -------------------
    Each cluster UUID is mapped to an angular position derived *solely* from
    a hash of the UUID string itself (SHA-256, first 8 bytes as uint64,
    reduced to [0, 2pi)).  This means the angular position for any given
    cluster does NOT change when other clusters are added or removed — only
    the radius scales with N for visual separation.

    This replaces the previous rank-indexed approach (angle = 2pi*k/N) which
    shifted every surviving cluster's home position whenever N changed.

    Special cases
    -------------
    - 0 clusters → empty dict.
    - 1 cluster  → canvas centre (circle degenerate).
    - 2 clusters → symmetric left/right split; each side is determined by the
                   cluster's own hash (lower hash value goes left), so adding a
                   third cluster doesn't disturb the surviving two.

    Radius
    ------
    radius = min(W, H) * 0.35  (fixed, same as before)

    The canvas (400×300) gives each cluster a home ~105 units from centre,
    which provides comfortable visual separation for up to ~12 clusters before
    homes start to crowd.  Scale if corpus grows beyond that.
    """
    if not cluster_ids:
        return {}

    cx = CANVAS_WIDTH / 2.0
    cy = CANVAS_HEIGHT / 2.0

    def _angle_for(cid: str) -> float:
        """Map a cluster UUID string to a stable angle in [0, 2π) via SHA-256."""
        digest = hashlib.sha256(cid.encode()).digest()
        # Take the first 8 bytes as a big-endian unsigned int and scale to [0, 1).
        raw = int.from_bytes(digest[:8], byteorder="big")
        fraction = raw / (2 ** 64)
        return fraction * 2.0 * math.pi

    real_clusters = [cid for cid in cluster_ids if not cid.startswith("noise-")]
    noise_clusters = [cid for cid in cluster_ids if cid.startswith("noise-")]

    # Deduplicate and sort deterministically by raw hash angle
    real_clusters = sorted(list(set(real_clusters)), key=lambda c: _angle_for(c))

    radius_inner = min(CANVAS_WIDTH, CANVAS_HEIGHT) * 0.34
    radius_outer = min(CANVAS_WIDTH, CANVAS_HEIGHT) * 0.46

    positions: dict[str, tuple[float, float]] = {}

    if len(real_clusters) == 1:
        positions[real_clusters[0]] = (cx, cy)
    elif len(real_clusters) > 1:
        n = len(real_clusters)
        angles = [_angle_for(c) for c in real_clusters]
        # Hard floor: prefer 35° separation, but clamp to geometrically satisfiable bound for large N
        MIN_SEP_HARD = math.radians(35.0)   # 35° target
        max_possible_sep = (2.0 * math.pi / n) * 0.95
        min_sep = min(max(MIN_SEP_HARD, (2.0 * math.pi / n) * 0.75), max_possible_sep)

        # Pairwise shortest-arc circular relaxation
        for _ in range(200):
            max_violation = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    # Shortest angular displacement from angles[i] to angles[j] in [-π, π]
                    delta = (angles[j] - angles[i] + math.pi) % (2.0 * math.pi) - math.pi
                    dist = abs(delta)
                    if dist < min_sep:
                        violation = min_sep - dist
                        max_violation = max(max_violation, violation)
                        push = violation / 2.0
                        if delta >= 0:
                            angles[i] = (angles[i] - push) % (2.0 * math.pi)
                            angles[j] = (angles[j] + push) % (2.0 * math.pi)
                        else:
                            angles[i] = (angles[i] + push) % (2.0 * math.pi)
                            angles[j] = (angles[j] - push) % (2.0 * math.pi)
            if max_violation < 1e-4:
                break  # Converged cleanly

        for cid, angle in zip(real_clusters, angles):
            positions[cid] = (
                cx + radius_inner * math.cos(angle),
                cy + radius_inner * math.sin(angle),
            )

    real_angles = [
        math.atan2(positions[cid][1] - cy, positions[cid][0] - cx) % (2.0 * math.pi)
        for cid in real_clusters
    ] if len(real_clusters) > 1 else []

    for nid in noise_clusters:
        angle = _angle_for(nid)
        # Avoid collinearity: offset noise anchor if it aligns closely with any real cluster angle
        for ra in real_angles:
            diff = abs((angle - ra + math.pi) % (2.0 * math.pi) - math.pi)
            if diff < 0.35:
                # Shift away into angular gap
                shift = 0.40 if ((angle - ra + 2.0 * math.pi) % (2.0 * math.pi)) < math.pi else -0.40
                angle = (ra + shift) % (2.0 * math.pi)
        positions[nid] = (
            cx + radius_outer * math.cos(angle),
            cy + radius_outer * math.sin(angle),
        )

    return positions


@dataclass
class Node:
    """Represents one document on the canvas."""
    doc_id: str
    cluster_id: str
    x: float
    y: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    is_anchored: bool = False
    is_boundary_document: bool = False
    secondary_cluster_id: Optional[str] = None
    secondary_weight: float = 0.0

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

    When ``cluster_home_positions`` is provided (a dict mapping cluster ID →
    (x, y) home position), each node is attracted toward its cluster's fixed
    home position rather than toward the dynamic centroid of its cluster.
    This is the validated stable mode: use ``compute_home_positions()`` to
    build this dict before calling simulate().

    When ``cluster_home_positions`` is None, attraction falls back to dynamic
    centroid coupling, which can cause centroid drift when boundary documents
    are present.  Prefer the explicit home-positions path for production use.
    """
    n = len(nodes)
    final_energy = 0.0

    for iteration in range(max_iters):
        centroids = compute_cluster_centroids(nodes)

        fx = np.zeros(n)
        fy = np.zeros(n)

        # Node-to-node repulsion
        for i in range(n):
            for j in range(i + 1, n):
                dx = nodes[i].x - nodes[j].x
                dy = nodes[i].y - nodes[j].y
                dist_sq = dx * dx + dy * dy + 1e-4
                dist = math.sqrt(dist_sq)

                same_cluster = (nodes[i].cluster_id == nodes[j].cluster_id)
                k_rep = REPULSION_K if same_cluster else REPULSION_K * INTER_CLUSTER_REPULSION_MULTIPLIER

                force = k_rep / dist_sq
                fx[i] += force * dx / dist
                fy[i] += force * dy / dist
                fx[j] -= force * dx / dist
                fy[j] -= force * dy / dist

        cx_canvas = CANVAS_WIDTH / 2.0
        cy_canvas = CANVAS_HEIGHT / 2.0
        
        for i, node in enumerate(nodes):
            is_noise = node.cluster_id.startswith("noise-")

            if cluster_home_positions is not None:
                c_primary = cluster_home_positions.get(node.cluster_id, (cx_canvas, cy_canvas))
            else:
                c_primary = centroids[node.cluster_id]
                
            dx_p = c_primary[0] - node.x
            dy_p = c_primary[1] - node.y
            primary_weight = 1.0 - node.secondary_weight if node.is_boundary_document else 1.0

            # Spring attraction to home / centroid
            fx[i] += ATTRACTION_K * dx_p * primary_weight
            fy[i] += ATTRACTION_K * dy_p * primary_weight

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

            # Repel noise outliers away from real cluster centroids
            if is_noise:
                for cid, centroid in centroids.items():
                    if not cid.startswith("noise-"):
                        cdx = node.x - centroid[0]
                        cdy = node.y - centroid[1]
                        cdist_sq = cdx * cdx + cdy * cdy + 1e-4
                        cdist = math.sqrt(cdist_sq)
                        if cdist < 45.0:
                            rep_f = 4000.0 / cdist_sq
                            fx[i] += rep_f * (cdx / cdist)
                            fy[i] += rep_f * (cdy / cdist)

            # Center gravity: pull non-anchored cluster members inward, but exclude noise outliers
            # so they stay around the peripheral orbit without getting pulled through clusters
            if not node.is_anchored and not is_noise:
                fx[i] += GRAVITY_K * (cx_canvas - node.x)
                fy[i] += GRAVITY_K * (cy_canvas - node.y)

        total_energy = 0.0
        MARGIN_X = 24.0
        MARGIN_Y = 24.0
        for i, node in enumerate(nodes):
            node.velocity_x = (node.velocity_x + fx[i] * DT) * DAMPING
            node.velocity_y = (node.velocity_y + fy[i] * DT) * DAMPING

            if node.is_anchored:
                node.velocity_x *= ANCHOR_VELOCITY_DAMPING
                node.velocity_y *= ANCHOR_VELOCITY_DAMPING

            node.x += node.velocity_x * DT
            node.y += node.velocity_y * DT

            # Clamp coordinates within safe canvas bounding box to prevent boundary escape
            node.x = max(MARGIN_X, min(CANVAS_WIDTH - MARGIN_X, node.x))
            node.y = max(MARGIN_Y, min(CANVAS_HEIGHT - MARGIN_Y, node.y))

            total_energy += node.velocity_x ** 2 + node.velocity_y ** 2

        final_energy = total_energy

        if total_energy < ENERGY_THRESHOLD:
            return iteration + 1, final_energy

    return max_iters, final_energy
