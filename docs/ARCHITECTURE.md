# Parallax System Architecture

This document describes the implemented, empirically verified architecture of **Parallax — AI-Powered Research Synthesis Engine**.

---

## 1. System Pipeline & Data Flow

```
Academic PDF Documents
  │
  ▼
[1. PDF Ingestion & Validation Subsystem]
  - Magic byte validation (%PDF-) & .pdf extension check
  - File size bounds check (<= 50 MB)
  - Strict filename sanitization (directory escape & null byte stripping)
  - SHA-256 deduplication
  - Text stream extraction via pypdf
  │
  ▼
[2. Chunking & Dense Embeddings Subsystem]
  - Contiguous 400-word chunking with 50-word overlap
  - sentence-transformers/all-mpnet-base-v2 (768-dimensional dense vector space)
  - Document-level mean pooling & unit L2-normalization (||v||_2 = 1.0)
  - Persistent SHA-256 .npy disk caching at data/embedding_cache/<sha256>.npy
  │
  ▼
[3. Constraint-Aware Separation]
  - Load active user constraints from constraints.json ({doc_id: forced_cluster_id})
  - Partition corpus into unconstrained documents vs. constrained documents
  │
  ▼
[4. Density Clustering & Boundary Detection]
  - HDBSCAN (min_cluster_size=2, min_samples=1, Euclidean metric on unit vectors)
  - Unconstrained documents cluster autonomously into natural density themes
  - Fallback to KMeans when corpus is degenerate or uniformly sparse (N < 6)
  - Re-inject constrained documents deterministically into their forced cluster assignments
  - Compute normalized global cluster centroids
  - Evaluate boundary documents: flagged when (sim_top1 - sim_top2) < 0.05
  │
  ▼
[5. Stable Cluster Identity Lineage]
  - Track cluster continuity across executions via set overlap: |C_new ∩ C_old| / |C_old| >= 0.5
  - Historical cluster UUIDs preserved in cluster_mapping.json; pruned on document deletion
  │
  ▼
[6. Automatic Topic Modeling Subsystem]
  - Class-based TF-IDF (c-TF-IDF) term uniqueness extraction across cluster text
  - KeyBERT cosine re-ranking against cluster centroids
  - Persistent topic and term cache at data/embedding_cache/<sha256>.txt
  │
  ▼
[7. Force-Directed Spatial Layout Subsystem]
  - Normalized 400 × 300 coordinate system
  - Deterministic circular home position hashing with >= 35° pairwise angular relaxation
  - Outlier gap bisector anchoring on outer perimeter with convex hull clearance isolation
  - Euler force simulation: intra/inter-cluster repulsion, centroid spring attraction, damping
  │
  ▼
[8. Interactive 3-Zone Frontend]
  - Zone 1: Collapsible 56px → 220px NavRail (zero canvas reflow)
  - Zone 2: Interactive 60 FPS HTML5 Canvas (Konva) with CommandBar and CanvasDock
  - Zone 3: 360px Sliding Contextual Inspector Workspaces (Search, Library, Clusters, Evaluation, Inspector)
  - In-app deep-linking PDF reader modal with term highlighting
```

---

## 2. Component Architectures

### 2.1 Ingestion & Chunking Subsystem (`backend/ingestion/ingest.py`)
- **Validation:** Enforces magic byte `%PDF-` signature check, `.pdf` extension check, and a maximum file size limit (50 MB per PDF).
- **Sanitization:** Strips path separators (`/`, `\`), null bytes (`\x00`), and relative path components (`..`) to prevent directory traversal outside `data/sample_docs/`.
- **Extraction:** Extracts text streams via `pypdf`. Corrupted or unparseable PDFs are gracefully isolated into `skipped_documents` with error logging.
- **Chunking:** Splits document text into 400-word blocks with 50-word overlap to ensure semantic continuity across paragraph boundaries.

### 2.2 Dense Embedding Subsystem (`backend/embeddings/`)
- **Model:** `sentence-transformers/all-mpnet-base-v2` (768-dimensional dense vector space).
- **Pooling & Normalization:** Document chunks are embedded individually, aggregated via arithmetic mean pooling into a single document vector, and normalized to the unit hypersphere ($\|v\|_2 = 1.0$).
- **Disk Caching:** Embeddings are keyed by the SHA-256 hash of the raw PDF content and stored at `data/embedding_cache/<sha256>.npy`. Identical files bypass model inference on subsequent executions.

### 2.3 Constraint-Aware Clustering Subsystem (`backend/clustering/pipeline.py`)
- **Partition Pipeline:**
  1. Constrained documents are separated from unconstrained documents prior to density clustering.
  2. HDBSCAN runs strictly on unconstrained documents, preventing manual user overrides from distorting natural density estimates.
  3. Discovered clusters inherit stable UUIDs from historical state via overlap matching.
  4. Constrained documents are deterministically merged into their designated cluster assignments.
  5. Global cluster centroids are recomputed across all assigned members.
  6. Boundary condition evaluated: documents where $(\text{sim}_{\text{top1}} - \text{sim}_{\text{top2}}) < 0.05$ receive secondary cluster attraction flags.
- **Noise Classification:** Documents unassigned by density clustering receive stable `noise-*` identifiers.

### 2.4 Stable Cluster Identity Subsystem (`backend/clustering/pipeline.py`)
- Tracks cluster continuity across incremental executions by calculating document set overlap:
  $$\text{Overlap}(C_{\text{new}}, C_{\text{old}}) = \frac{|C_{\text{new}} \cap C_{\text{old}}|}{|C_{\text{old}}|}$$
- If $\text{Overlap} \ge 0.5$, the cluster inherits the historical UUID. Unmatched clusters receive new cryptographically random UUIDs (`cluster-<8hex>`). Historical records for deleted documents are pruned from `cluster_mapping.json`.

### 2.5 Topic Modeling Subsystem (`backend/topics/topic_modeling.py`)
- **c-TF-IDF Term Extraction:** Evaluates term uniqueness across aggregated cluster texts:
  $$W_{c, t} = tf_{c, t} \times \log\left(1 + \frac{A}{f_t}\right)$$
  where $A$ is the average word count per cluster and $f_t$ is total term frequency across all clusters.
- **KeyBERT Semantic Centroid Alignment:** Reranks candidate keywords using a composite score (60% cosine similarity to the normalized cluster centroid embedding + 40% c-TF-IDF term uniqueness).
- **Text Caching:** Extracted text is cached to `data/embedding_cache/<sha256>.txt`.

### 2.6 Force-Directed Spatial Layout Subsystem (`backend/layout/physics.py`)
- **Canvas Space:** 400 × 300 normalized coordinate system.
- **Home Anchoring:** Real clusters are mapped to angles on an inner orbit ($r = \min(W, H) \times 0.34$) via SHA-256 integer hashes, resolved via pairwise shortest-arc circular relaxation ($\ge 35^\circ$).
- **Outlier Isolation:** Noise nodes are anchored to angular gap bisectors (voids) on an outer periphery ($r = \min(W, H) \times 0.46$), receive zero center gravity, experience strong mutual repulsion ($k=8000$), and undergo geometric hull clearance verification (`ensure_outlier_hull_isolation()`).
- **Simulation Forces:**
  - Intra-cluster repulsion ($k=4000$) and inter-cluster repulsion ($k=12000$).
  - Centroid spring attraction ($k=0.5$), split proportionally for boundary documents.
  - Center gravity ($k=0.01$) for non-noise cluster members.
  - Velocity damping ($0.85$), anchor damping ($0.05$), and margin clamping ($[24, W-24], [24, H-24]$).

### 2.7 Zero-LLM Semantic Search Subsystem (`backend/search/semantic_search.py`)
- **Mechanism:** Encodes incoming query strings into 768-D vectors using `all-mpnet-base-v2` and computes exact cosine similarity via unit vector dot product $q \cdot d$.
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

## 3. Frontend Architecture (3-Zone Design)

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

## 4. Security & Robustness Boundaries

1. **Path Traversal Defenses:** All file retrieval, document deletion, and upload endpoints enforce strict path sanitization (`sanitize_filename()`). Slashes, backslashes, null bytes (`\x00`), and relative path components (`../`) are stripped or normalized to prevent directory escape outside `data/sample_docs/`.
2. **File Ingestion Validation:** PDF uploads undergo strict multi-stage validation including filename extension checks, `%PDF-` magic byte signature verification, 50MB file size limits, and SHA-256 deduplication before ingestion or chunking.
3. **Constraint Input Validation:** Constraint creation (`POST /api/constraints`) enforces non-empty, non-whitespace string identifiers for both document IDs and cluster IDs, returning controlled 400 Bad Request responses for malformed payloads.
4. **Deployment Scope & CORS Policy:** Parallax is designed as a local/single-user research tool. The FastAPI backend configures `allow_origins=["*"]` with `allow_credentials=False` as a local development assumption to support local Vite dev servers and disk-opened HTML canvases without external credential exposure. A public deployment would require TLS termination, strict origin whitelisting, and authentication.

---

## 5. Pipeline Component Summary

| Component | Implementation File | Key Algorithm / Model | Output Artifact |
|---|---|---|---|
| Ingestion & Validation | `backend/ingestion/ingest.py` | Magic bytes, pypdf extraction | Extracted text stream |
| Embeddings & Caching | `backend/embeddings/pipeline.py` | `all-mpnet-base-v2` (768-D) | `data/embedding_cache/<hash>.npy` |
| Constraint Separation | `backend/clustering/pipeline.py` | Set partitioning | Partitioned document sets |
| Density Clustering | `backend/clustering/pipeline.py` | HDBSCAN (Euclidean on L2-norm) | Natural clusters + Noise (`-1`) |
| Constraint Injection | `backend/clustering/pipeline.py` | Deterministic override | 100% satisfied assignments |
| Stable UUID Lineage | `backend/clustering/pipeline.py` | Jaccard / Overlap matching | `cluster_mapping.json` |
| Topic Modeling | `backend/topics/topic_modeling.py` | c-TF-IDF + KeyBERT alignment | Cluster topics & keywords |
| Force-Directed Layout | `backend/layout/physics.py` | Angular hashing + Euler physics | 2D $(x, y)$ coordinates |
| Semantic Search | `backend/search/semantic_search.py` | Vector dot product ($q \cdot d$) | Ranked relevance & snippets |
