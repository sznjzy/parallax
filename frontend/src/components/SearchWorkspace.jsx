/**
 * SearchWorkspace.jsx
 *
 * Polished research search results inspector.
 * Renders ranked documents with similarity scores, match locations, and excerpt snippets.
 */
import React from 'react'
import { useApp } from '../state/AppContext'
import { useSearch } from '../hooks/useSearch'
import { clusterColor } from '../canvas/clusterColor'

export default function SearchWorkspace({ onClose }) {
  const { state, dispatch } = useApp()
  const { clearSearch } = useSearch()

  const results = state.searchResults?.results || []
  const query = state.searchResults?.query || state.searchQuery

  return (
    <div className="inspector-panel" role="region" aria-label="Search Workspace">
      {/* Header */}
      <div className="inspector-header">
        <div>
          <span className="inspector-eyebrow">WORKSPACE</span>
          <h2 className="inspector-title">Semantic Search</h2>
        </div>
        <button className="inspector-close-btn" onClick={onClose} title="Close inspector (Esc)" aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </div>

      {!state.searchActive || results.length === 0 ? (
        <div className="inspector-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.4 }}>
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <p>Type a research concept or keyword into the search bar (or press <kbd>/</kbd>) to rank the corpus.</p>
        </div>
      ) : (
        <div className="inspector-scrollable">
          {/* Query Summary Bar */}
          <div className="search-query-summary">
            <span className="search-summary-text">
              &ldquo;{query}&rdquo; · <span className="search-count">{results.length} results</span>
            </span>
            <button className="btn-link" onClick={clearSearch}>Clear</button>
          </div>

          {/* Results List */}
          <div className="search-result-list">
            {results.map((res) => {
              const isSelected = state.selectedDocId === res.doc_id
              const isOutlier = res.cluster_id === 'noise' || res.cluster_id.startsWith('noise-')
              const clr = isOutlier ? 'var(--color-text-muted)' : clusterColor(res.cluster_id)
              const pct = Math.round(res.similarity_score * 100)
              const displayTopic = isOutlier ? 'Outlier' : res.topic_label

              return (
                <div
                  key={res.doc_id}
                  className={`search-result-row ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    dispatch({ type: 'SELECT_NODE', doc_id: res.doc_id })
                    dispatch({
                      type: 'VIEW_DOCUMENT',
                      filename: res.filename,
                      doc_id: res.doc_id,
                      page: res.page_number || 1,
                      highlightTerm: res.highlight_term || (res.match_type === 'exact' ? query : null),
                      searchMatch: res,
                    })
                  }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      dispatch({ type: 'SELECT_NODE', doc_id: res.doc_id })
                      dispatch({
                        type: 'VIEW_DOCUMENT',
                        filename: res.filename,
                        doc_id: res.doc_id,
                        page: res.page_number || 1,
                        highlightTerm: res.highlight_term || (res.match_type === 'exact' ? query : null),
                        searchMatch: res,
                      })
                    }
                  }}
                >
                  {/* Row Top: Rank + Title + Score */}
                  <div className="search-row-header">
                    <span className="search-rank">#{res.rank}</span>
                    <span className="search-filename truncate" title={res.filename}>
                      {res.filename}
                    </span>
                    <span className="search-pct font-mono">{pct}%</span>
                  </div>

                  {/* Row Meta: Match type, Page, Topic */}
                  <div className="search-row-meta">
                    <span className="search-meta-pill">
                      {res.match_type === 'exact' ? `Exact · Pg ${res.page_number}` : res.match_type === 'partial' ? `Keyword · Pg ${res.page_number}` : 'Semantic Match'}
                    </span>
                    <span className="search-topic-text truncate" style={{ color: clr }}>
                      {displayTopic}
                    </span>
                  </div>

                  {/* Excerpt Snippet */}
                  {res.snippet && (
                    <div className="search-snippet truncate-2">
                      &ldquo;{res.snippet}&rdquo;
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
