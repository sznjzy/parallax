"""
backend/api/main.py

FastAPI application entry-point.  Run with:
    uvicorn backend.api.main:app --reload

Endpoints
---------
GET  /              — liveness probe
GET  /api/status    — pipeline readiness check (documents found, model available)
POST /api/organize  — run the full pipeline and return canvas node positions
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api.pipeline import SAMPLE_DOCS_DIR

app = FastAPI(
    title="Parallax API",
    version="0.2.0",
    description=(
        "Persistent Semantic Research Canvas — backend API. "
        "POST /api/organize to run the embedding → clustering → layout pipeline "
        "and receive canvas-ready node positions."
    ),
)

# Allow the Vite dev server (localhost:5173) to hit the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# GET /  — liveness probe (unchanged)
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
def health_check():
    """Quick liveness probe — returns OK so you can confirm the server started."""
    return {"status": "ok", "project": "Parallax", "api_version": "0.2.0"}


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

@app.post("/api/organize", tags=["pipeline"])
def organize():
    """
    Run the full embedding → clustering → layout pipeline on every PDF currently
    in `data/sample_docs/` and return canvas-ready node positions.

    Response — JSON array of node objects:
    ```json
    [
      {
        "doc_id":               "doc-paper1.pdf",
        "x":                    142.3,
        "y":                    87.6,
        "velocity_x":           0.000012,
        "velocity_y":          -0.000003,
        "is_anchored":          true,
        "cluster_id":           "cluster-a1b2c3d4",
        "is_boundary_document": false
      },
      ...
    ]
    ```

    **Deferred / known simplifications (v0.2):**
    - The document set is fixed to whatever is on disk in `data/sample_docs/`;
      file upload handling will be added when the frontend upload interaction
      is built.
    - Pipeline execution is synchronous and blocks the request thread.
      For large corpora (>50 docs) this will time out; async job handling
      is a future improvement.
    - The Phase 1 / Phase 2 holdback split mirrors the validated integration
      test. A future version will let callers supply their own document set
      or phase split.
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

    try:
        from backend.api.pipeline import run_pipeline
        nodes = run_pipeline(SAMPLE_DOCS_DIR)
    except ValueError as exc:
        # run_pipeline raises ValueError for empty/unparseable corpus
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        # Unexpected errors — surface them clearly rather than a silent 500
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {type(exc).__name__}: {exc}",
        )

    return nodes
