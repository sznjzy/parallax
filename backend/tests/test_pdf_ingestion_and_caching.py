"""
backend/tests/test_pdf_ingestion_and_caching.py

Comprehensive test suite for Phase 4:
  1. PDF validation (magic bytes, extensions, size limits)
  2. Filename sanitization & path traversal prevention
  3. Content SHA-256 deduplication
  4. Live ingestion with chunking and disk embedding caching (.npy)
  5. Cache hit verification and duplicate detection
  6. Corrupted/unparseable PDF graceful error handling
  7. API endpoint testing for POST /api/documents/upload and DELETE /api/documents/{filename}
"""

import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.embeddings.embedding_cache import (
    get_cached_embedding,
    save_cached_embedding,
    is_cached,
    _cache_key,
)
from backend.ingestion.ingest import (
    validate_pdf_file,
    sanitize_filename,
    compute_file_hash,
    save_and_ingest_pdf,
    delete_document_file,
    MAX_PDF_SIZE_BYTES,
)


class MockEmbeddingModel:
    """Fast deterministic mock for sentence transformer embedding model."""
    def __init__(self, dim: int = 768):
        self.dim = dim

    def encode(self, texts: list[str], convert_to_numpy: bool = True) -> np.ndarray:
        n = len(texts)
        # Generate predictable vector based on text length
        vectors = []
        for text in texts:
            seed_val = len(text) % 1000
            rng = np.random.default_rng(seed=seed_val)
            vec = rng.normal(0, 1, size=self.dim)
            vectors.append(vec)
        raw = np.array(vectors)
        norms = np.linalg.norm(raw, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        return raw / norms


class TestPdfIngestionAndCaching(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="parallax_test_ingest_"))
        self.docs_dir = self.temp_dir / "docs"
        self.cache_dir = self.temp_dir / "cache"
        self.docs_dir.mkdir(parents=True)
        self.cache_dir.mkdir(parents=True)
        self.mock_model = MockEmbeddingModel(dim=768)

        # Sample valid PDF bytes from existing paper1.pdf if available, or minimal valid PDF
        sample_pdf_path = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs" / "paper1.pdf"
        if sample_pdf_path.exists():
            self.valid_pdf_bytes = sample_pdf_path.read_bytes()
        else:
            # Construct a minimal valid PDF byte sequence
            self.valid_pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n210\n%%EOF"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_pdf_file_checks(self):
        """Test magic byte signature, extension, and size validation."""
        # Valid PDF
        valid, err = validate_pdf_file("test.pdf", b"%PDF-1.4 header content")
        self.assertTrue(valid)
        self.assertIsNone(err)

        # Non-pdf extension
        valid, err = validate_pdf_file("malicious.exe", b"%PDF-1.4 header content")
        self.assertFalse(valid)
        self.assertIn("Invalid file extension", err)

        # Empty payload
        valid, err = validate_pdf_file("empty.pdf", b"")
        self.assertFalse(valid)
        self.assertIn("empty", err.lower())

        # Invalid magic bytes (plain text renamed to .pdf)
        valid, err = validate_pdf_file("fake.pdf", b"Hello world this is not a PDF")
        self.assertFalse(valid)
        self.assertIn("Missing standard %PDF- magic signature", err)

        # Size limit exceeding
        oversized = b"%PDF-" + b"0" * 100
        valid, err = validate_pdf_file("huge.pdf", oversized, max_size_bytes=50)
        self.assertFalse(valid)
        self.assertIn("exceeds maximum allowed limit", err)

    def test_sanitize_filename_traversal_defense(self):
        """Ensure filenames strip traversal paths and illegal characters."""
        self.assertEqual(sanitize_filename("../../etc/passwd.pdf"), "passwd.pdf")
        self.assertEqual(sanitize_filename("..\\..\\windows\\system32.pdf"), "system32.pdf")
        self.assertEqual(sanitize_filename("My Research Paper (2026)!?.pdf"), "My_Research_Paper__2026___.pdf")
        self.assertEqual(sanitize_filename(".hidden.pdf"), "hidden.pdf")
        self.assertEqual(sanitize_filename("no_extension"), "no_extension.pdf")

    def test_save_and_ingest_pdf_success_and_cache(self):
        """Test end-to-end ingestion: text extraction, chunking, and disk caching."""
        with patch("backend.embeddings.embedding_cache._CACHE_DIR", self.cache_dir):

            result = save_and_ingest_pdf(
                filename="uploaded_paper.pdf",
                content=self.valid_pdf_bytes,
                docs_dir=self.docs_dir,
                embed_immediately=True,
                model=self.mock_model,
            )

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["filename"], "uploaded_paper.pdf")
            self.assertEqual(result["doc_id"], "doc-uploaded_paper.pdf")
            self.assertTrue(result["cached"])
            self.assertGreater(result["num_chunks"], 0)

            saved_file = self.docs_dir / "uploaded_paper.pdf"
            self.assertTrue(saved_file.exists())
            self.assertEqual(saved_file.stat().st_size, len(self.valid_pdf_bytes))

            # Verify that embedding cache file exists
            file_hash = compute_file_hash(self.valid_pdf_bytes)
            cache_file = self.cache_dir / f"{file_hash}.npy"
            self.assertTrue(cache_file.exists())

            # Load cached embedding and verify vector shape and normalization
            cached_vec = np.load(cache_file)
            self.assertEqual(cached_vec.shape, (768,))
            self.assertAlmostEqual(float(np.linalg.norm(cached_vec)), 1.0, places=4)

    def test_duplicate_pdf_detection_by_hash(self):
        """Uploading an identical PDF content should return duplicate status without duplicating files."""
        with patch("backend.embeddings.embedding_cache._CACHE_DIR", self.cache_dir):

            # First upload
            res1 = save_and_ingest_pdf(
                filename="first.pdf",
                content=self.valid_pdf_bytes,
                docs_dir=self.docs_dir,
                embed_immediately=True,
                model=self.mock_model,
            )
            self.assertEqual(res1["status"], "success")

            # Second upload of same content with a different name
            res2 = save_and_ingest_pdf(
                filename="second_copy.pdf",
                content=self.valid_pdf_bytes,
                docs_dir=self.docs_dir,
                embed_immediately=True,
                model=self.mock_model,
            )
            self.assertEqual(res2["status"], "duplicate")
            self.assertEqual(res2["filename"], "first.pdf")

            # Verify only one file exists on disk
            pdf_files = list(self.docs_dir.glob("*.pdf"))
            self.assertEqual(len(pdf_files), 1)

    def test_corrupted_pdf_graceful_rejection(self):
        """Corrupted PDF that has PDF header but fails text parsing must be rejected and cleaned up."""
        corrupted_bytes = b"%PDF-1.4 corrupted broken structure %%EOF"
        result = save_and_ingest_pdf(
            filename="corrupt.pdf",
            content=corrupted_bytes,
            docs_dir=self.docs_dir,
            embed_immediately=True,
            model=self.mock_model,
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("no extractable text", result["message"].lower())
        self.assertFalse((self.docs_dir / "corrupt.pdf").exists())

    def test_delete_document_and_cleanup(self):
        """Test document deletion and state cleanup."""
        # Create a document file
        doc_file = self.docs_dir / "to_delete.pdf"
        doc_file.write_bytes(self.valid_pdf_bytes)
        self.assertTrue(doc_file.exists())

        # Create dummy state file with mapping
        state_file = self.temp_dir / "cluster_mapping.json"
        state_file.write_text('{"cluster-1": ["doc-to_delete.pdf", "doc-other.pdf"]}', encoding="utf-8")

        deleted = delete_document_file("to_delete.pdf", docs_dir=self.docs_dir, state_file=state_file)
        self.assertTrue(deleted)
        self.assertFalse(doc_file.exists())

        # Check state file pruned
        import json
        state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["cluster-1"], ["doc-other.pdf"])

    def test_api_upload_endpoint_integration(self):
        """Test FastAPI POST /api/documents/upload and DELETE /api/documents/{filename}."""
        client = TestClient(app)

        with patch("backend.api.main.SAMPLE_DOCS_DIR", self.docs_dir), \
             patch("backend.embeddings.embedding_cache._CACHE_DIR", self.cache_dir), \
             patch("backend.api.main._get_model", return_value=self.mock_model):

            # 1. Upload valid PDF
            files = [
                ("files", ("test_upload_paper.pdf", io.BytesIO(self.valid_pdf_bytes), "application/pdf")),
                ("files", ("invalid_file.txt", io.BytesIO(b"not a pdf"), "text/plain")),
            ]

            response = client.post("/api/documents/upload", files=files)
            self.assertEqual(response.status_code, 200)
            data = response.json()

            self.assertEqual(data["total_uploaded"], 1)
            self.assertEqual(data["total_skipped"], 1)
            self.assertEqual(data["uploaded"][0]["filename"], "test_upload_paper.pdf")
            self.assertEqual(data["skipped"][0]["status"], "error")

            # 2. Check GET /api/documents lists the uploaded file
            list_res = client.get("/api/documents")
            self.assertEqual(list_res.status_code, 200)
            docs = list_res.json()["documents"]
            self.assertTrue(any(d["filename"] == "test_upload_paper.pdf" for d in docs))

            # 3. Delete the uploaded file via DELETE /api/documents/{filename}
            del_res = client.delete("/api/documents/test_upload_paper.pdf")
            self.assertEqual(del_res.status_code, 200)
            self.assertTrue(del_res.json()["deleted"])

            # 4. Deleting non-existent file returns 404
            del_res_404 = client.delete("/api/documents/non_existent.pdf")
            self.assertEqual(del_res_404.status_code, 404)


if __name__ == "__main__":
    unittest.main()
