# PARALLAX VERIFIED ARCHITECTURE

This document describes the implemented and empirically verified architecture of Parallax.

## Current Verified State

Phase 10 — Complete Quantitative Evaluation (2026-10-04)

---

## 1. System Pipeline & Data Flow

```
PDF Document
  │
  ▼
[1. PDF Ingestion & Validation]
  - Magic byte validation (%PDF-)
  - SHA-256 deduplication
  - Text extraction (pypdf)
  │
  ▼
[2. Chunking & Embeddings]
  - 400-word contiguous chunking with 50-word overlap
  - sentence-transformers/all-mpnet-base-v2 (768-D)
  - Unit L2-normalization & document-level mean pooling
  - Persistent SHA-256 .npy embedding disk cache
  │
  ▼
[3. Constraint-Aware Separation]
  - Extract active manual user constraints from constraints.json
  - Split corpus into constrained vs. unconstrained document sets
  │
  ▼
[4. Density Clustering & Boundary Detection]
  - HDBSCAN (min_cluster_size=2, min_samples=1) on unconstrained documents
  - Re-inject forced user constraints into assigned clusters
  - Compute normalized global cluster centroids
  - Evaluate boundary documents based on centroid cosine similarity margin
  │
  ▼
[5. Stable Identity Lineage]
  - Overlap percentage comparison (|New ∩ Old| / |Old| >= 0.5)
  - Persistent UUID preservation in cluster_mapping.json
  │
  ▼
[6. Automatic Topic Modeling]
  - Class-based TF-IDF (c-TF-IDF) term uniqueness extraction
  - KeyBERT cosine re-ranking against cluster centroids
  - Persistent topic metadata and text disk cache
  │
  ▼
[7. Force-Directed Layout Physics]
  - Deterministic circular home position hashing with >=35° angular relaxation
  - Euler force simulation: intra/inter-cluster repulsion, centroid spring attraction
  - Outlier gap bisector placement & convex hull clearance isolation (ADR-007)
  │
  ▼
[8. Interactive 3-Zone Frontend]
  - Zone 1: Collapsible 56px→220px NavRail (zero canvas reflow)
  - Zone 2: Interactive 60 FPS HTML5 Canvas (Konva) with CommandBar and CanvasDock
  - Zone 3: 360px Sliding Contextual Inspector Workspaces (Search, Library, Clusters, Evaluation, Inspector)
  - In-app deep-linking PDF reader modal
```

---

## 2. Component Architectures

### 2.1 Ingestion & Chunking Subsystem (`backend/ingestion/ingest.py`)
- **Validation:** Enforces magic byte `%PDF-` signature check, `.pdf` extension check, and a maximum size limit (25 MB per PDF).
- **Extraction:** Extracts text streams via `pypdf`. Empty or corrupt PDFs are gracefully isolated into `skipped_documents`.
- **Chunking:** Splits document text into 400-word blocks with 50-word overlap to ensure semantic preservation across paragraph boundaries.

### 2.2 Dense Embedding Subsystem (`backend/embeddings/`)
- **Model:** `sentence-transformers/all-mpnet-base-v2` (768-dimensional dense vector space).
- **Pooling & Normalization:** Chunks are embedded individually and mean-pooled into a single canvas document vector, then normalized to the unit hypersphere ($\|v\|_2 = 1.0$).
- **Disk Caching:** Embeddings are keyed by the SHA-256 hash of the raw PDF content and stored at `data/embedding_cache/<sha256>.npy`. Identical files bypass model inference on subsequent executions.

### 2.3 Constraint-Aware Clustering Subsystem (`backend/clustering/pipeline.py`)
- **Architecture (ADR-001):**
  1. Constrained documents are separated from unconstrained documents prior to density clustering.
  2. HDBSCAN runs strictly on unconstrained documents, preventing manual constraints from distorting natural density estimates.
  3. Stable cluster UUIDs are assigned to discovered clusters via overlap matching.
  4. Constrained documents are deterministically merged into their target cluster assignments.
  5. Global cluster centroids are calculated across all active cluster members.
  6. Boundary flags are evaluated: documents where $(\text{sim}_{\text{top1}} - \text{sim}_{\text{top2}}) < 0.05$ receive secondary cluster attraction.
- **Noise Classification:** Documents not assigned to any density cluster receive stable `noise-*` identifiers.

### 2.4 Stable Cluster Identity Subsystem (`backend/clustering/pipeline.py`)
- Tracks cluster continuity across incremental executions by calculating document set overlap:
  $$\text{Overlap}(C_{\text{new}}, C_{\text{old}}) = \frac{|C_{\text{new}} \cap C_{\text{old}}|}{|C_{\text{old}}|}$$
- If $\text{Overlap} \ge 0.5$, the cluster inherits the historical UUID. Unmatched clusters receive new cryptographically random UUIDs (`cluster-<8hex>`). Historical records for deleted documents are pruned from `cluster_mapping.json`.

### 2.5 Topic Modeling Subsystem (`backend/topics/topic_modeling.py`)
- **c-TF-IDF Extraction (ADR-008):** Evaluates term uniqueness across aggregated cluster texts:
  $$W_{c, t} = tf_{c, t} \times \log\left(1 + \frac{A}{f_t}\right)$$
  where $A$ is the average word count per cluster and $f_t$ is total term frequency across all clusters.
- **KeyBERT Semantic Centroid Alignment:** Reranks candidate keywords using a composite score (60% cosine similarity to the normalized cluster centroid embedding + 40% c-TF-IDF term uniqueness).
- **Text Caching:** Extracted text is cached to `data/embedding_cache/<sha256>.txt`.

### 2.6 Force-Directed Spatial Layout Subsystem (`backend/layout/physics.py`)
- **Canvas Space:** 400 × 300 normalized coordinate system.
- **Home Anchoring (ADR-004):** Real clusters are mapped to angles on an inner orbit ($r = \min(W, H) \times 0.34$) via SHA-256 integer hashes, resolved via pairwise shortest-arc circular relaxation ($\ge 35^\circ$).
- **Outlier Isolation (ADR-007):** Noise nodes are anchored to angular gap bisectors (voids) on an outer periphery ($r = \min(W, H) \times 0.46$), receive zero center gravity, experience strong mutual repulsion ($k=8000$), and undergo geometric hull clearance testing (`ensure_outlier_hull_isolation()`).
- **Simulation Forces:**
  - Intra-cluster repulsion ($k=4000$) and inter-cluster repulsion ($k=12000$).
  - Centroid spring attraction ($k=0.5$), split proportionally for boundary documents.
  - Center gravity ($k=0.01$) for non-noise cluster members.
  - Damping ($0.85$), anchor damping ($0.05$), and margin clamping ($[24, W-24], [24, H-24]$).

### 2.7 Zero-LLM Semantic Search Subsystem (`backend/search/semantic_search.py`)
- **Mechanism (ADR-010):** Encodes incoming query strings into 768-D vectors using `all-mpnet-base-v2` and computes exact cosine similarity via unit vector dot product $q \cdot d$.
- **Cluster Relevance:** Aggregates document-level scores to compute cluster-level metrics (`mean_similarity`, `max_similarity`, `matched_docs_count`).
- **Snippet Grounding:** Extracts representative matched passages from cached document text.
- **Read-Only:** Pure functional query execution with zero mutation to corpus state or layout.

### 2.8 Evaluation Harness Subsystem (`backend/evaluation/`)
- Comprehensive benchmark package executing:
  - **E1:** HDBSCAN vs KMeans vs Agglomerative on synthetic and real 34-paper corpora.
  - **E2:** Constraint effectiveness across unconstrained baseline, single constraint, 3 competing constraints, and outlier integration.
  - **E3:** Multi-stage incremental stability ($N=20 \to 27 \to 34$).
  - **E4:** Semantic search information retrieval against explicit ground truth annotations.
  - **Scalability:** Latency profiling across $N \in [34, 50, 100, 250, 500]$ over 5 repetitions.

---

## 3. Frontend Architecture (3-Zone Minimalist Design — ADR-011)

- **Framework:** React 18 with Vite 5 and Konva 9 (`react-konva`).
- **Zone 1: Navigation Rail (`NavRail.jsx`):** Fixed 56px structural footprint expanding on hover to a 220px overlay (`cubic-bezier(0.22, 1, 0.36, 1)`). Hovering triggers zero canvas reflow, maintaining 60 FPS.
- **Zone 2: Canvas Centerpiece (`ResearchCanvas.jsx`):** Interactive Konva stage with pan, zoom, boundary rings, search radiant halos, and theme-aware contrast cards. Supported by floating `CommandBar.jsx` and `CanvasDock.jsx`.
- **Zone 3: Contextual Inspector Drawer (`InspectorDrawer.jsx`):** 360px sliding panel hosting dedicated workspaces:
  - `SearchWorkspace.jsx`: Ranked search results with passage snippets.
  - `LibraryWorkspace.jsx`: Corpus inventory, PDF upload dropzone, and cache badges.
  - `ClusterInspector.jsx`: Topic label override, cluster merge, and k-way split controls.
  - `EvaluationWorkspace.jsx`: Live silhouette scores, Davies-Bouldin index, and constraint satisfaction.
  - `DocumentInspector.jsx`: Grounded evidence cards displaying centroid distance, top terms, and similar papers.
- **Modals:**
  - `SettingsModal.jsx`: Theme switcher (Dark/Light) and cache/architecture inspector.
  - `PdfViewerModal.jsx`: Deep-linking PDF reader with page navigation and search highlights.

---

## 4. Architecture Evolution Log

- **Phase 0 (2026-10-02):** Baseline system audit and architectural baseline specification.
- **Phase 1 (2026-10-02):** True constraint-aware clustering pipeline implemented (ADR-001).
- **Phase 2 (2026-10-02):** Stable cluster UUID lineage and cyclic angular relaxation implemented (ADR-003, ADR-004).
- **Phase 3 (2026-10-02):** Testing foundation with synthetic fixtures and unified runner established.
- **Phase 4 (2026-10-02):** Safe PDF upload, validation, chunking, and disk caching implemented.
- **Post-Phase 4 (2026-10-03):** Outlier spatial isolation implemented (ADR-007).
- **Phase 5 (2026-10-03):** Automatic topic modeling via c-TF-IDF and KeyBERT centroid alignment implemented (ADR-008).
- **Phase 6 (2026-10-03):** Zero-LLM semantic search engine and radiant canvas heatmap implemented.
- **Phase 7 (2026-10-04):** Interactive cluster lifecycle management (Rename, Merge, Split) implemented.
- **Phase 8 (2026-10-04):** 3-Zone frontend redesign, grounded evidence inspection, and in-app PDF viewer implemented (ADR-011).
- **Phase 9 (2026-10-04):** Performance optimization (React node memoization, clean render cycles, physics stability verification).
- **Phase 10 (2026-10-04):** Complete quantitative evaluation suite implemented and verified (E1, E2, E3, E4, Scalability).
