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
import React, { useState } from 'react'
import { useApp } from '../state/AppContext'
import { useConstraints } from '../hooks/useConstraints'
import { clusterColor } from '../canvas/clusterColor'

export default function EvaluationPanel() {
  const { state, dispatch } = useApp()
  const { removeConstraint, clearAllConstraints } = useConstraints()
  const [skippedOpen, setSkippedOpen] = useState(false)
  const [constraintsOpen, setConstraintsOpen] = useState(true)
  const [docsOpen, setDocsOpen] = useState(false)

  const eval_ = state.evaluation

  const toggleDoc = (filename) => dispatch({ type: 'TOGGLE_DOC', filename })
  const selectAll = () => dispatch({ type: 'SELECT_ALL_DOCS' })
  const clearAll = () => dispatch({ type: 'CLEAR_ALL_DOCS' })

  const selectedCount = state.selectedDocs?.size ?? 0
  const totalDocs = state.availableDocs.length
  const allSelected = selectedCount === totalDocs && totalDocs > 0
  const noneSelected = selectedCount === 0

  return (
    <aside className="app-sidebar" id="evaluation-panel" aria-label="Evaluation metrics">
      <div className="sidebar-header">
        <span className="sidebar-title">Metrics</span>
        {state.mockMode && (
          <span className="badge badge-mock" style={{ fontSize: '0.65rem', padding: '1px 6px' }}>MOCK</span>
        )}
      </div>

      <div className="sidebar-body">

        {/* ── Document Selector ────────────────────────────────────── */}
        {state.availableDocs.length > 0 && (
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
                {/* Select All / Clear buttons */}
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
                          gap: 8,
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
        )}

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
        <Legend nodes={state.nodes} />
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

function Legend({ nodes }) {
  const clusters = [...new Set(nodes.filter(n => !n.cluster_id.startsWith('noise-')).map(n => n.cluster_id))]
  if (clusters.length === 0) return null

  return (
    <div className="glass-card">
      <div className="glass-card-title">Clusters</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {clusters.map(cid => {
          const count = nodes.filter(n => n.cluster_id === cid).length
          const clr = clusterColor(cid)
          const short = cid.replace('cluster-', '')
          return (
            <div key={cid} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
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
                }}
              >
                {short}
              </span>
              <span className="truncate monospace" style={{ fontSize: 'var(--text-xs)', flex: 1 }}>{cid}</span>
              <span className="badge badge-default" style={{ fontSize: '0.6rem', padding: '0 5px' }}>{count}</span>
            </div>
          )
        })}
        {nodes.filter(n => n.cluster_id.startsWith('noise-')).length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
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
            <span className="truncate" style={{ fontSize: 'var(--text-xs)', flex: 1, color: 'var(--color-text-subtle)' }}>noise</span>
            <span className="badge badge-default" style={{ fontSize: '0.6rem', padding: '0 5px' }}>
              {nodes.filter(n => n.cluster_id.startsWith('noise-')).length}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
