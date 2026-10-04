/**
 * NavRail.jsx
 *
 * Collapsible research navigation rail for Parallax:
 * - Collapsed: 56px icon-only rail
 * - Hover / Pointer enter: Smoothly expands to 220px with labels & counts
 * - Smooth transition with cubic-bezier(0.22, 1, 0.36, 1)
 */
import React from 'react'
import { useApp } from '../state/AppContext'

export default function NavRail() {
  const { state, dispatch } = useApp()
  const { workspaceMode, searchActive, searchResults, availableDocs, selectedDocs, topics, nodes } = state

  const setMode = (mode) => {
    if (workspaceMode === mode) {
      dispatch({ type: 'SET_WORKSPACE_MODE', mode: null })
    } else {
      dispatch({ type: 'SET_WORKSPACE_MODE', mode })
    }
  }

  const matchCount = searchResults?.results?.length ?? 0
  const activeClusterCount = Object.keys(topics || {}).length || new Set(nodes.filter(n => !n.cluster_id.startsWith('noise-')).map(n => n.cluster_id)).size
  const totalDocs = availableDocs.length
  const selectedCount = selectedDocs?.size ?? 0

  return (
    <aside className="nav-rail-wrapper">
      <nav className="nav-rail" aria-label="Primary Navigation">
      {/* Top Section: Parallax Logo Mark + Title */}
      <div className="nav-rail-group">
        <button
          className="nav-rail-logo"
          onClick={() => dispatch({ type: 'SET_WORKSPACE_MODE', mode: null })}
          title="Parallax — Canvas Centerpiece"
          aria-label="Parallax Home"
        >
          <div className="nav-rail-icon-box">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 3a9 9 0 0 1 9 9" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </div>
          <span className="nav-rail-logo-text">PARALLAX</span>
        </button>

        <div className="nav-rail-divider" />

        {/* 1. Canvas Focus */}
        <button
          className={`nav-rail-item ${workspaceMode === null ? 'active' : ''}`}
          onClick={() => dispatch({ type: 'SET_WORKSPACE_MODE', mode: null })}
          title="Canvas (1)"
          aria-label="Canvas Workspace"
        >
          <div className="nav-rail-icon-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <circle cx="15.5" cy="8.5" r="1.5" />
              <circle cx="12" cy="15.5" r="1.5" />
            </svg>
          </div>
          <span className="nav-rail-item-label">Canvas</span>
          <span className="nav-rail-shortcut">1</span>
        </button>

        {/* 2. Semantic Search */}
        <button
          className={`nav-rail-item ${workspaceMode === 'search' ? 'active' : ''}`}
          onClick={() => setMode('search')}
          title="Semantic Search (2 or /)"
          aria-label="Search Workspace"
        >
          <div className="nav-rail-icon-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            {searchActive && matchCount > 0 && (
              <span className="nav-rail-dot-badge" />
            )}
          </div>
          <span className="nav-rail-item-label">Search</span>
          {searchActive && matchCount > 0 ? (
            <span className="nav-rail-count-badge">{matchCount}</span>
          ) : (
            <span className="nav-rail-shortcut">2</span>
          )}
        </button>

        {/* 3. Document Library */}
        <button
          className={`nav-rail-item ${workspaceMode === 'library' ? 'active' : ''}`}
          onClick={() => setMode('library')}
          title="Document Library (3)"
          aria-label="Library Workspace"
        >
          <div className="nav-rail-icon-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
              <path d="M6 6h10" />
              <path d="M6 10h10" />
            </svg>
            {totalDocs > 0 && (
              <span className="nav-rail-dot-badge" />
            )}
          </div>
          <span className="nav-rail-item-label">Library</span>
          {totalDocs > 0 ? (
            <span className="nav-rail-count-badge">{selectedCount}/{totalDocs}</span>
          ) : (
            <span className="nav-rail-shortcut">3</span>
          )}
        </button>

        {/* 4. Clusters & Topics */}
        <button
          className={`nav-rail-item ${workspaceMode === 'cluster' ? 'active' : ''}`}
          onClick={() => setMode('cluster')}
          title="Clusters & Topics (4)"
          aria-label="Clusters Workspace"
        >
          <div className="nav-rail-icon-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16.5 9.4 7.55 4.24a1.78 1.78 0 0 0-2.5 1.55v12.42a1.78 1.78 0 0 0 2.5 1.55L16.5 14.6a1.78 1.78 0 0 0 0-3.2z" />
              <circle cx="19" cy="12" r="2" />
            </svg>
            {activeClusterCount > 0 && (
              <span className="nav-rail-dot-badge" />
            )}
          </div>
          <span className="nav-rail-item-label">Clusters</span>
          {activeClusterCount > 0 ? (
            <span className="nav-rail-count-badge">{activeClusterCount}</span>
          ) : (
            <span className="nav-rail-shortcut">4</span>
          )}
        </button>

        {/* 5. Evaluation & Metrics */}
        <button
          className={`nav-rail-item ${workspaceMode === 'evaluation' ? 'active' : ''}`}
          onClick={() => setMode('evaluation')}
          title="Evaluation & Metrics (5)"
          aria-label="Evaluation Workspace"
        >
          <div className="nav-rail-icon-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 3v18h18" />
              <path d="m19 9-5 5-4-4-3 3" />
            </svg>
          </div>
          <span className="nav-rail-item-label">Evaluation</span>
          <span className="nav-rail-shortcut">5</span>
        </button>
      </div>

      {/* Bottom Section: Settings */}
      <div className="nav-rail-group nav-rail-bottom">
        <button
          className={`nav-rail-item ${workspaceMode === 'settings' ? 'active' : ''}`}
          onClick={() => setMode('settings')}
          title="Settings & Appearance"
          aria-label="Settings Modal"
        >
          <div className="nav-rail-icon-box">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </div>
          <span className="nav-rail-item-label">Settings</span>
        </button>
      </div>
    </nav>
  </aside>
)
}
