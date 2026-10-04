/**
 * useOrganize.js
 *
 * Wraps POST /api/organize.
 * In mock mode (VITE_MOCK_API=true), returns the static fixture after a
 * realistic 1.5s simulated delay so loading state UX can be verified.
 *
 * Returns:
 *   run()       — triggers the pipeline
 *   isRunning   — true while the request is in-flight
 *   error       — last error string, or null
 */
import { useCallback, useState } from 'react'
import { useApp } from '../state/AppContext'
import { MOCK_ORGANIZE_RESPONSE } from '../state/mockFixture'

export function useOrganize() {
  const { state, dispatch } = useApp()
  const [isRunning, setIsRunning] = useState(false)
  const [isRerunningLayout, setIsRerunningLayout] = useState(false)
  const [error, setError] = useState(null)

  const run = useCallback(async () => {
    setIsRunning(true)
    setError(null)
    dispatch({ type: 'SET_STATUS', status: 'running', message: 'Organising documents…' })

    try {
      let data

      if (state.mockMode) {
        // Simulate realistic network + pipeline latency.
        await new Promise(r => setTimeout(r, 1500))
        data = MOCK_ORGANIZE_RESPONSE
      } else {
        // Build the request body — send selected filenames if the user has
        // chosen a subset, otherwise send an empty list (= run all).
        const allFilenames = state.availableDocs.map(d => d.filename)
        const selected = [...(state.selectedDocs ?? [])]
        // Only send a filter if the user deselected at least one doc.
        const filenames = selected.length > 0 && selected.length < allFilenames.length
          ? selected
          : []

        const runCount = filenames.length || allFilenames.length
        if (runCount > 0) {
          dispatch({
            type: 'SET_STATUS',
            status: 'running',
            message: `Embedding ${runCount} doc${runCount !== 1 ? 's' : ''}… (cached docs load instantly)`,
          })
        }

        const res = await fetch('/api/organize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filenames }),
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${res.status}`)
        }
        data = await res.json()
      }

      dispatch({ type: 'SET_NODES', nodes: data.nodes ?? [] })
      dispatch({ type: 'SET_TOPICS', topics: data.topics ?? {} })
      dispatch({ type: 'SET_EVALUATION', evaluation: data.evaluation ?? null })
      dispatch({ type: 'SET_SKIPPED', skipped: data.skipped_documents ?? [] })
      dispatch({ type: 'SET_STATUS', status: 'ready', message: null })

      // Refresh doc list & constraints from backend so state is 100% in sync
      if (!state.mockMode) {
        fetch('/api/documents')
          .then(r => r.json())
          .then(d => dispatch({ type: 'SET_AVAILABLE_DOCS', docs: d.documents ?? [] }))
          .catch(() => { })

        fetch('/api/constraints')
          .then(r => r.json())
          .then(d => dispatch({ type: 'SET_CONSTRAINTS', constraints: d ?? [] }))
          .catch(() => { })
      }
    } catch (err) {
      const msg = err.message || 'Unknown error'
      setError(msg)
      dispatch({ type: 'SET_STATUS', status: 'error', message: msg })
    } finally {
      setIsRunning(false)
    }
  }, [state.mockMode, state.availableDocs, state.selectedDocs, dispatch])

  const rerunLayout = useCallback(async () => {
    setIsRerunningLayout(true)
    setError(null)
    dispatch({ type: 'SET_STATUS', status: 'running', message: 'Rerunning physics layout…' })

    try {
      let data

      if (state.mockMode) {
        await new Promise(r => setTimeout(r, 600))
        data = MOCK_ORGANIZE_RESPONSE
      } else {
        const allFilenames = state.availableDocs.map(d => d.filename)
        const selected = [...(state.selectedDocs ?? [])]
        const filenames = selected.length > 0 && selected.length < allFilenames.length
          ? selected
          : []

        const res = await fetch('/api/organize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filenames }),
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${res.status}`)
        }
        data = await res.json()
      }

      dispatch({ type: 'SET_NODES', nodes: data.nodes ?? [] })
      if (data.topics) dispatch({ type: 'SET_TOPICS', topics: data.topics })
      if (data.evaluation) dispatch({ type: 'SET_EVALUATION', evaluation: data.evaluation })
      dispatch({ type: 'SET_STATUS', status: 'ready', message: null })
    } catch (err) {
      const msg = err.message || 'Unknown error'
      setError(msg)
      dispatch({ type: 'SET_STATUS', status: 'error', message: msg })
    } finally {
      setIsRerunningLayout(false)
    }
  }, [state.mockMode, state.availableDocs, state.selectedDocs, dispatch])

  return { run, rerunLayout, isRunning, isRerunningLayout, error }
}
