/**
 * useSearch.js
 *
 * Hook for semantic search across corpus document embeddings.
 * Interacts with POST /api/search.
 */

import { useCallback, useRef } from 'react'
import { useApp } from '../state/AppContext'

export function useSearch() {
  const { state, dispatch } = useApp()
  const latestQueryRef = useRef('')

  const clearSearch = useCallback(() => {
    latestQueryRef.current = ''
    dispatch({ type: 'CLEAR_SEARCH' })
  }, [dispatch])

  const search = useCallback(async (query, top_k = null) => {
    const trimmed = query ? query.trim() : ''
    latestQueryRef.current = trimmed
    if (!trimmed) {
      clearSearch()
      return null
    }

    dispatch({ type: 'SET_SEARCH_QUERY', query: trimmed })
    dispatch({ type: 'SET_SEARCHING', isSearching: true })

    if (state.mockMode) {
      // Mock search mode for offline preview / testing
      const queryWords = trimmed.toLowerCase().split(/\s+/).filter(Boolean)
      const mockResults = state.nodes.map((n, idx) => {
        const name = n.doc_id.toLowerCase()
        const wordMatch = queryWords.some(w => name.includes(w))
        const baseSim = wordMatch ? 0.82 - idx * 0.04 : 0.35 - idx * 0.03
        const sim = Math.max(0.1, Math.min(0.98, baseSim))
        return {
          doc_id: n.doc_id,
          filename: n.doc_id.replace(/^doc-/, ''),
          similarity_score: sim,
          cluster_id: n.cluster_id,
          topic_label: state.topics?.[n.cluster_id]?.topic_label || `Topic ${n.cluster_id.slice(0, 6)}`,
          snippet: `Relevant excerpt matching query "${trimmed}" in ${n.doc_id}...`,
          rank: 0,
        }
      })

      mockResults.sort((a, b) => b.similarity_score - a.similarity_score)
      mockResults.forEach((r, i) => { r.rank = i + 1 })

      const clusterRelevance = {}
      mockResults.forEach(r => {
        if (!clusterRelevance[r.cluster_id]) {
          clusterRelevance[r.cluster_id] = {
            cluster_id: r.cluster_id,
            topic_label: r.topic_label,
            mean_similarity: r.similarity_score,
            max_similarity: r.similarity_score,
            matched_docs_count: 1,
          }
        }
      })

      const payload = {
        query: trimmed,
        results: top_k ? mockResults.slice(0, top_k) : mockResults,
        query_embedding_dim: 768,
        total_corpus_searched: state.nodes.length,
        cluster_relevance: clusterRelevance,
      }

      dispatch({ type: 'SET_SEARCH_RESULTS', results: payload })
      return payload
    }

    try {
      const body = {
        query: trimmed,
        top_k: top_k || null,
        filenames: state.selectedDocs?.size > 0 ? Array.from(state.selectedDocs) : null,
      }

      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Search failed with status ${response.status}`)
      }

      const data = await response.json()
      if (latestQueryRef.current === trimmed) {
        dispatch({ type: 'SET_SEARCH_RESULTS', results: data })
      }
      return data
    } catch (err) {
      console.error('[useSearch] Search error:', err)
      if (latestQueryRef.current === trimmed) {
        dispatch({ type: 'SET_SEARCHING', isSearching: false })
        dispatch({
          type: 'SET_STATUS',
          status: 'error',
          message: `Search failed: ${err.message}`,
        })
      }
      return null
    }
  }, [state.mockMode, state.nodes, state.topics, state.selectedDocs, dispatch, clearSearch])


  return {
    search,
    clearSearch,
    searchQuery: state.searchQuery || '',
    searchResults: state.searchResults,
    isSearching: state.isSearching,
    searchActive: state.searchActive,
  }
}
