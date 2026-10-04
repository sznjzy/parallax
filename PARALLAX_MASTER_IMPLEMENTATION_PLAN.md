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

# Phase 8 — Frontend Polish + Evidence Explanation

The goal is to make the existing Parallax functionality feel like one coherent, polished research synthesis application.

Focus on improving:

### Existing search UX
- search result presentation
- search state
- PDF opening
- highlighted search matches
- result navigation
- canvas highlighting
- clear/reset behavior

### Existing cluster UX
- cluster selection
- cluster topic display
- rename/merge/split controls
- useful confirmation/error states
- cluster information presentation

### Existing document UX
When selecting a paper, show lightweight evidence already available in the system:
- cluster/topic
- outlier status
- similarity information
- representative keywords
- nearby/related documents
- source PDF
- available metadata

### Existing cluster evidence
When selecting a cluster, show:
- cluster name
- document count
- topic
- representative keywords
- representative documents
- existing similarity/relationship information

### General UX
- loading states
- empty states
- error handling
- tooltips
- consistent visual hierarchy
- navigation
- accessibility where practical
- responsive behavior where relevant
- canvas controls
- PDF viewer integration

IMPORTANT:
- Phase 8 should primarily improve and expose existing functionality.
- It should NOT create a new research-analysis subsystem.
- It should NOT require an LLM.
- It should NOT add speculative research capabilities.

---

# Phase 9 — Performance + Reliability

Keep this focused.

Evaluate:
- embedding caching
- ingestion caching
- unnecessary recomputation
- search latency
- clustering runtime
- layout runtime
- frontend rendering
- incremental updates

Profile before optimizing.

Do not introduce unnecessary infrastructure (no Redis, microservices, Kubernetes, queues, or distributed systems unless a measured problem genuinely requires them).

If the system performs adequately, document the measurements and move on.

---

# Phase 10 — Complete Evaluation

Focus on demonstrating that the system works rather than adding more features.

Evaluate where meaningful:

### Clustering
- HDBSCAN
- KMeans
- Agglomerative clustering

Metrics:
- Silhouette
- Davies-Bouldin
- Calinski-Harabasz
- number of clusters
- noise/outlier percentage
- runtime

### Constraints
Evaluate:
- constraint satisfaction
- effect of constraints
- clustering changes
- stability

### Incremental behavior
Evaluate:
- cluster identity preservation
- spatial stability
- document additions
- layout displacement

### Semantic search
Evaluate search behavior using a manually constructed/reasonable evaluation set if possible.

Do NOT fabricate ground truth.
Do NOT fabricate metrics.
Only report experiments that are actually performed.

---

# Phase 11 — Documentation

Update:
- README
- architecture documentation
- setup instructions
- API documentation
- methodology
- evaluation
- limitations
- usage
- screenshots/examples where appropriate

The documentation must describe what is actually implemented.

---

# Phase 12 — Security + Robustness

Keep this lightweight and practical.

Test:
- malformed PDFs
- oversized uploads
- invalid IDs
- malformed API requests
- duplicate files
- empty documents
- corrupted cache
- unusual text
- filesystem safety
- API errors
- frontend error states

Fix meaningful issues. Do not turn this into a separate security research project.

---

# Phase 13 — Final Regression

Perform final end-to-end validation:

PDF upload
→ ingestion
→ chunking
→ embeddings
→ constraint-aware clustering
→ topic modeling
→ layout
→ semantic search
→ PDF navigation/highlighting
→ cluster rename
→ cluster merge
→ cluster split
→ frontend interactions

Verify that all core functionality works together.

Do not add new features during this phase.

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

