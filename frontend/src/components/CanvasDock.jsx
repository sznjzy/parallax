/**
 * CanvasDock.jsx
 *
 * Floating canvas toolbar anchored at bottom center of the Parallax workspace.
 * Minimal scientific software dock:
 *   [ ▶ Run Analysis ]   │   [ ↗ Fit View ]   │   [ ⋯ Overflow Menu ]
 */
import React, { useState, useRef, useEffect } from 'react'
import { useApp } from '../state/AppContext'
import { useOrganize } from '../hooks/useOrganize'

export default function CanvasDock({ onRun, isRunning: propIsRunning }) {
  const { state, dispatch } = useApp()
  const { run: hookRun, rerunLayout, isRunning: hookIsRunning, isRerunningLayout } = useOrganize()
  const run = onRun || hookRun
  const isRunning = propIsRunning !== undefined ? propIsRunning : hookIsRunning
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  // Close menu on click outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [menuOpen])

  const handleExportPng = () => {
    setMenuOpen(false)
    window.dispatchEvent(new CustomEvent('parallax:export-png'))
  }

  const handleExportJson = () => {
    setMenuOpen(false)
    const exportData = {
      timestamp: new Date().toISOString(),
      nodes: state.nodes,
      topics: state.topics,
      evaluation: state.evaluation,
      constraints: state.constraints,
    }
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `parallax-export-${Date.now()}.json`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const handleRecenter = () => {
    setMenuOpen(false)
    window.dispatchEvent(new CustomEvent('parallax:recenter'))
  }

  return (
    <div className="canvas-dock" role="toolbar" aria-label="Canvas Actions">
      {/* Primary Action: Run Analysis */}
      <button
        id="btn-run-analysis"
        className="canvas-dock-primary-btn"
        onClick={() => run()}
        disabled={isRunning || isRerunningLayout}
        title="Execute semantic clustering & physics layout pipeline"
        aria-label="Run Semantic Pipeline"
      >
        {isRunning ? (
          <span className="dock-spinner" />
        ) : (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
        )}
        <span>{isRunning ? 'Running Analysis…' : 'Run Analysis'}</span>
      </button>

      <div className="canvas-dock-separator" />

      {/* Recenter / Fit View Button */}
      <button
        className="canvas-dock-icon-btn"
        onClick={handleRecenter}
        title="Fit & Recenter Canvas"
        aria-label="Fit View"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="15 3 21 3 21 9" />
          <polyline points="9 21 3 21 3 15" />
          <line x1="21" y1="3" x2="14" y2="10" />
          <line x1="3" y1="21" x2="10" y2="14" />
        </svg>
      </button>

      {/* Overflow Menu Button */}
      <div style={{ position: 'relative' }} ref={menuRef}>
        <button
          className={`canvas-dock-icon-btn ${menuOpen ? 'active' : ''}`}
          onClick={() => setMenuOpen(!menuOpen)}
          title="More actions"
          aria-label="More Canvas Options"
          aria-expanded={menuOpen}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="1.5" />
            <circle cx="19" cy="12" r="1.5" />
            <circle cx="5" cy="12" r="1.5" />
          </svg>
        </button>

        {menuOpen && (
          <div className="canvas-dock-dropdown" role="menu">
            <button
              id="btn-rerun-layout"
              className="canvas-dock-dropdown-item"
              onClick={() => {
                setMenuOpen(false)
                rerunLayout()
              }}
              disabled={isRunning || isRerunningLayout || state.nodes.length === 0}
              role="menuitem"
            >
              {isRerunningLayout ? (
                <span className="dock-spinner-dark" />
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                </svg>
              )}
              <span>{isRerunningLayout ? 'Rerunning Layout…' : 'Rerun Physics Layout'}</span>
            </button>

            <button
              className="canvas-dock-dropdown-item"
              onClick={handleExportPng}
              disabled={state.nodes.length === 0}
              role="menuitem"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
              <span>Export Canvas PNG</span>
            </button>

            <button
              className="canvas-dock-dropdown-item"
              onClick={handleExportJson}
              disabled={state.nodes.length === 0}
              role="menuitem"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <span>Export Layout JSON</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
