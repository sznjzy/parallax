# PARALLAX PROGRESS

This file records the actual implementation state of the Parallax repository.

## Current Phase

Phase 2 — Stable Cluster Identity + Layout Correctness

## Status

READY FOR APPROVAL

## Completed Phases

- **Phase 0 — Existing System Audit**: Audited repository structure, backend pipeline, frontend components, physics simulation, constraint mechanism, and existing test suites.
- **Phase 1 — Fix Core Clustering + Constraint Architecture**: Implemented true constraint-aware clustering (ADR-001) in `backend/clustering/pipeline.py` via `run_constraint_aware_clustering()`. Constrained documents are separated prior to HDBSCAN, forced cluster IDs merged, global cluster centroids computed, boundary flags derived, and evaluation contracts computed.

## Current Phase Notes

Phase 1 established genuine separation of constrained documents before unconstrained clustering. Phase 2 will focus on stable cluster UUID continuity, deterministic cluster home positions, and spatial stability across incremental additions.

## Phase History

| Phase | Status | Commit | Notes |
|---|---|---|---|
| 0 | COMPLETE | 26e25d0 | Existing system audit: verified architecture, baseline execution, and identified constraint handling discrepancy |
| 1 | COMPLETE | e5f972d | True constraint-aware clustering: separate constrained docs before HDBSCAN, global centroid merging, unit test suite |
| 2 | NOT STARTED | — | Stable cluster identity and layout |
| 3 | NOT STARTED | — | Testing and evaluation foundation |
| 4 | NOT STARTED | — | PDF ingestion and caching |
| 5 | NOT STARTED | — | Cluster topic modeling |
| 6 | NOT STARTED | — | Semantic search and canvas heatmap |
| 7 | NOT STARTED | — | Cluster lifecycle management |
| 8 | NOT STARTED | — | Citation network |
| 9 | NOT STARTED | — | Semantic frontier / candidate gap radar |
| 10 | NOT STARTED | — | Idea Ghost Node |
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
