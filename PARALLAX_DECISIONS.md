# PARALLAX ARCHITECTURAL DECISIONS

Record important architectural decisions here so future sessions do not repeatedly reconsider settled choices.

## ADR-001 — Constraint-Aware Clustering

Status: ACCEPTED

Constrained documents must be separated before unconstrained clustering.

Target flow:

All documents
→ constraint processing
→ constrained documents + unconstrained documents
→ HDBSCAN on unconstrained documents
→ merge constrained assignments with discovered clusters
→ final clusters
→ layout

Do not run HDBSCAN over every document and merely overwrite constrained labels afterward.

## ADR-002 — Primary Clustering Method

Status: ACCEPTED

HDBSCAN remains the primary unconstrained clustering algorithm.

KMeans may remain as a fallback or evaluation baseline where appropriate.

## ADR-003 — Stable Cluster Identity

Status: ACCEPTED

Clusters should have stable IDs that survive incremental additions when continuity can be established.

## ADR-004 — Deterministic Spatial Anchoring

Status: ACCEPTED

Cluster home positions should be deterministic from stable cluster identity where appropriate, so incremental updates do not randomly reshuffle the canvas.

## ADR-005 — Research Gap Terminology

Status: ACCEPTED

The system must use language such as:

- candidate semantic frontier
- candidate research gap
- candidate gap requiring human validation

It must not claim to objectively discover the true research gap.

## ADR-006 — Idea Ghost Node

Status: ACCEPTED

The Idea Ghost Node is non-mutating. Embedding a user idea must not automatically add it to the corpus or mutate clustering.

## Future Decisions

Add new ADRs below as major architectural decisions are made.
