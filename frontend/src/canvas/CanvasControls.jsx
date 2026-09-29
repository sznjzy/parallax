/**
 * CanvasControls.jsx
 *
 * Floating action button bar (bottom-right corner of the canvas).
 * Controls:
 *   - Run Pipeline  — triggers POST /api/organize
 *   - Rerun Layout  — re-triggers clustering & physics layout using cached embeddings
 *   - Export PNG    — download canvas screenshot
 *   - Export JSON   — download clusters and metrics dataset
 *   - Reset Zoom    — resets Stage transform via ref callback
 *   - Toggle Theme  — dark ↔ light
 *   - Mock badge    — visible indicator when running in mock mode
 *
 * Props
 * -----
 *   onRun         () => void
 *   onResetZoom   () => void
 *   isRunning     boolean
 */
import React from 'react'
import { useApp } from '../state/AppContext'

export default function CanvasControls({ onRun, onResetZoom, isRunning }) {
  const { state, dispatch } = useApp()

  const toggleTheme = () => {
    dispatch({ type: 'SET_THEME', theme: state.theme === 'dark' ? 'light' : 'dark' })
  }

  const exportPNG = () => {
    window.dispatchEvent(new CustomEvent('parallax-export-png'))
  }

  const exportJSON = () => {
    window.dispatchEvent(new CustomEvent('parallax-export-json'))
  }

  const hasNodes = state.nodes.length > 0

  return (
    <div className="canvas-controls">
      {/* Mock mode badge */}
      {state.mockMode && (
        <span className="badge badge-mock" style={{ alignSelf: 'flex-end', marginBottom: 4 }}>
          MOCK
        </span>
      )}

      {/* Primary: Run pipeline */}
      <button
        id="btn-run-pipeline"
        className="btn btn-primary"
        onClick={onRun}
        disabled={isRunning}
        title="Run embedding → clustering → layout pipeline"
      >
        {isRunning ? (
          <>
            <span className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
            Running…
          </>
        ) : (
          <>
            <RunIcon />
            Run Pipeline
          </>
        )}
      </button>

      {/* Rerun Layout */}
      {hasNodes && (
        <button
          id="btn-rerun-layout"
          className="btn btn-secondary"
          onClick={onRun}
          disabled={isRunning}
          title="Re-run clustering and force-directed layout"
        >
          <ShuffleIcon />
          Rerun Layout
        </button>
      )}

      {/* Export PNG */}
      {hasNodes && (
        <button
          id="btn-export-png"
          className="btn btn-ghost btn-icon"
          onClick={exportPNG}
          title="Export Canvas as High-Res PNG"
        >
          <ImageIcon />
        </button>
      )}

      {/* Export JSON */}
      {hasNodes && (
        <button
          id="btn-export-json"
          className="btn btn-ghost btn-icon"
          onClick={exportJSON}
          title="Export Clusters & Metrics as JSON"
        >
          <CodeIcon />
        </button>
      )}

      {/* Reset zoom */}
      <button
        id="btn-reset-zoom"
        className="btn btn-secondary btn-icon"
        onClick={onResetZoom}
        title="Reset zoom and pan to fit all nodes"
      >
        <ResetIcon />
      </button>

      {/* Theme toggle */}
      <button
        id="btn-toggle-theme"
        className="btn btn-ghost btn-icon"
        onClick={toggleTheme}
        title={`Switch to ${state.theme === 'dark' ? 'light' : 'dark'} theme`}
      >
        {state.theme === 'dark' ? <SunIcon /> : <MoonIcon />}
      </button>
    </div>
  )
}

/* ── Inline SVG icons ─────────────────────────────────────────────── */
function RunIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
      <path d="M8 5v14l11-7z"/>
    </svg>
  )
}

function ShuffleIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/>
    </svg>
  )
}

function ImageIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
      <circle cx="8.5" cy="8.5" r="1.5"/>
      <polyline points="21 15 16 10 5 21"/>
    </svg>
  )
}

function CodeIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="16 18 22 12 16 6"/>
      <polyline points="8 6 2 12 8 18"/>
    </svg>
  )
}

function ResetIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
      <path d="M3 3v5h5"/>
    </svg>
  )
}

function SunIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="5"/>
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  )
}
