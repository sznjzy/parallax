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
│   │   ├── __init__.py              # Ingestion package marker
│   │   └── ingest.py                # Safe PDF validation, deduplication, chunking, disk caching, deletion
│   ├── layout/
│   │   └── physics.py               # 2D force-directed simulation and deterministic angular anchors
│   ├── topics/
│   │   ├── __init__.py              # Topic modeling package marker
│   │   └── topic_modeling.py        # c-TF-IDF, KeyBERT semantic centroid alignment, keyword extraction
│   ├── search/
│   │   ├── __init__.py              # Search package marker
│   │   └── semantic_search.py       # Exact cosine similarity search, snippet extraction, cluster relevance
│   └── tests/
│       ├── fixtures/
│       │   ├── __init__.py          # Fixtures package marker
│       │   └── synthetic_corpora.py # Synthetic embedding corpus generators (well-separated, overlapping, boundary)
│       ├── test_constraint_aware_clustering.py # ADR-001 density isolation & constraint handling
│       ├── test_stable_identity_and_layout.py  # UUID lineage & circular angular relaxation
│       ├── test_clustering_quality.py          # HDBSCAN/KMeans silhouette benchmarks & boundary detection
│       ├── test_constraint_impact.py           # Constraint satisfaction & reassignment impact
│       ├── test_spatial_stability.py           # Force simulation energy convergence & margin clamping
│       ├── test_api_endpoints.py               # FastAPI test client integration & constraint CRUD
│       ├── test_pdf_ingestion_and_caching.py   # PDF magic byte validation, hash deduplication, live caching, upload/delete API
│       ├── test_outlier_spatial_isolation.py   # ADR-007 Outlier noise classification & convex hull spatial isolation
│       ├── test_topic_modeling.py              # ADR-008 c-TF-IDF, KeyBERT semantic alignment & dynamic updates
│       └── test_semantic_search.py             # Cosine similarity ranking, empty query/corpus edge cases, search API
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Root UI layout, health checking, topbar
│   │   ├── index.css                # Design system tokens and styling
│   │   ├── canvas/
│   │   │   ├── ResearchCanvas.jsx   # Konva Stage/Layer canvas container with pan/zoom/drag
│   │   │   ├── DocumentNode.jsx     # Document circle rendering, boundary rings, drag handlers, radiant search halos
│   │   │   ├── ClusterRegion.jsx    # Cluster hulls/regions, centroid labels, cluster relevance highlights
│   │   │   ├── CanvasControls.jsx   # Zoom, fit-to-screen, and organize actions
│   │   │   └── clusterColor.js      # Deterministic palette assigning distinct colors to clusters
│   │   ├── components/
│   │   │   ├── SearchBar.jsx        # Semantic search topbar input with debounce, clear, and match counter
│   │   │   ├── EvaluationPanel.jsx  # Metrics sidebar (Silhouette score, constraints, search results, doc list)
│   │   │   ├── StatusBanner.jsx     # Loading/error notification overlay
│   │   │   ├── PdfViewerModal.jsx   # In-app PDF reader modal
│   │   │   ├── SelectedNodeBar.jsx  # Floating bottom bar with actions for active node
│   │   │   ├── NodeTooltip.jsx      # Hover tooltip for canvas nodes
│   │   │   └── ConstraintToast.jsx  # Toast notifications for manual constraint placement
│   │   ├── hooks/
│   │   │   ├── useOrganize.js       # Pipeline execution hook
│   │   │   ├── useSearch.js         # Semantic search execution and state hook
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

### 4. Constraint Processing (True Constraint-Aware Flow — ADR-001)
- **Schema**: `Constraint(doc_id, forced_cluster_id, created_at, source)` persisted to `backend/api/constraints.json`.
- **Pipeline Implementation**: `run_constraint_aware_clustering()` in `backend/clustering/pipeline.py` implements the strict ADR-001 lifecycle:
  1. Constrained documents are separated from unconstrained documents prior to clustering.
  2. HDBSCAN runs strictly on unconstrained document embeddings, completely preventing manual constraints from distorting unconstrained density estimates and cluster formation.
  3. Stable cluster UUIDs are assigned to discovered clusters via overlap matching.
  4. Constrained documents are merged directly into their forced cluster assignments.
  5. Global cluster centroids are calculated across all active cluster members.
  6. Boundary document flags and secondary cluster couplings are evaluated against global centroids.
  7. Evaluation contract calculates both Silhouette score and exact Constraint Satisfaction Rate (`(applied - violated) / applied`).

### 5. Layout Physics Simulation
- **Canvas Size**: 400×300 coordinate space.
- **Cluster Anchors**: `compute_home_positions()` maps real cluster UUIDs to angular positions on an inner orbit ($r = \min(W,H) \times 0.34$) via SHA-256 integer hashes, relaxed via pairwise shortest-arc circular relaxation ($\ge 35^\circ$). Noise anchors (`noise-*`) are placed strictly on the outer periphery ($r = \min(W,H) \times 0.46$) at the angular gap bisectors (voids) between adjacent real clusters.
- **Simulation**: Force-directed Euler integration with:
  - Intra-cluster repulsion ($k=4000$) and inter-cluster repulsion ($k=12000$).
  - Spring attraction ($k=0.5$) toward cluster home positions (split proportionally for boundary documents).
  - Strong mutual repulsion ($k=8000$, $d < 65.0$) between noise outlier nodes and real cluster nodes.
  - Center gravity ($k=0.01$) applied exclusively to non-noise cluster members, keeping noise documents on the outer perimeter.
  - Velocity damping ($0.85$), strong anchor damping ($0.05$ for manual user pins), and canvas margin clamping ($[24, W-24], [24, H-24]$).
### 6. Automatic Topic Modeling (c-TF-IDF + KeyBERT — ADR-008)
- **Engine**: `backend.topics.topic_modeling` (`extract_cluster_topics()`, `compute_ctfidf()`).
- **c-TF-IDF Formula**: $W_{c, t} = tf_{c, t} \times \log\left(1 + \frac{A}{f_t}\right)$, where $A$ is average words per cluster and $f_t$ is total term frequency across all clusters.
- **KeyBERT Semantic Alignment**: Candidate keywords are re-ranked using a combined score (60% cosine similarity to normalized cluster centroid embedding + 40% c-TF-IDF uniqueness).
- **Text Disk Cache**: Extracted document text is cached at `data/embedding_cache/<sha256>.txt` to ensure instantaneous topic recalculations on cached corpora.
- **Dynamic Updates**: Topics, titles, and representative keywords automatically recalculate whenever cluster membership changes (incremental PDF additions or manual drag-and-drop constraints).

### 7. Semantic Search Engine & Heatmap (Phase 6)
- **Engine**: `backend.search.semantic_search` (`search_corpus()`, `SearchResult`, `ClusterRelevance`).
- **Model Space**: Uses the same `sentence-transformers/all-mpnet-base-v2` unit-normalized 768-dim space as corpus embeddings.
- **Similarity Metric**: Cosine similarity via unit-vector dot product $q \cdot d$, bounded in $[-1.0, 1.0]$.
- **Cluster Association & Relevance**: Integrates document cluster membership from `cluster_mapping.json` and computes cluster-level aggregates (`mean_similarity`, `max_similarity`, `matched_docs_count`).
- **Explainability**: Extracts representative matching snippet passages from cached document text.
- **Non-Mutating**: Pure read-only operation; zero mutation of corpus, clustering, layout, or constraints.
- **Zero LLM**: Operates deterministically without external LLM calls.

## Frontend Architecture (3-Zone Minimalist Design — ADR-011)

- **Stack**: React 18 + Vite + Konva / react-konva + Lucide icons.
- **Design System**: Vanilla CSS tokens in `frontend/src/index.css` (high-contrast dark and light modes, restrained glassmorphism, 60fps hardware-accelerated motion tokens, `@media (prefers-reduced-motion)` support).
- **Zone 1: Collapsible Navigation Rail**: `NavRail.jsx` provides a fixed 56px layout footprint that smoothly expands on hover to a 220px overlay (`width 240ms cubic-bezier(0.22, 1, 0.36, 1)`), exposing primary destinations (Canvas, Search, Library, Clusters, Evaluation, Settings) without triggering canvas layout reflows.
- **Zone 2: Canvas Centerpiece**: `ResearchCanvas.jsx` renders clustered document nodes with convex hulls / cluster boundaries, smooth dragging, real-time boundary rings, manual constraint creation, dynamic search heatmap radiant halos, and theme-aware high-contrast annotation cards. Floating `CommandBar.jsx` hosts semantic search and status pill; floating `CanvasDock.jsx` hosts primary pipeline execution, view recentering, and physics layout rerun with loading spinners.
- **Zone 3: Contextual Inspector Drawer**: `InspectorDrawer.jsx` is a 360px sliding contextual workspace panel hosting dedicated views:
  - `SearchWorkspace.jsx`: Ranked cosine similarity matches with passage snippets and jump-to-source triggers.
  - `LibraryWorkspace.jsx`: Corpus inventory, PDF upload dropzone, cache state badges, and deletion controls.
  - `ClusterInspector.jsx`: Topic label override/rename, cluster merge, and k-way semantic split controls.
  - `EvaluationWorkspace.jsx`: Silhouette score, Davies-Bouldin index, constraint satisfaction rate, and cluster breakdown.
  - `DocumentInspector.jsx`: Grounded evidence inspection showing cluster membership, centroid distance, representative keywords, and similar papers without requiring generative LLMs.
- **Modals**:
  - `SettingsModal.jsx`: Appearance (Dark/Light theme), caching status, and architecture metrics.
  - `PdfViewerModal.jsx`: In-app deep-linking PDF reader with page navigation and search term highlights.

## Verified API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Liveness health check |
| GET | `/api/status` | Readiness check (PDF count, dependency availability) |
| POST | `/api/organize` | Execute embedding, clustering, physics layout, and topic modeling pipeline |
| POST | `/api/search` | Semantic search across corpus with cosine similarity ranking and cluster relevance |
| GET | `/api/documents` | List available PDFs in corpus with cache status |
| POST | `/api/documents/upload` | Multi-PDF upload with validation, deduplication, and immediate caching |
| DELETE | `/api/documents/{filename}` | Delete PDF from corpus with constraint and state pruning |
| GET | `/api/documents/{filename}/pdf` | Stream PDF file for in-browser viewing |
| GET | `/api/constraints` | List all active user constraints |
| POST | `/api/constraints` | Create or update user constraint (idempotent PUT) |
| DELETE | `/api/constraints/{doc_id}` | Remove constraint for specific document |
| DELETE | `/api/constraints` | Clear all user constraints |
| GET | `/api/clusters` | List active clusters with topics, keywords, and document counts |
| PUT | `/api/clusters/{cluster_id}/topic` | Rename cluster topic label with persistent override |
| POST | `/api/clusters/merge` | Merge source cluster into target cluster |
| POST | `/api/clusters/{cluster_id}/split` | Split cluster into k sub-clusters using semantic embeddings |
| POST | `/api/analyze` | Fast demo endpoint with cluster topic modeling (no physics layout) |

## Architectural Principles

### Zero-LLM Architecture
Parallax intentionally does not require a generative LLM. Semantic representation uses embedding models (`sentence-transformers/all-mpnet-base-v2`), while clustering, topic modeling, search, visualization, and evidence presentation rely on deterministic or measurable computational signals.

## Known Limitations & Deviations Identified

1. **Performance Profiling**: System profiling and runtime benchmarks across caching, clustering, and layout to be conducted in Phase 9.
2. **Evaluation & Benchmarks**: Systematic benchmarking across clustering algorithms, synthetic fixtures, and parameter spaces is scheduled for Phase 10.

## Architecture Change Log

- **Phase 0 (2026-10-02)**: Complete baseline audit performed and documented. System structure, data flow, physics layout, and constraint pipeline audited against source code.
- **Phase 1 (2026-10-02)**: Implemented true constraint-aware clustering pipeline (`run_constraint_aware_clustering()`), separating constrained documents before HDBSCAN execution, merging forced assignments, computing global centroids and boundaries, and adding dedicated test suite `test_constraint_aware_clustering.py`.
- **Phase 2 (2026-10-02)**: Verified and hardened stable cluster UUID lineage across incremental updates with full state persistence, fixed cyclic angular relaxation in `compute_home_positions()` using pairwise shortest-arc resolution, and added dedicated test suite `test_stable_identity_and_layout.py`.
- **Phase 3 (2026-10-02)**: Established comprehensive automated testing and evaluation foundation: modular synthetic corpus fixtures (`synthetic_corpora.py`), test suites for clustering quality, constraint impact, spatial stability, and API endpoints, and a unified test discovery runner `run_all_tests.py` covering 28 test cases with zero external runtime dependencies.
- **Phase 4 (2026-10-02)**: Implemented production-grade PDF upload, validation, deduplication, text chunking, and immediate `.npy` disk caching in `backend/ingestion/ingest.py`, exposed `POST /api/documents/upload` and `DELETE /api/documents/{filename}`, added comprehensive test suite `test_pdf_ingestion_and_caching.py` (35/35 tests passing), and added frontend upload/delete controls in `EvaluationPanel.jsx`.
- **Post-Phase 4 Correction (2026-10-03)**: Implemented outlier spatial isolation (ADR-007): angular gap bisector anchoring for noise clusters, strong mutual noise-cluster repulsion, gravity exclusion, and geometric convex hull clearance guarantee (`ensure_outlier_hull_isolation()`), adding regression suite `test_outlier_spatial_isolation.py` (39/39 tests passing).
- **Phase 5 (2026-10-03)**: Implemented automatic cluster topic modeling via Class-based TF-IDF (c-TF-IDF) and KeyBERT semantic centroid alignment in `backend/topics/topic_modeling.py`, added extracted text disk caching (`<sha256>.txt`), integrated topics into `run_pipeline()`, `/api/organize`, and `/api/analyze`, updated frontend `ClusterRegion.jsx` and `EvaluationPanel.jsx` to render dynamic topic titles and representative keywords, and added comprehensive test suite `test_topic_modeling.py` (47/47 tests passing).
- **Phase 6 (2026-10-03)**: Implemented semantic search engine (`backend/search/semantic_search.py`), exact cosine similarity ranking against cached 768-dim embeddings, `POST /api/search` endpoint with cluster relevance aggregation, topbar `SearchBar.jsx`, canvas radiant glowing heatmap halos (`DocumentNode.jsx`), cluster relevance highlights (`ClusterRegion.jsx`), and ranked match sidebar (`EvaluationPanel.jsx`), adding dedicated test suite `test_semantic_search.py` (55/55 tests passing).
- **Phase 7 (2026-10-04)**: Implemented interactive cluster lifecycle management (`backend/clustering/lifecycle.py`) supporting cluster renaming (`PUT /api/clusters/{cluster_id}/topic`), cluster merging (`POST /api/clusters/merge`), and cluster splitting (`POST /api/clusters/{cluster_id}/split`) with persistent topic overrides, constraint synchronization, stable UUID lineage, and UI lifecycle controls in `EvaluationPanel.jsx` (67/67 tests passing).
- **Roadmap Scope Reduction (2026-10-04)**: Streamlined remaining roadmap to eliminate citation networks, speculative gap radar, and standalone explorer subsystems in favor of focused frontend evidence inspection, performance profiling, rigorous evaluation, and hardening.
- **Phase 8 (2026-10-04)**: Complete frontend redesign following 3-Zone Architecture (ADR-011): collapsible 56px→220px NavRail with zero-reflow 60fps overlay, floating CommandBar and CanvasDock with physics rerun and loading spinners, 360px contextual sliding InspectorDrawer (Search, Library, Clusters, Evaluation, and Document Inspector workspaces), refined Light/Dark theme text contrast, and in-app deep-link PDF viewer (67/67 automated tests passing, production build clean).
