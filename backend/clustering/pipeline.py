"""
clustering/pipeline.py

Constraint-aware clustering pipeline — HDBSCAN with KMeans fallback,
stable cluster UUID lineage, boundary document detection, and evaluation.

Public API
----------
    cluster_embeddings(embeddings) -> (labels, centers)
    compute_boundary_flags(embeddings, labels, centers) -> list[tuple[bool, int | None, float]]
    assign_stable_cluster_ids(docs, labels, state_file) -> dict
    compute_evaluation(embeddings, labels_or_cluster_ids) -> EvaluationContract | None
    run_constraint_aware_clustering(docs, embeddings, state_file, forced_assignments) -> dict

Constants
---------
    BOUNDARY_MARGIN : float
        Canonical boundary-detection threshold (cosine-similarity gap).
        Imported by api/pipeline.py and physics.py so there is exactly one definition.
"""

import logging
import uuid
import json
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.clustering.constraints import evaluate_constraint_satisfaction

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
# Canonical boundary-detection margin.
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
    constraint_satisfaction_rate: float | None
    num_constraints_applied: int | None
    num_constraints_violated: int | None


def cluster_embeddings(embeddings: np.ndarray) -> tuple[np.ndarray, dict]:
    """
    Cluster embeddings using HDBSCAN, falling back to KMeans if it fails.
    Returns: (cluster_labels, cluster_centers_dict)
    """
    num_samples = len(embeddings)
    if num_samples == 0:
        return np.array([], dtype=int), {}

    if num_samples == 1:
        norm = np.linalg.norm(embeddings[0])
        center = embeddings[0] / norm if norm > 0 else embeddings[0]
        return np.zeros(1, dtype=int), {0: center}

    labels = None
    if num_samples >= 2 and hdbscan is not None:
        try:
            clusterer = hdbscan.HDBSCAN(min_cluster_size=2, min_samples=1, metric='euclidean')
            labels = clusterer.fit_predict(embeddings)

            unique_labels = set(l for l in labels if l != -1)
            if len(unique_labels) < 2 and num_samples >= 3:
                logger.warning(
                    "HDBSCAN produced degenerate clusters (mostly noise or single cluster). "
                    "Falling back to KMeans."
                )
                labels = None
        except Exception as exc:
            logger.warning("HDBSCAN failed with error: %s — falling back to KMeans", exc)
            labels = None

    # KMeans Fallback
    if labels is None:
        if num_samples < 3 or KMeans is None:
            labels = np.zeros(num_samples, dtype=int)
        else:
            best_k = max(2, min(5, num_samples // 3))
            logger.info("Running KMeans with k=%d", best_k)
            kmeans = KMeans(n_clusters=best_k, random_state=42, n_init='auto')
            labels = kmeans.fit_predict(embeddings)

    # Compute centroids for non-noise clusters
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
        assigned_pos = cids.index(assigned_label) if assigned_label in cids else -1

        top1_idx = sorted_indices[0]
        top2_idx = sorted_indices[1]

        if assigned_pos == -1:
            results.append((False, None, 0.0))
            continue

        if assigned_pos in (top1_idx, top2_idx):
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
            assigned_sim = similarities[assigned_pos]
            other_idx = top1_idx
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


def assign_stable_cluster_ids(docs: list, labels: np.ndarray, state_file: Path | None = None) -> dict[int, str]:
    """
    Assign stable UUIDs to clusters based on overlap with previous state.
    """
    # Build new clusters: label -> set(doc_ids)
    new_clusters: dict[int, set] = {}
    current_doc_ids: set[str] = set()
    for i, doc in enumerate(docs):
        current_doc_ids.add(doc["id"])
        if i < len(labels):
            lbl = labels[i]
            if lbl == -1:
                continue
            new_clusters.setdefault(lbl, set()).add(doc["id"])

    # Load old state: uuid -> set(doc_ids)
    old_state: dict[str, set] = {}
    if state_file and Path(state_file).exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                raw_state = json.load(f)
                old_state = {k: set(v) for k, v in raw_state.items()}
        except Exception:
            pass

    # Corpus pruning
    pruned_state: dict[str, set] = {}
    for old_uuid, old_docs in old_state.items():
        surviving = old_docs & current_doc_ids
        if surviving:
            pruned_state[old_uuid] = surviving
        else:
            logger.debug("Pruned cluster %s — no surviving documents in corpus", old_uuid)
    old_state = pruned_state

    label_to_uuid: dict[int, str] = {}
    used_uuids: set[str] = set()

    # Compute overlaps
    overlaps: list[tuple[float, int, int, str]] = []
    for lbl, new_docs in new_clusters.items():
        for old_uuid, old_docs in old_state.items():
            intersection = len(new_docs & old_docs)
            if intersection > 0 and len(old_docs) > 0:
                overlap_pct = intersection / len(old_docs)
                if overlap_pct >= 0.5:
                    overlaps.append((overlap_pct, intersection, lbl, old_uuid))

    # Sort by overlap pct descending, then raw count descending
    overlaps.sort(reverse=True, key=lambda x: (x[0], x[1]))

    # Assign greedily
    for overlap_pct, intersection, lbl, old_uuid in overlaps:
        if lbl not in label_to_uuid and old_uuid not in used_uuids:
            label_to_uuid[lbl] = old_uuid
            used_uuids.add(old_uuid)

    # Assign new UUIDs for remaining labels
    for lbl in new_clusters.keys():
        if lbl not in label_to_uuid:
            new_uuid = f"cluster-{uuid.uuid4().hex[:8]}"
            label_to_uuid[lbl] = new_uuid
            used_uuids.add(new_uuid)

    # Save new state if state_file given
    if state_file:
        new_state: dict[str, list] = {}
        for lbl, new_docs in new_clusters.items():
            if lbl in label_to_uuid:
                new_state[label_to_uuid[lbl]] = list(new_docs)
        try:
            Path(state_file).parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(new_state, f, indent=2)
        except Exception as exc:
            logger.warning("Could not persist cluster_mapping state: %s", exc)

    return label_to_uuid


def compute_evaluation(
    embeddings: np.ndarray, labels_or_cluster_ids: list[str] | np.ndarray
) -> "EvaluationContract | None":
    """
    Compute EvaluationContract for clustering results.
    Accepts either numeric labels (-1 for noise) or string cluster IDs ("noise-*" for noise).
    """
    if len(embeddings) == 0:
        return EvaluationContract(
            silhouette_score=None,
            num_clusters=0,
            constraint_satisfaction_rate=None,
            num_constraints_applied=None,
            num_constraints_violated=None,
        )

    # Convert to uniform string IDs
    if isinstance(labels_or_cluster_ids, np.ndarray) and np.issubdtype(labels_or_cluster_ids.dtype, np.integer):
        str_labels = [f"cluster_{l}" if l != -1 else "noise" for l in labels_or_cluster_ids]
    else:
        str_labels = [str(item) for item in labels_or_cluster_ids]

    valid_indices = [i for i, cid in enumerate(str_labels) if not cid.startswith("noise")]
    unique_valid = sorted(list(set(str_labels[i] for i in valid_indices)))

    score = None
    if len(unique_valid) >= 2 and len(valid_indices) >= 3 and silhouette_score is not None:
        cid_to_int = {cid: idx for idx, cid in enumerate(unique_valid)}
        num_labels = np.array([cid_to_int[str_labels[i]] for i in valid_indices])
        try:
            score = float(silhouette_score(
                embeddings[valid_indices], num_labels, metric='cosine'
            ))
        except Exception as exc:
            logger.debug("Silhouette computation skipped/failed: %s", exc)
            score = None

    return EvaluationContract(
        silhouette_score=score,
        num_clusters=len(unique_valid),
        constraint_satisfaction_rate=None,
        num_constraints_applied=None,
        num_constraints_violated=None,
    )


def run_constraint_aware_clustering(
    docs: list[dict],
    embeddings: np.ndarray,
    state_file: Path | None = None,
    forced_assignments: dict[str, str] | None = None,
) -> dict:
    """
    Execute true constraint-aware clustering (ADR-001).

    Workflow:
      1. Separate all documents into unconstrained and constrained sets.
      2. Run HDBSCAN ONLY on unconstrained document embeddings.
      3. Track and assign stable cluster UUIDs for discovered unconstrained clusters.
      4. Merge constrained documents directly into their forced cluster assignments.
      5. Compute global cluster centroids for all active non-noise clusters.
      6. Compute boundary document detection against global cluster centroids.
      7. Calculate complete evaluation metrics (silhouette score + constraint satisfaction).

    Returns a dict with:
      - doc_cluster_ids: list[str] (length N)
      - boundary_flags: list[tuple[bool, str | None, float]] (length N)
      - cluster_centers: dict[str, np.ndarray] (mapping cluster_id -> normalized centroid)
      - evaluation: EvaluationContract
      - unconstrained_indices: list[int]
      - constrained_indices: list[int]
    """
    N = len(docs)
    if N == 0:
        return {
            "doc_cluster_ids": [],
            "boundary_flags": [],
            "cluster_centers": {},
            "evaluation": EvaluationContract(None, 0, None, 0, 0),
            "unconstrained_indices": [],
            "constrained_indices": [],
        }

    if forced_assignments is None:
        forced_assignments = {}

    unconstrained_indices: list[int] = []
    constrained_indices: list[int] = []
    unconstrained_docs: list[dict] = []

    for i, doc in enumerate(docs):
        doc_id = doc["id"]
        if doc_id in forced_assignments:
            constrained_indices.append(i)
        else:
            unconstrained_indices.append(i)
            unconstrained_docs.append(doc)

    doc_cluster_ids = [""] * N
    M = len(unconstrained_docs)

    # -----------------------------------------------------------------------
    # Step 2 & 3: Unconstrained clustering ONLY on unconstrained documents
    # -----------------------------------------------------------------------
    if M == 0:
        # All documents constrained — no unconstrained clustering
        pass
    elif M == 1:
        # Single unconstrained document
        unconstrained_labels = np.zeros(1, dtype=int)
        label_to_uuid = assign_stable_cluster_ids(unconstrained_docs, unconstrained_labels, state_file)
        doc_cluster_ids[unconstrained_indices[0]] = label_to_uuid.get(0, f"cluster-{uuid.uuid4().hex[:8]}")
    else:
        # M >= 2: Run HDBSCAN exclusively on unconstrained embeddings
        unconstrained_embs = embeddings[unconstrained_indices]
        unconstrained_labels, _ = cluster_embeddings(unconstrained_embs)
        label_to_uuid = assign_stable_cluster_ids(unconstrained_docs, unconstrained_labels, state_file)

        for u_idx, orig_idx in enumerate(unconstrained_indices):
            lbl = unconstrained_labels[u_idx]
            if lbl == -1:
                doc_cluster_ids[orig_idx] = f"noise-{docs[orig_idx]['id']}"
            else:
                doc_cluster_ids[orig_idx] = label_to_uuid[lbl]

    # -----------------------------------------------------------------------
    # Step 4: Merge constrained assignments directly
    # -----------------------------------------------------------------------
    for orig_idx in constrained_indices:
        doc_id = docs[orig_idx]["id"]
        doc_cluster_ids[orig_idx] = forced_assignments[doc_id]

    # -----------------------------------------------------------------------
    # Step 5: Compute global cluster centroids for all active non-noise clusters
    # -----------------------------------------------------------------------
    cluster_centers: dict[str, np.ndarray] = {}
    unique_real_clusters = sorted(list(set(cid for cid in doc_cluster_ids if not cid.startswith("noise-"))))

    for cid in unique_real_clusters:
        member_indices = [i for i, c in enumerate(doc_cluster_ids) if c == cid]
        if member_indices:
            member_embs = embeddings[member_indices]
            center = member_embs.mean(axis=0)
            norm = np.linalg.norm(center)
            cluster_centers[cid] = center / norm if norm > 0 else center

    # -----------------------------------------------------------------------
    # Step 6: Boundary document detection against global cluster centroids
    # -----------------------------------------------------------------------
    boundary_flags: list[tuple[bool, str | None, float]] = [(False, None, 0.0)] * N
    cids = list(cluster_centers.keys())

    if len(cids) >= 2:
        center_matrix = np.array([cluster_centers[cid] for cid in cids])
        for orig_idx in unconstrained_indices:
            cid = doc_cluster_ids[orig_idx]
            if cid.startswith("noise-") or cid not in cids:
                continue

            emb = embeddings[orig_idx]
            similarities = np.dot(center_matrix, emb)
            sorted_indices = np.argsort(similarities)[::-1]

            assigned_pos = cids.index(cid)
            top1_idx = sorted_indices[0]
            top2_idx = sorted_indices[1]

            if assigned_pos in (top1_idx, top2_idx):
                best_sim = similarities[top1_idx]
                second_best_sim = similarities[top2_idx]
                is_b = (best_sim - second_best_sim) < BOUNDARY_MARGIN
                sec_cid = cids[top2_idx] if cids[top2_idx] != cid else (cids[top1_idx] if len(cids) > 1 else None)
                total_sim = max(1e-4, best_sim + second_best_sim)
                sec_w = second_best_sim / total_sim
                if not is_b:
                    sec_cid = None
                    sec_w = 0.0
                boundary_flags[orig_idx] = (is_b, sec_cid, sec_w)
            else:
                assigned_sim = similarities[assigned_pos]
                other_idx = top1_idx
                other_sim = similarities[other_idx]
                is_b = (assigned_sim - other_sim) < BOUNDARY_MARGIN
                sec_cid = cids[other_idx]
                total_sim = max(1e-4, assigned_sim + other_sim)
                sec_w = other_sim / total_sim
                if not is_b:
                    sec_cid = None
                    sec_w = 0.0
                boundary_flags[orig_idx] = (is_b, sec_cid, sec_w)

    # -----------------------------------------------------------------------
    # Step 7: Complete evaluation (silhouette score + constraint satisfaction)
    # -----------------------------------------------------------------------
    valid_indices = [i for i, cid in enumerate(doc_cluster_ids) if not cid.startswith("noise-")]
    unique_valid_cids = sorted(list(set(doc_cluster_ids[i] for i in valid_indices)))

    sil_score = None
    if len(unique_valid_cids) >= 2 and len(valid_indices) >= 3 and silhouette_score is not None:
        cid_to_num = {cid: idx for idx, cid in enumerate(unique_valid_cids)}
        num_labels = np.array([cid_to_num[doc_cluster_ids[i]] for i in valid_indices])
        try:
            sil_score = float(silhouette_score(
                embeddings[valid_indices], num_labels, metric='cosine'
            ))
        except Exception as exc:
            logger.debug("Silhouette computation exception: %s", exc)
            sil_score = None

    csr, applied, violated = evaluate_constraint_satisfaction(
        [{"doc_id": docs[i]["id"], "cluster_id": doc_cluster_ids[i]} for i in range(N)],
        forced_assignments,
    )

    evaluation = EvaluationContract(
        silhouette_score=sil_score,
        num_clusters=len(unique_valid_cids),
        constraint_satisfaction_rate=csr,
        num_constraints_applied=applied,
        num_constraints_violated=violated,
    )

    return {
        "doc_cluster_ids": doc_cluster_ids,
        "boundary_flags": boundary_flags,
        "cluster_centers": cluster_centers,
        "evaluation": evaluation,
        "unconstrained_indices": unconstrained_indices,
        "constrained_indices": constrained_indices,
    }
