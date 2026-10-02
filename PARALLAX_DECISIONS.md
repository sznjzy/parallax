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

## ADR-007 — Outlier and Noise Document Spatial Isolation

Status: ACCEPTED

Outlier / noise documents (`noise-*`) must retain their semantic noise classification and must not visually or spatially appear inside any cluster's visual region / expanded convex hull.

Architectural guarantees:
1. **Gap Bisector Anchoring**: Outlier home positions are deterministically assigned to the angular gap bisectors (voids) between adjacent real clusters on the outer periphery ($r = \min(W, H) \times 0.46$).
2. **Mutual Repulsion**: Noise nodes experience strong mutual repulsion ($k=8000$) away from all real cluster members, and real cluster members avoid engulfing noise nodes.
3. **Gravity Exclusion**: Non-noise cluster members receive inward center gravity ($k=0.01$), whereas noise nodes are strictly excluded from center gravity to maintain peripheral placement.
4. **Geometric Hull Clearance Post-Condition**: `ensure_outlier_hull_isolation()` geometrically tests noise coordinates against all expanded cluster hulls ($P=24.0\text{px}$) and radially/tangentially displaces any enclosed node outside the visual hull boundary by a safety margin ($\ge 14.0\text{px}$).

## ADR-008 — Automatic Cluster Topic Modeling (c-TF-IDF + KeyBERT)

Status: ACCEPTED

Cluster topic labels, representative keywords, and topic metadata must be derived purely from the actual textual contents of documents assigned to each cluster, without external LLM dependencies or hardcoded labels.

Architectural guarantees:
1. **Class-based TF-IDF (c-TF-IDF)**: Aggregates text per cluster and evaluates term uniqueness:
   $$W_{c, t} = tf_{c, t} \times \log\left(1 + \frac{A}{f_t}\right)$$
   where $A$ is average words per cluster and $f_t$ is total term frequency across all clusters.
2. **KeyBERT Semantic Alignment**: Candidate keywords are optionally re-ranked against the normalized cluster embedding centroid using cosine similarity (60% semantic similarity + 40% c-TF-IDF uniqueness) using the existing sentence-transformers embedding model.
3. **Dynamic Topic Reactivity**: Topics and representative keywords automatically recalculate whenever cluster membership changes (incremental PDF additions or manual drag-and-drop constraints).
4. **Outlier Noise Preservation**: Noise documents (`noise-*`) receive dedicated outlier metadata (`Outlier (<filename>)`) and are never conflated with real semantic topics.

## Future Decisions

Add new ADRs below as major architectural decisions are made.

