"""
backend/api/main.py

FastAPI application entry-point.  Run with:
    uvicorn backend.api.main:app --reload

Endpoints
---------
GET  /              — liveness probe
GET  /api/status    — pipeline readiness check (documents found, model available)
POST /api/organize  — run the full pipeline and return canvas node positions
POST /api/analyze   — fast analysis endpoint: accepts uploaded PDFs, skips layout
                       simulation, returns clustering metrics only (for demos)
"""
import tempfile
import shutil
from pathlib import Path
from dataclasses import asdict
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.api.pipeline import SAMPLE_DOCS_DIR
from backend.embeddings.embedding_cache import is_cached, cache_stats
from backend.clustering.constraints import (
    load_constraints,
    add_constraint,
    remove_constraint,
)
from backend.ingestion.ingest import (
    save_and_ingest_pdf,
    delete_document_file,
    validate_pdf_file,
)

app = FastAPI(
    title="Parallax API",
    version="0.2.0",
    description=(
        "Persistent Semantic Research Canvas — backend API. "
        "POST /api/organize to run the embedding → clustering → layout pipeline "
        "and receive canvas-ready node positions."
    ),
)

# Allow the Vite dev server and the standalone demo HTML (opened from disk)
# to hit the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Module-level model cache — loaded once on first request, reused thereafter.
# This avoids the 5-10s cold-start on every /api/analyze call.
# ---------------------------------------------------------------------------

_model_cache: Any = None


def _get_model() -> Any:
    """Return the cached embedding model, loading it on first call."""
    global _model_cache
    if _model_cache is None:
        from backend.embeddings.pipeline import load_model
        _model_cache = load_model()
    return _model_cache


# ---------------------------------------------------------------------------
# Fast analysis helper — embedding + clustering only, NO layout simulation.
# Used by /api/analyze so the demo response is fast.
# ---------------------------------------------------------------------------

def _run_analysis_only(pdf_folder: Path) -> dict:
    """
    Run embedding + clustering on every PDF in pdf_folder.
    Skips the force-directed physics layout simulation entirely,
    which is the main source of latency in run_pipeline().

    Returns a dict:
        {
          "clusters":   list of {cluster_id, documents: [...], boundary_docs: [...]},
          "evaluation": {silhouette_score, num_clusters, ...},
          "skipped_documents": [...]
        }
    """
    from backend.embeddings.pipeline import (
        extract_text_from_pdf, chunk_text, embed_document_chunks, MODEL_NAME
    )
    from backend.clustering.pipeline import run_constraint_aware_clustering
    from backend.clustering.constraints import load_constraints
    from backend.topics.topic_modeling import extract_cluster_topics

    model = _get_model()
    pdf_files = sorted(pdf_folder.glob("*.pdf"))

    docs_all: list[dict] = []
    embeddings_list: list[np.ndarray] = []
    skipped: list[dict] = []

    for pdf_path in pdf_files:
        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            skipped.append({"filename": pdf_path.name, "reason": "PDF parse failed or empty"})
            continue
        chunks = chunk_text(text)
        if not chunks:
            skipped.append({"filename": pdf_path.name, "reason": "No text chunks after chunking"})
            continue

        doc_id = f"doc-{pdf_path.name}"
        canvas_vec, _ = embed_document_chunks(model, chunks)
        docs_all.append({"id": doc_id, "filename": pdf_path.name, "text": text})
        embeddings_list.append(canvas_vec)

    if not docs_all:
        raise ValueError("No text could be extracted from any uploaded PDF.")

    embeddings_all = np.array(embeddings_list)

    constraints = load_constraints()
    forced_assignments = {c.doc_id: c.forced_cluster_id for c in constraints}

    clustering_res = run_constraint_aware_clustering(
        docs_all, embeddings_all, state_file=STATE_FILE, forced_assignments=forced_assignments
    )
    doc_cluster_ids = clustering_res["doc_cluster_ids"]
    boundary_flags = clustering_res["boundary_flags"]
    evaluation = clustering_res["evaluation"]

    # Extract cluster topics via c-TF-IDF / KeyBERT
    topics = extract_cluster_topics(
        docs=docs_all,
        doc_cluster_ids=doc_cluster_ids,
        cluster_centers=clustering_res.get("cluster_centers"),
        model=model,
        top_n=5,
    )

    # Build per-cluster groupings for the UI
    cluster_groups: dict[str, dict] = {}
    for i, doc in enumerate(docs_all):
        cid = doc_cluster_ids[i]
        orig_cid = cid
        if cid.startswith("noise-"):
            cid = "noise"

        is_boundary_flag = boundary_flags[i]
        is_boundary = bool(is_boundary_flag[0]) if isinstance(is_boundary_flag, (tuple, list)) else bool(is_boundary_flag)

        if cid not in cluster_groups:
            t_info = topics.get(orig_cid, {})
            cluster_groups[cid] = {
                "cluster_id": cid,
                "topic_label": t_info.get("topic_label", "Outliers" if cid == "noise" else f"Topic {cid[:6]}"),
                "keywords": t_info.get("keywords", []),
                "top_terms": t_info.get("top_terms", []),
                "documents": [],
                "boundary_documents": [],
            }

        entry = {"doc_id": doc["id"], "filename": doc["filename"]}
        if is_boundary:
            cluster_groups[cid]["boundary_documents"].append(entry)
        else:
            cluster_groups[cid]["documents"].append(entry)

    eval_dict: dict | None = None
    if evaluation is not None:
        eval_dict = {
            "silhouette_score": evaluation.silhouette_score,
            "num_clusters": evaluation.num_clusters,
            "constraint_satisfaction_rate": evaluation.constraint_satisfaction_rate,
            "num_constraints_applied": evaluation.num_constraints_applied,
            "num_constraints_violated": evaluation.num_constraints_violated,
        }

    return {
        "clusters": list(cluster_groups.values()),
        "topics": topics,
        "evaluation": eval_dict,
        "skipped_documents": skipped,
        "total_documents_processed": len(docs_all),
    }


_ANALYZE_STATE_FILE = Path(__file__).parent / "cluster_mapping_analyze.json"

# Reuse the same STATE_FILE path for analyze (keeps UUID lineage consistent)
from backend.api.pipeline import SAMPLE_DOCS_DIR
STATE_FILE = Path(__file__).parent / "cluster_mapping.json"


# ---------------------------------------------------------------------------
# GET /  — liveness probe (unchanged)
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
@app.get("/api/", tags=["health"])
def health_check():
    """Quick liveness probe — returns OK so you can confirm the server started."""
    return {"status": "ok", "project": "Parallax", "api_version": "0.3.0"}


# ---------------------------------------------------------------------------
# GET /api/status  — pipeline readiness check
# ---------------------------------------------------------------------------

@app.get("/api/status", tags=["health"])
def pipeline_status():
    """
    Lightweight readiness check for the frontend to show a sensible loading/
    error state before calling /api/organize.

    Returns the number of PDFs discovered in data/sample_docs/ and whether
    the sentence-transformers package is importable (model is not actually
    loaded here — that happens on first /api/organize call).
    """
    pdf_count = len(list(SAMPLE_DOCS_DIR.glob("*.pdf"))) if SAMPLE_DOCS_DIR.exists() else 0

    try:
        import sentence_transformers  # noqa: F401
        model_available = True
    except ImportError:
        model_available = False

    if pdf_count == 0:
        state = "no_documents"
    elif not model_available:
        state = "missing_dependencies"
    else:
        state = "ready"

    return {
        "state": state,
        "pdf_count": pdf_count,
        "model_available": model_available,
        "docs_folder": str(SAMPLE_DOCS_DIR),
    }


# ---------------------------------------------------------------------------
# POST /api/organize  — run the pipeline
# ---------------------------------------------------------------------------

class OrganizeRequest(BaseModel):
    """
    Optional request body for POST /api/organize.
    If `filenames` is provided (non-empty), only those PDFs are processed.
    If omitted or empty, all PDFs in data/sample_docs/ are processed.
    """
    filenames: list[str] = []


@app.post("/api/organize", tags=["pipeline"])
def organize(body: OrganizeRequest = None):
    """
    Run the embedding → clustering → layout pipeline.

    Accepts an optional JSON body::

        { "filenames": ["paper1.pdf", "paper3.pdf"] }

    If **filenames** is provided and non-empty, only those documents are
    processed (cached embeddings are used where available, so previously
    embedded docs are near-instant).  If omitted, all PDFs in
    ``data/sample_docs/`` are processed.
    """
    if not SAMPLE_DOCS_DIR.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Documents folder not found: {SAMPLE_DOCS_DIR}. "
                   "Create 'data/sample_docs/' and drop PDFs into it.",
        )

    pdf_files = list(SAMPLE_DOCS_DIR.glob("*.pdf"))
    if not pdf_files:
        raise HTTPException(
            status_code=400,
            detail="No PDF files found in data/sample_docs/. "
                   "Add at least one PDF before calling /api/organize.",
        )

    # Build the doc_filter set from the request body
    doc_filter: set[str] | None = None
    if body and body.filenames:
        doc_filter = set(body.filenames)

    try:
        from backend.api.pipeline import run_pipeline
        result = run_pipeline(SAMPLE_DOCS_DIR, doc_filter=doc_filter)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {type(exc).__name__}: {exc}",
        )

    return result


# ---------------------------------------------------------------------------
# GET /api/documents  — list available PDFs with cache status
# ---------------------------------------------------------------------------

@app.get("/api/documents", tags=["pipeline"])
def list_documents():
    """
    List all PDF files available in ``data/sample_docs/`` along with their
    embedding cache status so the frontend can show which docs are
    pre-computed and which need fresh embedding.

    Response::

        {
          "documents": [
            {
              "filename": "paper1.pdf",
              "size_bytes": 2215244,
              "cached": true
            },
            ...
          ],
          "total": 21,
          "cached": 15,
          "uncached": 6
        }
    """
    if not SAMPLE_DOCS_DIR.exists():
        return {"documents": [], "total": 0, "cached": 0, "uncached": 0}

    pdf_files = sorted(SAMPLE_DOCS_DIR.glob("*.pdf"))

    docs = []
    cached_count = 0
    for p in pdf_files:
        cached = is_cached(p)
        if cached:
            cached_count += 1
        docs.append({
            "filename": p.name,
            "size_bytes": p.stat().st_size,
            "cached": cached,
        })

    return {
        "documents": docs,
        "total": len(docs),
        "cached": cached_count,
        "uncached": len(docs) - cached_count,
    }


@app.get("/api/documents/{filename}/pdf", tags=["pipeline"])
@app.get("/api/documents/{filename}/file", tags=["pipeline"])
def get_document_pdf(filename: str):
    """
    Serve a PDF document directly by filename (e.g. 'paper1.pdf' or 'doc-paper1.pdf')
    for in-browser viewing.
    """
    safe_name = filename.removeprefix("doc-")
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"

    # Path traversal protection
    clean_name = Path(safe_name).name
    pdf_path = SAMPLE_DOCS_DIR / clean_name

    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"PDF '{clean_name}' not found in {SAMPLE_DOCS_DIR.name}.",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=clean_name,
        headers={
            "Content-Disposition": f'inline; filename="{clean_name}"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@app.post("/api/documents/upload", tags=["pipeline"])
async def upload_documents(files: list[UploadFile] = File(...)):
    """
    Robust multi-PDF upload endpoint for live corpus ingestion.
    Validates PDF signatures, sanitizes filenames, detects duplicates,
    extracts chunks, and pre-computes / caches document embeddings on disk.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > 30:
        raise HTTPException(status_code=400, detail="Maximum 30 PDFs per upload batch.")

    model = _get_model()
    uploaded_results = []
    skipped_results = []

    for upload in files:
        try:
            content = await upload.read()
            res = save_and_ingest_pdf(
                filename=upload.filename or "upload.pdf",
                content=content,
                docs_dir=SAMPLE_DOCS_DIR,
                embed_immediately=True,
                model=model,
            )
            if res["status"] in ("success", "duplicate"):
                uploaded_results.append(res)
            else:
                skipped_results.append(res)
        except Exception as exc:
            skipped_results.append({
                "filename": upload.filename or "unknown.pdf",
                "doc_id": None,
                "status": "error",
                "message": f"Unexpected error during ingestion: {exc}",
            })

    return {
        "uploaded": uploaded_results,
        "skipped": skipped_results,
        "total_uploaded": len(uploaded_results),
        "total_skipped": len(skipped_results),
    }


@app.delete("/api/documents/{filename}", tags=["pipeline"], status_code=200)
def delete_document(filename: str):
    """
    Remove a PDF document from the active corpus.
    Also cleans up associated manual constraints and cluster mapping entries.
    """
    deleted = delete_document_file(filename, docs_dir=SAMPLE_DOCS_DIR, state_file=STATE_FILE)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")
    return {"deleted": True, "filename": filename}






# ---------------------------------------------------------------------------
# POST /api/search — Semantic Search over Document Corpus (Phase 6)
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    top_k: int | None = None
    filenames: list[str] | None = None


@app.post("/api/search", tags=["search"])
def search_documents(body: SearchRequest):
    """
    Semantic search across corpus document embeddings.
    Embeds query using all-mpnet-base-v2, computes cosine similarity,
    and returns ranked documents with cluster associations and cluster relevance.
    """
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")

    try:
        from backend.search.semantic_search import search_corpus
        model = _get_model()
        doc_filter = set(body.filenames) if body.filenames else None

        result = search_corpus(
            query=body.query.strip(),
            corpus_dir=SAMPLE_DOCS_DIR,
            model=model,
            top_k=body.top_k,
            doc_filter=doc_filter,
            state_file=STATE_FILE,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")


# ---------------------------------------------------------------------------
# Cluster Lifecycle Endpoints (Phase 7 — Rename, Merge, Split)
# ---------------------------------------------------------------------------

class RenameClusterRequest(BaseModel):
    topic_label: str


class MergeClustersRequest(BaseModel):
    source_cluster_ids: list[str] = []
    source_cluster_id: str | None = None
    target_cluster_id: str
    new_topic_label: str | None = None


class SplitClusterRequest(BaseModel):
    k: int = 2
    new_topic_labels: list[str] | None = None


@app.get("/api/clusters", tags=["clusters"])
def list_clusters():
    """
    List all active clusters with member document lists, counts, and topic metadata.
    """
    try:
        from backend.clustering.lifecycle import get_cluster_lifecycle_state
        model = _get_model()
        return get_cluster_lifecycle_state(
            state_file=STATE_FILE,
            docs_dir=SAMPLE_DOCS_DIR,
            model=model,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list clusters: {exc}")


@app.put("/api/clusters/{cluster_id}/topic", tags=["clusters"])
def rename_cluster(cluster_id: str, body: RenameClusterRequest):
    """
    Rename a cluster by saving a custom topic title override to persistent metadata.
    """
    if not body.topic_label or not body.topic_label.strip():
        raise HTTPException(status_code=400, detail="topic_label cannot be empty.")

    try:
        from backend.clustering.lifecycle import rename_cluster_topic
        result = rename_cluster_topic(
            cluster_id=cluster_id,
            new_topic_label=body.topic_label.strip(),
            state_file=STATE_FILE,
        )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to rename cluster: {exc}")


@app.post("/api/clusters/merge", tags=["clusters"])
def merge_cluster_endpoint(body: MergeClustersRequest):
    """
    Merge one or more source clusters into a target cluster.
    Reassigns all documents from source clusters to the target cluster,
    updates persistent constraints and cluster mapping, and updates topic modeling.
    """
    sources = list(body.source_cluster_ids)
    if body.source_cluster_id and body.source_cluster_id not in sources:
        sources.append(body.source_cluster_id)

    if not sources:
        raise HTTPException(status_code=400, detail="Must provide at least one source cluster ID to merge.")
    if not body.target_cluster_id or not body.target_cluster_id.strip():
        raise HTTPException(status_code=400, detail="target_cluster_id cannot be empty.")

    try:
        from backend.clustering.lifecycle import merge_clusters
        model = _get_model()
        result = merge_clusters(
            source_cluster_ids=sources,
            target_cluster_id=body.target_cluster_id.strip(),
            new_topic_label=body.new_topic_label,
            state_file=STATE_FILE,
            docs_dir=SAMPLE_DOCS_DIR,
            model=model,
        )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to merge clusters: {exc}")


@app.post("/api/clusters/{cluster_id}/split", tags=["clusters"])
def split_cluster_endpoint(cluster_id: str, body: SplitClusterRequest = SplitClusterRequest()):
    """
    Split an existing cluster into k sub-clusters using document embeddings.
    The largest sub-cluster retains the original cluster UUID lineage, while
    the remaining sub-clusters receive new stable UUIDs.
    """
    if body.k < 2:
        raise HTTPException(status_code=400, detail="k must be an integer >= 2.")

    try:
        from backend.clustering.lifecycle import split_cluster
        model = _get_model()
        result = split_cluster(
            cluster_id=cluster_id,
            k=body.k,
            new_topic_labels=body.new_topic_labels,
            state_file=STATE_FILE,
            docs_dir=SAMPLE_DOCS_DIR,
            model=model,
        )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to split cluster: {exc}")




# ---------------------------------------------------------------------------
# Constraint endpoints  (Track A — manual correction / persistent memory)
# ---------------------------------------------------------------------------

class ConstraintRequest(BaseModel):
    doc_id: str
    cluster_id: str


@app.get("/api/constraints", tags=["constraints"])
def list_constraints():
    """
    Return all currently active user constraints.

    Response — JSON array:
    ```json
    [
      {
        "doc_id":            "doc-paper1.pdf",
        "forced_cluster_id": "cluster-3a1b721f",
        "created_at":        "2026-08-14T21:00:00+00:00",
        "source":            "user"
      }
    ]
    ```
    """
    constraints = load_constraints()
    return [asdict(c) for c in constraints]


@app.post("/api/constraints", tags=["constraints"], status_code=201)
def create_constraint(body: ConstraintRequest):
    """
    Add or replace a user constraint.

    If the document already has a constraint it is overwritten (idempotent
    PUT semantics — the last manual drag wins).

    Body:
    ```json
    { "doc_id": "doc-paper1.pdf", "cluster_id": "cluster-3a1b721f" }
    ```

    Response — the saved constraint object.
    """
    try:
        constraint = add_constraint(body.doc_id, body.cluster_id)
        return asdict(constraint)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save constraint: {exc}",
        )


@app.delete("/api/constraints/{doc_id}", tags=["constraints"], status_code=204)
def delete_constraint(doc_id: str):
    """
    Remove the constraint for the given document.
    Returns 204 No Content whether or not the constraint existed.
    """
    remove_constraint(doc_id)  # Returns False if not found — still 204.


@app.delete("/api/constraints", tags=["constraints"], status_code=204)
def delete_all_constraints():
    """
    Remove all active constraints atomically from disk.
    """
    from backend.clustering.constraints import clear_all_constraints
    clear_all_constraints()


# ---------------------------------------------------------------------------
# POST /api/analyze  — fast demo endpoint (upload PDFs, get metrics back)
# ---------------------------------------------------------------------------

@app.post("/api/analyze", tags=["demo"])
async def analyze_uploaded_pdfs(files: list[UploadFile] = File(...)):
    """
    Fast demo endpoint for project review presentations.

    Accepts 1–10 uploaded PDF files (multipart/form-data), runs the
    embedding + clustering pipeline on them, and returns clustering metrics
    and per-cluster document groupings.

    **Key difference from /api/organize:** The force-directed physics layout
    simulation is skipped entirely, making this endpoint significantly faster
    while still demonstrating the core semantic clustering and evaluation.

    The embedding model is cached in memory after the first call, so
    subsequent requests are much faster.

    Response shape:
    ```json
    {
      "total_documents_processed": 7,
      "clusters": [
        {
          "cluster_id": "cluster-a1b2c3d4",
          "documents": [
            {"doc_id": "doc-paper1.pdf", "filename": "paper1.pdf"}
          ],
          "boundary_documents": [
            {"doc_id": "doc-paper3.pdf", "filename": "paper3.pdf"}
          ]
        }
      ],
      "evaluation": {
        "silhouette_score": 0.3175,
        "num_clusters": 3,
        "constraint_satisfaction_rate": null,
        "num_constraints_applied": null,
        "num_constraints_violated": null
      },
      "skipped_documents": []
    }
    ```
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > 15:
        raise HTTPException(status_code=400, detail="Maximum 15 PDFs per request.")

    # Validate that all uploads are PDFs
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"File '{f.filename}' is not a PDF. Only PDF files are accepted.",
            )

    # Save uploads to a temp directory
    tmp_dir = Path(tempfile.mkdtemp(prefix="parallax_analyze_"))
    try:
        for upload in files:
            dest = tmp_dir / upload.filename
            content = await upload.read()
            dest.write_bytes(content)

        result = _run_analysis_only(tmp_dir)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis error: {type(exc).__name__}: {exc}",
        )
    finally:
        # Always clean up the temp directory
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return result

