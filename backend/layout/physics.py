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

    if real_clusters:
        # Collect real cluster angles in [0, 2π)
        real_c_angles = [
            (cid, math.atan2(positions[cid][1] - cy, positions[cid][0] - cx) % (2.0 * math.pi))
            for cid in real_clusters
        ]
        real_c_angles.sort(key=lambda x: x[1])
        n_real = len(real_c_angles)

        # Build list of available angular gaps between adjacent real clusters
        gaps = []
        for i in range(n_real):
            a_curr = real_c_angles[i][1]
            a_next = real_c_angles[(i + 1) % n_real][1]
            gap_size = (a_next - a_curr) % (2.0 * math.pi)
            if gap_size == 0.0 and n_real == 1:
                gap_size = 2.0 * math.pi
            mid_angle = (a_curr + gap_size / 2.0) % (2.0 * math.pi)
            gaps.append({"mid_angle": mid_angle, "size": gap_size, "index": i})

        # Sort gaps by size descending (largest gaps first)
        gaps.sort(key=lambda g: g["size"], reverse=True)

        for idx, nid in enumerate(sorted(noise_clusters)):
            # Assign noise cluster to an angular gap bisector
            assigned_gap = gaps[idx % len(gaps)]
            base_angle = assigned_gap["mid_angle"]
            # If multiple noise nodes share the same gap, spread them slightly within the gap
            count_in_gap = idx // len(gaps)
            if count_in_gap > 0:
                offset_sign = 1 if count_in_gap % 2 == 1 else -1
                offset_mag = min(0.25, assigned_gap["size"] * 0.2) * ((count_in_gap + 1) // 2)
                angle = (base_angle + offset_sign * offset_mag) % (2.0 * math.pi)
            else:
                angle = base_angle

            positions[nid] = (
                cx + radius_outer * math.cos(angle),
                cy + radius_outer * math.sin(angle),
            )
    else:
        for nid in noise_clusters:
            angle = _angle_for(nid)
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

def compute_convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Monotone chain convex hull (Andrew's algorithm)."""
    if len(points) <= 2:
        return points
    sorted_pts = sorted(points, key=lambda p: (p[0], p[1]))
    lower = []
    for p in sorted_pts:
        while len(lower) >= 2 and ((lower[-1][0] - lower[-2][0]) * (p[1] - lower[-2][1]) - (lower[-1][1] - lower[-2][1]) * (p[0] - lower[-2][0])) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(sorted_pts):
        while len(upper) >= 2 and ((upper[-1][0] - upper[-2][0]) * (p[1] - upper[-2][1]) - (upper[-1][1] - upper[-2][1]) * (p[0] - upper[-2][0])) <= 0:
            upper.pop()
        upper.append(p)
    lower.pop()
    upper.pop()
    return lower + upper


def expand_hull_polygon(hull: list[tuple[float, float]], cx: float, cy: float, padding: float = 24.0) -> list[tuple[float, float]]:
    """Port of frontend ClusterRegion.jsx expandHull()."""
    if len(hull) == 0:
        return []
    if len(hull) == 1:
        return hull
    if len(hull) == 2:
        p1, p2 = hull
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy) or 1.0
        lat_pad = min(padding, 18.0)
        end_pad = min(padding, 16.0)
        nx = (-dy / length) * lat_pad
        ny = (dx / length) * lat_pad
        ex = (dx / length) * end_pad
        ey = (dy / length) * end_pad
        return [
            (p1[0] - ex + nx, p1[1] - ey + ny),
            (p2[0] + ex + nx, p2[1] + ey + ny),
            (p2[0] + ex - nx, p2[1] + ey - ny),
            (p1[0] - ex - nx, p1[1] - ey - ny),
        ]
    expanded = []
    for p in hull:
        vx = p[0] - cx
        vy = p[1] - cy
        dist = math.hypot(vx, vy)
        if dist < 1e-4:
            expanded.append((p[0] + padding, p[1]))
        else:
            expanded.append((p[0] + (vx / dist) * padding, p[1] + (vy / dist) * padding))
    return expanded


def is_point_inside_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    """Ray-casting algorithm testing whether (x, y) is inside polygon."""
    n = len(poly)
    if n < 3:
        return False
    inside = False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def ensure_outlier_hull_isolation(nodes: list[Node], padding: float = 24.0, safety_margin: float = 14.0) -> None:
    """
    Post-condition guarantee: Enforce that no noise/outlier document node
    is enclosed within or visually overlapping any real cluster's convex hull visual region.
    """
    clusters: dict[str, list[Node]] = {}
    noise_nodes: list[Node] = []
    for node in nodes:
        if node.cluster_id.startswith("noise-"):
            noise_nodes.append(node)
        else:
            clusters.setdefault(node.cluster_id, []).append(node)

    if not noise_nodes or not clusters:
        return

    cx_canvas = CANVAS_WIDTH / 2.0
    cy_canvas = CANVAS_HEIGHT / 2.0
    MARGIN_X = 24.0
    MARGIN_Y = 24.0

    for cid, cnodes in clusters.items():
        pts = [(cn.x, cn.y) for cn in cnodes]
        cx_c = sum(p[0] for p in pts) / len(pts)
        cy_c = sum(p[1] for p in pts) / len(pts)
        raw_hull = pts if len(pts) <= 2 else compute_convex_hull(pts)
        expanded_poly = expand_hull_polygon(raw_hull, cx_c, cy_c, padding=padding)

        for n_node in noise_nodes:
            is_inside = is_point_inside_polygon(n_node.x, n_node.y, expanded_poly)
            
            min_dist_to_hull = 0.0
            if not is_inside and len(expanded_poly) >= 2:
                min_dist_to_hull = min(
                    math.hypot(n_node.x - p[0], n_node.y - p[1]) for p in expanded_poly
                )
            
            if is_inside or (min_dist_to_hull < safety_margin):
                vx = n_node.x - cx_c
                vy = n_node.y - cy_c
                dist = math.hypot(vx, vy)
                if dist < 1e-4:
                    vx = n_node.x - cx_canvas
                    vy = n_node.y - cy_canvas
                    dist = math.hypot(vx, vy)
                    if dist < 1e-4:
                        vx, vy, dist = 0.0, 1.0, 1.0

                ux = vx / dist
                uy = vy / dist

                step = 6.0
                for _ in range(40):
                    n_node.x += ux * step
                    n_node.y += uy * step
                    
                    if n_node.x <= MARGIN_X or n_node.x >= CANVAS_WIDTH - MARGIN_X or \
                       n_node.y <= MARGIN_Y or n_node.y >= CANVAS_HEIGHT - MARGIN_Y:
                        if n_node.y >= CANVAS_HEIGHT - MARGIN_Y or n_node.y <= MARGIN_Y:
                            slide_dir = 1.0 if (n_node.x - cx_c) >= 0 else -1.0
                            n_node.x += slide_dir * step * 1.5
                        if n_node.x <= MARGIN_X or n_node.x >= CANVAS_WIDTH - MARGIN_X:
                            slide_dir = 1.0 if (n_node.y - cy_c) >= 0 else -1.0
                            n_node.y += slide_dir * step * 1.5

                    n_node.x = max(MARGIN_X, min(CANVAS_WIDTH - MARGIN_X, n_node.x))
                    n_node.y = max(MARGIN_Y, min(CANVAS_HEIGHT - MARGIN_Y, n_node.y))

                    if not is_point_inside_polygon(n_node.x, n_node.y, expanded_poly):
                        d_hull = min(math.hypot(n_node.x - p[0], n_node.y - p[1]) for p in expanded_poly)
                        if d_hull >= safety_margin:
                            break


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

            # Repel noise outliers away from all real cluster nodes with strong mutual repulsion
            if is_noise:
                for j_other, other in enumerate(nodes):
                    if not other.cluster_id.startswith("noise-"):
                        odx = node.x - other.x
                        ody = node.y - other.y
                        odist_sq = odx * odx + ody * ody + 1e-4
                        odist = math.sqrt(odist_sq)
                        if odist < 65.0:
                            rep_f = 8000.0 / odist_sq
                            fx[i] += rep_f * (odx / odist)
                            fy[i] += rep_f * (ody / odist)
                            # Push real cluster node slightly away so cluster members don't engulf noise
                            fx[j_other] -= (rep_f * 0.4) * (odx / odist)
                            fy[j_other] -= (rep_f * 0.4) * (ody / odist)

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
            ensure_outlier_hull_isolation(nodes)
            return iteration + 1, final_energy

    ensure_outlier_hull_isolation(nodes)
    return max_iters, final_energy
