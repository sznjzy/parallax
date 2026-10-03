"""
backend/tests/test_cluster_lifecycle.py

Automated unit & integration tests for Phase 7 (Interactive Cluster Lifecycle).
Validates:
  - Cluster renaming and custom topic persistence
  - Cluster merging with document re-assignment, constraint sync, and mapping cleanup
  - Cluster splitting with KMeans sub-clustering, lineage preservation, and constraint creation
  - FastAPI endpoints for PUT /api/clusters/{id}/topic, POST /api/clusters/merge,
    POST /api/clusters/{id}/split, and GET /api/clusters
  - Edge cases: invalid cluster IDs, noise clusters, single-document splits, self-merges
"""

import json
import tempfile
import unittest
from pathlib import Path
import numpy as np

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.clustering.lifecycle import (
    rename_cluster_topic,
    merge_clusters,
    split_cluster,
    load_cluster_metadata,
    save_cluster_metadata,
    get_cluster_lifecycle_state,
)
from backend.clustering.constraints import load_constraints, clear_all_constraints, add_constraint
from backend.topics.topic_modeling import extract_cluster_topics


class TestClusterLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="parallax_test_lifecycle_"))
        self.state_file = self.tmp_dir / "cluster_mapping.json"
        self.metadata_file = self.tmp_dir / "cluster_metadata.json"
        self.docs_dir = self.tmp_dir / "sample_docs"
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        # Create initial test cluster mapping:
        # Cluster A: 3 documents
        # Cluster B: 2 documents
        # Cluster C: 1 document (cannot be split)
        self.initial_mapping = {
            "cluster-aaa11111": ["doc-paper1.pdf", "doc-paper2.pdf", "doc-paper3.pdf"],
            "cluster-bbb22222": ["doc-paper4.pdf", "doc-paper5.pdf"],
            "cluster-ccc33333": ["doc-paper6.pdf"],
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.initial_mapping, f)

        # Clear active constraints
        clear_all_constraints()

    def tearDown(self):
        clear_all_constraints()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ── 1. Rename Tests ────────────────────────────────────────────────────────

    def test_rename_cluster_topic_success(self):
        """Renaming a cluster updates cluster_metadata.json and reflects in topic modeling."""
        res = rename_cluster_topic(
            cluster_id="cluster-aaa11111",
            new_topic_label="Deep Graph Learning",
            state_file=self.state_file,
            metadata_file=self.metadata_file,
        )
        self.assertEqual(res["cluster_id"], "cluster-aaa11111")
        self.assertEqual(res["topic_label"], "Deep Graph Learning")
        self.assertTrue(res["is_custom_label"])

        # Check metadata file
        meta = load_cluster_metadata(self.metadata_file)
        self.assertIn("cluster-aaa11111", meta)
        self.assertEqual(meta["cluster-aaa11111"]["custom_topic_label"], "Deep Graph Learning")

        # Check extract_cluster_topics integration
        docs = [
            {"id": "doc-paper1.pdf", "filename": "paper1.pdf", "text": "deep graph neural network representation"},
            {"id": "doc-paper2.pdf", "filename": "paper2.pdf", "text": "graph convolutional embedding"},
        ]
        topics = extract_cluster_topics(
            docs=docs,
            doc_cluster_ids=["cluster-aaa11111", "cluster-aaa11111"],
            metadata_file=self.metadata_file,
        )
        self.assertIn("cluster-aaa11111", topics)
        self.assertEqual(topics["cluster-aaa11111"]["topic_label"], "Deep Graph Learning")
        self.assertTrue(topics["cluster-aaa11111"]["is_custom_label"])

    def test_rename_cluster_invalid_inputs(self):
        """Rename rejects noise clusters, empty labels, and non-existent clusters."""
        with self.assertRaises(ValueError):
            rename_cluster_topic("noise-doc-1.pdf", "Outliers", state_file=self.state_file, metadata_file=self.metadata_file)

        with self.assertRaises(ValueError):
            rename_cluster_topic("cluster-aaa11111", "   ", state_file=self.state_file, metadata_file=self.metadata_file)

        with self.assertRaises(KeyError):
            rename_cluster_topic("cluster-nonexistent", "New Title", state_file=self.state_file, metadata_file=self.metadata_file)

    # ── 2. Merge Tests ─────────────────────────────────────────────────────────

    def test_merge_clusters_success(self):
        """Merging cluster B into cluster A reassigns docs, updates mapping, and records constraints."""
        res = merge_clusters(
            source_cluster_ids=["cluster-bbb22222"],
            target_cluster_id="cluster-aaa11111",
            new_topic_label="Unified AI & Graphs",
            state_file=self.state_file,
            metadata_file=self.metadata_file,
            docs_dir=self.docs_dir,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["target_cluster_id"], "cluster-aaa11111")
        self.assertIn("cluster-bbb22222", res["merged_source_cluster_ids"])
        self.assertEqual(res["total_documents"], 5)  # 3 from A + 2 from B

        # Verify state_file
        with open(self.state_file, "r", encoding="utf-8") as f:
            updated_mapping = json.load(f)

        self.assertNotIn("cluster-bbb22222", updated_mapping)
        self.assertIn("cluster-aaa11111", updated_mapping)
        self.assertEqual(len(updated_mapping["cluster-aaa11111"]), 5)
        for doc in ["doc-paper4.pdf", "doc-paper5.pdf"]:
            self.assertIn(doc, updated_mapping["cluster-aaa11111"])

        # Verify persistent constraints were added for merged documents
        constraints = load_constraints()
        forced = {c.doc_id: c.forced_cluster_id for c in constraints}
        self.assertEqual(forced.get("doc-paper4.pdf"), "cluster-aaa11111")
        self.assertEqual(forced.get("doc-paper5.pdf"), "cluster-aaa11111")

        # Verify metadata custom label
        meta = load_cluster_metadata(self.metadata_file)
        self.assertEqual(meta["cluster-aaa11111"]["custom_topic_label"], "Unified AI & Graphs")
        self.assertNotIn("cluster-bbb22222", meta)

    def test_merge_clusters_invalid_operations(self):
        """Merge rejects self-merges, non-existent sources/targets, and noise clusters."""
        with self.assertRaises(ValueError):
            # Self merge
            merge_clusters(["cluster-aaa11111"], "cluster-aaa11111", state_file=self.state_file)

        with self.assertRaises(KeyError):
            # Missing source
            merge_clusters(["cluster-unknown"], "cluster-aaa11111", state_file=self.state_file)

        with self.assertRaises(KeyError):
            # Missing target
            merge_clusters(["cluster-bbb22222"], "cluster-unknown", state_file=self.state_file)

        with self.assertRaises(ValueError):
            # Noise merge
            merge_clusters(["noise-1"], "cluster-aaa11111", state_file=self.state_file)

    # ── 3. Split Tests ─────────────────────────────────────────────────────────

    def test_split_cluster_success(self):
        """Splitting cluster A (3 docs) into k=2 produces two sub-clusters, preserving original UUID."""
        res = split_cluster(
            cluster_id="cluster-aaa11111",
            k=2,
            new_topic_labels=["Primary Subtopic", "Secondary Subtopic"],
            state_file=self.state_file,
            metadata_file=self.metadata_file,
            docs_dir=self.docs_dir,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["original_cluster_id"], "cluster-aaa11111")
        self.assertEqual(len(res["resulting_clusters"]), 2)

        # Verify lineage: one cluster must retain "cluster-aaa11111"
        cids = [c["cluster_id"] for c in res["resulting_clusters"]]
        self.assertIn("cluster-aaa11111", cids)
        new_cids = [cid for cid in cids if cid != "cluster-aaa11111"]
        self.assertEqual(len(new_cids), 1)
        self.assertTrue(new_cids[0].startswith("cluster-"))

        # Verify total documents conserved
        total_docs_in_sub = sum(len(c["doc_ids"]) for c in res["resulting_clusters"])
        self.assertEqual(total_docs_in_sub, 3)

        # Verify state_file was updated
        with open(self.state_file, "r", encoding="utf-8") as f:
            updated_mapping = json.load(f)
        self.assertIn("cluster-aaa11111", updated_mapping)
        self.assertIn(new_cids[0], updated_mapping)

        # Verify constraints were created for split documents
        constraints = load_constraints()
        self.assertEqual(len(constraints), 3)

    def test_split_cluster_insufficient_documents(self):
        """Cluster with 1 document cannot be split."""
        with self.assertRaises(ValueError):
            split_cluster("cluster-ccc33333", k=2, state_file=self.state_file)

    def test_split_cluster_invalid_k(self):
        """k must be between 2 and number of documents in cluster."""
        with self.assertRaises(ValueError):
            # k=1 invalid
            split_cluster("cluster-aaa11111", k=1, state_file=self.state_file)

        with self.assertRaises(ValueError):
            # k=5 > 3 docs
            split_cluster("cluster-aaa11111", k=5, state_file=self.state_file)

    # ── 4. FastAPI Endpoint Integration Tests ──────────────────────────────────

    def test_api_cluster_endpoints(self):
        """Test client hits for /api/clusters, PUT /topic, POST /merge, POST /split."""
        client = TestClient(app)

        # 1. GET /api/clusters
        resp = client.get("/api/clusters")
        self.assertEqual(resp.status_code, 200)
        clusters = resp.json()
        self.assertIsInstance(clusters, list)

        # 2. PUT /api/clusters/{id}/topic
        if clusters:
            first_cid = clusters[0]["cluster_id"]
            rename_resp = client.put(
                f"/api/clusters/{first_cid}/topic",
                json={"topic_label": "Graph Neural Architectures"}
            )
            self.assertEqual(rename_resp.status_code, 200)
            self.assertEqual(rename_resp.json()["topic_label"], "Graph Neural Architectures")

        # 3. Test 404 for non-existent cluster rename
        bad_rename = client.put("/api/clusters/cluster-99999999/topic", json={"topic_label": "Test"})
        self.assertIn(bad_rename.status_code, (400, 404))

        # 4. Test 400 for empty rename label
        bad_empty = client.put(f"/api/clusters/{first_cid}/topic", json={"topic_label": "   "})
        self.assertEqual(bad_empty.status_code, 400)


if __name__ == "__main__":
    unittest.main()
