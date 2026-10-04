# Parallax — Reproducibility & Verification Guide

This document provides exact, end-to-end instructions for reproducing all system workflows, automated test suites, and empirical evaluation benchmarks in Parallax.

---

## 1. System Requirements & Environment

### Hardware Requirements
- **CPU:** 4+ cores recommended (tested on x86_64 CPU).
- **RAM:** Minimum 8 GB (16 GB recommended for full scalability benchmarks at $N=500$).
- **Storage:** ~2 GB free disk space (includes virtual environment, PyTorch CPU wheel, sentence-transformers model weights, and embedding cache).
- **GPU:** Optional. The default CPU build of PyTorch is fully sufficient for inference and testing.

### Software Requirements
- **Python:** 3.10, 3.11, or 3.12.
- **Node.js:** v18.0+ or v20.0+.
- **Package Managers:** `pip` (Python) and `npm` (Node).
- **Operating System:** Windows 10/11, macOS, or Linux (Ubuntu 20.04+).

---

## 2. Installation & Setup

### Step 1: Clone Repository
```bash
git clone https://github.com/sznjzy/parallax.git
cd parallax
```

### Step 2: Backend Setup
```bash
# Create and activate Python virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

# Install package in editable mode and install dependencies
pip install -e .
pip install -r requirements.txt
```

### Step 3: Frontend Setup
```bash
cd frontend
npm install
cd ..
```

---

## 3. Running the Live Application

### Terminal 1: Backend API Service
```bash
# From repository root with virtual environment activated:
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```
- API Liveness Probe: `http://127.0.0.1:8000/`
- Interactive OpenAPI / Swagger Docs: `http://127.0.0.1:8000/docs`

### Terminal 2: Frontend Interactive UI
```bash
# From repository root:
cd frontend
npm run dev
```
- Accessible in web browser at `http://localhost:5173/`

---

## 4. Running Automated Regression Test Suites

Parallax includes **68 automated unit and integration tests** covering ingestion, clustering, constraints, spatial layout physics, topic modeling, semantic search, security hardening, and API endpoints.

```bash
# From repository root with virtual environment activated:
python -u run_all_tests.py
```

### Expected Output:
```
Ran 68 tests in ~85-115s
OK
Total Tests Run: 68
Failures: 0
Errors: 0
Skipped: 0
ALL TESTS PASSED SUCCESSFULLY.
```

To verify the production frontend build:
```bash
cd frontend
npm run build
```
### Expected Output:
```
vite build
✓ 242 modules transformed.
dist/index.html
dist/assets/index-...css
dist/assets/index-...js
✓ built in ~1.5-2.5s (0 errors)
```

---

## 5. Sample Research Corpus & Licensing Scope

The full evaluation corpus consists of **34 academic papers** (`paper1.pdf` through `paper34.pdf`) spanning Deep Learning, Distributed Systems, Computer Networking, Compiler Optimization, and Information Visualization, plus one intentional culinary outlier paper (`paper34.pdf`).

To respect copyright and publisher distribution policies:
- **Redistributable Papers (Tracked in Git):** 5 papers with explicit Creative Commons licenses are tracked directly in `data/sample_docs/` (`paper5.pdf`, `paper23.pdf`, `paper24.pdf`, `paper26.pdf`, `paper34.pdf`).
- **Restricted Papers (Local Reproduction):** 29 papers with restrictive publisher licenses are omitted from Git tracking and ignored by `.gitignore`.
- See [`data/sample_docs/README.md`](../data/sample_docs/README.md) for the complete 34-paper title/author/venue mapping and instructions to obtain missing papers from open-access publisher repositories.

---

## 6. Running the Empirical Evaluation Suite

The quantitative evaluation suite benchmarks clustering quality (E1), constraint satisfaction (E2), incremental multi-stage stability (E3), semantic search information retrieval (E4), and scalability ($N=34$ to $500$).

```bash
# From repository root with virtual environment activated:
python -u backend/evaluation/run_all_evaluations.py
```

### Generated Artifacts:
Upon completion, the evaluation runner writes:
1. `docs/EVALUATION.md` (or `EVALUATION_REPORT.md`) — Complete Markdown report with comparative tables.
2. `evaluation_results.json` — Machine-readable raw JSON data.

---

## 7. Evaluation Subsystems & Methodological Design

### E1 — Clustering Quality Benchmark
- **Synthetic Benchmark:** Evaluates HDBSCAN, KMeans (Oracle-$k$), and Agglomerative Clustering (Oracle-$k$) across synthetic Gaussian clusters ($k \in [2, 8]$) with injected noise points. Measures Adjusted Rand Index ($ARI$), Normalized Mutual Information ($NMI$), Silhouette, Davies-Bouldin, and noise classification.
- **Real 34-Paper Corpus:** Runs on 768-D embeddings from `data/sample_docs/` extracted with `sentence-transformers/all-mpnet-base-v2`. Compares HDBSCAN autonomous discovery against KMeans ($k=2..8$) and Agglomerative Clustering ($k=2..8$).

### E2 — Constraint Effectiveness
Evaluates production `run_constraint_aware_clustering()` across 4 controlled conditions:
- **Condition A:** Unconstrained baseline ($0$ constraints).
- **Condition B:** Single document reassignment ($1$ constraint).
- **Condition C:** Multiple competing constraints ($3$ constraints).
- **Condition D:** Outlier integration (forcing outlier `paper34.pdf` into target cluster $c_0$).
- **Metrics:** Constraint Satisfaction Rate ($CSR$), unconstrained partition stability ($ARI$), centroid displacement ($\Delta c$), and silhouette impact ($\Delta SS$).

### E3 — Incremental Multi-Stage Stability
Evaluates cluster UUID preservation and spatial layout continuity across sequential corpus expansions using exact documented subsets:
- **Stage 0 ($N=20$):** `paper1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 15, 17, 18, 19, 20, 23, 24, 25, 29, 30`
- **Stage 1 ($N=27$):** Stage 0 + `paper3, 12, 13, 14, 16, 31, 32`
- **Stage 2 ($N=34$):** Stage 1 + `paper21, 22, 26, 27, 28, 33, 34`
- **Metrics:** Lineage Preservation Rate ($LPR$), Document Reassignment Rate ($DRR$), mean/median/max spatial displacement (px).

### E4 — Semantic Search Retrieval
Evaluates in-memory vector dot product retrieval (`search_corpus()`) across 5 academic queries (Q1–Q5) with explicit ground truth document mappings in `backend/evaluation/ground_truth_search.json`.
- **Metrics:** Precision@3 ($P@3$), Precision@5 ($P@5$), Recall@5 ($R@5$), Mean Reciprocal Rank ($MRR$), and outlier `paper34.pdf` ranking.

### Scalability Benchmark
Measures execution latencies across synthetic corpora of size $N \in [34, 50, 100, 250, 500]$ over 5 repetitions (mean $\pm$ std) for HDBSCAN clustering, KMeans clustering, 2D force-directed layout physics (80 iterations), and vector dot-product search.

---

## 8. Key Parameters & Configuration

| Module | Parameter | Value | Rationale |
|---|---|---|---|
| **Embeddings** | Model | `sentence-transformers/all-mpnet-base-v2` | 768-D dense semantic representations with cosine normalization |
| **Embeddings** | Chunk size | 400 words | Contiguous text window with 50-word overlap |
| **Clustering** | `min_cluster_size` | 2 | Permits small micro-topics in small academic corpora ($N \approx 20-50$) |
| **Clustering** | `min_samples` | 1 | Restricts excessive noise generation on small datasets |
| **Clustering** | `metric` | `euclidean` | Equivalent to Cosine Distance on unit L2-normalized vectors |
| **Boundary Detection** | `BOUNDARY_MARGIN` | 0.05 | Flagged if $(\text{sim}_{\text{top1}} - \text{sim}_{\text{top2}}) < 0.05$ |
| **Layout Physics** | Canvas dimensions | 400 × 300 | Normalized coordinate system scaled by frontend viewports |
| **Layout Physics** | Max iterations | 80 | Empirical convergence threshold for energy dissipation |
| **Layout Physics** | Minimum angular separation | $35^\circ$ | Pairwise shortest-arc circular relaxation between cluster homes |

---

## 9. Empirical Observations & Known System Limitations

1. **Force-Directed Physics Scaling:** Physics simulation scales quadratically $O(N^2)$ with the number of canvas nodes. While execution is fast for small corpora ($123.6\text{ ms}$ at $N=34$, $904.3\text{ ms}$ at $N=100$), execution at $N=500$ takes $\approx 18.6\text{ seconds}$ per 80 iterations on CPU. For interactive UI rendering, corpus sizes between $N=20$ and $N=100$ provide the smoothest experience.
2. **Density-Based Clustering on Small Datasets:** When corpus size is very small ($N < 6$) or documents are uniformly sparse, HDBSCAN may classify a majority of points as noise. Parallax incorporates an automatic fallback to KMeans in such degenerate regimes.
3. **Information Retrieval Ground Truth:** The search evaluation ground truth reflects academic topic relevance defined on the evaluated 34-paper sample corpus; ranking performance on arbitrary external corpora depends on domain vocabulary and embedding model domain transfer.

---

## 10. Security Boundaries & Deployment Assumptions

1. **Filesystem & Path Traversal Defenses:** All file retrieval, document deletion, and upload endpoints enforce strict path sanitization (`sanitize_filename()`). Slashes, backslashes, null bytes (`\x00`), and relative path components (`../`) are stripped or normalized to prevent directory escape outside `data/sample_docs/`.
2. **File Ingestion Validation:** PDF uploads undergo strict multi-stage validation including filename extension checks, `%PDF-` magic byte signature verification, 50MB file size limits, and SHA-256 deduplication before ingestion or chunking.
3. **Constraint Input Validation:** Constraint creation (`POST /api/constraints`) enforces non-empty, non-whitespace string identifiers for both document IDs and cluster IDs, returning controlled 400 Bad Request responses for malformed payloads.
4. **Deployment Scope & CORS Policy:** Parallax is intended as a local/single-user research application. The FastAPI backend configures `allow_origins=["*"]` with `allow_credentials=False` as a local/development deployment assumption to support local Vite dev servers and disk-opened HTML canvases without external credential exposure. A production/public deployment would require a stricter origin policy, TLS termination, and authentication.
