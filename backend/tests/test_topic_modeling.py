"""
backend/tests/test_topic_modeling.py

Comprehensive test suite for Phase 5 Automatic Cluster Topic Modeling.
Validates:
  1. c-TF-IDF calculation correctness, term weighting, and cluster differentiation.
  2. Academic stopword and generic filler filtering.
  3. Topic label formatting and representative keyword extraction.
  4. KeyBERT semantic centroid alignment and re-ranking.
  5. Dynamic topic updates when cluster membership or constraints change.
  6. Outlier / noise document topic handling.
  7. Edge cases (empty corpus, single document, missing text fallback).
  8. End-to-end integration with run_pipeline() and API endpoints.
"""

import unittest
import numpy as np
from pathlib import Path
from fastapi.testclient import TestClient

from backend.topics.topic_modeling import (
    compute_ctfidf,
    extract_cluster_topics,
    _clean_text,
    _format_topic_label,
    DEFAULT_STOPWORDS,
)
from backend.api.main import app
from backend.api.pipeline import run_pipeline, SAMPLE_DOCS_DIR


class TestTopicModeling(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_clean_text_and_stopwords(self):
        """Verify text normalization strips punctuation and stopword filtering removes academic boilerplate."""
        raw = "This paper presents a proposed novel approach for Quantum Computing, with 99.9% fidelity!"
        cleaned = _clean_text(raw)
        self.assertNotIn("%", cleaned)
        self.assertNotIn("!", cleaned)
        self.assertIn("quantum computing", cleaned)

        # Check default academic stopwords
        self.assertIn("paper", DEFAULT_STOPWORDS)
        self.assertIn("proposed", DEFAULT_STOPWORDS)
        self.assertIn("approach", DEFAULT_STOPWORDS)
        self.assertIn("results", DEFAULT_STOPWORDS)

    def test_compute_ctfidf_term_differentiation(self):
        """c-TF-IDF should give highest weight to terms unique and frequent within each cluster."""
        cluster_texts = {
            "cluster-nlp": (
                "transformer attention mechanism language models bert gpt tokenizer sequence "
                "deep learning neural networks natural language processing"
            ),
            "cluster-quantum": (
                "quantum computing qubits superposition entanglement quantum circuit gates "
                "fidelity decoherence quantum algorithms"
            ),
            "cluster-db": (
                "relational database sql transaction index btree concurrency acid "
                "query optimization distributed storage replication"
            ),
        }

        cids, terms, matrix = compute_ctfidf(cluster_texts, ngram_range=(1, 2), max_features=100)

        self.assertEqual(len(cids), 3)
        self.assertGreater(len(terms), 0)
        self.assertEqual(matrix.shape, (3, len(terms)))

        # Verify cluster-nlp top term relates to NLP/transformer
        nlp_idx = cids.index("cluster-nlp")
        top_nlp_idx = np.argsort(matrix[nlp_idx])[::-1][0]
        top_nlp_term = terms[top_nlp_idx]
        self.assertIn(top_nlp_term, ["transformer", "attention", "language", "models", "bert", "gpt", "tokenizer"])

        # Verify cluster-quantum top term relates to quantum
        q_idx = cids.index("cluster-quantum")
        top_q_idx = np.argsort(matrix[q_idx])[::-1][0]
        top_q_term = terms[top_q_idx]
        self.assertIn(top_q_term, ["quantum", "qubits", "entanglement", "superposition", "circuit"])

        # Verify cluster-db top term relates to database
        db_idx = cids.index("cluster-db")
        top_db_idx = np.argsort(matrix[db_idx])[::-1][0]
        top_db_term = terms[top_db_idx]
        self.assertIn(top_db_term, ["database", "sql", "transaction", "index", "btree", "concurrency"])

    def test_extract_cluster_topics_structure(self):
        """extract_cluster_topics should return well-formed TopicMetadata dictionaries."""
        docs = [
            {"id": "doc-1", "filename": "nlp1.pdf", "text": "transformer attention language models deep learning"},
            {"id": "doc-2", "filename": "nlp2.pdf", "text": "bert roberta fine-tuning natural language tokenization"},
            {"id": "doc-3", "filename": "quantum1.pdf", "text": "quantum computing qubits quantum teleportation circuit"},
            {"id": "doc-4", "filename": "quantum2.pdf", "text": "quantum gates decoherence error correction qubits"},
            {"id": "doc-noise", "filename": "noise1.pdf", "text": "isolated random text outlier anomaly"},
        ]
        doc_cluster_ids = [
            "cluster-nlp",
            "cluster-nlp",
            "cluster-quantum",
            "cluster-quantum",
            "noise-doc-noise1.pdf",
        ]

        topics = extract_cluster_topics(docs, doc_cluster_ids, top_n=3)

        self.assertIn("cluster-nlp", topics)
        self.assertIn("cluster-quantum", topics)
        self.assertIn("noise-doc-noise1.pdf", topics)

        # Real cluster validation
        nlp_meta = topics["cluster-nlp"]
        self.assertEqual(nlp_meta["cluster_id"], "cluster-nlp")
        self.assertEqual(nlp_meta["doc_count"], 2)
        self.assertIsInstance(nlp_meta["topic_label"], str)
        self.assertGreater(len(nlp_meta["keywords"]), 0)
        self.assertGreater(len(nlp_meta["top_terms"]), 0)

        # Noise outlier validation
        noise_meta = topics["noise-doc-noise1.pdf"]
        self.assertIn("Outlier", noise_meta["topic_label"])
        self.assertEqual(noise_meta["top_terms"], ["outlier"])

    def test_dynamic_topic_updates_when_cluster_changes(self):
        """Topic labels and keywords must update dynamically when documents are moved to a new cluster."""
        docs = [
            {"id": "doc-1", "text": "compiler llvm ir code generation optimization"},
            {"id": "doc-2", "text": "compiler register allocation instruction scheduling"},
            {"id": "doc-3", "text": "compiler parsing syntax abstract syntax tree"},
        ]

        # Initial: doc-3 is in cluster-compiler
        topics_initial = extract_cluster_topics(docs, ["cluster-compiler", "cluster-compiler", "cluster-compiler"])
        self.assertIn("compiler", topics_initial["cluster-compiler"]["top_terms"][0].lower())

        # Move doc-3 to a separate robotics cluster with new document
        docs_updated = docs + [{"id": "doc-4", "text": "robotics inverse kinematics trajectory planning manipulator"}]
        cids_updated = ["cluster-compiler", "cluster-compiler", "cluster-robotics", "cluster-robotics"]

        topics_updated = extract_cluster_topics(docs_updated, cids_updated)
        self.assertIn("cluster-robotics", topics_updated)
        self.assertEqual(topics_updated["cluster-robotics"]["doc_count"], 2)
        self.assertEqual(topics_updated["cluster-compiler"]["doc_count"], 2)

    def test_keybert_semantic_reranking_with_mock_model(self):
        """KeyBERT re-ranking should combine c-TF-IDF score with cosine similarity to cluster centroid."""
        docs = [
            {"id": "doc-1", "text": "neural network deep learning backpropagation gradient descent"},
            {"id": "doc-2", "text": "convolutional network vision image classification resnet"},
        ]
        doc_cluster_ids = ["cluster-vision", "cluster-vision"]

        # Synthetic centroid vector
        dim = 8
        centroid = np.ones(dim) / np.sqrt(dim)
        cluster_centers = {"cluster-vision": centroid}

        class MockEmbeddingModel:
            def encode(self, texts, convert_to_numpy=True):
                # Return synthetic vectors having different similarities
                res = []
                for t in texts:
                    if "vision" in t or "network" in t:
                        v = np.ones(dim)  # high similarity
                    else:
                        v = np.zeros(dim)
                        v[0] = 1.0
                    res.append(v)
                return np.array(res)

        mock_model = MockEmbeddingModel()
        topics = extract_cluster_topics(
            docs, doc_cluster_ids, cluster_centers=cluster_centers, model=mock_model, top_n=3
        )
        self.assertIn("cluster-vision", topics)
        self.assertGreater(len(topics["cluster-vision"]["keywords"]), 0)

    def test_edge_cases_empty_and_fallback(self):
        """Empty corpus or documents without text should not crash and should produce fallback metadata."""
        # Empty docs
        self.assertEqual(extract_cluster_topics([], []), {})

        # Document without text (fallback to filename)
        docs = [{"id": "doc-test", "filename": "distributed_consensus_raft.pdf", "text": ""}]
        topics = extract_cluster_topics(docs, ["cluster-1"])
        self.assertIn("cluster-1", topics)
        self.assertEqual(topics["cluster-1"]["doc_count"], 1)

    def test_run_pipeline_returns_topics(self):
        """Full run_pipeline() on sample_docs should return 'topics' with real keywords."""
        res = run_pipeline(SAMPLE_DOCS_DIR, doc_filter={"paper1.pdf", "paper2.pdf", "paper3.pdf"})
        self.assertIn("nodes", res)
        self.assertIn("topics", res)
        topics = res["topics"]
        self.assertIsInstance(topics, dict)

        # Check that all unique cluster IDs in nodes exist in topics
        node_cids = {n["cluster_id"] for n in res["nodes"]}
        for cid in node_cids:
            self.assertIn(cid, topics)
            topic_meta = topics[cid]
            self.assertIn("topic_label", topic_meta)
            self.assertIn("keywords", topic_meta)
            self.assertIn("doc_count", topic_meta)

    def test_api_analyze_endpoint_includes_topics(self):
        """POST /api/analyze demo endpoint should return cluster topics and keywords."""
        sample_pdfs = list(SAMPLE_DOCS_DIR.glob("*.pdf"))[:3]
        files = [
            ("files", (p.name, p.read_bytes(), "application/pdf"))
            for p in sample_pdfs
        ]
        response = self.client.post("/api/analyze", files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("clusters", data)
        self.assertIn("topics", data)
        for cluster in data["clusters"]:
            self.assertIn("topic_label", cluster)
            self.assertIn("keywords", cluster)


if __name__ == "__main__":
    unittest.main()
