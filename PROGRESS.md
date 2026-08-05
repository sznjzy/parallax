# Parallax Project Progress

## 1. Project Summary
Parallax is a persistent semantic research canvas designed to organize research documents spatially by meaning. The core technical claim being validated is that the system provides a persistent, stable semantic organization that survives incremental updates and corrections—meaning documents organically cluster into topics that gracefully accommodate new papers without capriciously rearranging the entire layout, unlike a one-shot regenerated summary.

## 2. Architecture Overview
The backend pipeline consists of three core components:

* **Embedding Pipeline:** Extracts text from PDFs and embeds them using `sentence-transformers/all-mpnet-base-v2` into semantic vectors. All chunks for a document are embedded and mean-pooled into a single canvas-position vector (re-normalized), with per-chunk vectors retained in memory for future question-grounded highlighting. Contract defined in `.agent/skills/embedding-pipeline/SKILL.md`.
* **Constrained Clustering:** Uses HDBSCAN with cosine distance to dynamically group the embedded vectors into topics, identifying boundary documents (cross-disciplinary papers) and assigning stable UUIDs. Contract defined in `.agent/skills/constrained-clustering/SKILL.md`.
* **Incremental Layout Engine:** Uses a continuous force-directed physics simulation (attraction/repulsion forces, cluster gravity, and velocity damping) to render these clusters on a 2D canvas, keeping clusters distinct while respecting boundary document weights. Contract defined in `.agent/skills/incremental-layout/SKILL.md`.

**Data Flow:** PDF → text → chunk → mean-pool embed → clustering → stable ID assignment → `compute_home_positions()` → layout → rendered positions.

## 3. What Has Been Validated

### a) Spike B — Layout Stability (physics engine, synthetic data)
**What was tested:** The stability and convergence of the force-directed physics engine in isolation using synthetic, deterministic test data.
* **The original bug & fix:** The initial attempt at Phase 2 incremental updates used a hard displacement cap for anchoring existing nodes, which caused linear drift across the canvas. This was fixed by using velocity damping (`ANCHOR_VELOCITY_DAMPING = 0.05`) instead, which smoothly bleeds kinetic energy while allowing tension to resolve.
* **The Phase 1 convergence bug & fix:** Clusters were initially collapsing into each other because boundary nodes created dynamic centroid coupling (pulling cluster centroids together). This was fixed by replacing the old hardcoded `CLUSTER_CENTRES` list with `compute_home_positions(cluster_ids)`, which generates well-separated fixed home positions for an arbitrary number of clusters (SHA-256 hash-derived angle per UUID, scaled to canvas), wired into every `simulate()` call.
* **Cross-phase home-position stability fix:** The initial `compute_home_positions()` assigned angles by sorted rank (`2pi*k/N`). This caused every surviving cluster's home position to shift whenever N changed (a new cluster added), defeating the stability guarantee. Fixed by deriving each cluster UUID's angle from a SHA-256 hash of the UUID string itself — the angle depends only on the cluster's identity, not on how many other clusters exist. Radius still scales with N. Verified by test 1c in `backend/tests/test_determinism_and_boundary.py`: adding a 4th cluster leaves the 3 surviving clusters at byte-identical positions.
* **Final validated numbers (post-hardening pass, real code path):**
  * Phase 1 (Initial Layout): Converged in 85/2000 iterations. Pairwise cluster separation: A-B 166.5, B-C 181.0, A-C 174.2 canvas units.
  * Phase 2 (Incremental Update): Converged in 72/200 iterations, **avg_displacement_existing_nodes = 0.0789 canvas units**, max_displacement = 0.1462 canvas units.
* **Boundary node validation:** The engine correctly positions boundary documents between their affiliated clusters, weighted by their secondary cluster similarity.

### b) Spike A — Clustering Quality (real PDF data)
**What was tested:** The ability of the embedding and clustering logic to produce accurate, distinct semantic topics on real research papers.
* **Test Corpus:** All 21 PDFs in `data/sample_docs/`.
* **Results (post-hardening pass):** Silhouette score = **0.3175** (5 clusters on 21 documents). The constraint fields (`constraint_satisfaction_rate`, `num_constraints_applied`, `num_constraints_violated`) are now correctly returned as `null` rather than the previous fake `1.0` placeholder — they will be populated once manual-correction / constraint-storage is implemented.
* **Silhouette score change — mean-pooling as root cause (not a bug):** The score dropped from **0.398** (pre-hardening, first-chunk-only) to **0.3175** (post-hardening, full-document mean-pool). This is a deliberate consequence of Tier 2's change in how each document is represented:
  * **Before:** only the first 400-word chunk (roughly the abstract + introduction) was embedded. Abstract embeddings are dense and topically coherent — they name the problem domain explicitly — so clusters built from them are tight.
  * **After:** all chunks are embedded and mean-pooled into a single unit-normalized canvas vector. Longer papers contain sections (related work, experimental setup, conclusions) that discuss adjacent topics and use generic language. Averaging these in pulls each document's embedding slightly toward the centre of the embedding space, softening the cosine-distance margin between clusters and lowering silhouette score.
  * **Why this is correct, not a regression:** Representing a paper only by its abstract conceals its actual content and risks misclassifying papers whose abstracts under-describe their methodology (e.g., a systems paper that mentions ML only in passing). Full-document mean-pooling ensures the canvas position reflects the whole paper, at the cost of slightly wider inter-cluster overlap. The 0.32 score is still comfortably above the 0.25 target set in the README and the 5-cluster grouping remains semantically sensible (validated manually).
  * **Correctness check:** `embed_document_chunks()` L2-normalizes each chunk embedding before averaging, then re-normalizes the pooled vector. For single-chunk documents the operation is identity (one normalized vector, mean = itself, re-normalize = no-op). The silhouette drop is therefore not caused by near-zero or malformed chunk embeddings — it is a genuine signal that full-document embeddings are more diffuse than abstract-only embeddings.
* **Boundary-document detection:** Uses the canonical `compute_boundary_flags()` from `clustering/pipeline.py` (the duplicate in `api/pipeline.py` was removed). Includes an edge-case fix: if a document's HDBSCAN-assigned cluster is not in the cosine top-2, the comparison is done against the assigned cluster vs. the single best other cluster, rather than two unrelated clusters.
* **Overlap formula (Task 12):** The denominator in `assign_stable_cluster_ids()` was changed from `min(len(new_docs), len(old_docs))` to `len(old_docs)`, so overlap measures "what fraction of the OLD cluster survived." This is more conservative and avoids false merges when a large new cluster absorbs a small old one.

### c) Pipeline Integration — Live API Validation & Stress Test (real PDFs)
**What was tested:** Chaining embedding, clustering, and layout into a live FastAPI endpoint (`/api/organize`) on a full 21-PDF real-world corpus, verifying JSON serialization and cross-request stable UUID tracking.
* **The critical JSON serialization bug that is now fixed:** A `TypeError: 'numpy.bool' object is not iterable` caused a `500 Internal Server Error` during the `jsonable_encoder` phase when the boundary flags (derived from numpy operations) were returned. The fix explicitly casts `node.is_boundary_document` and `node.is_anchored` to native Python `bool` types in `backend/api/pipeline.py`.
* **Live Stability (Unchanged Corpus):** Identical consecutive `POST /api/organize` requests yield **100% identical UUIDs** across all clusters and noise assignments.
* **Pruning & Overlap Logic (Delete/Add PDF):** Verified live by deleting and restoring `paper21.pdf` from the corpus.
  * Pruning dynamically removes the document from `cluster_mapping.json`.
  * Unaffected clusters perfectly retain their existing UUIDs.
  * A sibling document (`paper20`) previously clustered with `paper21` correctly re-clusters (due to HDBSCAN topological shifts) and gracefully adopts the stable UUID of the new existing cluster it joins (`cluster-788d3b38`).
  * Restoring `paper21` correctly forms a distinct new lineage and assigns a brand new UUID to the reinstated cluster, correctly demonstrating that extinct cluster lineage UUIDs (`cluster-3aee70a5`) are forgotten when completely dissolved.
* **Phase 1 / Phase 2 CLI Stress Test:** (Historic) The CLI stress-test `python -m backend.api.pipeline` forces a holdback/reveal split, demonstrating a "Phase 2 incremental update" where 14 nodes are anchored and 7 nodes are mobile. Converges at/near the 200-iteration cap with an avg displacement of ~10-14 canvas units. The live API endpoint is a single-pass implementation and does not exhibit this artificial phase-split tension.

## 4. Known Limitations / Honest Gaps
* **Environment Constraint:** On Python 3.13, `numpy 1.26` forces a local source compilation which hangs or fails on Windows without C++ Build Tools. The `requirements.txt` has been updated to use `numpy>=2.0,<3.0` which has prebuilt cp313 wheels and has been verified to be compatible with the rest of the ML stack (Torch, hdbscan, scikit-learn).
* The Phase 2 non-convergence within 200 iterations under the demo stress-test is a known issue when cluster assignments shift substantially between phases. The single-pass live API path does not exhibit this problem.
* The overlap-matching threshold (50% of old cluster) was validated for the specific paper20 ML→ML/Compiler migration described below; broader empirical validation across many scenarios has not been done.
* The `cluster_mapping.json` now prunes entries for docs no longer in the corpus on each run (Task 13 is fixed). No unbounded growth.
* Only PDF ingestion has been tested; text notes and web content have not been implemented.
* No frontend/canvas rendering exists yet — everything validated so far is backend-only.
* The LLM synthesis feature and question-grounded highlighting feature have not been started. Per-chunk embeddings are now retained in memory (not persisted to disk) as a prerequisite.
* The cluster home position uses a SHA-256 hash of the UUID. A real minimum angular gap of 0.597 degrees across 20 UUIDs was verified. Sub-1-degree collisions are possible at higher cluster counts, so minimum-gap enforcement (nudging a new angle away from existing ones if it lands too close) is a reasonable future improvement.
* The manual correction/constraint-storage feature has not been started. This is the core differentiator and the next thing to build.
* `constraint_satisfaction_rate` and `num_constraints_*` are explicitly `null` in the API response until constraint storage is implemented — previously they were fake `1.0`.

## 5. File/Module Map
* `backend/embeddings/pipeline.py` — core embedding logic; `embed_document_chunks()` for multi-chunk mean-pooling
* `backend/clustering/pipeline.py` — core clustering logic; canonical `BOUNDARY_MARGIN`; `compute_evaluation()`
* `backend/layout/physics.py` — core force-directed layout engine; `compute_home_positions()`
* `backend/tests/spike_layout.py` — layout validation wrapper (standalone, synthetic data, uses `compute_home_positions()`)
* `backend/tests/spike_clustering.py` — clustering validation wrapper (real PDF data, uses `compute_evaluation()`)
* `backend/api/pipeline.py` — integration pipeline; `run_pipeline()` is single-pass; `main()` is the Phase 1/Phase 2 CLI stress-test
* `backend/api/main.py` — FastAPI app; `/api/organize` returns `{"nodes": [...], "evaluation": {...}, "skipped_documents": [...]}`
* `backend/api/cluster_mapping.json` — persistent stable-ID state (gitignored; pruned on each run)
* `pyproject.toml` — package setup for editable install (`pip install -e .`)
* `.agent/skills/` — the three skill files defining technical contracts for embeddings, clustering, and layout
* `data/sample_docs/` — test corpus containing 21 real PDFs (`paper1.pdf` through `paper21.pdf`), covering Neural Networks, Distributed Systems, Networking/Security, and Compilers.

## 6. Recommended Next Steps
1. **Manual Correction/Constraint-Storage:** Build the ability for a user to drag a document to fix a mistake, and persist that constraint across runs. This is the core differentiator of Parallax and the most important thing to build next.
2. **Frontend Rendering (Canvas UI):** Visualize the pipeline's output. The `/api/organize` endpoint now returns stable, well-formed positions with evaluation metrics.
3. **LLM Synthesis Feature:** Add cross-cluster semantic comparisons.
4. **Question-Grounded Highlighting:** Allow the user to ask a question and highlight relevant documents on the canvas. Per-chunk embeddings are now retained in memory as a prerequisite for this feature.
5. **Phase 2 convergence tuning:** Investigate whether `MAX_ITERATIONS` should be higher for the demo stress-test path, or whether the force parameters need rebalancing when many anchored nodes shift cluster assignments simultaneously.
