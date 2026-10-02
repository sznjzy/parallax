"""
backend/ingestion/ingest.py

Robust PDF Ingestion, Validation, and Embedding Caching Pipeline for Parallax.

Public API
----------
    validate_pdf_file(filename: str, content: bytes, max_size_bytes: int = 50 * 1024 * 1024) -> tuple[bool, str | None]
    sanitize_filename(filename: str) -> str
    compute_file_hash(content: bytes) -> str
    save_and_ingest_pdf(filename: str, content: bytes, docs_dir: Path, embed_immediately: bool = True, model: Any = None) -> dict
    delete_document_file(filename: str, docs_dir: Path, state_file: Path | None = None) -> bool
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from backend.embeddings.pipeline import (
    extract_text_from_pdf,
    chunk_text,
    embed_document_chunks,
    load_model,
    MODEL_NAME,
)
from backend.embeddings.embedding_cache import (
    save_cached_embedding,
    get_cached_embedding,
    is_cached,
    save_cached_text,
)
from backend.clustering.constraints import remove_constraint

logger = logging.getLogger(__name__)

# Max PDF upload size: 50 MB
MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024
PDF_MAGIC_BYTES = b"%PDF-"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and invalid character injection.
    Only allows alphanumeric, underscore, hyphen, and period.
    """
    base_name = Path(filename).name.strip()
    # Normalize extension to lowercase .pdf
    if not base_name.lower().endswith(".pdf"):
        base_name = f"{base_name}.pdf"
    
    stem = base_name[:-4]
    # Replace non-alphanumeric/dash/underscore with underscore
    clean_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", stem)
    # Remove leading dots or dashes
    clean_stem = clean_stem.lstrip("._-")
    if not clean_stem:
        clean_stem = "document"

    return f"{clean_stem}.pdf"


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hex digest of file bytes."""
    return hashlib.sha256(content).hexdigest()


def validate_pdf_file(
    filename: str,
    content: bytes,
    max_size_bytes: int = MAX_PDF_SIZE_BYTES,
) -> tuple[bool, str | None]:
    """
    Validate uploaded PDF file properties.
    Checks:
      - Non-empty byte payload
      - File size <= max_size_bytes
      - Filename ends in .pdf
      - Magic bytes header contains b'%PDF-' in first 1024 bytes
    """
    if not content or len(content) == 0:
        return False, "File is empty (0 bytes)."

    if len(content) > max_size_bytes:
        mb_limit = max_size_bytes // (1024 * 1024)
        return False, f"File size exceeds maximum allowed limit of {mb_limit}MB."

    if not filename.lower().endswith(".pdf"):
        return False, f"Invalid file extension: '{filename}'. Only .pdf files are accepted."

    # Validate PDF magic header
    header_chunk = content[:1024]
    if PDF_MAGIC_BYTES not in header_chunk:
        return False, "Invalid PDF header: Missing standard %PDF- magic signature."

    return True, None


def find_existing_by_hash(docs_dir: Path, target_hash: str) -> Path | None:
    """Check if any existing PDF in docs_dir has the same SHA-256 hash."""
    if not docs_dir.exists():
        return None
    for pdf_file in docs_dir.glob("*.pdf"):
        try:
            with open(pdf_file, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()
                if h == target_hash:
                    return pdf_file
        except Exception:
            continue
    return None


def save_and_ingest_pdf(
    filename: str,
    content: bytes,
    docs_dir: Path,
    embed_immediately: bool = True,
    model: Any = None,
) -> dict:
    """
    Process, validate, safely store, and cache an uploaded PDF.

    Returns dict with status and metadata:
      {
        "filename": str,
        "doc_id": str,
        "size_bytes": int,
        "sha256": str,
        "num_chunks": int,
        "cached": bool,
        "status": "success" | "duplicate" | "error",
        "message": str | None
      }
    """
    is_valid, err = validate_pdf_file(filename, content)
    if not is_valid:
        return {
            "filename": filename,
            "doc_id": None,
            "size_bytes": len(content),
            "sha256": compute_file_hash(content) if content else "",
            "num_chunks": 0,
            "cached": False,
            "status": "error",
            "message": err,
        }

    file_hash = compute_file_hash(content)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Check content-based duplicate
    existing_file = find_existing_by_hash(docs_dir, file_hash)
    if existing_file is not None:
        doc_id = f"doc-{existing_file.name}"
        cached = is_cached(existing_file)
        return {
            "filename": existing_file.name,
            "doc_id": doc_id,
            "size_bytes": len(content),
            "sha256": file_hash,
            "num_chunks": 0,
            "cached": cached,
            "status": "duplicate",
            "message": f"Document already exists as '{existing_file.name}'.",
        }

    # Sanitize and disambiguate filename if name collision exists with different hash
    clean_name = sanitize_filename(filename)
    target_path = docs_dir / clean_name
    if target_path.exists():
        stem = clean_name[:-4]
        clean_name = f"{stem}_{file_hash[:8]}.pdf"
        target_path = docs_dir / clean_name

    # Write file to destination
    try:
        target_path.write_bytes(content)
    except Exception as exc:
        return {
            "filename": clean_name,
            "doc_id": None,
            "size_bytes": len(content),
            "sha256": file_hash,
            "num_chunks": 0,
            "cached": False,
            "status": "error",
            "message": f"Failed to save file: {exc}",
        }

    # Extract text
    text = extract_text_from_pdf(target_path)
    if not text.strip():
        # Clean up unparseable PDF to prevent corrupting corpus
        target_path.unlink(missing_ok=True)
        return {
            "filename": clean_name,
            "doc_id": None,
            "size_bytes": len(content),
            "sha256": file_hash,
            "num_chunks": 0,
            "cached": False,
            "status": "error",
            "message": "PDF contains no extractable text or is password-protected/corrupted.",
        }

    save_cached_text(target_path, text)

    chunks = chunk_text(text, max_words=400)
    if not chunks:
        target_path.unlink(missing_ok=True)
        return {
            "filename": clean_name,
            "doc_id": None,
            "size_bytes": len(content),
            "sha256": file_hash,
            "num_chunks": 0,
            "cached": False,
            "status": "error",
            "message": "Text could not be divided into valid chunks.",
        }

    doc_id = f"doc-{clean_name}"
    cached = False

    # Immediate embedding computation to populate disk cache
    if embed_immediately:
        try:
            if model is None:
                model = load_model()
            canvas_vec, _ = embed_document_chunks(model, chunks)
            save_cached_embedding(target_path, canvas_vec)
            cached = True
            logger.info("Embedded and cached %s (SHA: %s)", clean_name, file_hash[:8])
        except Exception as exc:
            logger.warning("Failed to immediately embed %s: %s", clean_name, exc)

    return {
        "filename": clean_name,
        "doc_id": doc_id,
        "size_bytes": len(content),
        "sha256": file_hash,
        "num_chunks": len(chunks),
        "cached": cached,
        "status": "success",
        "message": "Document ingested and cached successfully.",
    }


def delete_document_file(
    filename: str,
    docs_dir: Path,
    state_file: Path | None = None,
) -> bool:
    """
    Safely delete a document file, prune associated user constraints and cluster mapping state.
    """
    clean_name = sanitize_filename(filename)
    target_path = docs_dir / clean_name
    
    deleted = False
    if target_path.exists() and target_path.is_file():
        target_path.unlink()
        deleted = True
        logger.info("Deleted document file %s", clean_name)

    doc_id = f"doc-{clean_name}"
    
    # Remove any constraint associated with this doc
    remove_constraint(doc_id)

    # Prune from cluster_mapping.json if present
    if state_file is not None and state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            modified = False
            for cluster_id, doc_ids in list(state.items()):
                if doc_id in doc_ids:
                    state[cluster_id] = [d for d in doc_ids if d != doc_id]
                    modified = True
            if modified:
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                logger.info("Pruned %s from state file %s", doc_id, state_file.name)
        except Exception as exc:
            logger.warning("Failed to prune state file: %s", exc)

    return deleted
