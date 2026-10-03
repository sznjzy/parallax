/**
 * PdfViewerModal.jsx
 *
 * Full-featured in-browser PDF reader modal with deterministic search-to-highlight navigation.
 * Opens when a user clicks a search result in the sidebar, selects a node and chooses
 * "Open PDF", double-clicks a canvas node, or clicks view in the documents list.
 *
 * Capabilities:
 *  - Native in-browser PDF rendering with standard URL fragment `#page=N&search=phrase`
 *  - Deterministic page jumping and query highlighting
 *  - Grounded match excerpt banner with visual highlight
 *  - Direct "Open in New Tab" button preserving page & search query parameters
 *  - "Download PDF" button
 *  - Outlier / Cluster tag indicator
 *  - Keyboard shortcut (ESC) to dismiss
 */
import React, { useState, useEffect } from 'react'
import { useApp } from '../state/AppContext'
import { clusterColor } from '../canvas/clusterColor'

function HighlightedSnippet({ text, term, query }) {
  if (!text) return null
  const target = term || query
  if (!target || !target.trim()) return <span>{text}</span>

  const escaped = target.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'))

  return (
    <span>
      {parts.map((part, i) =>
        part.toLowerCase() === target.trim().toLowerCase() ? (
          <mark
            key={i}
            style={{
              background: 'rgba(250, 204, 21, 0.4)',
              color: '#fef08a',
              padding: '1px 4px',
              borderRadius: 3,
              fontWeight: 700,
              border: '1px solid rgba(250, 204, 21, 0.6)',
            }}
          >
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </span>
  )
}

export default function PdfViewerModal() {
  const { state, dispatch } = useApp()
  const filename = state.viewingDoc
  const [isLoading, setIsLoading] = useState(true)

  // Find node metadata for this document if present on canvas
  const matchingNode = state.nodes.find(
    n => n.doc_id === filename || n.doc_id === `doc-${filename}` || n.doc_id.replace(/^doc-/, '') === filename
  )
  const clusterId = matchingNode?.cluster_id
  const isOutlier = clusterId ? (
    clusterId.startsWith('noise-') || clusterId === 'noise' || clusterId === 'unassigned' || clusterId === 'cluster-unassigned'
  ) : false
  const color = clusterId ? clusterColor(clusterId) : 'var(--color-accent)'

  const match = state.viewerMatch
  const page = state.viewerPage || match?.page_number || 1
  const highlight = state.viewerHighlight || match?.highlight_term || (match?.match_type === 'exact' ? state.searchResults?.query : null)

  // Close on Escape key
  useEffect(() => {
    if (!filename) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        dispatch({ type: 'CLOSE_DOCUMENT_VIEWER' })
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [filename, dispatch])

  // Reset loading spinner on filename or page change
  useEffect(() => {
    setIsLoading(true)
  }, [filename, page, highlight])

  if (!filename) return null

  const basePdfUrl = `/api/documents/${encodeURIComponent(filename)}/pdf`
  const hashParts = []
  if (page && page > 1) {
    hashParts.push(`page=${page}`)
  }
  if (highlight) {
    hashParts.push(`search=${encodeURIComponent(highlight)}`)
  }
  const pdfUrl = hashParts.length > 0 ? `${basePdfUrl}#${hashParts.join('&')}` : basePdfUrl
  const displayName = filename.replace(/^doc-/, '')

  return (
    <div
      className="pdf-modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          dispatch({ type: 'CLOSE_DOCUMENT_VIEWER' })
        }
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="pdf-modal-title"
    >
      <div className="pdf-modal-container">
        {/* Modal Header */}
        <div className="pdf-modal-header">
          <div className="pdf-modal-title-group">
            <div className="pdf-file-icon" aria-hidden="true">
              <PdfIcon />
            </div>
            <div className="pdf-modal-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <h2 id="pdf-modal-title" className="pdf-modal-filename" title={displayName} style={{ margin: 0 }}>
                  {displayName}
                </h2>
                {clusterId && (
                  <span
                    className="badge"
                    style={{
                      fontSize: '0.68rem',
                      padding: '1px 7px',
                      background: isOutlier ? 'var(--color-surface-2)' : `${color}18`,
                      color: isOutlier ? 'var(--color-text-muted)' : color,
                      borderColor: isOutlier ? 'var(--color-border)' : `${color}40`,
                      fontFamily: 'var(--font-mono)',
                      fontWeight: isOutlier ? 600 : 400,
                    }}
                  >
                    {isOutlier ? 'Outlier' : clusterId}
                  </span>
                )}
                {match && (
                  <span
                    className="badge"
                    style={{
                      fontSize: '0.68rem',
                      padding: '1px 7px',
                      background: match.match_type === 'exact' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(88, 166, 255, 0.15)',
                      color: match.match_type === 'exact' ? '#22c55e' : 'var(--color-accent)',
                      borderColor: match.match_type === 'exact' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(88, 166, 255, 0.3)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    #{match.rank} Match • {Math.round(match.similarity_score * 100)}% Relevance
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="pdf-modal-actions">
            {/* Open in new browser tab */}
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost btn-sm"
              title="Open PDF in a new browser tab with page and search parameters"
              id="btn-open-pdf-tab"
            >
              <ExternalLinkIcon />
              <span>Open in New Tab</span>
            </a>

            {/* Download */}
            <a
              href={basePdfUrl}
              download={displayName}
              className="btn btn-ghost btn-sm"
              title="Download PDF"
            >
              <DownloadIcon />
              <span>Download</span>
            </a>

            {/* Close Button */}
            <button
              className="btn btn-ghost btn-icon"
              onClick={() => dispatch({ type: 'CLOSE_DOCUMENT_VIEWER' })}
              title="Close viewer (Esc)"
              aria-label="Close PDF viewer"
              id="btn-close-pdf-modal"
            >
              <CloseIcon />
            </button>
          </div>
        </div>

        {/* Search Match Highlight Excerpt Banner */}
        {match && (
          <div
            style={{
              padding: '8px 16px',
              background: 'rgba(88, 166, 255, 0.08)',
              borderBottom: '1px solid var(--color-border)',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
              fontSize: '0.78rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span
                  style={{
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    padding: '1px 6px',
                    borderRadius: 3,
                    background: match.match_type === 'exact' ? '#22c55e' : 'var(--color-accent)',
                    color: '#0d1117',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {match.match_type === 'exact' ? 'Exact Match' : match.match_type === 'partial' ? 'Keyword Match' : 'Semantic Match'}
                </span>
                <span style={{ color: 'var(--color-text)', fontWeight: 600 }}>
                  Page {page}
                </span>
                {match.match_count > 0 && (
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '0.72rem' }}>
                    ({match.match_count} {match.match_count === 1 ? 'occurrence' : 'occurrences'} in document)
                  </span>
                )}
              </div>
              {(highlight || state.searchResults?.query) && (
                <span style={{ color: 'var(--color-text-muted)', fontSize: '0.72rem', fontStyle: 'italic' }}>
                  Query: &ldquo;{state.searchResults?.query || highlight}&rdquo;
                </span>
              )}
            </div>

            {match.snippet && (
              <div
                style={{
                  color: 'var(--color-text-subtle)',
                  fontSize: '0.74rem',
                  lineHeight: 1.4,
                  marginTop: 2,
                  fontFamily: 'var(--font-sans)',
                }}
              >
                &ldquo;
                <HighlightedSnippet
                  text={match.snippet}
                  term={match.highlight_term}
                  query={state.searchResults?.query}
                />
                &rdquo;
              </div>
            )}
          </div>
        )}

        {/* Modal Body / Viewer */}
        <div className="pdf-modal-body">
          {isLoading && (
            <div className="pdf-loading-overlay">
              <div className="pdf-spinner" />
              <span>Loading {displayName} (Page {page})…</span>
            </div>
          )}

          <iframe
            key={pdfUrl}
            src={pdfUrl}
            title={`PDF Document: ${displayName}`}
            className="pdf-iframe"
            onLoad={() => setIsLoading(false)}
          />
        </div>
      </div>
    </div>
  )
}

/* ── SVG Icons ──────────────────────────────────────────────────────── */
function PdfIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <line x1="10" y1="9" x2="8" y2="9" />
    </svg>
  )
}

function ExternalLinkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
