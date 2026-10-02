/**
 * mockFixture.js
 *
 * Static fixture derived from the real /api/organize response (response1.json).
 * Used when VITE_MOCK_API=true so the canvas can be developed / screenshot
 * without running the uvicorn backend.
 *
 * The fixture intentionally includes:
 *   - 5 distinct clusters (cluster-*)
 *   - 2 noise nodes (noise-doc-paper*.pdf)
 *   - 1 boundary document (paper11.pdf)
 *   - 0 skipped_documents (all PDFs parsed OK)
 * This covers the common render path completely.
 */
export const MOCK_ORGANIZE_RESPONSE = {
  nodes: [
    // ── cluster-3a1b721f  (ML / NLP group, left side) ─────────────
    { doc_id: "doc-paper1.pdf", x: 97, y: 138, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-3a1b721f", is_boundary_document: false },
    { doc_id: "doc-paper2.pdf", x: 77, y: 138, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-3a1b721f", is_boundary_document: false },
    { doc_id: "doc-paper3.pdf", x: 97, y: 118, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-3a1b721f", is_boundary_document: false },
    { doc_id: "doc-paper4.pdf", x: 117, y: 138, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-3a1b721f", is_boundary_document: false },
    { doc_id: "doc-paper5.pdf", x: 97, y: 158, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-3a1b721f", is_boundary_document: false },

    // ── cluster-d19e46af  (Systems / Architecture, top centre) ────
    { doc_id: "doc-paper6.pdf", x: 185, y: 68, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-d19e46af", is_boundary_document: false },
    { doc_id: "doc-paper7.pdf", x: 165, y: 68, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-d19e46af", is_boundary_document: false },
    { doc_id: "doc-paper8.pdf", x: 185, y: 48, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-d19e46af", is_boundary_document: false },
    { doc_id: "doc-paper9.pdf", x: 205, y: 68, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-d19e46af", is_boundary_document: false },
    { doc_id: "doc-paper10.pdf", x: 185, y: 88, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-d19e46af", is_boundary_document: false },

    // ── cluster-8048b303  (Compilers / PL, left-ish) ──────────────
    { doc_id: "doc-paper11.pdf", x: 150, y: 200, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-8048b303", is_boundary_document: true },
    { doc_id: "doc-paper15.pdf", x: 170, y: 200, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-8048b303", is_boundary_document: false },

    // ── cluster-f7ddbe0c  (Hardware / Microarchitecture, right top) ─
    { doc_id: "doc-paper14.pdf", x: 295, y: 103, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-f7ddbe0c", is_boundary_document: false },
    { doc_id: "doc-paper16.pdf", x: 315, y: 103, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-f7ddbe0c", is_boundary_document: false },

    // ── cluster-788d3b38  (Distributed Systems, right bottom) ──────
    { doc_id: "doc-paper17.pdf", x: 285, y: 208, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-788d3b38", is_boundary_document: false },
    { doc_id: "doc-paper18.pdf", x: 265, y: 208, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-788d3b38", is_boundary_document: false },
    { doc_id: "doc-paper19.pdf", x: 285, y: 188, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-788d3b38", is_boundary_document: false },

    // ── cluster-3aee70a5  (Compiler+ML crossover) ──────────────────
    { doc_id: "doc-paper20.pdf", x: 200, y: 140, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-3aee70a5", is_boundary_document: false },
    { doc_id: "doc-paper21.pdf", x: 220, y: 140, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-3aee70a5", is_boundary_document: false },

    // ── noise nodes ────────────────────────────────────────────────
    { doc_id: "doc-paper12.pdf", x: 259, y: 250, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "noise-doc-paper12.pdf", is_boundary_document: false },
    { doc_id: "doc-paper13.pdf", x: 50, y: 250, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "noise-doc-paper13.pdf", is_boundary_document: false },
  ],
  topics: {
    "cluster-3a1b721f": {
      cluster_id: "cluster-3a1b721f",
      topic_label: "NLP / Language Models",
      keywords: [{ keyword: "language models", score: 0.95 }, { keyword: "nlp", score: 0.88 }],
      top_terms: ["language models", "nlp", "transformers", "attention", "tokens"],
      doc_count: 5,
    },
    "cluster-d19e46af": {
      cluster_id: "cluster-d19e46af",
      topic_label: "Systems / Memory Architecture",
      keywords: [{ keyword: "memory architecture", score: 0.92 }, { keyword: "cache", score: 0.85 }],
      top_terms: ["memory architecture", "cache", "latency", "bandwidth", "storage"],
      doc_count: 5,
    },
    "cluster-8048b303": {
      cluster_id: "cluster-8048b303",
      topic_label: "Compilers / Program Analysis",
      keywords: [{ keyword: "compilers", score: 0.91 }, { keyword: "program analysis", score: 0.84 }],
      top_terms: ["compilers", "program analysis", "optimization", "ir", "llvm"],
      doc_count: 2,
    },
    "cluster-f7ddbe0c": {
      cluster_id: "cluster-f7ddbe0c",
      topic_label: "Hardware / Microarchitecture",
      keywords: [{ keyword: "microarchitecture", score: 0.90 }, { keyword: "accelerator", score: 0.83 }],
      top_terms: ["microarchitecture", "accelerator", "fpga", "chip", "pipeline"],
      doc_count: 2,
    },
    "cluster-788d3b38": {
      cluster_id: "cluster-788d3b38",
      topic_label: "Distributed Systems / Consensus",
      keywords: [{ keyword: "distributed systems", score: 0.94 }, { keyword: "consensus", score: 0.87 }],
      top_terms: ["distributed systems", "consensus", "replication", "fault tolerance", "rpc"],
      doc_count: 3,
    },
    "cluster-3aee70a5": {
      cluster_id: "cluster-3aee70a5",
      topic_label: "ML Compilers / Graph Optimization",
      keywords: [{ keyword: "graph optimization", score: 0.89 }, { keyword: "tensor", score: 0.82 }],
      top_terms: ["graph optimization", "tensor", "kernel", "autotuning", "compilation"],
      doc_count: 2,
    },
  },
  evaluation: {
    silhouette_score: 0.3798,
    num_clusters: 6,
    constraint_satisfaction_rate: null,
    num_constraints_applied: null,
    num_constraints_violated: null,
  },
  skipped_documents: [],
}

/** Fixture for edge-case: zero documents */
export const MOCK_EMPTY_RESPONSE = {
  nodes: [],
  evaluation: null,
  skipped_documents: [],
}

/** Fixture for edge-case: single cluster */
export const MOCK_SINGLE_CLUSTER_RESPONSE = {
  nodes: [
    { doc_id: "doc-paper1.pdf", x: 185.0, y: 145.0, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-aaaabbbb", is_boundary_document: false },
    { doc_id: "doc-paper2.pdf", x: 195.0, y: 150.0, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-aaaabbbb", is_boundary_document: false },
    { doc_id: "doc-paper3.pdf", x: 205.0, y: 148.0, velocity_x: 0, velocity_y: 0, is_anchored: false, cluster_id: "cluster-aaaabbbb", is_boundary_document: false },
  ],
  evaluation: {
    silhouette_score: null,
    num_clusters: 1,
    constraint_satisfaction_rate: null,
    num_constraints_applied: null,
    num_constraints_violated: null,
  },
  skipped_documents: [],
}

/** Fixture for mock constraints (empty by default) */
export const MOCK_CONSTRAINTS = []
