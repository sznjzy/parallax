# PARALLAX PROGRESS

This file records the actual implementation state of the Parallax repository.

## Current Phase

Phase 1 — Fix Core Clustering + Constraint Architecture

## Status

READY FOR APPROVAL

## Completed Phases

- **Phase 0 — Existing System Audit**: Audited repository structure, backend pipeline, frontend components, physics simulation, constraint mechanism, and existing test suites.

## Current Phase Notes

Phase 0 audit confirmed that constrained documents are currently processed by HDBSCAN alongside unconstrained documents, with cluster IDs overridden post-hoc in `_map_to_nodes()`. Phase 1 will implement genuine separation of constrained documents prior to unconstrained clustering according to ADR-001.

## Phase History

| Phase | Status | Commit | Notes |
|---|---|---|---|
| 0 | COMPLETE | db92c38 | Existing system audit: verified architecture, baseline execution, and identified constraint handling discrepancy |
| 1 | NOT STARTED | — | Fix core clustering + constraint architecture |
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

1. Constrained documents are included in HDBSCAN density calculation before post-hoc re-labeling in `backend/api/pipeline.py` (to be resolved in Phase 1).

## Rules

- Do not mark a phase complete without implementation, testing, state updates, and a git commit.
- Do not infer completion from the master plan.
- This file must reflect repository reality.
