# Parallax — AI-Powered Semantic Research Canvas

> **Status:** Release Verification Complete.
> All **68 backend unit/integration tests** pass with 0 errors, frontend production build is clean with 0 errors, and empirical evaluation benchmarks are documented in [`docs/EVALUATION.md`](docs/EVALUATION.md).

---

## 1. Executive Summary & Overview

**Parallax** is an interactive semantic research synthesis engine that enables researchers, students, and engineers to organize, explore, and synthesize complex academic literature on an interactive 2D spatial canvas. Unlike traditional conversational AI tools that offer opaque generative summaries prone to hallucination, Parallax uses deterministic mathematical models, unsupervised density clustering, persistent human-in-the-loop constraints, and zero-LLM semantic search to deliver fully grounded, verifiable literature maps.

### The Problem
Traditional literature tools present papers either as flat search lists or static folder trees. While modern conversational AI tools offer text summaries, they frequently hallucinate claims, discard user spatial organization upon re-indexing, and obscure why specific papers are grouped together.

### The Parallax Approach
1. **Dense Vector Semantics:** Maps research documents into a continuous 768-dimensional semantic hypersphere using `sentence-transformers/all-mpnet-base-v2`.
2. **Autonomous Density Clustering:** Discovers natural research themes and isolates outlier literature using HDBSCAN without requiring manual cluster count specification.
3. **Persistent User Constraints:** When a user drags a document to a different cluster, that human intent is preserved as a persistent constraint across subsequent pipeline runs.
4. **Stateful Identity & Spatial Anchoring:** Cluster identifiers (UUIDs) and spatial layouts remain stable across incremental document additions.
5. **Grounded Evidence Inspection:** Explanations for cluster membership, topics, and search relevance are derived purely from measurable mathematical signals (cosine similarity, c-TF-IDF term uniqueness, and centroid alignment) with **zero generative LLM dependencies**.

---

## 2. Core Processing Pipeline

```
Academic PDF Documents
  │
  ▼
[1. Safe Ingestion & Deduplication]  ──► Magic bytes signature validation, sanitization & SHA-256 hash checks
  │
  ▼
[2. Text Extraction & Chunking]     ──► Contiguous 400-word windows with 50-word overlap (pypdf)
  │
  ▼
[3. Dense Vector Embeddings]        ──► all-mpnet-base-v2 (768-D), mean pooling, unit L2-norm
  │                                      (Disk cached at data/embedding_cache/<sha256>.npy)
  ▼
[4. Constraint-Aware Separation]    ──► Partitions corpus into constrained vs. unconstrained sets
  │
  ▼
[5. HDBSCAN Density Clustering]     ──► Autonomous cluster discovery on unconstrained documents
  │                                      (KMeans fallback for small/degenerate corpora)
  ▼
[6. Constraint Assignment & Merge]  ──► Deterministically re-injects forced user constraints
  │
  ▼
[7. Stable Identity Tracking]       ──► Jaccard/overlap lineage matching against state file
  │
  ▼
[8. Automatic Topic Modeling]       ──► Class-based TF-IDF (c-TF-IDF) + KeyBERT centroid alignment
  │
  ▼
[9. Force-Directed Spatial Layout]  ──► Deterministic circular home anchors, Euler physics integration
  │                                      with noise perimeter isolation (ADR-007)
  ▼
[10. Interactive 3-Zone Interface]  ──► 60 FPS HTML5 Canvas (Konva) + Contextual Inspector Workspaces
```

---

## 3. Major Features

- **Constraint-Aware Clustering:** Separates constrained documents prior to density estimation, ensuring manual user corrections achieve 100% satisfaction without distorting natural cluster formation.
- **Density-Based Clustering & Outlier Isolation:** Unsupervised theme discovery via HDBSCAN with automatic peripheral spatial isolation for noise documents (`noise-*`).
- **Stable Cluster Identity:** Persistent UUID continuity across incremental updates with overlap tracking ($\ge 50\%$).
- **Deterministic Incremental Layout:** Circular angular anchor relaxation ($\ge 35^\circ$) and force-directed node simulation with position reuse to minimize visual disruption.
- **Automatic Topic Modeling:** Extraction of dynamic cluster titles and representative keywords using c-TF-IDF and KeyBERT semantic alignment from cached text.
- **Zero-LLM Semantic Search:** Fast in-memory vector dot product retrieval with cosine similarity ranking, passage snippet extraction, and aggregated cluster relevance.
- **Canvas Heatmap Visualization:** Dynamic radiant search halos on document nodes and cluster region highlights for query relevance.
- **In-App PDF Reader & Evidence Inspector:** Deep-linking PDF viewer modal with search term navigation and grounded evidence cards displaying centroid distance and top terms.
- **Interactive Cluster Lifecycle:** Full support for custom topic renaming, cluster merging, and $k$-way semantic splitting.
- **Empirical Evaluation Suite:** Automated benchmark harness evaluating clustering quality, constraint effectiveness, incremental stability, search relevance, and scalability.

---

## 4. Technology Stack

### Backend
- **Language & Runtime:** Python 3.10+
- **Web Framework:** FastAPI (`0.111+`), Uvicorn (`0.29+`)
- **Embeddings & ML:** `sentence-transformers` (`2.6+`, `all-mpnet-base-v2`), PyTorch (`2.0+` CPU build)
- **Clustering & Numerics:** `hdbscan` (`0.8.33+`), `scikit-learn` (`1.4+`), `numpy` (`2.0+`)
- **PDF Ingestion:** `pypdf` (`4.0+`), `python-multipart`

### Frontend
- **Framework & Tooling:** React 18, Vite 5
- **Canvas Rendering:** Konva 9, `react-konva` 18 (HTML5 2D Canvas)
- **Design System:** Custom CSS tokens supporting high-contrast Dark & Light themes

---

## 5. Repository Structure

```
parallax/
├── backend/
│   ├── api/
│   │   ├── main.py                  # FastAPI application routes & middleware
│   │   ├── pipeline.py              # End-to-end processing pipeline orchestrator
│   │   ├── cluster_mapping.json     # Persistent cluster UUID state
│   │   └── constraints.json         # Persistent user constraint store
│   ├── clustering/
│   │   ├── pipeline.py              # HDBSCAN clustering, boundary detection, stable IDs
│   │   ├── constraints.py           # Constraint management & validation
│   │   └── lifecycle.py             # Cluster rename, merge, and split operations
│   ├── embeddings/
│   │   ├── pipeline.py              # Text extraction, chunking, all-mpnet-base-v2 embedding
│   │   └── embedding_cache.py       # SHA-256 disk cache for embeddings (.npy)
│   ├── ingestion/
│   │   └── ingest.py                # Safe PDF validation, deduplication, chunking, caching
│   ├── layout/
│   │   └── physics.py               # 2D force-directed simulation & angular home anchors
│   ├── topics/
│   │   └── topic_modeling.py        # c-TF-IDF & KeyBERT semantic topic extraction
│   ├── search/
│   │   └── semantic_search.py       # In-memory vector search & cluster relevance aggregation
│   ├── evaluation/
│   │   ├── run_all_evaluations.py   # Master evaluation orchestrator & report generator
│   │   ├── eval_clustering_e1.py    # E1 Clustering quality benchmarks
│   │   ├── eval_constraints_e2.py   # E2 Constraint satisfaction experiments
│   │   ├── eval_incremental_e3.py   # E3 Multi-stage incremental stability
│   │   ├── eval_search_e4.py        # E4 Semantic search retrieval evaluation
│   │   ├── eval_scalability.py      # Scalability latency benchmark (N=34 to 500)
│   │   └── ground_truth_search.json # Ground truth relevance annotations
│   └── tests/                       # 68 modular backend test cases
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Root layout with 3-Zone architecture
│   │   ├── index.css                # Minimalist design system tokens
│   │   ├── canvas/                  # Konva canvas stage, nodes, regions, dock, command bar
│   │   ├── components/              # Navigation rail, contextual inspector workspaces, PDF modal
│   │   ├── hooks/                   # Custom React hooks (useOrganize, useSearch, useConstraints, etc.)
│   │   └── state/                   # Global AppContext & reducer
│   └── package.json                 # Frontend package manifest
├── data/
│   ├── sample_docs/                 # Sample research corpus (5 tracked open-access PDFs)
│   └── embedding_cache/             # Precomputed SHA-256 .npy embedding cache
├── docs/
│   ├── ARCHITECTURE.md              # Detailed system architecture document
│   ├── EVALUATION.md                # Quantitative evaluation report
│   └── REPRODUCIBILITY.md           # Reproduction and environment guide
├── demo/
│   └── index.html                   # Standalone visual demonstration
├── evaluation_results.json          # Machine-readable evaluation output
├── requirements.txt                 # Backend Python dependencies
├── pyproject.toml                   # Python package configuration
└── run_all_tests.py                 # Unified test suite runner
```

---

## 6. Installation & Setup

### Prerequisites
- Python 3.10+
- Node.js 18+ and `npm`

### 1. Backend Setup
```bash
# Clone the repository
git clone https://github.com/sznjzy/parallax.git
cd parallax

# Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

# Install package in editable mode and install requirements
pip install -e .
pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

---

## 7. Running the Application

### Start Backend API Server
```bash
# Run with virtual environment activated:
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```
- API Liveness: `http://127.0.0.1:8000/`
- Interactive Swagger Docs: `http://127.0.0.1:8000/docs`

### Start Frontend Dev Server
```bash
# In a separate terminal:
cd frontend
npm run dev
```
- Open browser at `http://localhost:5173/`

---

## 8. Verification & Testing

### Run Automated Backend Test Suite
```bash
python -u run_all_tests.py
```
*Current verified status:* **68/68 tests passed (0 failures, 0 errors)** in ~85–115 seconds.

### Build Production Frontend
```bash
cd frontend
npm run build
```
*Current verified status:* **0 errors, bundle generated cleanly in ~1.5–2.5 seconds.**

---

## 9. Sample Research Corpus & Licensing

The full evaluation corpus consists of **34 academic papers** spanning Deep Learning, Distributed Systems, Computer Networking, Compiler Optimization, and Information Visualization, plus one intentional culinary outlier paper (`paper34.pdf`).

To respect copyright and publisher distribution policies:
- **Redistributable Papers (Tracked in Git):** 5 papers with explicit Creative Commons licenses are included directly in `data/sample_docs/` (`paper5.pdf`, `paper23.pdf`, `paper24.pdf`, `paper26.pdf`, `paper34.pdf`).
- **Restricted Papers (Local Reproduction):** 29 papers with restrictive publisher licenses are omitted from Git tracking.
- For instructions on obtaining the remaining papers from open-access publisher repositories to replicate the full 34-paper benchmark, see [`data/sample_docs/README.md`](data/sample_docs/README.md).

---

## 10. Quantitative Evaluation Results

To run the complete quantitative evaluation suite:
```bash
python -u backend/evaluation/run_all_evaluations.py
```

This generates [`docs/EVALUATION.md`](docs/EVALUATION.md) and [`evaluation_results.json`](evaluation_results.json).

### Key Empirical Findings:
- **E1 (Clustering Quality):** On the 34-paper research corpus, HDBSCAN achieves Cosine Silhouette = **0.3485** and Davies-Bouldin Index = **1.1616** in **10.93 ms**, outperforming KMeans ($k=2..8$, Silhouette $\in [0.2288, 0.3316]$) and Agglomerative Clustering ($k=2..8$, Silhouette $\in [0.2225, 0.3272]$).
- **E2 (Constraint Satisfaction):** Parallax achieves **100.0% Constraint Satisfaction Rate** across single-document, multi-document (3 competing constraints), and outlier integration conditions, maintaining unconstrained partition stability ($ARI \ge 0.8964$).
- **E3 (Incremental Lineage):** Multi-stage corpus expansions ($N_0=20 \to N_1=27 \to N_2=34$) achieve **83.3% to 90.9% Lineage Preservation Rate** with low average spatial displacement (~35–55 px).
- **E4 (Semantic Search):** In-memory vector dot product retrieval achieves **Mean MRR = 1.0000**, **Mean P@3 = 80.0%**, **Mean P@5 = 68.0%**, and **Mean R@5 = 96.0%** across evaluated research queries, placing the outlier `paper34.pdf` at rank #34 for computer science queries and rank #1 for culinary queries.

---

## 11. Verified API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Liveness health check |
| `GET` | `/api/status` | Readiness check (PDF document count and embedding dependency availability) |
| `POST` | `/api/organize` | Execute full ingestion, embedding, clustering, topic modeling, and physics layout pipeline |
| `POST` | `/api/search` | Semantic search across document embeddings with cosine similarity ranking and cluster relevance |
| `GET` | `/api/documents` | List available PDF documents with SHA-256 cache status |
| `POST` | `/api/documents/upload` | Multi-PDF upload with signature validation, chunking, and immediate disk caching |
| `DELETE` | `/api/documents/{filename}` | Delete PDF document and prune corresponding state |
| `GET` | `/api/documents/{filename}/pdf` | Stream raw PDF binary for in-app viewing |
| `GET` | `/api/constraints` | List all active user drag-and-drop constraints |
| `POST` | `/api/constraints` | Save or replace a user constraint (`{doc_id, forced_cluster_id}`) |
| `DELETE` | `/api/constraints/{doc_id}` | Remove constraint for a specific document |
| `DELETE` | `/api/constraints` | Clear all active constraints |
| `GET` | `/api/clusters` | List active clusters with topics, keywords, and document counts |
| `PUT` | `/api/clusters/{cluster_id}/topic` | Override and persist custom cluster topic label |
| `POST` | `/api/clusters/merge` | Merge source clusters into a target cluster and update constraints |
| `POST` | `/api/clusters/{cluster_id}/split` | Split a cluster into $k$ sub-clusters using semantic embeddings |
| `POST` | `/api/analyze` | Fast demo endpoint (clustering and topic modeling without physics simulation) |

---

## 12. Known System Limitations

1. **Force-Directed Physics Complexity:** The 2D Euler force simulation evaluates pairwise repulsion with $O(N^2)$ complexity. While near-instantaneous for small and medium corpora ($123.6\text{ ms}$ at $N=34$, $904.3\text{ ms}$ at $N=100$), simulation for $N=500$ nodes takes $\approx 18.6\text{ seconds}$ on CPU.
2. **Density Sensitivity on Sparse Corpora:** Density-based clustering (HDBSCAN) requires sufficient local point density. In very small ($N < 6$) or uniformly sparse corpora, HDBSCAN may classify a majority of documents as noise; Parallax automatically falls back to KMeans in such cases.
3. **Information Retrieval Ground Truth Scope:** The semantic search benchmark is evaluated against curated query-relevance annotations for the 34-paper sample corpus. Performance on external domains is dependent on `all-mpnet-base-v2` cross-domain embedding transfer.
4. **Single-Node Execution:** Ingestion, disk caching, and embedding generation operate on the local filesystem of a single server instance.

---

## 13. Documentation Links

- **[System Architecture](docs/ARCHITECTURE.md):** Detailed technical specifications of ingestion, embeddings, HDBSCAN clustering, topic modeling, physics layout, and security hardening.
- **[Empirical Evaluation](docs/EVALUATION.md):** Complete benchmark results covering clustering quality (E1), constraint satisfaction (E2), incremental stability (E3), semantic search (E4), and scalability.
- **[Reproducibility Guide](docs/REPRODUCIBILITY.md):** Step-by-step instructions, parameters, and verification procedures.
- **[Corpus Documentation](data/sample_docs/README.md):** Mapping of sample research PDFs, licensing terms, and download references.

---

## 14. License & Academic Use

This project was developed as a Final Year Engineering Project. The software implementation is provided under standard academic open-source terms. Included sample research papers retain their respective authors' Creative Commons licenses as documented in [`data/sample_docs/README.md`](data/sample_docs/README.md).
