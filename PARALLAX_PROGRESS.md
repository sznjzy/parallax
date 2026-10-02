# PARALLAX PROGRESS

This file records the actual implementation state of the Parallax repository.

## Current Phase

Phase 6 — Semantic Search + Canvas Heatmap

## Status

READY FOR APPROVAL

## Completed Phases

- **Phase 0 — Existing System Audit**: Audited repository structure, backend pipeline, frontend components, physics simulation, constraint mechanism, and existing test suites.
- **Phase 1 — Fix Core Clustering + Constraint Architecture**: Implemented true constraint-aware clustering (ADR-001) in `backend/clustering/pipeline.py` via `run_constraint_aware_clustering()`. Constrained documents are separated prior to HDBSCAN, forced cluster IDs merged, global cluster centroids computed, boundary flags derived, and evaluation contracts computed.
- **Phase 2 — Stable Cluster Identity + Layout Correctness**: Verified and hardened stable cluster UUID tracking across incremental updates with full state persistence, fixed circular shortest-arc angular relaxation in `compute_home_positions()`, and verified deterministic spatial anchoring and force-directed simulation stability.
- **Phase 3 — Testing + Evaluation Foundation**: Established synthetic corpora generators (`backend/tests/fixtures/synthetic_corpora.py`), comprehensive automated test suites for clustering quality, constraint impact, spatial stability, and API endpoints, and replaced legacy scratch test runners with a unified test discovery runner `run_all_tests.py` (28/28 unit tests passing).
- **Phase 4 — PDF Ingestion + Caching Hardening**: Implemented robust PDF validation (magic byte `%PDF-` checks, size limits, filename sanitization/traversal defense), content-hash SHA-256 deduplication, automatic text chunking and immediate `.npy` disk caching in `backend/ingestion/ingest.py`, `POST /api/documents/upload` and `DELETE /api/documents/{filename}` endpoints, and connected UI file upload controls in `EvaluationPanel.jsx` (35/35 unit tests passing).
- **Phase 5 — Automatic Cluster Topic Modeling**: Implemented Class-based TF-IDF (c-TF-IDF) in `backend/topics/topic_modeling.py` with optional KeyBERT semantic centroid alignment, academic stopword filtering, dynamic topic updating across constraint/corpus changes, text disk caching (`<hash>.txt`), and UI topic labels in `ClusterRegion.jsx` and `EvaluationPanel.jsx` (47/47 unit tests passing).

## Current Phase Notes

Phase 5 implemented automatic topic modeling via c-TF-IDF and KeyBERT keyword extraction without LLM dependencies. All 47 automated tests pass. Phase 6 will implement semantic search and canvas heatmap highlighting.

## Phase History

| Phase | Status | Commit | Notes |
|---|---|---|---|
| 0 | COMPLETE | 26e25d0 | Existing system audit: verified architecture, baseline execution, and identified constraint handling discrepancy |
| 1 | COMPLETE | 37cf1ba | True constraint-aware clustering: separate constrained docs before HDBSCAN, global centroid merging, unit test suite |
| 2 | COMPLETE | 147da2d | Stable cluster identity and layout: UUID overlap lineage, pairwise circular relaxation, anchor damping |
| 3 | COMPLETE | 22d8384 | Testing and evaluation foundation: synthetic corpora fixtures, modular test suites (quality, constraints, physics, API), unified runner |
| 4 | COMPLETE | 56147f5 | PDF upload & ingestion hardening: magic bytes validation, deduplication, disk caching, upload/delete API & UI |
| 5 | COMPLETE | 23c987e | Automatic cluster topic modeling: c-TF-IDF, KeyBERT semantic centroid alignment, text disk cache, UI integration |
| 6 | NOT STARTED | — | Semantic search and canvas heatmap |
| 7 | NOT STARTED | — | Cluster lifecycle management |
| 8 | NOT STARTED | — | Citation network |
| 9 | NOT STARTED | — | Semantic frontier / candidate gap radar |
| 10 | NOT STARTED | — | Deterministic zero-LLM Research Evidence Explorer (ADR-006, ADR-009) |
| 11 | NOT STARTED | — | Frontend polish |
| 12 | NOT STARTED | — | Performance and caching |
| 13 | NOT STARTED | — | Complete evaluation |
| 14 | NOT STARTED | — | Documentation |
| 15 | NOT STARTED | — | Security and robustness |
| 16 | NOT STARTED | — | Final regression |

## Open Issues

None currently active for completed phases.

## Rules

- Do not mark a phase complete without implementation, testing, state updates, and a git commit.
- Do not infer completion from the master plan.
- This file must reflect repository reality.
