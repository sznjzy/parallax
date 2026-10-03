/**
 * SelectedNodeBar.jsx
 *
 * Floating action bar that appears when a node is selected on the canvas.
 * Provides instant options to open/view the PDF document in the same browser,
 * open in a new tab, or inspect cluster details.
 */
import React from 'react'
import { useApp } from '../state/AppContext'
import { clusterColor } from '../canvas/clusterColor'

export default function SelectedNodeBar() {
  const { state, dispatch } = useApp()

  if (!state.selectedDocId) return null

  const node = state.nodes.find(n => n.doc_id === state.selectedDocId)
  if (!node) return null

  const filename = node.doc_id.replace(/^doc-/, '')
  const color = clusterColor(node.cluster_id)
  const isNoise = node.cluster_id.startsWith('noise-') || node.cluster_id === 'noise' || node.cluster_id === 'unassigned' || node.cluster_id === 'cluster-unassigned'
  const match = state.searchResults?.results?.find(
    r => r.doc_id === node.doc_id || r.filename === filename || r.doc_id === `doc-${filename}`
  )

  const basePdfUrl = `/api/documents/${encodeURIComponent(filename)}/pdf`
  const hashParts = []
  if (match?.page_number && match.page_number > 1) {
    hashParts.push(`page=${match.page_number}`)
  }
  const highlight = match?.highlight_term || (match?.match_type === 'exact' ? state.searchResults?.query : null)
  if (highlight) {
    hashParts.push(`search=${encodeURIComponent(highlight)}`)
  }
  const pdfUrl = hashParts.length > 0 ? `${basePdfUrl}#${hashParts.join('&')}` : basePdfUrl

  const handleOpenModal = () => {
    dispatch({
      type: 'VIEW_DOCUMENT',
      filename,
      doc_id: node.doc_id,
      page: match?.page_number || 1,
      highlightTerm: highlight,
      searchMatch: match || null,
    })
  }

  const handleDeselect = () => {
    dispatch({ type: 'SELECT_NODE', doc_id: null })
  }

  return (
    <div className="selected-node-bar" role="region" aria-label="Selected Document Actions">
      {/* Left: Document Info */}
      <div className="selected-node-info">
        <div className="selected-node-text">
          <span className="selected-node-filename" title={filename}>
            {filename}
          </span>
          <div className="selected-node-sub" style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
            <span
              className="badge"
              style={{
                fontSize: '0.65rem',
                padding: '1px 6px',
                background: isNoise ? 'var(--color-surface-2)' : `${color}18`,
                color: isNoise ? 'var(--color-text-muted)' : color,
                borderColor: isNoise ? 'var(--color-border)' : `${color}40`,
                fontFamily: 'var(--font-mono)',
                fontWeight: isNoise ? 600 : 400,
              }}
            >
              {isNoise ? 'Outlier' : node.cluster_id}
            </span>
            {match && (
              <span
                className="badge"
                style={{
                  fontSize: '0.62rem',
                  padding: '1px 6px',
                  background: match.match_type === 'exact' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(88, 166, 255, 0.15)',
                  color: match.match_type === 'exact' ? '#22c55e' : 'var(--color-accent)',
                  borderColor: match.match_type === 'exact' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(88, 166, 255, 0.3)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {Math.round(match.similarity_score * 100)}% Match{match.page_number ? ` • P.${match.page_number}` : ''}
              </span>
            )}
            {node.is_boundary_document && (
              <span className="badge badge-warning" style={{ fontSize: '0.6rem', padding: '1px 5px' }}>
                Boundary
              </span>
            )}
            {node.is_anchored && (
              <span className="badge badge-accent" style={{ fontSize: '0.6rem', padding: '1px 5px' }}>
                Pinned
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="selected-node-actions">
        {/* Open PDF Viewer Modal */}
        <button
          id="btn-open-pdf-modal"
          className="btn btn-primary btn-sm"
          onClick={handleOpenModal}
          title="Open and read PDF document in canvas viewer"
        >
          <PdfDocIcon />
          <span>Open PDF</span>
        </button>

        {/* Open in New Browser Tab */}
        <a
          id="btn-open-pdf-external"
          href={pdfUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-ghost btn-sm"
          title="Open PDF in a new browser tab"
        >
          <ExternalIcon />
          <span>New Tab</span>
        </a>

        {/* Deselect / Close */}
        <button
          className="btn btn-ghost btn-icon btn-sm"
          onClick={handleDeselect}
          title="Deselect document"
          aria-label="Deselect document"
        >
          <CloseIcon />
        </button>
      </div>
    </div>
  )
}

function PdfDocIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <line x1="10" y1="9" x2="8" y2="9" />
    </svg>
  )
}

function ExternalIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
