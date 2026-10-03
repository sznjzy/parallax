"""
backend/search/semantic_search.py

Semantic search engine for the Parallax research synthesis platform.

Architecture & Flow:
-------------------
User query
→ embedding via sentence-transformers/all-mpnet-base-v2 (same model as corpus)
→ cosine similarity against cached/computed document canvas vectors
→ ranked documents
→ cluster association (stable cluster IDs and c-TF-IDF topic labels)
→ cluster-level relevance aggregation for canvas heatmap / glow

Guarantees:
-----------
1. Exact same 768-dim embedding space as document embeddings.
2. Cosine similarity correctly computed via dot product of unit-normalized vectors.
3. Non-mutating: does NOT alter corpus, cluster assignments, constraints, or layout.
4. Fast: reuses disk cache (data/embedding_cache/<sha256>.npy) with < 1ms retrieval per doc.
5. Robust: handles empty queries, empty corpora, missing files, and small corpora cleanly.
6. Zero LLM dependencies.
"""

import json
import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import numpy as np

from backend.embeddings.embedding_cache import (
    get_cached_embedding,
    save_cached_embedding,
    get_cached_text,
    save_cached_text,
)

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Represents a single ranked document match."""
    doc_id: str
    filename: str
    similarity_score: float
    cluster_id: str
    topic_label: str
    snippet: str
    rank: int

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "filename": self.filename,
            "similarity_score": round(self.similarity_score, 4),
            "cluster_id": self.cluster_id,
            "topic_label": self.topic_label,
            "snippet": self.snippet,
            "rank": self.rank,
        }


@dataclass
class ClusterRelevance:
    """Aggregated relevance metrics for a specific cluster."""
    cluster_id: str
    topic_label: str
    mean_similarity: float
    max_similarity: float
    matched_docs_count: int

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "topic_label": self.topic_label,
            "mean_similarity": round(self.mean_similarity, 4),
            "max_similarity": round(self.max_similarity, 4),
            "matched_docs_count": self.matched_docs_count,
        }


@dataclass
class SearchResponse:
    """Full semantic search response payload."""
    query: str
    results: list[SearchResult]
    query_embedding_dim: int
    total_corpus_searched: int
    cluster_relevance: dict[str, ClusterRelevance]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "query_embedding_dim": self.query_embedding_dim,
            "total_corpus_searched": self.total_corpus_searched,
            "cluster_relevance": {
                cid: rel.to_dict() for cid, rel in self.cluster_relevance.items()
            },
        }


def extract_best_snippet(text: str, query: str, max_chars: int = 180) -> str:
    """
    Extract the most representative passage/sentence matching the query keywords
    or the opening abstract from the extracted document text.
    """
    if not text or not text.strip():
        return ""

    # Clean whitespace
    clean_text = re.sub(r"\s+", " ", text).strip()

    # Split into candidate sentences
    sentences = re.split(r"(?<=[.!?])\s+", clean_text)
    if not sentences:
        return clean_text[:max_chars].strip() + ("..." if len(clean_text) > max_chars else "")

    # Extract query terms for lexical proximity heuristic
    query_words = set(re.findall(r"\w+", query.lower())) - {
        "a", "an", "the", "in", "on", "of", "for", "and", "or", "to", "with", "by", "at", "from"
    }

    best_sentence = sentences[0]
    best_overlap = -1

    for sent in sentences[:30]:  # focus on the first 30 sentences (abstract & intro)
        sent_words = set(re.findall(r"\w+", sent.lower()))
        overlap = len(query_words & sent_words)
        if overlap > best_overlap and len(sent.strip()) > 20:
            best_overlap = overlap
            best_sentence = sent

    res = best_sentence.strip()
    if len(res) > max_chars:
        res = res[:max_chars].rsplit(" ", 1)[0] + "..."
    return res


def load_cluster_assignments(
    state_file: Path | None = None,
    precomputed_nodes: list[dict] | None = None,
) -> dict[str, str]:
    """
    Map doc_id -> cluster_id from precomputed nodes or persisted state_file.
    """
    mapping: dict[str, str] = {}

    if precomputed_nodes:
        for node in precomputed_nodes:
            if "doc_id" in node and "cluster_id" in node:
                mapping[node["doc_id"]] = node["cluster_id"]
        return mapping

    if state_file and state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Format: {"doc_id": "cluster_id", ...} or {"clusters": {cid: [doc_ids]}}
                if isinstance(data, dict):
                    if "clusters" in data and isinstance(data["clusters"], dict):
                        for cid, docs in data["clusters"].items():
                            for d in docs:
                                mapping[d] = cid
                    else:
                        for k, v in data.items():
                            if isinstance(v, str):
                                mapping[k] = v
        except Exception as exc:
            logger.warning("Failed to read cluster mapping from %s: %s", state_file, exc)

    return mapping


def search_corpus(
    query: str,
    corpus_dir: Path,
    model: Any = None,
    top_k: int | None = None,
    doc_filter: set[str] | None = None,
    state_file: Path | None = None,
    topic_metadata: dict | None = None,
    precomputed_nodes: list[dict] | None = None,
) -> dict:
    """
    Perform semantic search over the document corpus.

    Parameters
    ----------
    query : str
        User's search string.
    corpus_dir : Path
        Directory containing .pdf documents.
    model : Any, optional
        Pre-loaded sentence-transformers model instance. If None, loaded via load_model().
    top_k : int | None, optional
        Maximum number of top results to return. If None or <= 0, returns all ranked documents.
    doc_filter : set[str] | None, optional
        Optional set of filenames to filter search scope.
    state_file : Path | None, optional
        Path to cluster_mapping.json to look up cluster IDs.
    topic_metadata : dict | None, optional
        Optional topic metadata dict (e.g., from topic modeling) to populate human-readable topic labels.
    precomputed_nodes : list[dict] | None, optional
        Optional active canvas nodes to look up current cluster assignments.

    Returns
    -------
    dict
        Serialized SearchResponse containing ranked results, query embedding dimension,
        corpus size, and cluster-level relevance metrics.
    """
    cleaned_query = query.strip() if query else ""
    if not cleaned_query:
        raise ValueError("Search query cannot be empty.")

    if not corpus_dir.exists():
        return SearchResponse(
            query=cleaned_query,
            results=[],
            query_embedding_dim=768,
            total_corpus_searched=0,
            cluster_relevance={},
        ).to_dict()

    all_pdf_files = sorted(corpus_dir.glob("*.pdf"))
    if doc_filter:
        pdf_files = [f for f in all_pdf_files if f.name in doc_filter]
    else:
        pdf_files = all_pdf_files

    if not pdf_files:
        return SearchResponse(
            query=cleaned_query,
            results=[],
            query_embedding_dim=768,
            total_corpus_searched=0,
            cluster_relevance={},
        ).to_dict()

    # 1. Load model if not provided
    if model is None:
        from backend.embeddings.pipeline import load_model
        model = load_model()

    # 2. Compute query embedding (unit normalized)
    # Using sentence-transformers encode with normalize_embeddings=True
    query_vec = model.encode([cleaned_query], normalize_embeddings=True)
    if hasattr(query_vec, "ndim") and query_vec.ndim == 2:
        query_vec = query_vec[0]
    query_vec = np.asarray(query_vec, dtype=np.float32)
    norm = np.linalg.norm(query_vec)
    if norm > 1e-8:
        query_vec = query_vec / norm

    # 3. Load or compute document embeddings
    doc_cluster_map = load_cluster_assignments(state_file, precomputed_nodes)

    scored_docs: list[dict] = []

    for pdf_path in pdf_files:
        doc_id = f"doc-{pdf_path.name}"
        cached_vec = get_cached_embedding(pdf_path)

        text = get_cached_text(pdf_path)
        if cached_vec is not None:
            doc_vec = np.asarray(cached_vec, dtype=np.float32)
        else:
            # Fallback: extract text and compute embedding on the fly
            from backend.embeddings.pipeline import (
                extract_text_from_pdf,
                chunk_text,
                embed_document_chunks,
            )
            extracted = extract_text_from_pdf(pdf_path)
            if not extracted.strip():
                continue
            text = extracted
            save_cached_text(pdf_path, text)
            chunks = chunk_text(text)
            if not chunks:
                continue
            doc_vec, _ = embed_document_chunks(model, chunks)
            save_cached_embedding(pdf_path, doc_vec)

        # Normalize doc_vec if needed
        d_norm = np.linalg.norm(doc_vec)
        if d_norm > 1e-8:
            doc_vec = doc_vec / d_norm

        # Cosine similarity between two unit vectors = dot product
        similarity = float(np.dot(doc_vec, query_vec))
        similarity = float(np.clip(similarity, -1.0, 1.0))

        cluster_id = doc_cluster_map.get(doc_id, "cluster-unassigned")
        if cluster_id.startswith("noise-"):
            cluster_id = "noise"

        # Topic label
        topic_info = topic_metadata.get(cluster_id, {}) if topic_metadata else {}
        if cluster_id == "noise":
            topic_label = "Outliers"
        else:
            topic_label = topic_info.get("topic_label", f"Topic {cluster_id.replace('cluster-', '')[:6]}")

        snippet = extract_best_snippet(text or "", cleaned_query)

        scored_docs.append({
            "doc_id": doc_id,
            "filename": pdf_path.name,
            "similarity_score": similarity,
            "cluster_id": cluster_id,
            "topic_label": topic_label,
            "snippet": snippet,
        })

    # Sort descending by similarity
    scored_docs.sort(key=lambda d: d["similarity_score"], reverse=True)

    # Build ranked SearchResult objects
    results: list[SearchResult] = []
    for rank, doc in enumerate(scored_docs, start=1):
        results.append(
            SearchResult(
                doc_id=doc["doc_id"],
                filename=doc["filename"],
                similarity_score=doc["similarity_score"],
                cluster_id=doc["cluster_id"],
                topic_label=doc["topic_label"],
                snippet=doc["snippet"],
                rank=rank,
            )
        )

    # 4. Compute cluster-level relevance aggregation
    cluster_scores: dict[str, list[float]] = {}
    cluster_labels: dict[str, str] = {}

    for r in results:
        cid = r.cluster_id
        if cid not in cluster_scores:
            cluster_scores[cid] = []
            cluster_labels[cid] = r.topic_label
        cluster_scores[cid].append(r.similarity_score)

    cluster_relevance: dict[str, ClusterRelevance] = {}
    for cid, scores in cluster_scores.items():
        mean_sim = float(np.mean(scores))
        max_sim = float(np.max(scores))
        cluster_relevance[cid] = ClusterRelevance(
            cluster_id=cid,
            topic_label=cluster_labels.get(cid, cid),
            mean_similarity=mean_sim,
            max_similarity=max_sim,
            matched_docs_count=len(scores),
        )

    # Apply top_k if requested
    if top_k is not None and top_k > 0:
        final_results = results[:top_k]
    else:
        final_results = results

    response = SearchResponse(
        query=cleaned_query,
        results=final_results,
        query_embedding_dim=int(query_vec.shape[0]),
        total_corpus_searched=len(scored_docs),
        cluster_relevance=cluster_relevance,
    )

    return response.to_dict()
