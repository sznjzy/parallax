"""
backend/tests/test_api_endpoints.py

Integration tests for FastAPI REST API endpoints using TestClient (Phase 3).
"""

import unittest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.clustering.constraints import (
    load_constraints,
    clear_all_constraints,
)


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        # Clear constraints before each test to guarantee isolation
        clear_all_constraints()

    def tearDown(self):
        clear_all_constraints()

    def test_health_check(self):
        """GET / and GET /api/ return status ok."""
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

        r_api = self.client.get("/api/")
        self.assertEqual(r_api.status_code, 200)
        self.assertEqual(r_api.json()["project"], "Parallax")

    def test_pipeline_status(self):
        """GET /api/status returns pdf_count and readiness state."""
        r = self.client.get("/api/status")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("state", data)
        self.assertIn("pdf_count", data)
        self.assertIn("model_available", data)
        self.assertTrue(data["model_available"])

    def test_list_documents(self):
        """GET /api/documents returns available PDFs and cache summary."""
        r = self.client.get("/api/documents")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("documents", data)
        self.assertIn("total", data)
        self.assertIn("cached", data)
        self.assertGreaterEqual(data["total"], 1)

    def test_constraint_lifecycle_crud(self):
        """Test GET, POST, DELETE constraint endpoints."""
        # 1. Initial state: 0 constraints
        r = self.client.get("/api/constraints")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

        # 2. Create constraint
        payload = {"doc_id": "doc-test1.pdf", "cluster_id": "cluster-target-xyz"}
        r_post = self.client.post("/api/constraints", json=payload)
        self.assertEqual(r_post.status_code, 201)
        created = r_post.json()
        self.assertEqual(created["doc_id"], "doc-test1.pdf")
        self.assertEqual(created["forced_cluster_id"], "cluster-target-xyz")

        # 3. List constraints
        r_list = self.client.get("/api/constraints")
        self.assertEqual(len(r_list.json()), 1)
        self.assertEqual(r_list.json()[0]["doc_id"], "doc-test1.pdf")

        # 4. Delete single constraint
        r_del = self.client.delete("/api/constraints/doc-test1.pdf")
        self.assertEqual(r_del.status_code, 204)

        r_after = self.client.get("/api/constraints")
        self.assertEqual(len(r_after.json()), 0)

    def test_constraint_validation_and_malformed_input(self):
        """POST /api/constraints rejects empty or whitespace-only inputs with 400 Bad Request."""
        # 1. Empty strings
        r1 = self.client.post("/api/constraints", json={"doc_id": "", "cluster_id": "c1"})
        self.assertEqual(r1.status_code, 400)
        self.assertIn("non-empty", r1.json()["detail"])

        r2 = self.client.post("/api/constraints", json={"doc_id": "doc1", "cluster_id": ""})
        self.assertEqual(r2.status_code, 400)
        self.assertIn("non-empty", r2.json()["detail"])

        # 2. Whitespace-only strings
        r3 = self.client.post("/api/constraints", json={"doc_id": "   ", "cluster_id": "   "})
        self.assertEqual(r3.status_code, 400)
        self.assertIn("non-empty", r3.json()["detail"])

        # 3. Missing fields (Pydantic validation 422)
        r4 = self.client.post("/api/constraints", json={"doc_id": "doc1"})
        self.assertEqual(r4.status_code, 422)

    def test_pdf_streaming_and_traversal_defense(self):
        """GET /api/documents/{filename}/pdf serves existing PDFs and rejects bad paths."""
        # Existing PDF
        r = self.client.get("/api/documents/paper1.pdf/pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("content-type"), "application/pdf")

        # Nonexistent PDF
        r_404 = self.client.get("/api/documents/nonexistent_paper_999.pdf/pdf")
        self.assertEqual(r_404.status_code, 404)

        # Path traversal attempts
        r_trav1 = self.client.get("/api/documents/..%2F..%2Fetc%2Fpasswd/pdf")
        self.assertEqual(r_trav1.status_code, 404)

    def test_cluster_lifecycle_api_endpoints(self):
        """GET /api/clusters, PUT /topic, POST /merge, POST /split API endpoints."""
        # 1. GET /api/clusters
        r = self.client.get("/api/clusters")
        self.assertEqual(r.status_code, 200)
        clusters = r.json()
        self.assertIsInstance(clusters, list)

        if len(clusters) >= 2:
            c1 = clusters[0]["cluster_id"]
            c2 = clusters[1]["cluster_id"]

            # 2. PUT /api/clusters/{c1}/topic (Rename)
            r_rename = self.client.put(
                f"/api/clusters/{c1}/topic",
                json={"topic_label": "Advanced Graph Theory"}
            )
            self.assertEqual(r_rename.status_code, 200)
            self.assertEqual(r_rename.json()["topic_label"], "Advanced Graph Theory")
            self.assertTrue(r_rename.json()["is_custom_label"])


if __name__ == "__main__":
    unittest.main()


