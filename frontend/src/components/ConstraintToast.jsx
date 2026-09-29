/**
 * ConstraintToast.jsx
 *
 * Toast queue rendered at the bottom-centre of the screen.
 * Each toast auto-dismisses after 4 seconds and has an Undo button.
 *
 * Usage:
 *   const { showToast } = useToast()   (provided by ToastProvider)
 *   showToast({ docId, clusterId })
 *
 * This file exports both <ToastProvider> and the useToast hook.
 */
import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import { clusterColor } from '../canvas/clusterColor'
import { useConstraints } from '../hooks/useConstraints'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const { removeConstraint } = useConstraints()

  const showToast = useCallback(({ docId, clusterId }) => {
    const id = Date.now()
    setToasts(prev => [...prev.slice(-2), { id, docId, clusterId, exiting: false }])
  }, [])

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t))
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 200)
  }, [])

  const handleUndo = useCallback(async (toast) => {
    await removeConstraint(toast.docId).catch(() => {})
    dismiss(toast.id)
  }, [removeConstraint, dismiss])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-container" role="region" aria-label="Notifications" aria-live="polite">
        {toasts.map(toast => (
          <Toast
            key={toast.id}
            toast={toast}
            onDismiss={() => dismiss(toast.id)}
            onUndo={() => handleUndo(toast)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}

function Toast({ toast, onDismiss, onUndo }) {
  const clr     = clusterColor(toast.clusterId)
  const docLabel = toast.docId.replace('doc-', '').replace('.pdf', '')
  const clrLabel = toast.clusterId.replace('cluster-', '')

  useEffect(() => {
    const t = setTimeout(onDismiss, 6000)
    return () => clearTimeout(t)
  }, [onDismiss])

  return (
    <div className={`toast ${toast.exiting ? 'exiting' : ''}`} role="alert">
      <span
        style={{
          fontSize: '0.68rem',
          padding: '2px 6px',
          borderRadius: 'var(--radius-sm)',
          background: `${clr}20`,
          color: clr,
          border: `1px solid ${clr}40`,
          fontFamily: 'var(--font-mono)',
          fontWeight: 600,
        }}
      >
        {clrLabel}
      </span>
      <span>
        Pinned <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{docLabel}</strong>
      </span>
      <button
        className="btn btn-ghost toast-undo"
        onClick={onUndo}
        style={{ fontSize: '0.75rem', marginLeft: 4 }}
        aria-label={`Undo pinning ${docLabel}`}
      >
        Undo
      </button>
      <button
        className="btn btn-ghost btn-icon"
        onClick={onDismiss}
        style={{ width: 20, height: 20, minWidth: 20, fontSize: 10, padding: 0, marginLeft: -4 }}
        aria-label="Dismiss notification"
      >
        ✕
      </button>
    </div>
  )
}
