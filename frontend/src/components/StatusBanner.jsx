/**
 * StatusBanner.jsx
 *
 * Absolute-positioned banner inside the canvas area. Shows the
 * current pipeline / API status. Animates in/out via CSS classes.
 *
 * States
 * ------
 *   idle     → info prompt: "Click Run Pipeline to organise your documents"
 *   loading  → spinner + "Checking backend…"
 *   running  → spinner + descriptive message from state (e.g. "Embedding 3 docs…")
 *   error    → red banner with message + Retry button
 *   ready    → hidden (canvas is in use, no need for a banner)
 */
import React from 'react'
import { useApp } from '../state/AppContext'

export default function StatusBanner({ onRetry }) {
  const { state } = useApp()
  const { status, statusMessage } = state

  const isHidden = status === 'ready' || (status === 'idle' && state.nodes.length > 0)
  const isError  = status === 'error'
  const isSpinning = status === 'loading' || status === 'running'

  // Derive a friendly running message. The hook sets statusMessage to
  // something like "Embedding 5 docs… (cached docs load instantly)" — show
  // that if available, otherwise fall back to a generic label.
  const runningMessage = statusMessage || 'Organising documents…'

  return (
    <div
      id="status-banner"
      className={`status-banner ${isError ? 'error' : ''} ${isHidden ? 'hidden' : ''}`}
      role="status"
      aria-live="polite"
    >
      {isSpinning && <span className="spinner" aria-hidden="true" />}

      {isError && <span aria-hidden="true">⚠️</span>}

      <span>
        {status === 'idle'    && 'Click Run Pipeline to organise your documents'}
        {status === 'loading' && 'Checking backend…'}
        {status === 'running' && runningMessage}
        {status === 'error'   && (statusMessage || 'An error occurred')}
      </span>

      {isError && (
        <button
          id="btn-status-retry"
          className="btn btn-secondary"
          style={{ marginLeft: 4, padding: '3px 10px', fontSize: '0.75rem' }}
          onClick={onRetry}
        >
          Retry
        </button>
      )}
    </div>
  )
}
