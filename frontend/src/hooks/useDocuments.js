/**
 * useDocuments.js
 *
 * Fetches the list of available PDFs from GET /api/documents and populates
 * the availableDocs + selectedDocs state.
 *
 * Returns:
 *   fetchDocuments()  — manually refresh the document list
 *   isLoading         — true while the request is in-flight
 */
import { useCallback, useState } from 'react'
import { useApp } from '../state/AppContext'

export function useDocuments() {
  const { dispatch } = useApp()
  const [isLoading, setIsLoading] = useState(false)

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await fetch('/api/documents')
      if (!res.ok) return  // Silently fail — backend may not be up yet
      const data = await res.json()
      dispatch({ type: 'SET_AVAILABLE_DOCS', docs: data.documents ?? [] })
    } catch {
      // Backend not reachable — leave availableDocs empty
    } finally {
      setIsLoading(false)
    }
  }, [dispatch])

  return { fetchDocuments, isLoading }
}
