import uuid
import json
import numpy as np
from dataclasses import dataclass
from pathlib import Path

try:
    import hdbscan
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install -r requirements.txt")
    hdbscan = KMeans = silhouette_score = None

@dataclass
class ClusteringOutput:
    doc_id: str
    cluster_id: str
    cluster_confidence: float
    is_boundary_document: bool

@dataclass
class EvaluationContract:
    silhouette_score: float
    num_clusters: int
    constraint_satisfaction_rate: float
    num_constraints_applied: int
    num_constraints_violated: int

def cluster_embeddings(embeddings: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Cluster embeddings using HDBSCAN, falling back to KMeans if it fails.
    (constrained-clustering SKILL.md Rule 1)
    Returns: (cluster_labels, cluster_centers)
    """
    num_samples = len(embeddings)
    
    # HDBSCAN configuration.
    # min_cluster_size=2 because demo corpus is very small (10-15 docs).
    # min_samples=1 to avoid aggressively marking things as noise.
    if num_samples >= 2:
        clusterer = hdbscan.HDBSCAN(min_cluster_size=2, min_samples=1, metric='euclidean')
        labels = clusterer.fit_predict(embeddings)
        
        # Check for degenerate results: everything is noise (-1) or just 1 cluster.
        unique_labels = set(l for l in labels if l != -1)
        if len(unique_labels) < 2 and num_samples >= 3:
            print("  [WARN] HDBSCAN produced degenerate clusters (mostly noise or single cluster). Falling back to KMeans.")
            labels = None
    else:
        labels = None

    # KMeans Fallback
    if labels is None:
        if num_samples < 3:
            # Too small to meaningfully cluster, just put them in cluster 0
            labels = np.zeros(num_samples, dtype=int)
        else:
            # Heuristic K: sqrt(N/2) or simple sweep. 
            # For 10-15 docs, 3 or 4 clusters is usually a good guess.
            best_k = max(2, min(5, num_samples // 3))
            print(f"  [INFO] Running KMeans with k={best_k}")
            kmeans = KMeans(n_clusters=best_k, random_state=42, n_init='auto')
            labels = kmeans.fit_predict(embeddings)

    # Compute centroids
    unique_clusters = set(l for l in labels if l != -1)
    centers = {}
    for cid in unique_clusters:
        cluster_points = embeddings[labels == cid]
        center = cluster_points.mean(axis=0)
        # Re-normalize centroid so it stays on the hypersphere
        center_norm = np.linalg.norm(center)
        centers[cid] = center / center_norm if center_norm > 0 else center

    return labels, centers

def compute_boundary_flags(embeddings: np.ndarray, labels: np.ndarray, centers: dict) -> list[bool]:
    """
    Determine if a document is a boundary document (SKILL.md Output Contract).
    True if similarity to second-nearest cluster is close to assigned cluster.
    """
    is_boundary = []
    
    # Pre-calculate center matrix
    cids = list(centers.keys())
    if len(cids) < 2:
        return [False] * len(embeddings)
        
    center_matrix = np.array([centers[cid] for cid in cids])
    
    for i, emb in enumerate(embeddings):
        # Ignore noise points for boundary calculation
        if labels[i] == -1:
            is_boundary.append(False)
            continue
            
        # Cosine similarity = dot product (since both are L2 normalized)
        similarities = np.dot(center_matrix, emb)
        
        # Sort similarities descending
        sorted_indices = np.argsort(similarities)[::-1]
        
        best_sim = similarities[sorted_indices[0]]
        second_best_sim = similarities[sorted_indices[1]]
        
        # Margin threshold: if the gap is less than 0.05, it's a boundary document.
        # This is a tunable parameter depending on typical distance distributions.
        MARGIN = 0.05
        is_boundary.append((best_sim - second_best_sim) < MARGIN)
        
    return is_boundary

def assign_stable_cluster_ids(docs, labels, state_file: Path) -> dict:
    """
    Assign stable UUIDs to clusters based on overlap with previous state.
    """
    # Build new clusters: label -> set(doc_ids)
    new_clusters = {}
    for i, doc in enumerate(docs):
        lbl = labels[i]
        if lbl == -1:
            continue
        if lbl not in new_clusters:
            new_clusters[lbl] = set()
        new_clusters[lbl].add(doc["id"])

    # Load old state: uuid -> set(doc_ids)
    old_state = {}
    if state_file and state_file.exists():
        try:
            with open(state_file, "r") as f:
                raw_state = json.load(f)
                old_state = {k: set(v) for k, v in raw_state.items()}
        except Exception:
            pass
            
    label_to_uuid = {}
    used_uuids = set()
    
    # Compute overlaps
    overlaps = []
    print("\n[DEBUG] Overlap scores for new clusters against existing clusters:")
    for lbl, new_docs in new_clusters.items():
        for old_uuid, old_docs in old_state.items():
            intersection = len(new_docs & old_docs)
            if intersection > 0:
                overlap_pct = intersection / min(len(new_docs), len(old_docs))
                print(f"  New label {lbl} vs Old {old_uuid}: overlap = {intersection} docs ({overlap_pct:.0%})")
                if overlap_pct >= 0.5:
                    overlaps.append((overlap_pct, intersection, lbl, old_uuid))
                
    # Sort by overlap pct descending, then raw count descending
    overlaps.sort(reverse=True, key=lambda x: (x[0], x[1]))
    
    # Assign greedily
    for overlap_pct, intersection, lbl, old_uuid in overlaps:
        if lbl not in label_to_uuid and old_uuid not in used_uuids:
            print(f"  -> Assigning Old {old_uuid} to New label {lbl} (overlap: {intersection} docs, {overlap_pct:.0%})")
            label_to_uuid[lbl] = old_uuid
            used_uuids.add(old_uuid)
            
    # Assign new UUIDs for remaining labels
    for lbl in new_clusters.keys():
        if lbl not in label_to_uuid:
            new_uuid = f"cluster-{uuid.uuid4().hex[:8]}" # Short UUID for readability
            print(f"  -> Minting NEW UUID {new_uuid} for New label {lbl} (no meaningful overlap)")
            label_to_uuid[lbl] = new_uuid
            used_uuids.add(new_uuid)
            
    # Save new state
    new_state = {}
    for lbl, new_docs in new_clusters.items():
        new_state[label_to_uuid[lbl]] = list(new_docs)
        
    if state_file:
        with open(state_file, "w") as f:
            json.dump(new_state, f, indent=2)
        
    return label_to_uuid
