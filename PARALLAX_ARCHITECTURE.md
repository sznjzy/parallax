# PARALLAX VERIFIED ARCHITECTURE

This file describes the architecture that is actually implemented and verified in the repository.

## Last Verified

Phase 0 — Baseline Audit (2026-10-02)

## Repository Structure

```
parallax/
├── backend/
│   ├── api/
│   │   ├── main.py                  # FastAPI application and route handlers
│   │   ├── pipeline.py              # End-to-end integration orchestration
│   │   ├── cluster_mapping.json     # Persistent cluster UUID-to-document state
│   │   └── constraints.json         # Persistent user drag-and-drop constraints
│   ├── clustering/
│   │   ├── pipeline.py              # HDBSCAN + KMeans fallback, stable IDs, boundary detection
│   │   └── constraints.py           # Constraint schema, CRUD storage, and evaluation
│   ├── embeddings/
│   │   ├── pipeline.py              # Text extraction, chunking, all-mpnet-base-v2 embedding
│   │   └── embedding_cache.py       # SHA-256 disk cache for embeddings
│   ├── ingestion/
│   │   └── __init__.py              # Ingestion package marker
│   ├── layout/
│   │   └── physics.py               # 2D force-directed simulation and deterministic angular anchors
│   └── tests/
│       ├── test_determinism_and_boundary.py # Anchor determinism and boundary detection test suite
│       ├── spike_clustering.py     # Standalone clustering verification script
│       └── spike_layout.py         # Standalone layout verification script
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Root UI layout, health checking, topbar
│   │   ├── index.css                # Design system tokens and styling
│   │   ├── canvas/
│   │   │   ├── ResearchCanvas.jsx   # Konva Stage/Layer canvas container with pan/zoom/drag
│   │   │   ├── DocumentNode.jsx     # Document circle rendering, boundary rings, drag handlers
│   │   │   ├── ClusterRegion.jsx    # Cluster hulls/regions and centroid labels
│   │   │   ├── CanvasControls.jsx   # Zoom, fit-to-screen, and organize actions
│   │   │   └── clusterColor.js      # Deterministic palette assigning distinct colors to clusters
│   │   ├── components/
│   │   │   ├── EvaluationPanel.jsx  # Metrics sidebar (Silhouette score, constraints, document list)
│   │   │   ├── StatusBanner.jsx     # Loading/error notification overlay
│   │   │   ├── PdfViewerModal.jsx   # In-app PDF reader modal
│   │   │   ├── SelectedNodeBar.jsx  # Floating bottom bar with actions for active node
│   │   │   ├── NodeTooltip.jsx      # Hover tooltip for canvas nodes
│   │   │   └── ConstraintToast.jsx  # Toast notifications for manual constraint placement
│   │   ├── hooks/
│   │   │   ├── useOrganize.js       # Pipeline execution hook
│   │   │   ├── useConstraints.js    # Constraint fetch/mutate hook
│   │   │   ├── useDocuments.js      # Document list and cache inspection hook
│   │   │   └── useCanvasSize.js     # Canvas resize observer hook
│   │   └── state/
│   │       ├── AppContext.jsx       # Global application state and reducer
│   │       └── mockFixture.js       # Offline mock data for UI testing
├── data/
│   ├── sample_docs/                 # 32 research PDF documents for demo and testing
│   └── embedding_cache/             # SHA-256 .npy cache files
├── PARALLAX_AGENT_PROTOCOL.md       # Engineering agent operational rules
├── PARALLAX_PROGRESS.md             # Active phase tracking and progress log
├── PARALLAX_DECISIONS.md            # Architectural Decision Records (ADRs)
├── PARALLAX_ARCHITECTURE.md         # Verified system architecture
└── PARALLAX_MASTER_IMPLEMENTATION_PLAN.md # Master roadmap
```

## Backend Architecture

### 1. Ingestion & Chunking
- **Engine**: `pypdf` in `backend.embeddings.pipeline.extract_text_from_pdf`.
- **Chunking**: `chunk_text()` splits document text into contiguous 400-word blocks.
- **Handling**: Corrupted or empty PDFs return an empty string and are surfaced in `skipped_documents`.

### 2. Embeddings & Caching
- **Model**: `sentence-transformers/all-mpnet-base-v2` (768 dimensions).
- **Pooling**: `embed_document_chunks()` generates unit-normalized vectors for all chunks, mean-pools them into a single document canvas vector, and re-normalizes to the unit sphere. Per-chunk vectors are retained for fine-grained ranking.
- **Cache**: `backend.embeddings.embedding_cache` computes SHA-256 of raw PDF bytes and persists `.npy` vectors to `data/embedding_cache/<hash>.npy`. Cache hits bypass model inference entirely.

### 3. Clustering & Boundary Detection
- **Primary Method**: `HDBSCAN(min_cluster_size=2, min_samples=1, metric='euclidean')`.
- **Fallback**: `KMeans(n_clusters=best_k, random_state=42)` when HDBSCAN produces fewer than 2 non-noise clusters for $\ge 3$ samples.
- **Centroids**: Mean coordinate of cluster embeddings normalized to unit length.
- **Boundary Detection**: `compute_boundary_flags()` compares cosine similarities of document embedding against cluster centroids. If $(\text{sim}_{\text{top1}} - \text{sim}_{\text{top2}}) < \text{BOUNDARY\_MARGIN}$ (0.05), document is flagged `is_boundary_document=True` and receives secondary cluster coupling.
- **Stable Identity**: `assign_stable_cluster_ids()` tracks cluster continuity across runs by calculating overlap percentage $\frac{|\text{New} \cap \text{Old}|}{|\text{Old}|} \ge 0.5$, persisting mappings to `backend/api/cluster_mapping.json` with corpus pruning.

### 4. Constraint Processing (Baseline Status)
- **Schema**: `Constraint(doc_id, forced_cluster_id, created_at, source)` persisted to `backend/api/constraints.json`.
- **Audit Finding**: In the baseline implementation (`backend/api/pipeline.py`), `apply_constraints()` separates docs into unconstrained and forced mappings, but `_run_phase()` currently passes all document embeddings to `cluster_embeddings()`. Forced cluster assignments are only applied post-hoc in `_map_to_nodes()`. True constraint-aware separation (excluding constrained documents prior to HDBSCAN) is scheduled for Phase 1.

### 5. Layout Physics Simulation
- **Canvas Size**: 400×300 coordinate space.
- **Cluster Anchors**: `compute_home_positions()` maps cluster UUIDs to angular positions on an inner orbit ($r = \min(W,H) \times 0.34$) via SHA-256 integer hashes, relaxed via 1D angular collision resolution (minimum angular separation 35°).
- **Simulation**: Force-directed Euler integration with:
  - Intra-cluster repulsion ($k=4000$) and inter-cluster repulsion ($k=12000$).
  - Spring attraction ($k=0.5$) toward cluster home positions (split proportionally for boundary documents).
  - Center gravity ($k=0.01$) for non-noise, unanchored nodes.
  - Peripheral repulsive orbit ($r = \min(W,H) \times 0.46$) for noise outliers.
  - Velocity damping ($0.85$), strong anchor damping ($0.05$ for manual user pins), and canvas margin clamping ($[24, W-24], [24, H-24]$).

## Frontend Architecture

- **Stack**: React 18 + Vite + Konva / react-konva + Lucide icons.
- **Design System**: Vanilla CSS tokens in `frontend/src/index.css` (dark mode default, glassmorphism headers, responsive panel layouts).
- **Canvas Viewport**: `ResearchCanvas.jsx` renders clustered document nodes with convex hulls / cluster boundaries, smooth dragging, real-time boundary rings, and manual cluster reassignment via drag-and-drop.
- **Evaluation & Documents**: `EvaluationPanel.jsx` presents live clustering silhouette score, constraint satisfaction metrics, corpus document selection, and PDF reader modal triggers.

## Verified API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Liveness health check |
| GET | `/api/status` | Readiness check (PDF count, dependency availability) |
| POST | `/api/organize` | Execute embedding, clustering, physics layout pipeline |
| GET | `/api/documents` | List available PDFs in corpus with cache status |
| GET | `/api/documents/{filename}/pdf` | Stream PDF file for in-browser viewing |
| GET | `/api/constraints` | List all active user constraints |
| POST | `/api/constraints` | Create or update user constraint (idempotent PUT) |
| DELETE | `/api/constraints/{doc_id}` | Remove constraint for specific document |
| DELETE | `/api/constraints` | Clear all user constraints |
| POST | `/api/analyze` | Fast demo endpoint (clustering only, no physics layout) |

## Known Limitations & Deviations Identified in Phase 0

1. **Constrained Document Separation**: Baseline pipeline runs HDBSCAN over all embeddings and overwrites cluster IDs post-hoc instead of removing constrained documents before clustering (addressed in Phase 1).
2. **Scratch Files**: Multiple scratch test scripts exist in the repository root (`scratch_test_*.py`, `scratch_*.js`) from prior ad-hoc checks; these need to be consolidated or replaced with clean automated tests in Phase 3.
3. **PDF Ingestion Endpoint**: Live PDF upload is currently available only via `/api/analyze` for fast demo; unified upload to `data/sample_docs/` with cache invalidation is scheduled for Phase 4.
4. **Topic Modeling**: Cluster labeling is currently UUID-based without automated c-TF-IDF keyword extraction (scheduled for Phase 5).

## Architecture Change Log

- **Phase 0 (2026-10-02)**: Complete baseline audit performed and documented. System structure, data flow, physics layout, and constraint pipeline audited against source code.
