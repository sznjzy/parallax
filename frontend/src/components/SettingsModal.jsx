/**
 * SettingsModal.jsx
 *
 * Minimal preferences modal for Parallax.
 * Configures Appearance (Dark/Light theme) and inspects caching/engine diagnostics.
 */
import React from 'react'
import { useApp } from '../state/AppContext'

export default function SettingsModal({ onClose }) {
  const { state, dispatch } = useApp()
  const isDark = state.theme !== 'light'

  if (state.workspaceMode !== 'settings') return null

  const handleClose = () => {
    if (onClose) {
      onClose()
    } else {
      dispatch({ type: 'SET_WORKSPACE_MODE', mode: null })
    }
  }

  const handleToggleTheme = (mode) => {
    dispatch({ type: 'SET_THEME', theme: mode })
  }

  return (
    <div className="settings-modal-backdrop" onClick={handleClose} role="dialog" aria-modal="true">
      <div className="settings-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="settings-modal-header">
          <h2 className="settings-modal-title">Settings</h2>
          <button className="inspector-close-btn" onClick={handleClose} aria-label="Close settings">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
          </button>
        </div>

        <div className="settings-modal-body">
          {/* Appearance Section */}
          <div className="settings-section">
            <span className="settings-section-title">Appearance</span>
            <div className="settings-row">
              <span className="settings-label">Interface Theme</span>
              <div className="theme-toggle-group">
                <button
                  className={`theme-toggle-btn ${isDark ? 'active' : ''}`}
                  onClick={() => handleToggleTheme('dark')}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
                  <span>Dark</span>
                </button>
                <button
                  className={`theme-toggle-btn ${!isDark ? 'active' : ''}`}
                  onClick={() => handleToggleTheme('light')}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
                  <span>Light</span>
                </button>
              </div>
            </div>
          </div>

          {/* Performance Section */}
          <div className="settings-section">
            <span className="settings-section-title">Performance & Cache</span>
            <div className="settings-row">
              <div>
                <span className="settings-label">Embedding Disk Cache</span>
                <p className="settings-subtext">Precomputed 768-dim embeddings cached in memory & disk</p>
              </div>
              <span className="settings-badge-ok font-mono">Active (disk)</span>
            </div>
          </div>

          {/* Architecture Section */}
          <div className="settings-section">
            <span className="settings-section-title">Architecture</span>
            <div className="settings-row">
              <div>
                <span className="settings-label">Processing Engine</span>
                <p className="settings-subtext">Zero-LLM deterministic pipeline (HDBSCAN + all-mpnet-base-v2)</p>
              </div>
              <span className="settings-badge-ok font-mono">Zero-LLM</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
