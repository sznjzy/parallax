/**
 * DocumentInspector.jsx
 *
 * Reading-first contextual inspector for a selected document node.
 * Quiet, academic design with clean typography and progressive disclosure.
 */
import React, { useState } from 'react'
import { useApp } from '../state/AppContext'
import { useConstraints } from '../hooks/useConstraints'
import { useDocuments } from '../hooks/useDocuments'
import { clusterColor } from '../canvas/clusterColor'

export default function DocumentInspector({ onClose }) {
  const { state, dispatch } = useApp()
  const { addConstraint, removeConstraint } = useConstraints()
  const { deleteDoc } = useDocuments()

  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(true)
  const [constraintsOpen, setConstraintsOpen] = useState(false)
  const [showConfirmDelete, setShowConfirmDelete] = useState(false)
  const [showMoreMenu, setShowMoreMenu] = useState(false)

  const node = state.nodes.find(n => n.doc_id === state.selectedDocId)
  if (!node) {
    return (
      <div className="inspector-panel">
        <div className="inspector-header">
          <span className="inspector-eyebrow">DOCUMENT</span>
          <button className="inspector-close-btn" onClick={onClose} aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
          </button>
        </div>
        <div className="inspector-empty">
          <p>Select a document node on the canvas to inspect evidence.</p>
        </div>
      </div>
    )
  }

  const filename = node.doc_id.replace(/^doc-/, '')
  const isOutlier = node.cluster_id === 'noise' || node.cluster_id.startsWith('noise-')
  const clr = isOutlier ? 'var(--color-text-muted)' : clusterColor(node.cluster_id)
  const topicData = state.topics?.[node.cluster_id]
  const displayTopic = isOutlier ? 'Outlier / Unclustered' : (topicData?.topic_label || `Cluster ${node.cluster_id.slice(0, 8)}`)
  const keywords = topicData?.top_terms || []

  // Check if constrained
  const currentConstraint = state.constraints.find(c => c.doc_id === node.doc_id)

  // Search match
  const searchMatch = state.searchResults?.results?.find(r => r.doc_id === node.doc_id)

  const handleReadPdf = () => {
    dispatch({
      type: 'VIEW_DOCUMENT',
      filename,
      doc_id: node.doc_id,
      page: searchMatch?.page_number || 1,
      highlightTerm: searchMatch?.highlight_term || (searchMatch?.match_type === 'exact' ? state.searchResults?.query : null),
      searchMatch: searchMatch || null,
    })
  }

  const handleOpenNewTab = () => {
    window.open(`/api/documents/${filename}`, '_blank')
  }

  const handleDelete = async () => {
    await deleteDoc(filename)
    setShowConfirmDelete(false)
    dispatch({ type: 'SET_WORKSPACE_MODE', mode: null })
  }

  return (
    <div className="inspector-panel" role="region" aria-label={`Document Inspector for ${filename}`}>
      {/* Header */}
      <div className="inspector-header">
        <span className="inspector-eyebrow">DOCUMENT</span>
        <button className="inspector-close-btn" onClick={onClose} title="Close inspector (Esc)" aria-label="Close Inspector">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </div>

      <div className="inspector-scrollable">
        {/* Document Title */}
        <div className="inspector-section">
          <h2 className="doc-title" title={filename}>{filename}</h2>
          <div className="doc-meta-row">
            <span className="doc-cluster-indicator" style={{ backgroundColor: clr }} />
            <span className="doc-meta-label">Topic:</span>
            <span className="doc-meta-value">{displayTopic}</span>
          </div>

          {keywords.length > 0 && (
            <div className="doc-keywords-text">
              {keywords.slice(0, 5).join(' · ')}
            </div>
          )}
        </div>

        {/* Primary & Secondary Actions */}
        <div className="inspector-actions-row">
          <button className="btn btn-primary btn-block" onClick={handleReadPdf}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
            <span>Read PDF</span>
          </button>

          <div className="doc-secondary-actions">
            <button className="btn btn-secondary btn-sm" onClick={handleOpenNewTab} title="Open PDF in new browser tab">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              <span>New Tab</span>
            </button>

            <div style={{ position: 'relative' }}>
              <button
                className="btn btn-secondary btn-sm btn-icon"
                onClick={() => setShowMoreMenu(!showMoreMenu)}
                title="More document actions"
                aria-label="More actions"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/><circle cx="5" cy="12" r="1.5"/></svg>
              </button>

              {showMoreMenu && (
                <div className="doc-overflow-menu" role="menu">
                  <button
                    className="doc-overflow-item danger"
                    onClick={() => {
                      setShowMoreMenu(false)
                      setShowConfirmDelete(true)
                    }}
                    role="menuitem"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    <span>Delete Document</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="inspector-divider" />

        {/* Collapsible Section 1: Search Relevance (if active) */}
        {searchMatch && (
          <div className="inspector-collapsible">
            <button
              className="collapsible-header"
              onClick={() => setSearchOpen(!searchOpen)}
              aria-expanded={searchOpen}
            >
              <span className="collapsible-title">Search Relevance</span>
              <span className="collapsible-tag">{Math.round(searchMatch.similarity_score * 100)}% Match</span>
              <svg className={`collapsible-arrow ${searchOpen ? 'open' : ''}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
            </button>

            {searchOpen && (
              <div className="collapsible-body">
                <div className="metric-item">
                  <span className="metric-label">Match Type:</span>
                  <span className="metric-val">{searchMatch.match_type === 'exact' ? 'Exact Match' : searchMatch.match_type === 'partial' ? 'Keyword Match' : 'Semantic Similarity'}</span>
                </div>
                {searchMatch.page_number && (
                  <div className="metric-item">
                    <span className="metric-label">Page Location:</span>
                    <span className="metric-val">Page {searchMatch.page_number}</span>
                  </div>
                )}
                {searchMatch.snippet && (
                  <div className="doc-snippet-box">
                    &ldquo;{searchMatch.snippet}&rdquo;
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Collapsible Section 2: Evidence & Classification */}
        <div className="inspector-collapsible">
          <button
            className="collapsible-header"
            onClick={() => setEvidenceOpen(!evidenceOpen)}
            aria-expanded={evidenceOpen}
          >
            <span className="collapsible-title">Evidence & Classification</span>
            <svg className={`collapsible-arrow ${evidenceOpen ? 'open' : ''}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
          </button>

          {evidenceOpen && (
            <div className="collapsible-body">
              <div className="metric-item">
                <span className="metric-label">Cluster ID:</span>
                <span className="metric-val monospace">{node.cluster_id}</span>
              </div>
              <div className="metric-item">
                <span className="metric-label">Classification:</span>
                <span className="metric-val">{isOutlier ? 'Noise / Outlier' : 'Core Cluster Member'}</span>
              </div>
              {node.is_boundary && (
                <div className="metric-item">
                  <span className="metric-label">Topology:</span>
                  <span className="metric-val">Cluster Boundary</span>
                </div>
              )}
              {node.secondary_cluster && (
                <div className="metric-item">
                  <span className="metric-label">Secondary Cluster:</span>
                  <span className="metric-val monospace">{node.secondary_cluster}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Collapsible Section 3: Constraints */}
        <div className="inspector-collapsible">
          <button
            className="collapsible-header"
            onClick={() => setConstraintsOpen(!constraintsOpen)}
            aria-expanded={constraintsOpen}
          >
            <span className="collapsible-title">Constraint Status</span>
            <span className="collapsible-tag">{currentConstraint ? 'User Constrained' : 'Automatic'}</span>
            <svg className={`collapsible-arrow ${constraintsOpen ? 'open' : ''}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
          </button>

          {constraintsOpen && (
            <div className="collapsible-body">
              {currentConstraint ? (
                <div>
                  <div className="metric-item">
                    <span className="metric-label">Target Cluster:</span>
                    <span className="metric-val monospace">{currentConstraint.forced_cluster_id || currentConstraint.cluster_id}</span>
                  </div>
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ marginTop: 8 }}
                    onClick={() => removeConstraint(node.doc_id)}
                  >
                    Remove Manual Constraint
                  </button>
                </div>
              ) : (
                <p className="doc-subtle-hint">
                  Hold <strong>Shift</strong> while dragging this node on the canvas to manually assign it to a different cluster.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showConfirmDelete && (
        <div className="confirm-modal-backdrop">
          <div className="confirm-modal-card">
            <h3 className="confirm-title">Delete Document</h3>
            <p className="confirm-text">
              Are you sure you want to remove <strong>{filename}</strong> from the corpus?
            </p>
            <div className="confirm-actions">
              <button className="btn btn-secondary" onClick={() => setShowConfirmDelete(false)}>Cancel</button>
              <button className="btn btn-danger" onClick={handleDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
