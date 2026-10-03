"""
backend/search/__init__.py

Semantic search package for Parallax.
"""
from backend.search.semantic_search import search_corpus, SearchResult, SearchResponse

__all__ = ["search_corpus", "SearchResult", "SearchResponse"]
