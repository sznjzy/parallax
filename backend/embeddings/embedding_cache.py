"""
backend/embeddings/embedding_cache.py

Disk-based embedding cache for the Parallax pipeline.

Each PDF is hashed (SHA-256 of its raw bytes).  If a .npy file for that hash
already exists in the cache directory, the stored vector is returned directly
— no model inference needed.  This makes re-runs with the same PDFs nearly
instant (<1 ms vs 3–5 s per document).

Public API
----------
    get_cached_embedding(pdf_path: Path) -> np.ndarray | None
        Return the cached canvas vector, or None if not cached.

    save_cached_embedding(pdf_path: Path, vec: np.ndarray) -> None
        Persist a canvas vector for the given PDF.

    is_cached(pdf_path: Path) -> bool
        Quick check — True if a cache entry exists for this PDF.

    cache_stats(pdf_paths: list[Path]) -> dict
        Return {"total": N, "cached": M, "uncached": K} for a list of PDFs.

Cache location
--------------
    data/embedding_cache/<sha256>.npy
    (gitignored — regenerates automatically)
"""

import hashlib
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache lives next to the data/ folder — two levels up from this file,
# then into data/embedding_cache/.
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "embedding_cache"


def _ensure_cache_dir() -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def _cache_key(pdf_path: Path) -> str:
    """SHA-256 of the PDF's raw bytes — changes iff the file content changes."""
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        # Read in 64 KB chunks to avoid loading huge PDFs into memory at once.
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _cache_path(pdf_path: Path) -> Path:
    return _ensure_cache_dir() / f"{_cache_key(pdf_path)}.npy"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_cached(pdf_path: Path) -> bool:
    """Return True if this PDF already has a cached embedding."""
    try:
        return _cache_path(pdf_path).exists()
    except Exception:
        return False


def get_cached_embedding(pdf_path: Path) -> "np.ndarray | None":
    """
    Load and return the cached canvas vector for *pdf_path*, or None if
    no cache entry exists.
    """
    try:
        p = _cache_path(pdf_path)
        if p.exists():
            vec = np.load(p)
            logger.debug("Cache HIT  %s", pdf_path.name)
            return vec
        logger.debug("Cache MISS %s", pdf_path.name)
        return None
    except Exception as exc:
        logger.warning("Cache read error for %s: %s — re-embedding", pdf_path.name, exc)
        return None


def save_cached_embedding(pdf_path: Path, vec: np.ndarray) -> None:
    """Persist *vec* (canvas vector) for *pdf_path*."""
    try:
        p = _cache_path(pdf_path)
        np.save(p, vec)
        logger.debug("Cache SAVE %s → %s", pdf_path.name, p.name)
    except Exception as exc:
        logger.warning("Cache write error for %s: %s — continuing without cache", pdf_path.name, exc)


def cache_stats(pdf_paths: list) -> dict:
    """
    Return a summary dict:
        {"total": N, "cached": M, "uncached": K, "filenames_cached": [...]}
    Useful for the /api/documents endpoint.
    """
    cached = []
    uncached = []
    for p in pdf_paths:
        if is_cached(p):
            cached.append(p.name)
        else:
            uncached.append(p.name)
    return {
        "total": len(pdf_paths),
        "cached": len(cached),
        "uncached": len(uncached),
        "filenames_cached": cached,
    }
