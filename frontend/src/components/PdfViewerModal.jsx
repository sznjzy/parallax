/**
 * PdfViewerModal.jsx
 *
 * Full-featured in-browser PDF reader modal.
 * Opens when a user selects a node and chooses "Open PDF", double-clicks a node,
 * or clicks the view icon next to a paper in the documents list.
 *
 * Capabilities:
 *  - Native in-browser PDF rendering inside an iframe/embed
 *  - Direct "Open in New Tab" button (opens in the same browser in a new tab)
 *  - "Download PDF" button
 *  - Quick cluster tag indicator
 *  - Keyboard shortcut (ESC) to dismiss
 */
import React, { useState, useEffect } from 'react'
import { useApp } from '../state/AppContext'
import { clusterColor } from '../canvas/clusterColor'

export default function PdfViewerModal() {
  const { state, dispatch } = useApp()
  const filename = state.viewingDoc
  const [isLoading, setIsLoading] = useState(true)

  // Find node metadata for this document if present on canvas
  const matchingNode = state.nodes.find(
    n => n.doc_id === filename || n.doc_id === `doc-${filename}` || n.doc_id.replace(/^doc-/, '') === filename
  )
  const clusterId = matchingNode?.cluster_id
  const color = clusterId ? clusterColor(clusterId) : 'var(--color-accent)'

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

  // Reset loading spinner on filename change
  useEffect(() => {
    setIsLoading(true)
  }, [filename])

  if (!filename) return null

  const pdfUrl = `/api/documents/${encodeURIComponent(filename)}/pdf`
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
              <h2 id="pdf-modal-title" className="pdf-modal-filename" title={displayName}>
                {displayName}
              </h2>
              {clusterId && (
                <span
                  className="badge"
                  style={{
                    fontSize: '0.7rem',
                    padding: '1px 7px',
                    background: clusterId.startsWith('noise-') ? 'var(--color-surface-2)' : `${color}18`,
                    color: clusterId.startsWith('noise-') ? 'var(--color-text-muted)' : color,
                    borderColor: clusterId.startsWith('noise-') ? 'var(--color-border)' : `${color}40`,
                    fontFamily: 'var(--font-mono)',
                    marginTop: 3,
                    alignSelf: 'flex-start',
                  }}
                >
                  {clusterId.startsWith('noise-') ? 'Noise outlier' : clusterId}
                </span>
              )}
            </div>
          </div>

          <div className="pdf-modal-actions">
            {/* Open in new browser tab */}
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost btn-sm"
              title="Open PDF in a new browser tab"
              id="btn-open-pdf-tab"
            >
              <ExternalLinkIcon />
              <span>Open in New Tab</span>
            </a>

            {/* Download */}
            <a
              href={pdfUrl}
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

        {/* Modal Body / Viewer */}
        <div className="pdf-modal-body">
          {isLoading && (
            <div className="pdf-loading-overlay">
              <div className="pdf-spinner" />
              <span>Loading {displayName}…</span>
            </div>
          )}

          <iframe
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
