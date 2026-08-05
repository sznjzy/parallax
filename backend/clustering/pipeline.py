"""
clustering/pipeline.py

Constrained clustering pipeline — HDBSCAN with KMeans fallback.

Public API
----------
    cluster_embeddings(embeddings) -> (labels, centers)
    compute_boundary_flags(embeddings, labels, centers) -> list[bool]
    assign_stable_cluster_ids(docs, labels, state_file) -> dict
    compute_evaluation(embeddings, labels) -> EvaluationContract | None

Constants
---------
    BOUNDARY_MARGIN : float
        Canonical boundary-detection threshold (cosine-similarity gap).
        Imported by api/pipeline.py so there is exactly one definition.
"""

import logging
import uuid
import json
import numpy as np
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import hdbscan
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install -r requirements.txt")
    hdbscan = KMeans = silhouette_score = None

# ---------------------------------------------------------------------------
# Canonical boundary-detection margin (Task 6).
# This is the single definition — physics.py and api/pipeline.py import it
# from here rather than defining their own copies.
# ---------------------------------------------------------------------------
BOUNDARY_MARGIN = 0.05


@dataclass
class ClusteringOutput:
    doc_id: str
    cluster_id: str
    cluster_confidence: float
    is_boundary_document: bool

@dataclass
class EvaluationContract:
    silhouette_score: float | None
    num_clusters: int
    # constraint_satisfaction_rate, num_constraints_applied, and
    # num_constraints_violated are None until the manual-correction /
    # constraint-storage feature is implemented.  Do NOT substitute a fake
    # value (e.g. 1.0) — None signals that the metric is not yet meaningful.
    constraint_satisfaction_rate: float | None
    num_constraints_applied: int | None
    num_constraints_violated: int | None


def cluster_embeddings(embeddings: np.ndarray) -> tuple[np.ndarray, dict]:
    """
    Cluster embeddings using HDBSCAN, falling back to KMeans if it fails.
    (constrained-clustering SKILL.md Rule 1)
    Returns: (cluster_labels, cluster_centers_dict)
    """
    num_samples = len(embeddings)

    # HDBSCAN configuration.
    # min_cluster_size=2 because demo corpus is very small (10-15 docs).
    # min_samples=1 to avoid aggressively marking things as noise.
    labels = None
    if num_samples >= 2:
        clusterer = hdbscan.HDBSCAN(min_cluster_size=2, min_samples=1, metric='euclidean')
        labels = clusterer.fit_predict(embeddings)

        unique_labels = set(l for l in labels if l != -1)
        if len(unique_labels) < 2 and num_samples >= 3:
            logger.warning(
                "HDBSCAN produced degenerate clusters (mostly noise or single cluster). "
                "Falling back to KMeans."
            )
            labels = None

    # KMeans Fallback
    if labels is None:
        if num_samples < 3:
            labels = np.zeros(num_samples, dtype=int)
        else:
            best_k = max(2, min(5, num_samples // 3))
            logger.info("Running KMeans with k=%d", best_k)
            kmeans = KMeans(n_clusters=best_k, random_state=42, n_init='auto')
            labels = kmeans.fit_predict(embeddings)

    # Compute centroids
    unique_clusters = set(l for l in labels if l != -1)
    centers: dict = {}
    for cid in unique_clusters:
        cluster_points = embeddings[labels == cid]
        center = cluster_points.mean(axis=0)
        center_norm = np.linalg.norm(center)
        centers[cid] = center / center_norm if center_norm > 0 else center

    return labels, centers


def compute_boundary_flags(
    embeddings: np.ndarray, labels: np.ndarray, centers: dict
) -> list[tuple[bool, int | None, float]]:
    """
    Determine if a document is a boundary document and compute secondary cluster info.

    Returns: list of (is_boundary, secondary_label, secondary_weight)
    
    A document is flagged as a boundary document when the cosine-similarity
    gap between its assigned cluster and the next-best cluster is below
    BOUNDARY_MARGIN.

    Edge-case fix (Task 7): if the document's HDBSCAN-assigned cluster is NOT
    among the cosine top-2 most-similar clusters, compare the assigned cluster
    against the single best *other* cluster (not two unrelated clusters).
    """
    results: list[tuple[bool, int | None, float]] = []

    cids = list(centers.keys())
    if len(cids) < 2:
        return [(False, None, 0.0)] * len(embeddings)

    center_matrix = np.array([centers[cid] for cid in cids])

    for i, emb in enumerate(embeddings):
        if labels[i] == -1:
            results.append((False, None, 0.0))
            continue

        similarities = np.dot(center_matrix, emb)
        sorted_indices = np.argsort(similarities)[::-1]

        assigned_label = labels[i]
        # Position of the assigned cluster in the cids list
        assigned_pos = cids.index(assigned_label) if assigned_label in cids else -1

        top1_idx = sorted_indices[0]
        top2_idx = sorted_indices[1]

        if assigned_pos == -1:
            # Assigned cluster not in centers (noise or unknown) — not boundary
            results.append((False, None, 0.0))
            continue

        if assigned_pos in (top1_idx, top2_idx):
            # Normal case: assigned cluster is one of the two closest.
            best_sim = similarities[top1_idx]
            second_best_sim = similarities[top2_idx]
            is_boundary = (best_sim - second_best_sim) < BOUNDARY_MARGIN
            sec_lbl = cids[top2_idx]
            total_sim = max(1e-4, best_sim + second_best_sim)
            sec_weight = second_best_sim / total_sim
            if not is_boundary:
                sec_lbl = None
                sec_weight = 0.0
            results.append((is_boundary, sec_lbl, sec_weight))
        else:
            # Edge case: assigned cluster is NOT in cosine top-2.
            # Compare assigned cluster similarity against the best other cluster.
            assigned_sim = similarities[assigned_pos]
            other_idx = top1_idx  # best cluster that is not the assigned one
            other_sim = similarities[other_idx]
            is_boundary = (assigned_sim - other_sim) < BOUNDARY_MARGIN
            sec_lbl = cids[other_idx]
            total_sim = max(1e-4, assigned_sim + other_sim)
            sec_weight = other_sim / total_sim
            if not is_boundary:
                sec_lbl = None
                sec_weight = 0.0
            results.append((is_boundary, sec_lbl, sec_weight))

    return results


def compute_evaluation(
    embeddings: np.ndarray, labels: np.ndarray
) -> "EvaluationContract | None":
    """
    Compute the EvaluationContract for a clustering result.

    Returns None if there are fewer than 2 valid (non-noise) clusters, since
    silhouette score is undefined in that case.

    constraint_satisfaction_rate and num_constraints_* are returned as None
    because manual-correction / constraint-storage is not yet implemented.
    Returning None is honest; do not substitute a fake 1.0.
    """
    if silhouette_score is None:
        logger.warning("sklearn not available — cannot compute silhouette score")
        return None

    valid_indices = [i for i, l in enumerate(labels) if l != -1]
    unique_valid = set(labels[i] for i in valid_indices)

    if len(unique_valid) < 2:
        logger.info("Fewer than 2 valid clusters — silhouette score undefined")
        return EvaluationContract(
            silhouette_score=None,
            num_clusters=len(unique_valid),
            constraint_satisfaction_rate=None,
            num_constraints_applied=None,
            num_constraints_violated=None,
        )

    valid_idx_arr = np.array(valid_indices)
    score = float(silhouette_score(
        embeddings[valid_idx_arr], labels[valid_idx_arr], metric='cosine'
    ))

    return EvaluationContract(
        silhouette_score=score,
        num_clusters=len(unique_valid),
        constraint_satisfaction_rate=None,
        num_constraints_applied=None,
        num_constraints_violated=None,
    )


def assign_stable_cluster_ids(docs: list, labels: np.ndarray, state_file: Path) -> dict:
    """
    Assign stable UUIDs to clusters based on overlap with previous state.

    Overlap formula (Task 12): overlap_pct = intersection / len(old_docs),
    i.e., "what fraction of the OLD cluster survived into this new cluster."
    This correctly treats a 2/3 old-doc overlap differently from a 2/10 one.

    Corpus pruning (Task 13): entries in the state file for doc_ids no longer
    present in the current corpus are removed before computing overlaps,
    preventing unbounded growth of cluster_mapping.json.
    """
    # Build new clusters: label -> set(doc_ids)
    new_clusters: dict[int, set] = {}
    current_doc_ids: set[str] = set()
    for i, doc in enumerate(docs):
        current_doc_ids.add(doc["id"])
        lbl = labels[i]
        if lbl == -1:
            continue
        new_clusters.setdefault(lbl, set()).add(doc["id"])

    # Load old state: uuid -> set(doc_ids)
    old_state: dict[str, set] = {}
    if state_file and state_file.exists():
        try:
            with open(state_file, "r") as f:
                raw_state = json.load(f)
                old_state = {k: set(v) for k, v in raw_state.items()}
        except Exception:
            pass

    # --- Corpus pruning (Task 13) ---
    # Remove doc_ids from old_state entries that are no longer in the corpus.
    # Also remove entire UUID entries that become empty after pruning.
    pruned_state: dict[str, set] = {}
    for old_uuid, old_docs in old_state.items():
        surviving = old_docs & current_doc_ids
        if surviving:
            pruned_state[old_uuid] = surviving
        else:
            logger.debug(
                "Pruned cluster %s — no surviving documents in current corpus", old_uuid
            )
    old_state = pruned_state

    label_to_uuid: dict[int, str] = {}
    used_uuids: set[str] = set()

    # Compute overlaps
    overlaps: list[tuple[float, int, int, str]] = []
    logger.debug("Overlap scores for new clusters against existing clusters:")
    for lbl, new_docs in new_clusters.items():
        for old_uuid, old_docs in old_state.items():
            intersection = len(new_docs & old_docs)
            if intersection > 0:
                # Task 12: denominator is len(old_docs) — measures "what fraction
                # of the old cluster survived", not a symmetric min() measure.
                overlap_pct = intersection / len(old_docs)
                logger.debug(
                    "  New label %s vs Old %s: overlap = %d docs (%.0f%%)",
                    lbl, old_uuid, intersection, overlap_pct * 100
                )
                if overlap_pct >= 0.5:
                    overlaps.append((overlap_pct, intersection, lbl, old_uuid))

    # Sort by overlap pct descending, then raw count descending
    overlaps.sort(reverse=True, key=lambda x: (x[0], x[1]))

    # Assign greedily
    for overlap_pct, intersection, lbl, old_uuid in overlaps:
        if lbl not in label_to_uuid and old_uuid not in used_uuids:
            logger.debug(
                "  -> Assigning Old %s to New label %s (overlap: %d docs, %.0f%%)",
                old_uuid, lbl, intersection, overlap_pct * 100
            )
            label_to_uuid[lbl] = old_uuid
            used_uuids.add(old_uuid)

    # Assign new UUIDs for remaining labels
    for lbl in new_clusters.keys():
        if lbl not in label_to_uuid:
            new_uuid = f"cluster-{uuid.uuid4().hex[:8]}"
            logger.debug(
                "  -> Minting NEW UUID %s for New label %s (no meaningful overlap)",
                new_uuid, lbl
            )
            label_to_uuid[lbl] = new_uuid
            used_uuids.add(new_uuid)

    # Save new state
    new_state: dict[str, list] = {}
    for lbl, new_docs in new_clusters.items():
        new_state[label_to_uuid[lbl]] = list(new_docs)

    if state_file:
        with open(state_file, "w") as f:
            json.dump(new_state, f, indent=2)

    return label_to_uuid
