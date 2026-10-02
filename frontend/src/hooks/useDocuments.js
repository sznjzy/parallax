/**
 * useDocuments.js
 *
 * Fetches the list of available PDFs from GET /api/documents, handles PDF uploads
 * to POST /api/documents/upload, and deletes documents via DELETE /api/documents/{filename}.
 */
import { useCallback, useState } from 'react'
import { useApp } from '../state/AppContext'

export function useDocuments() {
  const { dispatch } = useApp()
  const [isLoading, setIsLoading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)

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

  const uploadDocuments = useCallback(async (files) => {
    if (!files || files.length === 0) return null
    setIsLoading(true)
    setUploadStatus('Uploading & embedding...')
    const formData = new FormData()
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i])
    }
    try {
      const res = await fetch('/api/documents/upload', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed')
      }
      const data = await res.json()
      await fetchDocuments()
      setUploadStatus(`Uploaded ${data.total_uploaded} file(s)`)
      setTimeout(() => setUploadStatus(null), 3000)
      return data
    } catch (err) {
      setUploadStatus(`Upload failed: ${err.message}`)
      setTimeout(() => setUploadStatus(null), 4000)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [fetchDocuments])

  const deleteDocument = useCallback(async (filename) => {
    setIsLoading(true)
    try {
      const res = await fetch(`/api/documents/${filename}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error('Failed to delete document')
      await fetchDocuments()
    } catch (err) {
      console.error('Delete error:', err)
    } finally {
      setIsLoading(false)
    }
  }, [fetchDocuments])

  return { fetchDocuments, uploadDocuments, deleteDocument, isLoading, uploadStatus }
}
