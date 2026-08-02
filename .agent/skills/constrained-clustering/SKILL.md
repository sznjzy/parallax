---
name: constrained-clustering
description: Use this skill whenever clustering documents in Parallax, handling user corrections (drag a document to a different cluster, merge two clusters), storing or applying must-link/cannot-link constraints, or evaluating clustering quality. Trigger on tasks involving "clustering", "recluster", "constraint", "user correction", "cluster quality", "silhouette score".
---

# Constrained Clustering Skill

## Purpose
Defines how Parallax groups documents by meaning while respecting the user's accumulated manual corrections, so clustering improves over time instead of resetting on every run.

## Core Rules

1. **Clustering algorithm.**
   - Default: HDBSCAN (handles variable cluster sizes/shapes and doesn't require pre-specifying cluster count — appropriate since the number of topics in a research corpus is unknown upfront).
   - Fallback for small/simple demo corpora where HDBSCAN under-clusters (labels everything noise): k-means with a heuristically chosen k (e.g., via elbow method or silhouette score sweep over k=2..8).
   - Never hardcode cluster count in production logic — always derive it or make it a tunable parameter, not a magic number.

2. **Constraint representation.**
   - Store user corrections as explicit pairs: `must_link: [(doc_id_a, doc_id_b)]` and `cannot_link: [(doc_id_a, doc_id_b)]`.
   - A manual "drag document out of cluster A" action generates a `cannot_link` constraint between that document and the centroid-nearest documents remaining in cluster A.
   - A manual "merge two clusters" action generates `must_link` constraints between the two cluster centroids' nearest representative documents (not all pairwise documents — that's O(n²) and unnecessary).
   - Constraints persist in a dedicated store (e.g., a JSON file or lightweight DB table) keyed by document ID pairs, independent of any single clustering run.

3. **Applying constraints on re-clustering.**
   - Use a constrained clustering approach (e.g., constrained k-means via `must_link`/`cannot_link` projection, or post-process HDBSCAN output by merging/splitting clusters to satisfy stored constraints before finalizing).
   - When constraints conflict with fresh embedding evidence (e.g., new documents pull a must-linked pair toward different natural clusters), prioritize explicit user constraints over raw embedding distance — the user's judgment is ground truth, the embedding is a heuristic.
   - Constraints should NOT silently expire — if a stored constraint can no longer be satisfied (e.g., referenced document was deleted), log this rather than failing silently.

4. **Incremental re-clustering.**
   - When new documents are added, do not necessarily recompute clusters for the entire corpus from scratch if avoidable — prefer assigning new documents to the nearest existing cluster (if within a similarity threshold) and only trigger a full re-cluster if new documents don't fit existing structure well (e.g., too many fall below the threshold, suggesting a new topic has emerged).

## Failure Modes to Avoid
- Treating every clustering run as independent — always load and apply stored constraints first.
- Applying must-link/cannot-link constraints as hard post-hoc overrides that ignore cluster cohesion entirely (can fragment otherwise sensible clusters) — balance constraint satisfaction against overall cluster quality, and report both metrics.
- Silently changing cluster IDs across runs — cluster identity should persist across incremental updates so the frontend doesn't lose track of "which cluster is which" (e.g., use stable cluster UUIDs, not array indices).

## Evaluation Contract
Every clustering run should report:
```json
{
  "silhouette_score": float,
  "num_clusters": int,
  "constraint_satisfaction_rate": float,
  "num_constraints_applied": int,
  "num_constraints_violated": int
}
```
This is used for the project's evaluation plan (clustering quality + constraint satisfaction metrics) — do not skip logging this on any clustering run, including demo runs.

## Output Contract
```json
{
  "doc_id": "string",
  "cluster_id": "string (stable UUID)",
  "cluster_confidence": float,
  "is_boundary_document": bool
}
```
`is_boundary_document` should be true when a document's similarity to its second-nearest cluster is within a small margin of its similarity to its assigned cluster — this flag drives the multi-membership visualization (documents rendered between clusters).