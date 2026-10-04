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

## ADR-006 — Grounded Evidence Inspection (Explainability without Generative AI)

Status: ACCEPTED (SUPERSEDES IDEA GHOST NODE & STANDALONE EXPLORER)

To maximize scientific rigor, defensibility, and viva explainability, Parallax exposes grounded evidence directly through lightweight frontend UI inspection rather than a complex standalone subsystem or generative AI explanations.

Architectural guarantees:
1. **Evidence-Grounded**: Explanations for cluster membership, topic relationships, and similarity rankings are computed purely from measurable signals (cosine similarity, representative keywords, centroid distance, c-TF-IDF topic overlap).
2. **Non-Mutating**: Inspecting evidence behind a paper or cluster does not alter clustering, state, or layout.
3. **Zero Fabrication**: The system never fabricates or invents unsupported explanations.
4. **No LLM Dependency**: Evidence and metrics are computed deterministically without external LLM dependencies.

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

## ADR-009 — Project Scope Reduction

Status: ACCEPTED

Parallax prioritizes depth, correctness, evaluation, and usability over adding a large number of speculative features.

Removed from the active implementation roadmap:
- Citation Network
- Research Frontier / Candidate Gap Radar
- Standalone Research Evidence Explorer subsystem

Rationale:
- Reduces feature bloat and unnecessary architectural complexity
- Eliminates unsupported scientific claims regarding automated "gap discovery"
- Avoids complex PDF citation parsing heuristics and unvalidated citation evaluation
- Retains lightweight evidence inspection in the frontend using existing measurable signals
- Simplifies testing and evaluation methodologies
- Improves academic defensibility, maintainability, and reliability of the core synthesis engine

## ADR-010 — Zero-LLM Architecture

Status: ACCEPTED

The Parallax system contains no generative LLM dependency.

Parallax functionality remains strictly based on:
- Semantic embeddings (`sentence-transformers/all-mpnet-base-v2` for dense vector representations)
- Exact cosine similarity metrics
- HDBSCAN / KMeans constraint-aware clustering
- Class-based TF-IDF (c-TF-IDF) and KeyBERT centroid-aligned topic extraction
- Extracted document text and structured metadata
- Deterministic 2D force-directed physics layout
- Measurable relationships and deterministic algorithms

No generative LLMs (OpenAI, Anthropic, Gemini, Ollama, local or hosted generative models, or LLM fallbacks/modes) are required or permitted for the system to function.

## ADR-011 — 3-Zone Minimalist Frontend Architecture & Contextual Workspaces

Status: ACCEPTED

The Parallax user interface is structured into three dedicated, uncluttered visual zones inspired by scientific and productivity tools (Obsidian, Notion, Linear):

1. **Zone 1: Collapsible Navigation Rail (Left)**: Fixed 56px layout footprint expanding smoothly to a 220px overlay on hover (`cubic-bezier(0.22, 1, 0.36, 1)`). Houses primary destinations (Canvas `1`, Search `2`, Library `3`, Clusters `4`, Evaluation `5`, and modal Settings). Because the structural layout width is rigidly 56px, rail hover triggers zero canvas resizing or hit-buffer redraws, delivering a stable 60 FPS experience.
2. **Zone 2: Canvas Centerpiece (Center)**: Full-viewport interactive Konva stage with floating top CommandBar (debounced semantic search and status pill) and floating bottom CanvasDock (Run Analysis with loading spinner, Fit View, and Rerun Physics Layout). Document and cluster labels use theme-aware dynamic contrast with white backdrops in Light Mode and dark backdrops in Dark Mode.
3. **Zone 3: Contextual Inspector Drawer (Right)**: 360px sliding contextual workspace drawer hosting dedicated views (Search Matches, Document Library & Upload, Cluster Lifecycle Controls, Evaluation Metrics, and Document Inspector). Drawer transitions smoothly via slide/fade without blank flashing.
4. **Modals & PDF Viewer**: Modal Settings with instant theme switching, cache inspection, and architecture stats. In-app deep-linking PDF reader modal (`PdfViewerModal.jsx`) displaying source pages and matched snippet terms.

## Future Decisions

Add new ADRs below as major architectural decisions are made.


