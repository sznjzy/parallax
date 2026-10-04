/**
 * InspectorDrawer.jsx
 *
 * Sliding contextual workspace drawer hosted on the right of the Parallax canvas.
 * Features:
 *   - Smooth slide / fade in from right (260ms cubic-bezier(0.22, 1, 0.36, 1))
 *   - Smooth slide / fade out to right without content flashing
 *   - Left edge resize handle
 *   - Renders active workspace component
 */
import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useApp } from '../state/AppContext'

import DocumentInspector from './DocumentInspector'
import ClusterInspector from './ClusterInspector'
import SearchWorkspace from './SearchWorkspace'
import LibraryWorkspace from './LibraryWorkspace'
import EvaluationWorkspace from './EvaluationWorkspace'

const MIN_WIDTH = 340
const MAX_WIDTH = 640
const DEFAULT_WIDTH = 380

export default function InspectorDrawer() {
  const { state, dispatch } = useApp()
  const { workspaceMode } = state

  const [drawerWidth, setDrawerWidth] = useState(DEFAULT_WIDTH)
  const [isResizing, setIsResizing] = useState(false)
  const isResizingRef = useRef(false)
  const startXRef = useRef(0)
  const startWidthRef = useRef(DEFAULT_WIDTH)

  // Keep track of the last active workspace mode to preserve content during close animation
  const [renderedMode, setRenderedMode] = useState(workspaceMode)

  const isOpen = Boolean(workspaceMode && workspaceMode !== 'settings')

  useEffect(() => {
    if (workspaceMode && workspaceMode !== 'settings') {
      setRenderedMode(workspaceMode)
    }
  }, [workspaceMode])

  // Drawer resize handling
  const handleMouseDown = useCallback((e) => {
    e.preventDefault()
    isResizingRef.current = true
    setIsResizing(true)
    startXRef.current = e.clientX
    startWidthRef.current = drawerWidth
  }, [drawerWidth])

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizingRef.current) return
      const delta = startXRef.current - e.clientX
      const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidthRef.current + delta))
      setDrawerWidth(newWidth)
    }

    const handleMouseUp = () => {
      if (isResizingRef.current) {
        isResizingRef.current = false
        setIsResizing(false)
      }
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [])

  const handleClose = () => {
    dispatch({ type: 'SET_WORKSPACE_MODE', mode: null })
  }

  return (
    <aside
      className={`inspector-drawer ${isOpen ? 'open' : 'closed'} ${isResizing ? 'resizing' : ''}`}
      style={{
        width: isOpen ? `${drawerWidth}px` : '0px',
      }}
      aria-hidden={!isOpen}
      aria-label="Contextual Inspector Drawer"
    >
      {/* Left resize handle */}
      {isOpen && (
        <div
          className={`drawer-resizer ${isResizing ? 'is-resizing' : ''}`}
          onMouseDown={handleMouseDown}
          title="Drag to resize inspector width"
          role="separator"
          aria-orientation="vertical"
        />
      )}

      {/* Main Drawer Workspace Content */}
      <div className="inspector-drawer-body" style={{ width: `${drawerWidth}px` }}>
        {renderedMode === 'document' && <DocumentInspector onClose={handleClose} />}
        {renderedMode === 'cluster' && <ClusterInspector onClose={handleClose} />}
        {renderedMode === 'search' && <SearchWorkspace onClose={handleClose} />}
        {renderedMode === 'library' && <LibraryWorkspace onClose={handleClose} />}
        {renderedMode === 'evaluation' && <EvaluationWorkspace onClose={handleClose} />}
      </div>
    </aside>
  )
}
