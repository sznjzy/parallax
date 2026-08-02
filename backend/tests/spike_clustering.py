import os
import uuid
import json
import numpy as np
from pathlib import Path

# Ensure graceful fallback if dependencies aren't installed yet
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics import silhouette_score
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install -r requirements.txt")
    SentenceTransformer = silhouette_score = None

from backend.embeddings.pipeline import (
    MODEL_NAME,
    EmbeddingOutput,
    extract_text_from_pdf,
    chunk_text,
    load_model,
    generate_embeddings
)

from backend.clustering.pipeline import (
    ClusteringOutput,
    EvaluationContract,
    cluster_embeddings,
    compute_boundary_flags
)

SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs"



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
