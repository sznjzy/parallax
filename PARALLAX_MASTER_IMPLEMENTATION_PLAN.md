# PARALLAX MASTER IMPLEMENTATION PLAN

## Mission

Turn the existing Parallax prototype into a robust, explainable, research-oriented AI research synthesis system.

Do not blindly rewrite the existing project. Preserve useful architecture and improve it incrementally.

## Global Requirements

- No fake functionality.
- No fabricated metrics or evaluation results.
- No unnecessary infrastructure.
- Preserve deterministic behavior where appropriate.
- Maintain explainability for viva.
- Add tests for meaningful functionality.
- Keep documentation synchronized.
- One git commit per completed phase.
- Execute one phase at a time.
- Stop for explicit approval before the next phase.

---

# Phase 0 — Existing System Audit

Audit:

- repository structure
- backend
- frontend
- ingestion
- chunking
- embeddings
- clustering
- constraints
- stable IDs
- layout
- APIs
- persistence
- evaluation
- tests
- documentation

Identify discrepancies between intended and actual behavior.

Special attention: verify whether constrained documents are genuinely excluded from unconstrained clustering or merely relabeled after HDBSCAN.

Deliverable: verified baseline and updated persistent state files.

---

# Phase 1 — Fix Core Clustering + Constraint Architecture

Implement true constraint-aware clustering.

Required flow:

All documents
→ constraint processing
→ constrained documents + unconstrained documents
→ HDBSCAN only on unconstrained documents
→ merge constrained assignments with discovered clusters
→ final clusters
→ layout

Handle:

- zero constrained docs
- one constrained doc
- many constrained docs
- all docs constrained
- noise
- tiny corpora
- invalid/conflicting constraints
- constraint removal
- incremental updates

Add focused tests proving actual behavior.

Do not simply overwrite HDBSCAN labels after clustering.

---

# Phase 2 — Stable Cluster Identity + Layout Correctness

Ensure:

- stable cluster UUIDs
- deterministic cluster home positions
- continuity during incremental additions
- stable layout where possible
- correct handling of cluster creation/disappearance
- no unnecessary random reshuffling

Preserve current force-directed design unless profiling or correctness requires change.

---

# Phase 3 — Testing + Evaluation Foundation

Establish a proper automated testing foundation.

Separate:

- constraint satisfaction
- unconstrained clustering quality
- constraint impact
- spatial stability
- incremental behavior

Remove or isolate stale scratch tests.

Create reusable evaluation fixtures/datasets where appropriate.

---

# Phase 4 — PDF Upload + Live Ingestion + Embedding Caching

Add robust PDF ingestion.

Target endpoint:

`POST /api/documents/upload`

Requirements:

- safe file validation
- extraction
- chunking
- ingestion
- duplicate handling
- embedding caching
- graceful errors
- incremental updates

Do not recompute embeddings unnecessarily.

---

# Phase 5 — Automatic Cluster Topic Modeling

Generate cluster topics automatically.

Preferred approach:

c-TF-IDF

Optional supporting method:

KeyBERT

Provide:

- cluster title/topic
- representative keywords
- topic metadata

Do not add an LLM dependency merely for labels unless justified.

Topics must update when cluster contents change.

---

# Phase 6 — Semantic Search + Canvas Heatmap

Add semantic search using the same embedding model.

Target:

`POST /api/search`

Flow:

query
→ embedding
→ cosine similarity
→ ranked documents
→ cluster association
→ canvas highlighting

Frontend should provide visual glow/heatmap/highlight behavior.

Search must not mutate the corpus.

---

# Phase 7 — Interactive Cluster Lifecycle

Implement:

### Rename

`PUT /api/clusters/{cluster_id}/topic`

### Merge

`POST /api/clusters/merge`

### Split

`POST /api/clusters/{cluster_id}/split`

Requirements:

- stable identity
- persistence
- validation
- frontend synchronization
- correct topic updates
- safe handling of invalid operations

Do not destroy identity/history unnecessarily.

---

# Phase 8 — Citation Network Overlay

Extract and represent citation relationships when citations can be reasonably matched within the corpus.

Provide:

- citation edges
- citation counts where valid
- overlay/toggle
- useful visualization

Do not claim perfect citation extraction.

Do not invent relationships.

---

# Phase 9 — Cross-Disciplinary Frontier / Candidate Gap Radar

Identify candidate semantic frontiers using signals such as:

- semantically distant clusters
- weakly connected areas
- cross-cluster similarity
- topic overlap/distance
- citation structure where reliable

Output should be framed as:

"candidate semantic frontier"

or

"candidate research gap requiring human validation"

Never claim objective discovery of the true research gap.

Provide an interpretable radar/visualization.

---

# Phase 10 — Research Evidence Explorer

Phase 10 is a deterministic, zero-LLM evidence exploration layer.

The goal is to make Parallax explainable, rigorous, and academically useful by allowing users to select a paper, cluster, or candidate research frontier and inspect the underlying evidence behind it.

> Every explanation shown by the Research Evidence Explorer must be traceable to an underlying measurable signal in the Parallax data model. The system should prefer transparent metrics, rankings, keywords, relationships, and source references over generated prose.

### Non-Negotiable Requirement: Zero LLM Dependency

The Research Evidence Explorer must function completely without:
- OpenAI
- Anthropic
- Gemini
- Ollama
- any local LLM
- any hosted LLM API
- any generative AI model
- any LLM-generated explanation
- any LLM-generated topic interpretation

Phase 10 must be entirely deterministic/evidence-based using data and models already required by the existing Parallax architecture. The feature must work with network access disabled, except where the application genuinely needs network access for existing non-LLM functionality.

There is NO hidden LLM fallback (do NOT implement "LLM optional", "LLM fallback", "use LLM if available", "AI explanation mode", environment variables for an LLM, API keys for an LLM, or model-provider abstractions for Phase 10). If a future feature wants natural-language summarization, that must be treated as a separate future feature and must not become part of Phase 10.

### Evidence Signals

Evidence must come directly from measurable signals such as:
- embedding cosine similarity
- document-to-cluster similarity
- distance to cluster centroid/representation
- cluster membership
- cluster size
- representative documents
- representative keywords
- c-TF-IDF scores
- topic overlap
- citation edges
- citation counts
- semantic similarity between clusters
- document ranking
- existing cluster metadata
- existing document metadata
- existing layout/position information where meaningful

The UI should present these signals directly and transparently (e.g., Paper X → Cluster Y showing cluster membership, cosine similarity to cluster representation, top shared terms, nearest documents, citation connections, related clusters, topic overlap). The system explains relationships through these measurable signals rather than generating natural-language claims with an LLM.

### Key Capabilities & Requirements

- **Why a paper belongs to its cluster**: Direct document-to-centroid cosine similarity, top shared terms (c-TF-IDF), membership metrics.
- **Representative papers/documents for the cluster**: Top-ranked papers closest to cluster centroid.
- **Representative keywords/topics**: Top c-TF-IDF / KeyBERT keywords and scores.
- **Closest semantically related papers**: k-nearest neighbors ranked by embedding cosine similarity.
- **More distant papers or clusters**: Ranked distance metrics across the corpus.
- **Related clusters & topic overlap**: Inter-cluster centroid cosine similarity and shared term overlap.
- **Citation relationships**: Direct citation edges, citation counts, and referenced papers where available.
- **Non-Mutating**: Inspecting evidence must NOT automatically mutate the corpus, clustering, or layout.
- **Seamless UX**: Integrates transparently with the existing Parallax canvas, document sidebar, and PDF viewer.

---

# Phase 11 — Frontend Polish + UX

Polish:

- navigation
- controls
- loading states
- errors
- tooltips
- cluster labels
- search UI
- topic UI
- citation overlay
- frontier radar
- evidence explorer
- PDF viewer
- constraint interactions
- accessibility where practical

Avoid unnecessary frontend rewrites.

---

# Phase 12 — Performance + Caching

Profile before optimizing.

Focus on:

- embedding caching
- PDF caching
- incremental recomputation
- layout performance
- frontend rendering
- search latency
- large-corpus behavior

Do not replace O(n²) layout without evidence that it is a real bottleneck.

---

# Phase 13 — Complete Evaluation

Run real experiments.

Compare where meaningful:

- MPNet + HDBSCAN
- MPNet + KMeans
- MPNet + Agglomerative

Measure:

- silhouette
- Davies-Bouldin
- Calinski-Harabasz
- number of clusters
- noise percentage
- runtime

Also evaluate, where ground truth or appropriate fixtures exist:

- constraint satisfaction
- incremental stability
- search behavior
- citation extraction
- frontier behavior

Never fabricate values.

---

# Phase 14 — Documentation

Update:

- README
- architecture
- setup
- API documentation
- methodology
- evaluation
- limitations
- usage
- screenshots/examples where useful

Documentation must describe actual implemented behavior.

---

# Phase 15 — Security + Robustness Audit

Test:

- malformed PDFs
- oversized uploads
- invalid IDs
- invalid requests
- duplicate uploads
- empty documents
- corrupted cache
- unusual text
- filesystem safety
- API errors
- frontend failures

Fix meaningful vulnerabilities and robustness issues.

---

# Phase 16 — Final Regression

Run end-to-end regression over:

PDF upload
→ ingestion
→ chunking
→ embeddings
→ constraints
→ clustering
→ topics
→ layout
→ search
→ cluster lifecycle
→ citation overlay
→ frontier analysis
→ research evidence explorer
→ frontend

Verify no major regressions.

Create final implementation report covering:

- architecture
- bugs fixed
- features
- tests
- evaluation
- performance
- limitations
- viva-relevant technical explanations
- future work
