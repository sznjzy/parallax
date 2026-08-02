# Parallax Project Progress

## 1. Project Summary
Parallax is a persistent semantic research canvas designed to organize research documents spatially by meaning. The core technical claim being validated is that the system provides a persistent, stable semantic organization that survives incremental updates and corrections—meaning documents organically cluster into topics that gracefully accommodate new papers without capriciously rearranging the entire layout, unlike a one-shot regenerated summary.

## 2. Architecture Overview
The backend pipeline consists of three core components:

* **Embedding Pipeline:** Extracts text from PDFs and embeds them using `sentence-transformers/all-mpnet-base-v2` into semantic vectors. Contract defined in `.agent/skills/embedding-pipeline/SKILL.md`.
* **Constrained Clustering:** Uses HDBSCAN with cosine distance to dynamically group the embedded vectors into topics, identifying boundary documents (cross-disciplinary papers) and assigning stable UUIDs. Contract defined in `.agent/skills/constrained-clustering/SKILL.md`.
* **Incremental Layout Engine:** Uses a continuous force-directed physics simulation (attraction/repulsion forces, cluster gravity, and velocity damping) to render these clusters on a 2D canvas, keeping clusters distinct while respecting boundary document weights. Contract defined in `.agent/skills/incremental-layout/SKILL.md`.

**Data Flow:** PDF → text → embedding → clustering → stable ID assignment → layout → rendered positions.

## 3. What Has Been Validated

### a) Spike B — Layout Stability
**What was tested:** The stability and convergence of the force-directed physics engine in isolation (using synthetic, separate test setups).
* **The original bug & fix:** The initial attempt at Phase 2 incremental updates used a hard displacement cap for anchoring existing nodes, which caused linear drift across the canvas. This was fixed by using velocity damping (`ANCHOR_VELOCITY_DAMPING = 0.05`) instead, which smoothly bleeds kinetic energy while allowing tension to resolve.
* **The Phase 1 convergence bug & fix:** Clusters were initially collapsing into each other because boundary nodes created dynamic centroid coupling (pulling cluster centroids together). This was fixed by calculating static `CLUSTER_CENTRES` and anchoring nodes to fixed home positions instead of dynamic centroids.
* **Final validated numbers:** 
  * Phase 1 (Initial Layout): Converged cleanly in 85/2000 iterations with pairwise separations of A-B: 114.5, B-C: 124.4, and A-C: 191.1 units.
  * Phase 2 (Incremental Update): Converged in 73/200 iterations, with an average existing-node displacement of just ~0.076 units.
* **Boundary node validation:** The engine correctly positioned boundary documents between their affiliated clusters weighted by their secondary cluster similarity, exactly matching the predicted position rather than snapping to a single center.

### b) Spike A — Clustering Quality
**What was tested:** The ability of the embedding and clustering logic to produce accurate, distinct semantic topics on real research papers.
* **Test Corpus:** A 15-document baseline (papers 1-15) cleanly separated into 3 known ground-truth topics (5x Neural Networks, 5x Distributed Systems, 5x Networking/Security).
* **Results:** The pipeline achieved perfect contiguous topic separation with a silhouette score of `0.398`. All evaluation contract fields were cleanly populated.
* **Boundary-document detection:** `paper16.pdf` (Kitsune, an ML+security bridging paper) was introduced. It scored `0.45` similarity to one cluster and `0.20` to the other. Because the gap (0.25) was wider than the `MARGIN=0.05` threshold, it was correctly NOT flagged as a boundary document. This was a deliberate decision: the paper showed a real secondary relationship, but was not genuinely ambiguous enough to warrant multi-membership layout handling.

### c) Pipeline Integration — Real End-to-End Test
**What was tested:** Chaining Spike A and Spike B together into a unified pipeline with Phase 1 and Phase 2 incremental updates on real PDFs.
* **The stable cluster ID bug:** HDBSCAN arbitrarily numbers clusters each run. This meant the same semantic cluster (e.g., papers 11/12/13) was labeled `cluster-2` in Phase 1 and `cluster-1` in Phase 2, breaking layout continuity. This was anticipated by the clustering skill contract but not initially enforced in code.
* **The fix:** Implemented an overlap-based UUID matching function (`assign_stable_cluster_ids`) persisted via a local JSON file (`backend/api/cluster_mapping.json`).
* **The stress test:** We deliberately held back a set of compiler papers for Phase 2, except for `paper20` (Reinforcement Learning for Register Allocation). In Phase 1, `paper20` clustered with the core ML papers. In Phase 2, the new compiler papers pulled `paper20` out to form a new ML/Compiler cluster.
* **Results:** The old ML cluster retained 5 out of 6 original documents (83% overlap). The new ML/Compiler cluster had 2 documents, meaning it shared 1 document with the old ML cluster (50% overlap). Thanks to greedy sorting-by-strength, the old ML cluster cleanly claimed the UUID (at 83%), and the new cluster minted a new UUID, successfully avoiding a false merge.
* **Safety Guarantee:** "The pipeline guarantees no clusters will merge with less than 50% relative document overlap, and in cases where a boundary document causes multiple clusters to meet this threshold, it guarantees the UUID is awarded to the strongest successor."
* **Limitation:** A single-candidate case at exactly the 50% threshold with no competing stronger match would still merge. This has not been separately stress-tested.

## 4. Known Limitations / Honest Gaps
* The overlap-matching threshold (50%) was chosen reasonably but is not exhaustively empirically validated across many scenarios—only the specific cases described above.
* The JSON persistence file (`backend/api/cluster_mapping.json`) grows unboundedly. No pruning mechanism exists yet for documents/clusters removed from the corpus.
* Only PDF ingestion has been tested; text notes and web content (mentioned in the original project scope) have not been implemented or tested yet.
* No frontend/canvas rendering exists yet—everything validated so far is backend-only, tested via printed terminal output.
* The LLM synthesis feature (cross-cluster comparison) and question-grounded highlighting feature have not been started.
* The manual correction/constraint-storage feature (user drags a document, system remembers it) has not been started. This is a core differentiator from the original pitch and is still pending.
* **Technical Debt:** The current implementation's clustering and layout logic still physically lives inside `backend/tests/spike_clustering.py` and `backend/tests/spike_layout.py`, which are reused directly by `pipeline.py`. It has not yet been refactored into the proper `backend/embeddings/` and `backend/clustering/` module structure that was originally scaffolded. This must happen before frontend work starts so the frontend integrates against a stable API/module boundary rather than importing from test files.

## 5. File/Module Map
* `backend/tests/spike_layout.py` — layout validation spike (standalone, synthetic data)
* `backend/tests/spike_clustering.py` — clustering validation spike (real PDF data)
* `backend/api/pipeline.py` — integration pipeline chaining both together on real data
* `backend/api/cluster_mapping.json` — persistent stable-ID state (gitignored)
* `.agent/skills/` — the three skill files defining technical contracts for embeddings, clustering, and layout
* `data/sample_docs/` — test corpus containing 21 real PDFs (`paper1.pdf` through `paper21.pdf`), covering Neural Networks, Distributed Systems, Networking/Security, and Compilers.

## 6. Recommended Next Steps
1. **Frontend Rendering (Canvas UI):** We need to visualize the pipeline's output. Proving that the documents spatially organize in a visually intuitive way for a real user is critical before adding complex interactive features.
2. **Manual Correction/Constraint-Storage:** Build the ability for a user to drag a document to fix a mistake, and persist that constraint across runs. This is the core differentiator of Parallax.
3. **LLM Synthesis Feature:** Add cross-cluster semantic comparisons.
4. **Question-Grounded Highlighting:** Allow the user to ask a question and highlight relevant documents on the canvas.
