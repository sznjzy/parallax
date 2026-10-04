/**
 * useConstraints.js
 *
 * Manages the persistent constraint list.
 * Wraps GET / POST / DELETE /api/constraints.
 * In mock mode, maintains an in-memory list (no fetch calls).
 *
 * Returns:
 *   constraints       — current list from AppContext
 *   addConstraint     — (doc_id, cluster_id) → Promise<Constraint>
 *   removeConstraint  — (doc_id) → Promise<void>
 *   fetchConstraints  — () → Promise<void>  (load on mount)
 *   isLoading         — true during any inflight request
 */
import { useCallback, useState } from 'react'
import { useApp } from '../state/AppContext'

export function useConstraints() {
  const { state, dispatch } = useApp()
  const [isLoading, setIsLoading] = useState(false)

  // ── Fetch all constraints from backend ────────────────────────────
  const fetchConstraints = useCallback(async () => {
    if (state.mockMode) {
      // Mock: start empty, add as user drags
      dispatch({ type: 'SET_CONSTRAINTS', constraints: [] })
      return
    }
    setIsLoading(true)
    try {
      const res = await fetch('/api/constraints')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      dispatch({ type: 'SET_CONSTRAINTS', constraints: data })
    } catch (err) {
      console.warn('[useConstraints] fetchConstraints error:', err.message)
    } finally {
      setIsLoading(false)
    }
  }, [state.mockMode, dispatch])

  // ── Add / update a constraint ─────────────────────────────────────
  const addConstraint = useCallback(async (doc_id, cluster_id) => {
    const constraint = {
      doc_id,
      forced_cluster_id: cluster_id,
      created_at: new Date().toISOString(),
      source: 'user',
    }

    if (state.mockMode) {
      dispatch({ type: 'ADD_CONSTRAINT', constraint })
      return constraint
    }

    setIsLoading(true)
    try {
      const res = await fetch('/api/constraints', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id, cluster_id }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      const saved = await res.json()
      dispatch({ type: 'ADD_CONSTRAINT', constraint: saved })
      return saved
    } catch (err) {
      console.error('[useConstraints] addConstraint error:', err.message)
      // Resync state with backend on failure to prevent stale UI state
      fetch('/api/constraints')
        .then(r => r.json())
        .then(d => dispatch({ type: 'SET_CONSTRAINTS', constraints: d ?? [] }))
        .catch(() => {})
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [state.mockMode, dispatch])

  // ── Remove a constraint ────────────────────────────────────────────
  const removeConstraint = useCallback(async (doc_id) => {
    if (state.mockMode) {
      dispatch({ type: 'REMOVE_CONSTRAINT', doc_id })
      return
    }

    setIsLoading(true)
    try {
      const res = await fetch(`/api/constraints/${encodeURIComponent(doc_id)}`, {
        method: 'DELETE',
      })
      if (!res.ok && res.status !== 404) throw new Error(`HTTP ${res.status}`)
      dispatch({ type: 'REMOVE_CONSTRAINT', doc_id })
    } catch (err) {
      console.error('[useConstraints] removeConstraint error:', err.message)
      // Resync state with backend on failure to prevent stale UI state
      fetch('/api/constraints')
        .then(r => r.json())
        .then(d => dispatch({ type: 'SET_CONSTRAINTS', constraints: d ?? [] }))
        .catch(() => {})
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [state.mockMode, dispatch])

  // ── Clear all constraints ──────────────────────────────────────────
  const clearAllConstraints = useCallback(async () => {
    if (state.mockMode) {
      dispatch({ type: 'CLEAR_CONSTRAINTS' })
      return
    }

    setIsLoading(true)
    try {
      const res = await fetch('/api/constraints', { method: 'DELETE' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      dispatch({ type: 'CLEAR_CONSTRAINTS' })
    } catch (err) {
      console.error('[useConstraints] clearAllConstraints error:', err.message)
      // Fallback: clear local state anyway
      dispatch({ type: 'CLEAR_CONSTRAINTS' })
    } finally {
      setIsLoading(false)
    }
  }, [state.mockMode, dispatch])

  return {
    constraints: state.constraints,
    addConstraint,
    removeConstraint,
    clearAllConstraints,
    fetchConstraints,
    isLoading,
  }
}
