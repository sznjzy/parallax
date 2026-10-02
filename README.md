# Parallax — Persistent Semantic Research Canvas

> **Status: Full-Stack Implementation Complete** — Backend clustering, incremental layout physics with 1D angular relaxation, persistent constraint satisfaction, embedding caching, collision-free cluster palettes, interactive HTML5 canvas UI, in-browser PDF reader, and evaluation metrics are fully implemented and verified. See [PROGRESS.md](PROGRESS.md) for full technical details.

## What is Parallax?

Parallax is a final-year CSE project that lets researchers drop PDFs/notes onto
an infinite visual canvas. Each document is automatically embedded, similar
documents are clustered together, and the result is rendered as a force-directed
physics layout. The key differentiator from tools like NotebookLM is
**persistence**: when a user manually corrects the AI (holds Shift and drags a document to a
different cluster), that correction is stored as a persistent constraint and respected in
all future re-clustering runs — the system never forgets it.

---

## Project Structure

```
parallax/
├── backend/
│   ├── embeddings/         PDF parsing, chunking, and embedding generation
│   │   └── embedding_cache.py  ← SHA-256 disk cache for instant reload
│   ├── clustering/         HDBSCAN clustering & stable UUID assignments
│   │   └── constraints.py      ← Constraint application & satisfaction math
│   ├── layout/             Force-directed incremental layout physics engine (with angular relaxation)
│   ├── api/                FastAPI application & integration pipeline
│   │   ├── main.py         → Live API endpoints (organize, constraints, documents)
│   │   ├── pipeline.py     → End-to-end integration pipeline
│   │   └── constraints.json → Persistent user constraints store
│   └── tests/              Validation wrappers (clustering, layout, determinism)
├── frontend/
│   ├── src/
│   │   ├── canvas/         Interactive Konva canvas, Cluster regions, Document nodes, Controls, clusterColor
│   │   ├── components/     Evaluation panel, Selected node bar, PDF modal, Toast
│   │   ├── hooks/          useOrganize, useConstraints, useDocuments, useCanvasSize
│   │   ├── state/          Global AppContext & reducer
│   │   └── index.css       Clean, minimalist design system tokens & styles
│   └── package.json        React + Vite + Konva + lucide-react
├── data/
│   └── sample_docs/        DROP YOUR PDFS HERE
├── requirements.txt        Python backend dependencies
└── README.md
```

---

## Quick Start

### Backend

```bash
# 1. Create and activate a virtual environment (Python 3.10+)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install the package in editable mode (required for backend.* imports)
pip install -e .
pip install -r requirements.txt

# 3. Start the API
uvicorn backend.api.main:app --reload
# → visit http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → visit http://localhost:5173
# The page pings the FastAPI backend at /api/ and shows the response.
```

---

## Spike Validation (run before building any UI)

### Spike A — Clustering quality

```bash
# 1. Drop 10-15 research PDFs into  data/sample_docs/
# 2. Run:
python -m backend.tests.spike_clustering
```

Reads all PDFs, embeds them with `all-mpnet-base-v2` (all chunks mean-pooled per document),
clusters via HDBSCAN (k-means fallback for small corpora), and prints:

- Per-cluster document lists with boundary flags
- Full evaluation contract (silhouette score, num_clusters; constraint fields are `null` until constraint-storage is implemented)

**Goal:** silhouette score > 0.25, clusters that match your intuition about the
topics in your reading list.  Adjust `HDBSCAN_MIN_CLUSTER_SIZE` and
`BOUNDARY_MARGIN` (in `clustering/pipeline.py`) if results look off.

---

### Spike B — Layout stability

```bash
python -m backend.tests.spike_layout
```

Creates synthetic nodes, runs initial force-directed layout to convergence,
anchors existing nodes, inserts 3 new nodes, runs incremental update, and
prints:

```json
{
  "avg_displacement_existing_nodes": ...,
  "max_displacement_existing_nodes": ...,
  "convergence_iterations": ...,
  "convergence_time_ms": ...
}
```

**Goal:** `avg_displacement_existing_nodes` should be very small (< 5 canvas
units) — proving existing nodes don't jump when new documents are added.

---

## Skills

Project-specific development conventions live in `.agent/skills/`:

| Skill | Controls |
|---|---|
| `embedding-pipeline` | Model choice, chunking rules, L2-norm, output contract |
| `constrained-clustering` | Algorithm, constraint representation, evaluation contract |
| `incremental-layout` | Physics parameters, anchoring, stability metrics |

**All code that touches embeddings, clustering, or layout must follow the
corresponding skill's output/evaluation contracts exactly**, since frontend
rendering, the synthesis feature, and the query-highlighting feature all depend
on those shapes.

---

## API

The FastAPI server exposes the backend pipeline over HTTP.

```bash
uvicorn backend.api.main:app --reload
# Interactive docs: http://localhost:8000/docs
```

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Liveness probe -- returns `{"status": "ok"}` |
| `GET`  | `/api/status` | Readiness check -- reports PDF count and whether embedding model is ready |
| `POST` | `/api/organize` | Runs the full pipeline on selected PDFs and returns canvas node positions + evaluation metrics |
| `GET`  | `/api/constraints` | Returns list of stored persistent user constraints |
| `POST` | `/api/constraints` | Adds or updates a persistent constraint (`{doc_id, forced_cluster_id}`) |
| `DELETE` | `/api/constraints/{doc_id}` | Deletes a single constraint for `doc_id` |
| `DELETE` | `/api/constraints` | Clears all stored constraints |
| `GET`  | `/api/documents` | Returns list of available PDFs with embedding cache status |
| `GET`  | `/api/documents/{filename}/pdf` | Streams raw PDF binary for the in-browser viewer and external tab reading |

### `POST /api/organize` -- Response shape (v0.3)

Returns a JSON **object** (not a bare array) with three keys:

```json
{
  "nodes": [
    {
      "doc_id":               "doc-paper1.pdf",
      "x":                    142.3,
      "y":                    87.6,
      "velocity_x":           0.000012,
      "velocity_y":          -0.000003,
      "is_anchored":          false,
      "cluster_id":           "cluster-a1b2c3d4",
      "is_boundary_document": false
    }
  ],
  "evaluation": {
    "silhouette_score":            0.3175,
    "num_clusters":                5,
    "constraint_satisfaction_rate": 1.0,
    "num_constraints_applied":     2,
    "num_constraints_violated":    0
  },
  "skipped_documents": [
    {"filename": "bad.pdf", "reason": "PDF parse failed or empty"}
  ]
}
```

- **`nodes`**: Combined incremental-layout + constrained-clustering output contract. Each node has the six layout fields plus `cluster_id` and `is_boundary_document` so the frontend can colour-code clusters without a second request.
- **`evaluation`**: Clustering quality metrics and persistent constraint satisfaction metrics (`constraint_satisfaction_rate`, `num_constraints_applied`, `num_constraints_violated`). Returns `null` for constraint metrics when no user constraints are active.
- **`skipped_documents`**: PDFs that could not be parsed. Empty list means all PDFs were processed successfully.

**Quick test via curl:**
```bash
curl -X POST http://localhost:8000/api/organize | python -m json.tool | head -60
```

**Known v0.3 simplifications (deferred):** document set is fixed to `data/sample_docs/`
(no file upload yet); pipeline runs synchronously so large corpora may time out.

---

## Technical Evaluation Axes

The project's evaluation centres on three claims:

1. **Clustering quality** — embeddings + HDBSCAN meaningfully organise real
   research documents (measured by silhouette score, validated in Spike A).
2. **Layout stability** — adding new documents does not disrupt existing spatial
   arrangement (measured by `avg_displacement_existing_nodes`, validated in
   Spike B).
3. **Constraint satisfaction** — stored user corrections are correctly respected
   across re-clustering runs (measured by `constraint_satisfaction_rate` in the
   clustering evaluation contract).

Every clustering run and every incremental layout update logs these metrics —
see the evaluation contracts in the skill files for the exact JSON shapes.
