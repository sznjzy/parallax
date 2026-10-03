"""
backend/topics/topic_modeling.py

Automatic Cluster Topic Modeling for Parallax (Phase 5).
Implements Class-based TF-IDF (c-TF-IDF) with optional KeyBERT semantic centroid alignment
to extract representative keywords, concise human-readable cluster titles, and topic metadata.

Public API
----------
    extract_cluster_topics(docs, doc_cluster_ids, cluster_centers=None, model=None, top_n=5) -> dict[str, dict]
    compute_ctfidf(cluster_texts, ngram_range=(1, 2), max_features=5000) -> (cluster_ids, terms, ctfidf_matrix)
"""

import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_METADATA_FILE = Path(__file__).resolve().parent.parent / "api" / "cluster_metadata.json"


try:
    from sklearn.feature_extraction.text import CountVectorizer
except ImportError:
    CountVectorizer = None

# Comprehensive academic/technical stopwords to filter generic filler words
DEFAULT_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can", "cannot", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "if", "in", "into", "is", "isn", "it", "its", "itself", "let",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn", "we", "were", "weren", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "won", "would", "you", "your", "yours", "yourself", "yourselves",
    # Common academic paper boilerplate words
    "paper", "study", "approach", "method", "proposed", "results", "based", "using", "presents",
    "show", "shown", "shows", "table", "figure", "section", "et", "al", "also", "one", "two", "three",
    "use", "used", "uses", "author", "authors", "conference", "journal", "university", "department",
    "introduction", "conclusion", "references", "abstract", "proceedings", "page", "pages", "vol", "no"
}


@dataclass
class TopicKeyword:
    keyword: str
    score: float


@dataclass
class TopicMetadata:
    cluster_id: str
    topic_label: str
    keywords: list[dict]
    top_terms: list[str]
    doc_count: int
    is_custom_label: bool = False

    def to_dict(self) -> dict:
        return asdict(self)



def _clean_text(text: str) -> str:
    """Normalize text: remove non-alphanumeric chars, lower case, extra whitespace."""
    if not text:
        return ""
    text = re.sub(r"[^a-zA-Z0-9\s_-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def compute_ctfidf(
    cluster_texts: dict[str, str],
    ngram_range: tuple[int, int] = (1, 2),
    max_features: int = 5000,
) -> tuple[list[str], list[str], np.ndarray]:
    """
    Compute class-based TF-IDF (c-TF-IDF) across cluster documents.

    Formula:
        W_{c, t} = tf_{c, t} * log(1 + A / f_t)
        where A = average words per cluster, f_t = total frequency of term t across all clusters.

    Returns:
        (cluster_ids_order, feature_names, ctfidf_matrix)
    """
    cids = list(cluster_texts.keys())
    texts = [cluster_texts[cid] for cid in cids]

    if CountVectorizer is None or not texts or all(not t.strip() for t in texts):
        return cids, [], np.zeros((len(cids), 0))

    try:
        vectorizer = CountVectorizer(
            ngram_range=ngram_range,
            stop_words=list(DEFAULT_STOPWORDS),
            max_features=max_features,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b",
            min_df=1,
        )
        count_matrix = vectorizer.fit_transform(texts).toarray().astype(float)
        feature_names = vectorizer.get_feature_names_out().tolist()
    except Exception as exc:
        logger.warning("CountVectorizer failed: %s — falling back to empty c-TF-IDF", exc)
        return cids, [], np.zeros((len(cids), 0))

    n_clusters, n_terms = count_matrix.shape
    if n_terms == 0 or n_clusters == 0:
        return cids, feature_names, np.zeros((n_clusters, n_terms))

    # Term frequencies per cluster: tf_{c, t}
    cluster_sums = count_matrix.sum(axis=1, keepdims=True)
    cluster_sums[cluster_sums == 0] = 1.0
    tf = count_matrix / cluster_sums

    # Global frequencies per term: f_t
    global_freq = count_matrix.sum(axis=0)
    
    # Average words per cluster: A
    avg_words = count_matrix.sum() / max(1, n_clusters)

    # Inverse cluster frequency: idf_t = log(1 + A / f_t)
    idf = np.log(1.0 + (avg_words / (global_freq + 1e-9)))

    ctfidf = tf * idf
    return cids, feature_names, ctfidf


def _format_topic_label(keywords: list[str], default_label: str) -> str:
    """Format the top 1-2 keywords into a clean, capitalized topic label."""
    if not keywords:
        return default_label

    # Pick top 1 or 2 keywords
    clean_kws = []
    for kw in keywords[:2]:
        # Filter out numbers-only or messy keywords
        kw_clean = re.sub(r"[-_]", " ", kw).strip()
        words = kw_clean.split()
        if len(words) == 1:
            clean_kws.append(words[0].capitalize())
        else:
            clean_kws.append(" ".join(w.capitalize() for w in words))

    if not clean_kws:
        return default_label

    if len(clean_kws) == 1:
        return clean_kws[0]
    
    # Combine 2 distinct keywords if they don't subsume each other
    if clean_kws[0].lower() in clean_kws[1].lower():
        return clean_kws[1]
    if clean_kws[1].lower() in clean_kws[0].lower():
        return clean_kws[0]

    return f"{clean_kws[0]} / {clean_kws[1]}"


def extract_cluster_topics(
    docs: list[dict],
    doc_cluster_ids: list[str],
    cluster_centers: dict[str, np.ndarray] | None = None,
    model: Any = None,
    top_n: int = 5,
    metadata_file: Path | None = None,
) -> dict[str, dict]:
    """
    Extract automatic topic models for all clusters in the corpus.

    Parameters
    ----------
    docs : list[dict]
        List of document dicts (must contain 'id' and optionally 'text' or 'filename').
    doc_cluster_ids : list[str]
        Cluster ID for each document (e.g. 'cluster-8aa90433' or 'noise-doc-1.pdf').
    cluster_centers : dict[str, np.ndarray] | None
        Normalized embedding centroids for real clusters (used for KeyBERT semantic scoring).
    model : Any | None
        Loaded SentenceTransformer model (optional, for KeyBERT embedding re-ranking).
    top_n : int
        Number of top representative keywords to extract per cluster.
    metadata_file : Path | None
        Optional path to cluster_metadata.json for persistent custom topic overrides.

    Returns
    -------
    dict[str, dict]
        Mapping cluster_id -> TopicMetadata.to_dict()
    """
    topics: dict[str, dict] = {}
    n_docs = len(docs)
    if n_docs == 0:
        return topics

    # Load custom metadata overrides if present
    custom_metadata = {}
    meta_path = metadata_file or DEFAULT_METADATA_FILE
    if meta_path and meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                custom_metadata = json.load(f)
        except Exception:
            custom_metadata = {}

    # Group document texts by cluster
    cluster_texts: dict[str, list[str]] = {}
    cluster_doc_counts: dict[str, int] = {}
    
    for i, doc in enumerate(docs):
        if i >= len(doc_cluster_ids):
            continue
        cid = doc_cluster_ids[i]
        text = doc.get("text", "")
        if not text:
            # Fallback to filename tokens
            fn = doc.get("filename", doc.get("id", ""))
            text = re.sub(r"\.pdf$", "", fn)
            text = re.sub(r"[-_0-9]", " ", text)

        cluster_texts.setdefault(cid, []).append(text)
        cluster_doc_counts[cid] = cluster_doc_counts.get(cid, 0) + 1

    # Aggregate text for non-noise clusters
    real_cluster_aggregated: dict[str, str] = {
        cid: _clean_text(" ".join(t_list))
        for cid, t_list in cluster_texts.items()
        if not cid.startswith("noise-")
    }

    # Handle noise outliers separately
    for cid, t_list in cluster_texts.items():
        if cid.startswith("noise-"):
            doc_fn = cid.replace("noise-doc-", "").replace("noise-", "")
            clean_fn = re.sub(r"\.pdf$", "", doc_fn)
            meta = TopicMetadata(
                cluster_id=cid,
                topic_label=f"Outlier ({clean_fn})" if clean_fn else "Outlier Document",
                keywords=[{"keyword": "outlier", "score": 1.0}],
                top_terms=["outlier"],
                doc_count=cluster_doc_counts.get(cid, 1),
                is_custom_label=False,
            )
            topics[cid] = meta.to_dict()

    if not real_cluster_aggregated:
        return topics

    # Compute c-TF-IDF across all real clusters
    ordered_cids, feature_names, ctfidf_matrix = compute_ctfidf(
        real_cluster_aggregated, ngram_range=(1, 2), max_features=5000
    )

    for row_idx, cid in enumerate(ordered_cids):
        short_id = cid.replace("cluster-", "")[:6]
        default_label = f"Topic {short_id}"
        custom_label = custom_metadata.get(cid, {}).get("custom_topic_label")
        is_custom = bool(custom_label and custom_label.strip())

        if ctfidf_matrix.shape[1] == 0:
            meta = TopicMetadata(
                cluster_id=cid,
                topic_label=custom_label.strip() if is_custom else default_label,
                keywords=[],
                top_terms=[],
                doc_count=cluster_doc_counts.get(cid, 0),
                is_custom_label=is_custom,
            )
            topics[cid] = meta.to_dict()
            continue

        scores = ctfidf_matrix[row_idx]
        top_indices = np.argsort(scores)[::-1][: top_n * 2]
        
        candidates = []
        for idx in top_indices:
            if scores[idx] > 0:
                candidates.append((feature_names[idx], float(scores[idx])))

        # KeyBERT semantic re-ranking if model and centroid are available
        if model is not None and cluster_centers and cid in cluster_centers and len(candidates) > 1:
            try:
                candidate_words = [c[0] for c in candidates]
                kw_embs = model.encode(candidate_words, convert_to_numpy=True)
                norms = np.linalg.norm(kw_embs, axis=1, keepdims=True)
                norms[norms == 0] = 1e-10
                kw_embs = kw_embs / norms

                centroid = cluster_centers[cid]
                cos_sims = np.dot(kw_embs, centroid)

                # Normalize c-tfidf scores to [0, 1]
                ctf_scores = np.array([c[1] for c in candidates])
                max_ctf = ctf_scores.max() if ctf_scores.max() > 0 else 1.0
                norm_ctf = ctf_scores / max_ctf

                # Combined score: 60% semantic similarity + 40% c-TF-IDF uniqueness
                combined_scores = 0.6 * cos_sims + 0.4 * norm_ctf
                reranked_indices = np.argsort(combined_scores)[::-1]

                ranked_candidates = [
                    (candidates[i][0], float(combined_scores[i]))
                    for i in reranked_indices
                ]
                candidates = ranked_candidates
            except Exception as exc:
                logger.debug("KeyBERT re-ranking failed for %s: %s", cid, exc)

        final_keywords = candidates[:top_n]
        top_terms = [kw[0] for kw in final_keywords]
        formatted_label = custom_label.strip() if is_custom else _format_topic_label(top_terms, default_label)

        meta = TopicMetadata(
            cluster_id=cid,
            topic_label=formatted_label,
            keywords=[{"keyword": kw[0], "score": round(kw[1], 4)} for kw in final_keywords],
            top_terms=top_terms,
            doc_count=cluster_doc_counts.get(cid, 0),
            is_custom_label=is_custom,
        )
        topics[cid] = meta.to_dict()

    return topics

