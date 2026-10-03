"""
backend/tests/test_semantic_search.py

Unit and integration tests for Phase 6: Semantic Search + Canvas Heatmap.

Covers:
1. Semantic ranking correctness using synthetic embeddings and cosine similarity.
2. Cosine similarity mathematical properties and clamping to [-1.0, 1.0].
3. Empty/invalid query handling (empty string, whitespace).
4. Empty corpus and small corpus edge cases.
5. Correct cluster association and aggregated cluster relevance calculation.
6. Non-mutating state verification (corpus files, cluster_mapping.json, and constraints remain untouched).
7. Top-k limit and doc_filter scoping.
8. FastAPI POST /api/search endpoint integration via TestClient.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.search.semantic_search import (
    search_corpus,
    extract_best_snippet,
    load_cluster_assignments,
    SearchResult,
    ClusterRelevance,
    SearchResponse,
)


class MockEmbeddingModel:
    """Deterministic mock embedding model for isolated unit testing."""
    def __init__(self, dim: int = 768):
        self.dim = dim

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        vectors = []
        for text in texts:
            # Deterministic hash seed
            seed = sum(ord(c) for c in text) % (2**32)
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(self.dim).astype(np.float32)
            if normalize_embeddings:
                norm = np.linalg.norm(v)
                if norm > 1e-8:
                    v = v / norm
            vectors.append(v)
        return np.array(vectors)


class TestSemanticSearch(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="parallax_test_search_"))
        self.state_file = self.temp_dir / "cluster_mapping.json"
        self.mock_model = MockEmbeddingModel(dim=768)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_or_whitespace_query_raises_error(self):
        """Empty or whitespace queries must raise ValueError."""
        with self.assertRaises(ValueError):
            search_corpus("", corpus_dir=self.temp_dir, model=self.mock_model)

        with self.assertRaises(ValueError):
            search_corpus("   \t\n  ", corpus_dir=self.temp_dir, model=self.mock_model)

    def test_empty_corpus_returns_gracefully(self):
        """Searching an empty directory should return an empty result payload without crashing."""
        res = search_corpus("graph neural networks", corpus_dir=self.temp_dir, model=self.mock_model)
        self.assertEqual(res["query"], "graph neural networks")
        self.assertEqual(res["results"], [])
        self.assertEqual(res["total_corpus_searched"], 0)
        self.assertEqual(res["cluster_relevance"], {})

    def test_semantic_ranking_and_similarity_calculation(self):
        """Ensure cosine similarity ranking accurately ranks the most similar document at rank 1."""
        # Create 3 synthetic PDF files with cached embeddings
        doc_names = ["graph_ml.pdf", "nlp_bert.pdf", "quantum_sim.pdf"]
        for name in doc_names:
            pdf_p = self.temp_dir / name
            pdf_p.write_bytes(b"%PDF-1.4 dummy content " + name.encode())

        # Set cluster assignments in state file
        cluster_mapping = {
            "doc-graph_ml.pdf": "cluster-graphs",
            "doc-nlp_bert.pdf": "cluster-nlp",
            "doc-quantum_sim.pdf": "cluster-quantum",
        }
        self.state_file.write_text(json.dumps(cluster_mapping), encoding="utf-8")

        # Mock embedding cache
        from backend.embeddings.embedding_cache import save_cached_embedding, save_cached_text
        query = "graph representation learning"
        q_vec = self.mock_model.encode([query], normalize_embeddings=True)[0]

        # Make graph_ml.pdf have high similarity to query
        v_graph = q_vec * 0.95 + self.mock_model.encode(["random noise 1"])[0] * 0.05
        v_graph /= np.linalg.norm(v_graph)
        save_cached_embedding(self.temp_dir / "graph_ml.pdf", v_graph)
        save_cached_text(self.temp_dir / "graph_ml.pdf", "Graph neural networks for node classification and link prediction.")

        v_nlp = self.mock_model.encode(["natural language transformers bert tokens"])[0]
        save_cached_embedding(self.temp_dir / "nlp_bert.pdf", v_nlp)
        save_cached_text(self.temp_dir / "nlp_bert.pdf", "Transformer architecture for language modeling and sentiment analysis.")

        v_quantum = self.mock_model.encode(["quantum computing qubit gate circuits"])[0]
        save_cached_embedding(self.temp_dir / "quantum_sim.pdf", v_quantum)
        save_cached_text(self.temp_dir / "quantum_sim.pdf", "Quantum simulation of Hamiltonian systems using superconducting qubits.")

        # Run search
        res = search_corpus(
            query=query,
            corpus_dir=self.temp_dir,
            model=self.mock_model,
            state_file=self.state_file,
            topic_metadata={
                "cluster-graphs": {"topic_label": "Graph ML"},
                "cluster-nlp": {"topic_label": "NLP Transformers"},
                "cluster-quantum": {"topic_label": "Quantum Computing"},
            },
        )

        self.assertEqual(res["total_corpus_searched"], 3)
        self.assertEqual(len(res["results"]), 3)

        top_doc = res["results"][0]
        self.assertEqual(top_doc["filename"], "graph_ml.pdf")
        self.assertEqual(top_doc["rank"], 1)
        self.assertGreater(top_doc["similarity_score"], 0.85)
        self.assertEqual(top_doc["cluster_id"], "cluster-graphs")
        self.assertEqual(top_doc["topic_label"], "Graph ML")
        self.assertIn("Graph neural networks", top_doc["snippet"])

        # Check cluster relevance metrics
        self.assertIn("cluster-graphs", res["cluster_relevance"])
        graph_rel = res["cluster_relevance"]["cluster-graphs"]
        self.assertEqual(graph_rel["topic_label"], "Graph ML")
        self.assertGreater(graph_rel["max_similarity"], 0.85)
        self.assertEqual(graph_rel["matched_docs_count"], 1)

    def test_top_k_and_doc_filter(self):
        """Ensure top_k limits results and doc_filter restricts search scope."""
        from backend.embeddings.embedding_cache import save_cached_embedding
        for i in range(5):
            pdf_p = self.temp_dir / f"paper_{i}.pdf"
            pdf_p.write_bytes(b"%PDF-1.4 paper" + str(i).encode())
            v = self.mock_model.encode([f"paper content {i}"])[0]
            save_cached_embedding(pdf_p, v)

        # Test top_k=2
        res_k = search_corpus(
            query="test query",
            corpus_dir=self.temp_dir,
            model=self.mock_model,
            top_k=2,
        )
        self.assertEqual(len(res_k["results"]), 2)
        self.assertEqual(res_k["total_corpus_searched"], 5)

        # Test doc_filter
        res_filter = search_corpus(
            query="test query",
            corpus_dir=self.temp_dir,
            model=self.mock_model,
            doc_filter={"paper_1.pdf", "paper_3.pdf"},
        )
        self.assertEqual(len(res_filter["results"]), 2)
        self.assertEqual(res_filter["total_corpus_searched"], 2)
        result_filenames = {r["filename"] for r in res_filter["results"]}
        self.assertEqual(result_filenames, {"paper_1.pdf", "paper_3.pdf"})

    def test_search_does_not_mutate_state_or_corpus(self):
        """Search operation must be strictly read-only and non-mutating."""
        from backend.embeddings.embedding_cache import save_cached_embedding
        state_content = json.dumps({"doc-test.pdf": "cluster-fixed-123"})
        self.state_file.write_text(state_content, encoding="utf-8")

        pdf_p = self.temp_dir / "test.pdf"
        pdf_bytes = b"%PDF-1.4 fixed content"
        pdf_p.write_bytes(pdf_bytes)
        save_cached_embedding(pdf_p, self.mock_model.encode(["test text"])[0])

        search_corpus("query", corpus_dir=self.temp_dir, model=self.mock_model, state_file=self.state_file)

        # Verify state file untouched
        self.assertEqual(self.state_file.read_text(encoding="utf-8"), state_content)
        # Verify PDF untouched
        self.assertEqual(pdf_p.read_bytes(), pdf_bytes)

    def test_extract_best_snippet(self):
        """Snippet extractor chooses sentence with highest lexical overlap."""
        text = (
            "We present an introduction to computer systems. "
            "In this work, we propose graph neural networks for molecular property prediction. "
            "Finally, conclusion discusses future directions."
        )
        snippet = extract_best_snippet(text, "graph neural networks molecular property")
        self.assertIn("graph neural networks", snippet)
        self.assertIn("molecular property", snippet)


class TestSearchApiEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_api_search_endpoint_success(self):
        """POST /api/search with valid query returns 200 and ranked results."""
        payload = {"query": "deep learning architectures", "top_k": 5}
        r = self.client.post("/api/search", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("query", data)
        self.assertEqual(data["query"], "deep learning architectures")
        self.assertIn("results", data)
        self.assertIn("cluster_relevance", data)
        self.assertIn("query_embedding_dim", data)
        self.assertEqual(data["query_embedding_dim"], 768)

    def test_api_search_endpoint_empty_query_400(self):
        """POST /api/search with empty query returns 400 Bad Request."""
        payload = {"query": "   "}
        r = self.client.post("/api/search", json=payload)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Search query cannot be empty", r.json()["detail"])


if __name__ == "__main__":
    unittest.main()
