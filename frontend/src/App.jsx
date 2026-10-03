/**
 * App.jsx
 *
 * Root application component. Owns the overall layout and orchestrates
 * the top-level data fetching flow on mount.
 *
 * Layout
 * ------
 *   ┌─────────────────────────────────────┐
 *   │  TopBar (logo + status pill)        │  52px
 *   ├──────────┬──────────────────────────┤
 *   │ Sidebar  │   Canvas (dot-grid bg)   │
 *   │ Metrics  │   ResearchCanvas         │
 *   │ Evaluat. │   StatusBanner (overlay) │
 *   │          │   CanvasControls         │
 *   └──────────┴──────────────────────────┘
 */
import React, { useEffect, useCallback, useState } from 'react'
import { useApp } from './state/AppContext'
import { useOrganize } from './hooks/useOrganize'
import { useConstraints } from './hooks/useConstraints'
import { useDocuments } from './hooks/useDocuments'
import { useToast } from './components/ConstraintToast'

import ResearchCanvas from './canvas/ResearchCanvas'
import CanvasControls from './canvas/CanvasControls'
import EvaluationPanel from './components/EvaluationPanel'
import StatusBanner from './components/StatusBanner'
import PdfViewerModal from './components/PdfViewerModal'
import SearchBar from './components/SearchBar'

export default function App() {
  const { state, dispatch } = useApp()
  const { run, isRunning }  = useOrganize()
  const { fetchConstraints } = useConstraints()
  const { fetchDocuments }   = useDocuments()
  const { showToast }       = useToast()

  // ── On mount: check backend status + load constraints + doc list ───
  useEffect(() => {
    dispatch({ type: 'SET_STATUS', status: 'loading', message: 'Checking backend…' })

    if (state.mockMode) {
      // In mock mode, skip the health check.
      dispatch({ type: 'SET_STATUS', status: 'idle' })
      fetchConstraints()
      return
    }

    fetch('/api/status')
      .then(r => r.json())
      .then(data => {
        if (data.state === 'ready') {
          dispatch({ type: 'SET_STATUS', status: 'idle' })
        } else if (data.state === 'no_documents') {
          dispatch({ type: 'SET_STATUS', status: 'error', message: `No PDFs found in ${data.docs_folder}. Add PDFs and restart.` })
        } else {
          dispatch({ type: 'SET_STATUS', status: 'error', message: 'Backend dependencies missing. Check requirements.txt.' })
        }
      })
      .catch(() => {
        dispatch({ type: 'SET_STATUS', status: 'error', message: 'Backend not reachable — start uvicorn first.' })
      })

    fetchConstraints()
    fetchDocuments()   // populate the document selector sidebar
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Constraint added callback ──────────────────────────────────────
  const handleConstraintAdded = useCallback((doc_id, cluster_id) => {
    showToast({ docId: doc_id, clusterId: cluster_id })
  }, [showToast])

  // ── Sidebar collapsed state ────────────────────────────────────────
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="app-shell" data-theme={state.theme}>
      {/* ── Top bar ─────────────────────────────────────────────── */}
      <header className="app-topbar" role="banner">
        <div className="app-logo">
          Parallax
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', fontWeight: 400, marginLeft: 4 }}>
            Semantic Research Canvas
          </span>
        </div>

        {/* Semantic Search Bar */}
        <SearchBar />

        <div className="app-topbar-actions">
          {/* Cluster count pill */}
          {state.evaluation && (
            <span className="badge badge-accent">
              {state.evaluation.num_clusters} clusters · {state.nodes.length} docs
            </span>
          )}

          {/* Silhouette score in topbar for quick glance */}
          {state.evaluation?.silhouette_score != null && (
            <span
              className={`badge ${state.evaluation.silhouette_score >= 0.25 ? 'badge-success' : 'badge-warning'}`}
              title="Silhouette score — target > 0.25"
            >
              SS {state.evaluation.silhouette_score.toFixed(3)}
            </span>
          )}

          {/* Sidebar toggle */}
          <button
            id="btn-sidebar-toggle"
            className="btn btn-ghost btn-icon"
            onClick={() => setSidebarOpen(o => !o)}
            title={sidebarOpen ? 'Hide metrics panel' : 'Show metrics panel'}
            aria-expanded={sidebarOpen}
            aria-controls="evaluation-panel"
          >
            {sidebarOpen ? <PanelCloseIcon /> : <PanelOpenIcon />}
          </button>
        </div>
      </header>

      {/* ── Main body ────────────────────────────────────────────── */}
      <div className="app-body">
        {/* Left sidebar */}
        <div className={`app-sidebar ${sidebarOpen ? '' : 'collapsed'}`}>
          <EvaluationPanel />
        </div>

        {/* Canvas area */}
        <main className="canvas-wrapper" role="main" aria-label="Research canvas">
          {/* Status overlay */}
          <StatusBanner onRetry={run} />

          {/* Konva canvas */}
          <ResearchCanvas onConstraintAdded={handleConstraintAdded} />

          {/* Floating controls */}
          <CanvasControls
            onRun={run}
            isRunning={isRunning}
            onResetZoom={() => {
              window.dispatchEvent(new CustomEvent('parallax-reset-zoom'))
            }}
          />
        </main>
      </div>

      {/* In-browser PDF Viewer Modal */}
      <PdfViewerModal />
    </div>
  )
}

/* ── Inline SVG icons ─────────────────────────────────────────────── */
function PanelCloseIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2"/>
      <path d="M9 3v18"/>
    </svg>
  )
}

function PanelOpenIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2"/>
      <path d="M9 3v18M15 9l3 3-3 3"/>
    </svg>
  )
}
