---
name: embedding-pipeline
description: Use this skill whenever generating, storing, updating, or querying document/text embeddings for Parallax — including ingesting new PDFs or notes, embedding user queries for the question-grounded highlighting feature, or building/updating the vector index. Trigger on tasks involving "embedding", "vectorize", "ingest document", "PDF parsing", "vector index", or "semantic search".
---

# Embedding Pipeline Skill

## Purpose
Defines the standard, consistent way Parallax converts documents and user queries into vector embeddings, so every part of the system (clustering, layout, query highlighting) operates on embeddings produced the same way.

## Core Rules

1. **Single embedding model for everything.** Documents AND user queries (for question-grounded highlighting) must be embedded with the exact same model. Never mix models — distances become meaningless if embeddings come from different spaces.
   - Default model: `sentence-transformers/all-mpnet-base-v2` (good quality/speed tradeoff for a student-scale corpus, ~768 dims). If swapped, re-embed the entire corpus — do not mix old and new embeddings.

2. **Chunking strategy for PDFs.**
   - Extract text via PDF parser (e.g., `pypdf` or `pdfplumber`).
   - For documents longer than ~2 pages, do NOT embed the whole document as one vector — split into logical chunks (abstract/intro, body sections) and store a mean-pooled or abstract-priority embedding as the document's "canvas position" vector, but retain per-chunk embeddings for finer-grained retrieval (used later by question-grounded highlighting).
   - Always store: `doc_id`, `chunk_id` (nullable if whole-doc), raw text, embedding vector, source filename, ingestion timestamp.

3. **Normalization.** All embeddings must be L2-normalized before storage, so cosine similarity == dot product (cheaper to compute at query time).

4. **Vector storage.**
   - At demo scale (dozens to low hundreds of documents), an in-memory NumPy matrix + brute-force cosine similarity is sufficient — do not over-engineer with a heavyweight vector DB unless corpus size or latency requirements demand it.
   - If scale grows, use FAISS (`IndexFlatIP` after normalization) — keep the interface abstracted so swapping the backend doesn't touch calling code.

5. **Query embedding (for question-grounded highlighting).**
   - Embed the raw user question with the same model, same normalization.
   - Do not attempt to append instructions/prefixes to the query unless the chosen embedding model explicitly requires an asymmetric "query:" / "passage:" prefix convention (check model card before assuming).

## Failure Modes to Avoid
- Re-embedding the same document twice on every incremental update (expensive, unnecessary) — only re-embed documents that are new or explicitly edited.
- Embedding documents in different languages without checking the model supports multilingual input — verify model card if this is relevant to the demo corpus.
- Silently dropping documents that fail PDF parsing — log and surface parsing failures instead of skipping silently.

## Output Contract
Every embedding operation should return/store an object shaped like:
```json
{
  "doc_id": "string",
  "embedding": [float, ...],
  "model_name": "string",
  "normalized": true,
  "source_type": "pdf" | "text" | "query"
}
```
This contract is depended on by the constrained-clustering and incremental-layout skills — do not change field names without updating those.