import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Any

try:
    from sentence_transformers import SentenceTransformer
    import pypdf
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install -r requirements.txt")
    SentenceTransformer = pypdf = None

MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"

@dataclass
class EmbeddingOutput:
    doc_id: str
    embedding: list[float]
    model_name: str
    normalized: bool
    source_type: str

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF, logging failures explicitly."""
    text_chunks = []
    try:
        if pypdf is None:
            raise ImportError("pypdf is not installed")
        
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_chunks.append(text)
        return "\n\n".join(text_chunks)
    except Exception as e:
        print(f"  [FAIL] Could not parse PDF {pdf_path.name}: {e}")
        return ""

def chunk_text(text: str, max_words: int = 400) -> list[str]:
    """
    Very basic chunking logic.
    embedding-pipeline SKILL.md Rule 2: chunk documents longer than ~2 pages.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def load_model() -> Any:
    """Load the single authorized embedding model (SKILL.md Rule 1)."""
    if SentenceTransformer is None:
        raise ImportError("sentence_transformers is not installed")
    print(f"Loading embedding model: {MODEL_NAME}...")
    return SentenceTransformer(MODEL_NAME)

def generate_embeddings(model: Any, texts: list[str]) -> np.ndarray:
    """Generate and L2-normalize embeddings (SKILL.md Rule 3)."""
    # encode() often returns a numpy array, but we ensure it and normalize
    embeddings = model.encode(texts, convert_to_numpy=True)
    # L2 Normalization
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    normalized_embeddings = embeddings / norms
    return normalized_embeddings
