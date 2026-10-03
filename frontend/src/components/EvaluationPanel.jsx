/**
 * EvaluationPanel.jsx
 *
 * Left sidebar panel displaying:
 *   0. Document Selector — pick which PDFs to run through the pipeline
 *   1. Clustering Quality (Silhouette score, cluster count)
 *   2. Constraint Satisfaction (satisfaction rate, applied/violated counts)
 *   3. Active Constraints list
 *   4. Skipped Documents list
 *   5. Cluster Legend
 *
 * Evaluation axes (from the assignment brief):
 *   1. Silhouette score        → target > 0.25 (achieved 0.3175)
 *   2. Layout stability        → this metric is computed offline; not live
 *   3. Constraint satisfaction → target > 0.95 (null until constraints built)
 */
import React, { useState, useRef } from 'react'
import { useApp } from '../state/AppContext'
import { useConstraints } from '../hooks/useConstraints'
import { useDocuments } from '../hooks/useDocuments'
import { clusterColor } from '../canvas/clusterColor'

export default function EvaluationPanel() {
  const { state, dispatch } = useApp()
  const { removeConstraint, clearAllConstraints } = useConstraints()
  const { uploadDocuments, deleteDocument, isLoading: docsLoading, uploadStatus } = useDocuments()
  const fileInputRef = useRef(null)
  const [skippedOpen, setSkippedOpen] = useState(false)
  const [constraintsOpen, setConstraintsOpen] = useState(true)
  const [docsOpen, setDocsOpen] = useState(false)

  const eval_ = state.evaluation

  const toggleDoc = (filename) => dispatch({ type: 'TOGGLE_DOC', filename })
  const selectAll = () => dispatch({ type: 'SELECT_ALL_DOCS' })
  const clearAll = () => dispatch({ type: 'CLEAR_ALL_DOCS' })

  const handleFileUpload = async (e) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    try {
      await uploadDocuments(files)
    } catch (err) {
      console.error(err)
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDeleteDoc = async (e, filename) => {
    e.preventDefault()
    e.stopPropagation()
    if (window.confirm(`Delete ${filename} from corpus?`)) {
      await deleteDocument(filename)
    }
  }

  const selectedCount = state.selectedDocs?.size ?? 0
  const totalDocs = state.availableDocs.length
  const allSelected = selectedCount === totalDocs && totalDocs > 0
  const noneSelected = selectedCount === 0

  return (
    <aside className="evaluation-panel-content" id="evaluation-panel" aria-label="Evaluation metrics">
      <div className="sidebar-header">
        <span className="sidebar-title">Metrics</span>
        {state.mockMode && (
          <span className="badge badge-mock" style={{ fontSize: '0.65rem', padding: '1px 6px' }}>MOCK</span>
        )}
      </div>

      <div className="sidebar-body">

        {/* ── Semantic Search Results (Phase 6) ─────────────────── */}
        {state.searchActive && state.searchResults && (
          <div className="glass-card" style={{ border: '1px solid var(--color-accent)', background: 'rgba(88, 166, 255, 0.05)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span className="glass-card-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-accent)' }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                Search Results
                <span className="badge badge-accent" style={{ fontSize: '0.65rem', padding: '0 6px' }}>
                  {state.searchResults.results.length}
                </span>
              </span>
              <button
                className="btn btn-ghost"
                style={{ fontSize: '0.65rem', padding: '1px 6px', color: 'var(--color-text-muted)' }}
                onClick={() => dispatch({ type: 'CLEAR_SEARCH' })}
                title="Clear active search"
              >
                Clear
              </button>
            </div>

            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginBottom: 8, fontStyle: 'italic' }}>
              Query: &ldquo;{state.searchResults.query}&rdquo;
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 280, overflowY: 'auto' }}>
              {state.searchResults.results.map((res) => {
                const isSelected = state.selectedDocId === res.doc_id
                const isOutlier = res.cluster_id === 'noise' || res.cluster_id.startsWith('noise-') || res.cluster_id === 'unassigned' || res.cluster_id === 'cluster-unassigned'
                const clr = isOutlier ? 'var(--color-text-muted)' : clusterColor(res.cluster_id)
                const pct = Math.round(res.similarity_score * 100)
                const shortCid = isOutlier ? 'Outlier' : res.cluster_id.replace('cluster-', '').slice(0, 6)
                const displayTopic = isOutlier ? 'Outlier' : res.topic_label

                return (
                  <div
                    key={res.doc_id}
                    onClick={() => {
                      dispatch({ type: 'SELECT_NODE', doc_id: res.doc_id })
                      dispatch({
                        type: 'VIEW_DOCUMENT',
                        filename: res.filename,
                        doc_id: res.doc_id,
                        page: res.page_number || 1,
                        highlightTerm: res.highlight_term || (res.match_type === 'exact' ? state.searchResults?.query : null),
                        searchMatch: res,
                      })
                    }}
                    style={{
                      padding: '6px 8px',
                      borderRadius: 'var(--radius-sm)',
                      background: isSelected ? 'var(--color-surface-2)' : 'rgba(255,255,255,0.03)',
                      border: `1px solid ${isSelected ? 'var(--color-accent)' : 'var(--color-border)'}`,
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 4,
                      transition: 'all 0.15s ease',
                    }}
                    title={res.match_type === 'exact' ? `Exact match on Page ${res.page_number}` : `Semantic match (cosine similarity: ${pct}%)`}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flex: 1 }}>
                        <span
                          style={{
                            fontSize: '0.62rem',
                            fontWeight: 700,
                            color: res.rank <= 3 ? 'var(--color-accent)' : 'var(--color-text-muted)',
                            fontFamily: 'var(--font-mono)',
                            minWidth: 16,
                          }}
                        >
                          #{res.rank}
                        </span>
                        <span
                          className="truncate"
                          style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--color-text)' }}
                          title={res.filename}
                        >
                          {res.filename.replace('.pdf', '')}
                        </span>
                      </div>
                      <span
                        style={{
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          color: pct >= 60 ? 'var(--color-success)' : pct >= 40 ? 'var(--color-accent)' : 'var(--color-text-muted)',
                          fontFamily: 'var(--font-mono)',
                          flexShrink: 0,
                        }}
                      >
                        {pct}%
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span
                        style={{
                          fontSize: '0.58rem',
                          padding: '0 4px',
                          borderRadius: 3,
                          background: isOutlier ? 'var(--color-surface-2)' : `${clr}18`,
                          color: isOutlier ? 'var(--color-text-muted)' : clr,
                          border: `1px solid ${isOutlier ? 'var(--color-border)' : `${clr}40`}`,
                          fontFamily: 'var(--font-mono)',
                          fontWeight: isOutlier ? 600 : 400,
                        }}
                      >
                        {shortCid}
                      </span>
                      <span
                        className="truncate"
                        style={{ fontSize: '0.62rem', color: 'var(--color-text-subtle)', flex: 1 }}
                      >
                        {displayTopic}
                      </span>
                      {res.match_type === 'exact' ? (
                        <span
                          style={{
                            fontSize: '0.58rem',
                            padding: '1px 5px',
                            borderRadius: 3,
                            background: 'rgba(34, 197, 94, 0.15)',
                            color: '#22c55e',
                            border: '1px solid rgba(34, 197, 94, 0.3)',
                            fontFamily: 'var(--font-mono)',
                            flexShrink: 0,
                            fontWeight: 600,
                          }}
                          title={`Exact match found on Page ${res.page_number} (${res.match_count} occurrences)`}
                        >
                          Exact • Pg {res.page_number}
                        </span>
                      ) : res.match_type === 'partial' ? (
                        <span
                          style={{
                            fontSize: '0.58rem',
                            padding: '1px 5px',
                            borderRadius: 3,
                            background: 'rgba(217, 119, 6, 0.15)',
                            color: '#d97706',
                            border: '1px solid rgba(217, 119, 6, 0.3)',
                            fontFamily: 'var(--font-mono)',
                            flexShrink: 0,
                            fontWeight: 600,
                          }}
                          title={`Keyword match on Page ${res.page_number}`}
                        >
                          Keyword • Pg {res.page_number}
                        </span>
                      ) : (
                        <span
                          style={{
                            fontSize: '0.58rem',
                            padding: '1px 5px',
                            borderRadius: 3,
                            background: 'rgba(88, 166, 255, 0.12)',
                            color: 'var(--color-accent)',
                            border: '1px solid rgba(88, 166, 255, 0.25)',
                            fontFamily: 'var(--font-mono)',
                            flexShrink: 0,
                          }}
                          title="Semantic vector similarity match (concept relatedness)"
                        >
                          Semantic
                        </span>
                      )}
                    </div>

                    {res.snippet && (
                      <p
                        style={{
                          fontSize: '0.62rem',
                          color: 'var(--color-text-muted)',
                          lineHeight: 1.3,
                          margin: 0,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                        title={res.snippet}
                      >
                        {res.snippet}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {state.searchActive && state.searchResults && <div className="divider" />}

        {/* ── Document Selector & Upload ─────────────────────────── */}
        <div className="glass-card">
          <div
            className="collapse-header"
            onClick={() => setDocsOpen(o => !o)}
            id="collapse-docs"
            aria-expanded={docsOpen}
          >
            <span className="glass-card-title" style={{ margin: 0 }}>
              Documents&nbsp;
              <span className="badge badge-accent" style={{ fontSize: '0.65rem', padding: '0 6px' }}>
                {selectedCount}/{totalDocs}
              </span>
            </span>
            <span className={`collapse-arrow ${docsOpen ? 'open' : ''}`}>▶</span>
          </div>

          {docsOpen && (
            <div style={{ marginTop: 8 }}>
              {/* Upload PDF Section */}
              <div style={{ marginBottom: 8 }}>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  multiple
                  accept=".pdf,application/pdf"
                  style={{ display: 'none' }}
                  id="pdf-upload-input"
                />
                <button
                  className="btn btn-primary"
                  style={{ width: '100%', fontSize: '0.75rem', padding: '5px 8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                  onClick={() => fileInputRef.current?.click()}
                  disabled={docsLoading}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  {docsLoading ? 'Processing...' : 'Upload Research PDFs'}
                </button>
                {uploadStatus && (
                  <div style={{ fontSize: '0.7rem', color: 'var(--color-accent)', marginTop: 4, textAlign: 'center' }}>
                    {uploadStatus}
                  </div>
                )}
              </div>

              {/* Select All / Clear buttons */}
              {totalDocs > 0 && (
                <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                  <button
                    className="btn btn-ghost"
                    style={{ fontSize: '0.7rem', padding: '2px 8px', flex: 1 }}
                    onClick={selectAll}
                    disabled={allSelected}
                  >
                    Select All
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ fontSize: '0.7rem', padding: '2px 8px', flex: 1 }}
                    onClick={clearAll}
                    disabled={noneSelected}
                  >
                    Clear
                  </button>
                </div>
              )}

              {/* Doc list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 240, overflowY: 'auto' }}>
                {state.availableDocs.map(doc => {
                  const checked = state.selectedDocs?.has(doc.filename) ?? false
                  const label = doc.filename.replace('.pdf', '')
                  return (
                    <label
                      key={doc.filename}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '3px 6px',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        background: checked ? 'var(--color-surface-2)' : 'transparent',
                        border: `1px solid ${checked ? 'var(--color-border)' : 'transparent'}`,
                        transition: 'background 0.15s',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleDoc(doc.filename)}
                        style={{ accentColor: 'var(--color-accent)', cursor: 'pointer' }}
                      />
                      <span style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {label}
                      </span>
                      {doc.cached && (
                        <span
                          title="Embedding cached — will load instantly"
                          style={{
                            fontSize: '0.6rem',
                            padding: '1px 5px',
                            borderRadius: 999,
                            background: 'rgba(34,197,94,0.15)',
                            color: '#22c55e',
                            border: '1px solid rgba(34,197,94,0.3)',
                            flexShrink: 0,
                          }}
                        >
                          cached
                        </span>
                      )}
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon"
                        style={{ padding: 2, width: 20, height: 20, flexShrink: 0, opacity: 0.7 }}
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          dispatch({ type: 'VIEW_DOCUMENT', filename: doc.filename })
                        }}
                        title={`Open ${doc.filename} in PDF viewer`}
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <polyline points="14 2 14 8 20 8" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon"
                        style={{ padding: 2, width: 20, height: 20, flexShrink: 0, opacity: 0.6, color: 'var(--color-error)' }}
                        onClick={(e) => handleDeleteDoc(e, doc.filename)}
                        title={`Delete ${doc.filename}`}
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                    </label>
                  )
                })}
              </div>

              {noneSelected && (
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-error)', marginTop: 6, fontStyle: 'italic' }}>
                  Select at least one document to run the pipeline.
                </p>
              )}
            </div>
          )}
        </div>

        <div className="divider" />

        {/* ── Clustering Quality ─────────────────────────────────── */}
        <div className="glass-card">
          <div className="glass-card-title">Clustering Quality</div>

          {/* Silhouette Score */}
          <MetricRow
            label="Silhouette Score"
            value={eval_ ? eval_.silhouette_score?.toFixed(4) : null}
            target={0.25}
            max={1}
            good={v => v >= 0.25}
            hint="Target > 0.25. Achieved 0.3175 on 21 PDFs."
          />

          {/* Num Clusters */}
          <div className="metric-row">
            <div className="metric-label">
              <span>Clusters Found</span>
              <span className="metric-value">
                {eval_ ? eval_.num_clusters : '—'}
              </span>
            </div>
          </div>
        </div>

        <div className="divider" />

        {/* ── Constraint Satisfaction ────────────────────────────── */}
        <div className="glass-card">
          <div className="glass-card-title">Constraint Satisfaction</div>

          <MetricRow
            label="Satisfaction Rate"
            value={eval_?.constraint_satisfaction_rate != null
              ? (eval_.constraint_satisfaction_rate === 1.0 || eval_.constraint_satisfaction_rate === 1 ? '100%' : `${(eval_.constraint_satisfaction_rate * 100).toFixed(1)}%`)
              : null}
            target="95%"
            max={100}
            good={v => v >= 95}
            nullLabel="N/A — drag a node to create a constraint"
          />

          <div className="metric-row">
            <div className="metric-label">
              <span>Applied</span>
              <span className="metric-value">
                {eval_?.num_constraints_applied ?? <NullBadge />}
              </span>
            </div>
          </div>

          <div className="metric-row">
            <div className="metric-label">
              <span>Violated</span>
              <span className={`metric-value ${eval_?.num_constraints_violated > 0 ? 'warn' : ''}`}>
                {eval_?.num_constraints_violated ?? <NullBadge />}
              </span>
            </div>
          </div>
        </div>

        <div className="divider" />

        {/* ── Active Constraints ─────────────────────────────────── */}
        {(() => {
          const activeDocIds = new Set(state.nodes.map(n => n.doc_id))
          const activeConstraints = state.constraints.filter(c => activeDocIds.has(c.doc_id))
          const inactiveConstraints = state.constraints.filter(c => !activeDocIds.has(c.doc_id))

          return (
            <div className="glass-card">
              <div
                className="collapse-header"
                onClick={() => setConstraintsOpen(o => !o)}
                id="collapse-constraints"
                aria-expanded={constraintsOpen}
              >
                <span className="glass-card-title" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                  Constraints
                  <span className="badge badge-accent" style={{ fontSize: '0.65rem', padding: '0 6px' }}>
                    {state.nodes.length > 0 ? activeConstraints.length : state.constraints.length}
                  </span>
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {state.constraints.length > 0 && (
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: '0.65rem', padding: '1px 6px', color: 'var(--color-danger)' }}
                      onClick={(e) => {
                        e.stopPropagation()
                        clearAllConstraints()
                      }}
                      title="Remove all constraints"
                    >
                      Clear All
                    </button>
                  )}
                  <span className={`collapse-arrow ${constraintsOpen ? 'open' : ''}`}>▶</span>
                </div>
              </div>

              {constraintsOpen && (
                <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {state.constraints.length === 0 ? (
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-subtle)', fontStyle: 'italic' }}>
                      Hold <strong>Shift + drag</strong> a node to pin it to a new cluster.
                    </p>
                  ) : (
                    <>
                      {activeConstraints.map(c => (
                        <ConstraintRow
                          key={c.doc_id}
                          constraint={c}
                          onRemove={() => removeConstraint(c.doc_id)}
                        />
                      ))}
                      {inactiveConstraints.length > 0 && state.nodes.length > 0 && (
                        <div style={{ marginTop: 6, borderTop: '1px solid var(--color-border)', paddingTop: 4 }}>
                          <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>
                            Saved for other docs ({inactiveConstraints.length}):
                          </span>
                          {inactiveConstraints.map(c => (
                            <ConstraintRow
                              key={c.doc_id}
                              constraint={c}
                              isInactive
                              onRemove={() => removeConstraint(c.doc_id)}
                            />
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          )
        })()}

        <div className="divider" />

        {/* ── Skipped Documents ──────────────────────────────────── */}
        {state.skippedDocuments.length > 0 && (
          <div className="glass-card">
            <div
              className="collapse-header"
              onClick={() => setSkippedOpen(o => !o)}
              id="collapse-skipped"
              aria-expanded={skippedOpen}
            >
              <span className="glass-card-title" style={{ margin: 0 }}>
                Skipped&nbsp;
                <span className="badge badge-danger" style={{ fontSize: '0.65rem', padding: '0 6px' }}>
                  {state.skippedDocuments.length}
                </span>
              </span>
              <span className={`collapse-arrow ${skippedOpen ? 'open' : ''}`}>▶</span>
            </div>

            {skippedOpen && (
              <ul className="skipped-list" style={{ marginTop: 8 }}>
                {state.skippedDocuments.map((s, i) => (
                  <li key={i} className="skipped-item">
                    <span className="skipped-item-name">{s.filename}</span>
                    <span className="skipped-item-reason">{s.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* ── Legend ────────────────────────────────────────────── */}
        <Legend nodes={state.nodes} topics={state.topics} />
      </div>
    </aside>
  )
}

/* ── Sub-components ──────────────────────────────────────────────── */

function MetricRow({ label, value, target, max, good, hint, nullLabel }) {
  const numVal = parseFloat(value)
  const isNull = value == null
  const isGood = !isNull && good && good(numVal)
  const fillPct = isNull ? 0 : Math.min(100, (numVal / (max ?? 1)) * 100)

  return (
    <div className="metric-row">
      <div className="metric-label" title={hint}>
        <span>{label}</span>
        <span className={`metric-value ${isNull ? 'null' : isGood ? 'good' : 'warn'}`}>
          {isNull ? '—' : value}
          {!isNull && target != null && (
            <span style={{ marginLeft: 4, fontSize: '0.65rem', color: 'var(--color-text-subtle)' }}>
              / {target}†
            </span>
          )}
        </span>
      </div>
      <div className="progress-bar">
        <div
          className={`progress-fill ${isNull ? '' : isGood ? 'good' : 'warn'}`}
          style={{ width: `${fillPct}%` }}
        />
      </div>
      {isNull && nullLabel && (
        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-subtle)', marginTop: 3, fontStyle: 'italic' }}>
          {nullLabel}
        </p>
      )}
    </div>
  )
}

function NullBadge() {
  return <span className="badge badge-default" style={{ fontSize: '0.65rem' }}>null</span>
}

function ConstraintRow({ constraint, onRemove, isInactive }) {
  const label = constraint.doc_id.replace('doc-', '').replace('.pdf', '')
  const clr = clusterColor(constraint.forced_cluster_id)
  const clusterLabel = constraint.forced_cluster_id.replace('cluster-', '')
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '4px 6px', borderRadius: 'var(--radius-sm)',
      background: isInactive ? 'transparent' : 'var(--color-surface-2)',
      border: '1px solid var(--color-border)',
      opacity: isInactive ? 0.6 : 1.0,
      gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        <span
          style={{
            fontSize: '0.65rem',
            padding: '1px 5px',
            borderRadius: 'var(--radius-sm)',
            background: isInactive ? 'var(--color-surface)' : `${clr}18`,
            color: clr,
            border: `1px solid ${clr}40`,
            fontFamily: 'var(--font-mono)',
            flexShrink: 0,
          }}
        >
          {clusterLabel}
        </span>
        <span className="truncate" style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}>
          {label}
        </span>
        {isInactive && (
          <span style={{ fontSize: '0.6rem', color: 'var(--color-text-subtle)' }}>
            (unselected)
          </span>
        )}
      </div>
      <button
        className="btn btn-ghost btn-icon"
        style={{ width: 22, height: 22, minWidth: 22, fontSize: 10, padding: 0 }}
        onClick={onRemove}
        title="Remove constraint"
        aria-label={`Remove constraint for ${label}`}
      >
        ✕
      </button>
    </div>
  )
}

function Legend({ nodes, topics }) {
  const clusters = [...new Set(nodes.filter(n => !n.cluster_id.startsWith('noise-')).map(n => n.cluster_id))]
  if (clusters.length === 0) return null

  return (
    <div className="glass-card">
      <div className="glass-card-title">Clusters & Topics</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {clusters.map(cid => {
          const count = nodes.filter(n => n.cluster_id === cid).length
          const clr = clusterColor(cid)
          const short = cid.replace('cluster-', '').slice(0, 6)
          const topicInfo = topics?.[cid]
          const topicTitle = topicInfo?.topic_label || `Topic ${short}`
          const topKeywords = topicInfo?.top_terms?.slice(0, 3).join(', ')

          return (
            <div key={cid} style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '3px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span
                  style={{
                    fontSize: '0.65rem',
                    padding: '1px 5px',
                    borderRadius: 'var(--radius-sm)',
                    background: `${clr}18`,
                    color: clr,
                    border: `1px solid ${clr}40`,
                    fontFamily: 'var(--font-mono)',
                    minWidth: '22px',
                    textAlign: 'center',
                    flexShrink: 0,
                  }}
                  title={cid}
                >
                  {short}
                </span>
                <span
                  className="truncate"
                  style={{ fontSize: 'var(--text-xs)', fontWeight: 600, flex: 1, color: 'var(--color-text)' }}
                  title={topicTitle}
                >
                  {topicTitle}
                </span>
                <span className="badge badge-default" style={{ fontSize: '0.6rem', padding: '0 5px' }}>{count}</span>
              </div>
              {topKeywords && (
                <span
                  className="truncate"
                  style={{
                    fontSize: '0.62rem',
                    color: 'var(--color-text-subtle)',
                    paddingLeft: 28,
                    fontStyle: 'italic',
                  }}
                  title={topicInfo?.top_terms?.join(', ')}
                >
                  {topKeywords}
                </span>
              )}
            </div>
          )
        })}
        {nodes.filter(n => n.cluster_id.startsWith('noise-')).length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 4, borderTop: '1px solid var(--color-border)' }}>
            <span
              style={{
                fontSize: '0.65rem',
                padding: '1px 5px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--color-surface-2)',
                color: 'var(--color-text-subtle)',
                border: '1px solid var(--color-border)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              —
            </span>
            <span className="truncate" style={{ fontSize: 'var(--text-xs)', flex: 1, color: 'var(--color-text-subtle)' }}>
              Outliers (isolated noise)
            </span>
            <span className="badge badge-default" style={{ fontSize: '0.6rem', padding: '0 5px' }}>
              {nodes.filter(n => n.cluster_id.startsWith('noise-')).length}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
