# PARALLAX PROGRESS

This file records the actual implementation state of the Parallax repository.

## Current Phase

Phase 8 — Frontend Polish + Evidence Explanation

## Status

READY FOR APPROVAL

## Completed Phases

- **Phase 0 — Existing System Audit**: Audited repository structure, backend pipeline, frontend components, physics simulation, constraint mechanism, and existing test suites.
- **Phase 1 — Fix Core Clustering + Constraint Architecture**: Implemented true constraint-aware clustering (ADR-001) in `backend/clustering/pipeline.py` via `run_constraint_aware_clustering()`. Constrained documents are separated prior to HDBSCAN, forced cluster IDs merged, global cluster centroids computed, boundary flags derived, and evaluation contracts computed.
- **Phase 2 — Stable Cluster Identity + Layout Correctness**: Verified and hardened stable cluster UUID tracking across incremental updates with full state persistence, fixed circular shortest-arc angular relaxation in `compute_home_positions()`, and verified deterministic spatial anchoring and force-directed simulation stability.
- **Phase 3 — Testing + Evaluation Foundation**: Established synthetic corpora generators (`backend/tests/fixtures/synthetic_corpora.py`), comprehensive automated test suites for clustering quality, constraint impact, spatial stability, and API endpoints, and replaced legacy scratch test runners with a unified test discovery runner `run_all_tests.py` (28/28 unit tests passing).
- **Phase 4 — PDF Ingestion + Caching Hardening**: Implemented robust PDF validation (magic byte `%PDF-` checks, size limits, filename sanitization/traversal defense), content-hash SHA-256 deduplication, automatic text chunking and immediate `.npy` disk caching in `backend/ingestion/ingest.py`, `POST /api/documents/upload` and `DELETE /api/documents/{filename}` endpoints, and connected UI file upload controls in `EvaluationPanel.jsx` (35/35 unit tests passing).
- **Phase 5 — Automatic Cluster Topic Modeling**: Implemented Class-based TF-IDF (c-TF-IDF) in `backend/topics/topic_modeling.py` with optional KeyBERT semantic centroid alignment, academic stopword filtering, dynamic topic updating across constraint/corpus changes, text disk caching (`<hash>.txt`), and UI topic labels in `ClusterRegion.jsx` and `EvaluationPanel.jsx` (47/47 unit tests passing).
- **Phase 6 — Semantic Search + Canvas Heatmap**: Implemented zero-LLM semantic search engine (`backend/search/semantic_search.py`) utilizing cached 768-dim embeddings (`all-mpnet-base-v2`) and exact cosine similarity, exposed `POST /api/search` with cluster association and aggregated cluster relevance, and added an interactive topbar SearchBar, canvas heatmap glowing halos/badges (`DocumentNode.jsx`), cluster relevance highlights (`ClusterRegion.jsx`), and ranked match sidebar (`EvaluationPanel.jsx`) (55/55 unit tests passing).
- **Phase 7 — Interactive Cluster Lifecycle**: Implemented interactive cluster lifecycle management (`backend/clustering/lifecycle.py`) with persistent custom topic title overrides (`PUT /api/clusters/{cluster_id}/topic`), cluster merging with document reassignment, constraint recording, and mapping cleanup (`POST /api/clusters/merge`), and cluster splitting using semantic embeddings with stable primary UUID lineage preservation (`POST /api/clusters/{cluster_id}/split`). Connected frontend lifecycle controls in `EvaluationPanel.jsx` via `useClusterLifecycle.js` (67/67 unit tests passing).

## Current Phase Notes

Phase 7 delivered complete interactive cluster lifecycle management (Rename, Merge, Split) with stable UUID lineage, persistent constraint synchronisation, and frontend UI controls. All 67 automated tests pass with 0 failures. The roadmap was scoped down to eliminate citation extraction, speculative gap radar, and standalone explorer subsystems. Phase 8 will focus on frontend polish and exposing existing measurable evidence in the UI.

## Phase History

| Phase | Status | Commit | Notes |
|---|---|---|---|
| 0 | COMPLETE | 26e25d0 | Existing system audit: verified architecture, baseline execution, and identified constraint handling discrepancy |
| 1 | COMPLETE | 37cf1ba | True constraint-aware clustering: separate constrained docs before HDBSCAN, global centroid merging, unit test suite |
| 2 | COMPLETE | 147da2d | Stable cluster identity and layout: UUID overlap lineage, pairwise circular relaxation, anchor damping |
| 3 | COMPLETE | 22d8384 | Testing and evaluation foundation: synthetic corpora fixtures, modular test suites (quality, constraints, physics, API), unified runner |
| 4 | COMPLETE | 56147f5 | PDF upload & ingestion hardening: magic bytes validation, deduplication, disk caching, upload/delete API & UI |
| 5 | COMPLETE | 23c987e | Automatic cluster topic modeling: c-TF-IDF, KeyBERT semantic centroid alignment, text disk cache, UI integration |
| 6 | COMPLETE | 6737909 | Semantic search engine, POST /api/search, canvas glowing halo heatmap, relevance sidebar |
| 7 | COMPLETE | c3e8170 | Interactive cluster lifecycle management (Rename, Merge, Split), REST endpoints, and UI integration |
| 8 | NOT STARTED | — | Frontend Polish + Evidence Explanation |
| 9 | NOT STARTED | — | Performance + Reliability |
| 10 | NOT STARTED | — | Complete Evaluation |
| 11 | NOT STARTED | — | Documentation |
| 12 | NOT STARTED | — | Security + Robustness |
| 13 | NOT STARTED | — | Final Regression |

## Open Issues

None currently active for completed phases.

## Rules

- Do not mark a phase complete without implementation, testing, state updates, and a git commit.
- Do not infer completion from the master plan.
- This file must reflect repository reality.
