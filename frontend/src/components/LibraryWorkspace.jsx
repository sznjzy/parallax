/**
 * LibraryWorkspace.jsx
 *
 * Single-column document corpus management workspace.
 * Minimal vertical list with selective run, disk cache state, upload dropzone, and quick reading.
 */
import React, { useState, useRef } from 'react'
import { useApp } from '../state/AppContext'
import { useDocuments } from '../hooks/useDocuments'
import { useOrganize } from '../hooks/useOrganize'

export default function LibraryWorkspace({ onClose }) {
  const { state, dispatch } = useApp()
  const { uploadFiles, deleteDoc, isUploading } = useDocuments()
  const { run, isRunning } = useOrganize()

  const [isDragging, setIsDragging] = useState(false)
  const [filterText, setFilterText] = useState('')
  const [docToDelete, setDocToDelete] = useState(null)
  const fileInputRef = useRef(null)

  const availableDocs = state.availableDocs || []
  const selectedDocs = state.selectedDocs || new Set()

  const filteredDocs = availableDocs.filter(d =>
    d.filename.toLowerCase().includes(filterText.toLowerCase())
  )

  const isAllSelected = availableDocs.length > 0 && selectedDocs.size === availableDocs.length

  const handleToggleAll = () => {
    if (isAllSelected) {
      dispatch({ type: 'DESELECT_ALL_DOCS' })
    } else {
      dispatch({ type: 'SELECT_ALL_DOCS' })
    }
  }

  const handleToggleDoc = (filename) => {
    dispatch({ type: 'TOGGLE_DOC_SELECTION', filename })
  }

  const handleFileDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files?.length > 0) {
      uploadFiles(Array.from(e.dataTransfer.files))
    }
  }

  const handleFileInput = (e) => {
    if (e.target.files?.length > 0) {
      uploadFiles(Array.from(e.target.files))
      e.target.value = ''
    }
  }

  const handleConfirmDelete = async () => {
    if (docToDelete) {
      await deleteDoc(docToDelete)
      setDocToDelete(null)
    }
  }

  return (
    <div className="inspector-panel" role="region" aria-label="Library Workspace">
      {/* Header */}
      <div className="inspector-header">
        <div>
          <span className="inspector-eyebrow">WORKSPACE</span>
          <h2 className="inspector-title">Document Library</h2>
        </div>
        <button className="inspector-close-btn" onClick={onClose} title="Close inspector (Esc)" aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </div>

      <div className="inspector-scrollable">
        {/* Compact Drag & Drop Upload Zone */}
        <div
          className={`library-dropzone ${isDragging ? 'dragging' : ''} ${isUploading ? 'uploading' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleFileDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf"
            onChange={handleFileInput}
            style={{ display: 'none' }}
          />
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <div className="dropzone-text">
            <span>{isUploading ? 'Ingesting PDF embeddings…' : 'Drop research PDFs here or click to browse'}</span>
          </div>
        </div>

        {/* Action & Filter Bar */}
        <div className="library-toolbar">
          <div className="library-search-box">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
            <input
              type="text"
              placeholder="Filter corpus…"
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="library-filter-input"
            />
          </div>

          <div className="library-selection-actions">
            <button className="btn-link" onClick={handleToggleAll}>
              {isAllSelected ? 'Deselect All' : 'Select All'}
            </button>
            <span className="library-count-text">
              {selectedDocs.size} of {availableDocs.length} selected
            </span>
          </div>
        </div>

        {/* Single-Column Vertical Document List */}
        <div className="library-doc-list">
          {filteredDocs.map((doc) => {
            const isSelected = selectedDocs.has(doc.filename)
            const isCached = doc.has_cached_embedding

            return (
              <div key={doc.filename} className={`library-doc-row ${isSelected ? 'active' : ''}`}>
                {/* Checkbox */}
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => handleToggleDoc(doc.filename)}
                  className="library-checkbox"
                  aria-label={`Select ${doc.filename}`}
                />

                {/* Info */}
                <div className="library-doc-info" onClick={() => handleToggleDoc(doc.filename)}>
                  <span className="library-doc-name truncate" title={doc.filename}>
                    {doc.filename}
                  </span>
                  <span className="library-doc-sub">
                    {isCached ? 'Cached' : 'Uncached'} · PDF
                  </span>
                </div>

                {/* Quick Actions */}
                <div className="library-row-actions">
                  <button
                    className="library-action-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      dispatch({
                        type: 'VIEW_DOCUMENT',
                        filename: doc.filename,
                        doc_id: `doc-${doc.filename}`,
                        page: 1,
                      })
                    }}
                    title="Read PDF"
                    aria-label="Read PDF"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                  </button>

                  <button
                    className="library-action-btn danger"
                    onClick={(e) => {
                      e.stopPropagation()
                      setDocToDelete(doc.filename)
                    }}
                    title="Delete PDF"
                    aria-label="Delete PDF"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  </button>
                </div>
              </div>
            )
          })}
        </div>

        {/* Run with Selection Button */}
        <div className="library-footer-actions">
          <button
            className="btn btn-primary btn-block"
            onClick={() => run()}
            disabled={isRunning || selectedDocs.size === 0}
          >
            <span>Run Pipeline with Selection ({selectedDocs.size})</span>
          </button>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {docToDelete && (
        <div className="confirm-modal-backdrop">
          <div className="confirm-modal-card">
            <h3 className="confirm-title">Delete Document</h3>
            <p className="confirm-text">
              Permanently remove <strong>{docToDelete}</strong> from your corpus?
            </p>
            <div className="confirm-actions">
              <button className="btn btn-secondary" onClick={() => setDocToDelete(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={handleConfirmDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
