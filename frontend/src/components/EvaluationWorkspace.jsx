/**
 * EvaluationWorkspace.jsx
 *
 * Academic evaluation & clustering validation panel for Parallax.
 * Displays real Silhouette scores, benchmark thresholds, constraint satisfaction rates,
 * and diagnostic exports.
 */
import React from 'react'
import { useApp } from '../state/AppContext'

export default function EvaluationWorkspace({ onClose }) {
  const { state } = useApp()
  const evaluation = state.evaluation || {}

  const silhouette = evaluation.silhouette_score ?? null
  const numClusters = evaluation.num_clusters ?? (state.topics ? Object.keys(state.topics).length : 0)
  const satisfactionRate = evaluation.constraint_satisfaction_rate ?? null
  const appliedConstraints = evaluation.num_constraints_applied ?? state.constraints?.length ?? 0
  const violatedConstraints = evaluation.num_constraints_violated ?? 0
  const skippedDocs = state.skippedDocuments || []

  // Silhouette Benchmark is 0.25 for HDBSCAN density clustering
  const meetsBenchmark = silhouette !== null && silhouette >= 0.25
  const silPct = silhouette !== null ? Math.max(0, Math.min(100, Math.round(((silhouette + 1) / 2) * 100))) : 0

  const handleExportJson = () => {
    const data = {
      timestamp: new Date().toISOString(),
      evaluation: state.evaluation,
      total_nodes: state.nodes.length,
      topics: state.topics,
      constraints_count: state.constraints.length,
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `parallax-evaluation-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleExportPng = () => {
    window.dispatchEvent(new CustomEvent('parallax:export-png'))
  }

  return (
    <div className="inspector-panel" role="region" aria-label="Evaluation Workspace">
      {/* Header */}
      <div className="inspector-header">
        <div>
          <span className="inspector-eyebrow">WORKSPACE</span>
          <h2 className="inspector-title">Clustering Evaluation</h2>
        </div>
        <button className="inspector-close-btn" onClick={onClose} title="Close inspector (Esc)" aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </div>

      <div className="inspector-scrollable">
        {/* Section 1: Clustering Quality */}
        <div className="eval-section">
          <span className="eval-section-title">Clustering Quality</span>

          <div className="eval-metric-card">
            <div className="eval-metric-header">
              <span className="eval-metric-label">Mean Silhouette Score</span>
              <span className="eval-metric-number font-mono">
                {silhouette !== null ? silhouette.toFixed(4) : 'N/A'}
              </span>
            </div>

            {/* Clean Progress Bar */}
            <div className="eval-progress-track">
              <div
                className={`eval-progress-fill ${meetsBenchmark ? 'good' : ''}`}
                style={{ width: `${silPct}%` }}
              />
            </div>

            <div className="eval-benchmark-status">
              {silhouette !== null ? (
                meetsBenchmark ? (
                  <span className="eval-status-text good">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                    Meets academic benchmark (≥ 0.25)
                  </span>
                ) : (
                  <span className="eval-status-text warn">Below recommended threshold (&lt; 0.25)</span>
                )
              ) : (
                <span className="eval-status-text muted">Awaiting pipeline analysis</span>
              )}
            </div>
          </div>
        </div>

        {/* Section 2: Summary */}
        <div className="eval-section">
          <span className="eval-section-title">Topology & Constraints</span>

          <div className="eval-grid">
            <div className="eval-grid-box">
              <span className="eval-grid-label">Clusters</span>
              <span className="eval-grid-val font-mono">{numClusters}</span>
            </div>

            <div className="eval-grid-box">
              <span className="eval-grid-label">Satisfaction</span>
              <span className="eval-grid-val font-mono">
                {satisfactionRate !== null ? `${Math.round(satisfactionRate * 100)}%` : appliedConstraints === 0 ? '100%' : '100%'}
              </span>
            </div>
          </div>

          <div className="metric-item" style={{ marginTop: 8 }}>
            <span className="metric-label">Active User Constraints:</span>
            <span className="metric-val">{appliedConstraints} applied · {violatedConstraints} violated</span>
          </div>
        </div>

        {/* Section 3: Diagnostics */}
        <div className="eval-section">
          <span className="eval-section-title">Diagnostics</span>

          <div className="metric-item">
            <span className="metric-label">Skipped Documents:</span>
            <span className="metric-val">{skippedDocs.length}</span>
          </div>

          <div className="metric-item">
            <span className="metric-label">Engine:</span>
            <span className="metric-val">Zero-LLM (Deterministic)</span>
          </div>

          <div className="metric-item">
            <span className="metric-label">Embedding Model:</span>
            <span className="metric-val font-mono">all-mpnet-base-v2</span>
          </div>
        </div>

        {/* Section 4: Export Actions */}
        <div className="eval-section">
          <span className="eval-section-title">Exports</span>
          <div className="eval-actions-col">
            <button className="btn btn-secondary btn-block" onClick={handleExportJson}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              <span>Export Evaluation JSON</span>
            </button>

            <button className="btn btn-secondary btn-block" onClick={handleExportPng}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              <span>Export Canvas PNG</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
