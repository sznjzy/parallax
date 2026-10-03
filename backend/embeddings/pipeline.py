"""
embeddings/pipeline.py

Embedding pipeline for the Parallax backend.

Public API
----------
    load_model() -> SentenceTransformer
    extract_text_from_pdf(pdf_path) -> str
    chunk_text(text, max_words=400) -> list[str]
    generate_embeddings(model, texts) -> np.ndarray
    embed_document_chunks(model, chunks) -> (canvas_vec, per_chunk_vecs)

Output contract (EmbeddingOutput dataclass):
    doc_id, embedding, model_name, normalized, source_type
"""

import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Any

try:
    from sentence_transformers import SentenceTransformer
    import pypdf
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install -r requirements.txt")
    SentenceTransformer = pypdf = None

MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"

@dataclass
class EmbeddingOutput:
    doc_id: str
    embedding: list[float]
    model_name: str
    normalized: bool
    source_type: str  # "pdf" | "text" | "query"


def extract_pages_from_pdf(pdf_path: Path) -> list[dict[str, Any]]:
    """
    Extract text page-by-page from a PDF, logging failures explicitly.
    Returns list of dicts: [{"page_number": 1, "text": "..."}, ...] (1-indexed).
    Returns empty list on failure — caller is responsible for handling errors.
    """
    pages: list[dict[str, Any]] = []
    try:
        if pypdf is None:
            raise ImportError("pypdf is not installed")

        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages.append({"page_number": idx + 1, "text": text})
        return pages
    except Exception as e:
        print(f"  [FAIL] Could not parse PDF {pdf_path.name}: {e}")
        return []


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from a PDF, logging failures explicitly.
    Returns empty string on failure — caller is responsible for tracking skipped files.
    (embedding-pipeline SKILL.md: do NOT silently drop — surface the failure upstream)
    """
    pages = extract_pages_from_pdf(pdf_path)
    if not pages:
        return ""
    non_empty = [p["text"] for p in pages if p["text"].strip()]
    return "\n\n".join(non_empty)


def chunk_text(text: str, max_words: int = 400) -> list[str]:
    """
    Split text into word-count-bounded chunks.
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
    """
    Generate and L2-normalize embeddings (SKILL.md Rule 3).
    Used for batches of texts when individual chunk handling is not needed.
    """
    embeddings = model.encode(texts, convert_to_numpy=True)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    return embeddings / norms


def embed_document_chunks(
    model: Any, chunks: list[str]
) -> tuple[np.ndarray, list[np.ndarray]]:
    """
    Embed all chunks for a single document and return:
        - canvas_vec      : mean-pooled, re-normalized embedding (shape: [dim])
                            Used as the document's single "canvas position" vector
                            for clustering and layout.
        - per_chunk_vecs  : list of per-chunk L2-normalized embeddings
                            Retained in memory for future question-grounded
                            highlighting (embedding-pipeline SKILL.md Rule 2).

    Rule 2 compliance: instead of using only chunks[0] (abstract/intro), ALL
    chunks are embedded and mean-pooled so longer papers are represented by
    their full content rather than just the opening section.
    """
    if not chunks:
        raise ValueError("embed_document_chunks requires at least one chunk")

    raw = model.encode(chunks, convert_to_numpy=True)  # shape: [n_chunks, dim]

    # L2-normalize each chunk embedding
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    per_chunk = raw / norms  # each row is a unit vector

    per_chunk_vecs: list[np.ndarray] = [per_chunk[i] for i in range(len(per_chunk))]

    # Mean-pool all chunk embeddings into a single canvas vector
    pooled = per_chunk.mean(axis=0)

    # Re-normalize after pooling so the canvas vector stays on the unit sphere
    pooled_norm = np.linalg.norm(pooled)
    if pooled_norm < 1e-10:
        canvas_vec = pooled
    else:
        canvas_vec = pooled / pooled_norm

    return canvas_vec, per_chunk_vecs
