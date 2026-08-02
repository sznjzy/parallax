import os
import uuid
import json
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Any

# Ensure graceful fallback if dependencies aren't installed yet
try:
    from sentence_transformers import SentenceTransformer
    import hdbscan
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    import pypdf
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install -r requirements.txt")
    # Stub classes so the file still parses
    SentenceTransformer = hdbscan = KMeans = silhouette_score = pypdf = None


# Configuration based on SKILL.md rules
MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs"

# =============================================================================
# Contracts
# =============================================================================

@dataclass
class EmbeddingOutput:
    doc_id: str
    embedding: list[float]
    model_name: str
    normalized: bool
    source_type: str

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


# =============================================================================
# Core Pipeline
# =============================================================================

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF, logging failures explicitly."""
    text_chunks = []
    try:
        if pypdf is None:
            raise ImportError("pypdf is not installed")
        
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_chunks.append(text)
        return "\n\n".join(text_chunks)
    except Exception as e:
        print(f"  [FAIL] Could not parse PDF {pdf_path.name}: {e}")
        return ""


def chunk_text(text: str, max_words: int = 400) -> list[str]:
    """
    Very basic chunking logic.
    embedding-pipeline SKILL.md Rule 2: chunk documents longer than ~2 pages.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def load_model() -> Any:
    """Load the single authorized embedding model (SKILL.md Rule 1)."""
    if SentenceTransformer is None:
        raise ImportError("sentence_transformers is not installed")
    print(f"Loading embedding model: {MODEL_NAME}...")
    return SentenceTransformer(MODEL_NAME)


def generate_embeddings(model: Any, texts: list[str]) -> np.ndarray:
    """Generate and L2-normalize embeddings (SKILL.md Rule 3)."""
    # encode() often returns a numpy array, but we ensure it and normalize
    embeddings = model.encode(texts, convert_to_numpy=True)
    # L2 Normalization
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    normalized_embeddings = embeddings / norms
    return normalized_embeddings


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


def main():
    print("\nParallax -- Spike C: Embedding & Clustering Validation")
    print("=" * 65)
    
    if not SAMPLE_DOCS_DIR.exists():
        print(f"[FAIL] Directory not found: {SAMPLE_DOCS_DIR}")
        return

    pdf_files = list(SAMPLE_DOCS_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDFs in {SAMPLE_DOCS_DIR.name}/")
    
    if not pdf_files:
        print("[FAIL] No PDFs to process. Stopping.")
        return
        
    if SentenceTransformer is None:
        print("[FAIL] Dependencies not loaded. Stopping.")
        return

    # 1. Ingestion
    print("\n1. INGESTION")
    print("-" * 50)
    docs = []
    for pdf_path in pdf_files:
        print(f"  Reading {pdf_path.name}...")
        text = extract_text_from_pdf(pdf_path)
        if text.strip():
            # Mean-pooling abstraction: for the spike, we'll embed the first 
            # substantial chunk as the document's 'canvas position' vector 
            # to represent its main topic (e.g. abstract/intro).
            chunks = chunk_text(text)
            if chunks:
                docs.append({
                    "id": str(uuid.uuid4()),
                    "filename": pdf_path.name,
                    "text": chunks[0]  # Using first chunk for canvas vector
                })
        else:
            print(f"  [WARN] No text extracted from {pdf_path.name}")

    if not docs:
        print("[FAIL] No valid text extracted from any PDFs.")
        return

    # 2. Embedding
    print("\n2. EMBEDDING")
    print("-" * 50)
    model = load_model()
    texts = [d["text"] for d in docs]
    embeddings = generate_embeddings(model, texts)
    
    # Create Output Contract objects
    embedding_outputs = []
    for i, d in enumerate(docs):
        output = EmbeddingOutput(
            doc_id=d["id"],
            embedding=embeddings[i].tolist(),
            model_name=MODEL_NAME,
            normalized=True,
            source_type="pdf"
        )
        embedding_outputs.append(output)
        
    print(f"  Generated {len(embedding_outputs)} embeddings (L2-normalized).")

    # 3. Clustering
    print("\n3. CLUSTERING")
    print("-" * 50)
    labels, centers = cluster_embeddings(embeddings)
    is_boundary = compute_boundary_flags(embeddings, labels, centers)
    
    # Calculate Silhouette Score
    # Silhouette score requires at least 2 clusters (excluding noise)
    valid_indices = [i for i, l in enumerate(labels) if l != -1]
    unique_valid = set(labels[i] for i in valid_indices)
    
    if len(unique_valid) >= 2:
        score = silhouette_score(embeddings[valid_indices], labels[valid_indices], metric='cosine')
    else:
        score = 0.0

    eval_contract = EvaluationContract(
        silhouette_score=float(score),
        num_clusters=len(unique_valid),
        constraint_satisfaction_rate=1.0, # No constraints yet
        num_constraints_applied=0,
        num_constraints_violated=0
    )

    # 4. Evaluation & Report
    print("\n4. EVALUATION & REPORT")
    print("-" * 50)
    print("Evaluation Contract:")
    print(json.dumps(eval_contract.__dict__, indent=2))
    
    print("\nCluster Groupings:")
    clusters = {}
    for i, (l, b) in enumerate(zip(labels, is_boundary)):
        cname = f"Cluster {l}" if l != -1 else "Noise (-1)"
        if cname not in clusters:
            clusters[cname] = []
        
        flag = " [BOUNDARY]" if b else ""
        clusters[cname].append(docs[i]["filename"] + flag)

    for cname, fnames in sorted(clusters.items()):
        print(f"\n  {cname}:")
        for fn in fnames:
            print(f"    - {fn}")

    # 5. Sanity Outputs (Similarity Matrix)
    print("\n5. DOCUMENT SIMILARITY PAIRS (Sanity Check)")
    print("-" * 50)
    
    pairs = []
    n = len(docs)
    for i in range(n):
        for j in range(i + 1, n):
            # dot product is cosine similarity for L2 normalized vectors
            sim = np.dot(embeddings[i], embeddings[j])
            pairs.append((sim, docs[i]["filename"], docs[j]["filename"]))
            
    # Sort by highest similarity
    pairs.sort(reverse=True)
    
    print("  Top most similar document pairs:")
    for sim, f1, f2 in pairs[:15]:  # Show top 15 pairs
        print(f"    {sim:.3f} | {f1} <-> {f2}")

    print("\n  Top least similar document pairs:")
    for sim, f1, f2 in pairs[-5:]:  # Show bottom 5 pairs
        print(f"    {sim:.3f} | {f1} <-> {f2}")

    print("\n  All similarity pairs involving paper16.pdf:")
    for sim, f1, f2 in pairs:
        if f1 == "paper16.pdf" or f2 == "paper16.pdf":
            print(f"    {sim:.3f} | {f1} <-> {f2}")


if __name__ == "__main__":
    main()
