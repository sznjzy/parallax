/**
 * App.jsx
 *
 * Root application component for Parallax Phase 8.
 * Implements the 3-Zone Architecture:
 *   [ NavRail (48px) ]  │  [ Research Canvas Centerpiece ]  │  [ InspectorDrawer (360px) ]
 */
import React, { useEffect, useCallback } from 'react'
import { useApp } from './state/AppContext'
import { useOrganize } from './hooks/useOrganize'
import { useConstraints } from './hooks/useConstraints'
import { useDocuments } from './hooks/useDocuments'
import { useToast } from './components/ConstraintToast'

import NavRail from './components/NavRail'
import CommandBar from './components/CommandBar'
import CanvasDock from './components/CanvasDock'
import InspectorDrawer from './components/InspectorDrawer'
import ResearchCanvas from './canvas/ResearchCanvas'
import SettingsModal from './components/SettingsModal'
import PdfViewerModal from './components/PdfViewerModal'

function isTextInputActive() {
  const el = document.activeElement
  if (!el) return false
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable
}

export default function App() {
  const { state, dispatch } = useApp()
  const { run, isRunning } = useOrganize()
  const { fetchConstraints } = useConstraints()
  const { fetchDocuments } = useDocuments()
  const { showToast } = useToast()

  // ── On mount: check backend status + load constraints + doc list ───
  useEffect(() => {
    dispatch({ type: 'SET_STATUS', status: 'loading', message: 'Checking backend…' })

    if (state.mockMode) {
      dispatch({ type: 'SET_STATUS', status: 'idle' })
      fetchConstraints()
      return
    }

    fetch('/api/status')
      .then(r => r.json())
      .then(data => {
        if (data.state === 'ready') {
          dispatch({ type: 'SET_STATUS', status: 'idle' })
        } else if (data.state === 'no_documents') {
          dispatch({ type: 'SET_STATUS', status: 'error', message: `No PDFs found in ${data.docs_folder}. Add PDFs and restart.` })
        } else {
          dispatch({ type: 'SET_STATUS', status: 'error', message: 'Backend dependencies missing. Check requirements.txt.' })
        }
      })
      .catch(() => {
        dispatch({ type: 'SET_STATUS', status: 'error', message: 'Backend not reachable — start uvicorn first.' })
      })

    fetchConstraints()
    fetchDocuments()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Constraint added callback (triggers toast with Undo) ───────────
  const handleConstraintAdded = useCallback((doc_id, cluster_id) => {
    showToast({ docId: doc_id, clusterId: cluster_id })
  }, [showToast])

  // ── Global input-safe keyboard shortcuts (1-5, Esc) ───────────────
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Never trigger numerical shortcuts while typing or interacting with modals
      if (isTextInputActive()) return
      if (state.viewingDoc) return // Let PDF modal handle its own Escape

      switch (e.key) {
        case '1':
          e.preventDefault()
          dispatch({ type: 'SET_WORKSPACE_MODE', mode: null })
          break
        case '2':
          e.preventDefault()
          dispatch({ type: 'SET_WORKSPACE_MODE', mode: 'search' })
          break
        case '3':
          e.preventDefault()
          dispatch({ type: 'SET_WORKSPACE_MODE', mode: 'library' })
          break
        case '4':
          e.preventDefault()
          dispatch({ type: 'SET_WORKSPACE_MODE', mode: 'cluster' })
          break
        case '5':
          e.preventDefault()
          dispatch({ type: 'SET_WORKSPACE_MODE', mode: 'evaluation' })
          break
        case 'Escape':
          if (state.workspaceMode !== null) {
            e.preventDefault()
            dispatch({ type: 'SET_WORKSPACE_MODE', mode: null })
          }
          break
        default:
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [state.viewingDoc, state.workspaceMode, dispatch])

  return (
    <div className="app-shell" data-theme={state.theme}>
      {/* 1. Global Left Navigation Rail (48px) */}
      <NavRail />

      {/* 2. Central Canvas Viewport */}
      <main className="canvas-wrapper" role="main" aria-label="Research Canvas">
        {/* Floating Top Command & Search Bar */}
        <CommandBar />

        {/* Konva Stage Canvas */}
        <ResearchCanvas onConstraintAdded={handleConstraintAdded} />

        {/* Floating Bottom Action Dock */}
        <CanvasDock
          onRun={run}
          isRunning={isRunning}
        />
      </main>

      {/* 3. Contextual Right Workspace Drawer */}
      <InspectorDrawer />

      {/* Settings & Appearance Modal — Only rendered when workspaceMode === 'settings' */}
      {state.workspaceMode === 'settings' && (
        <SettingsModal onClose={() => dispatch({ type: 'SET_WORKSPACE_MODE', mode: null })} />
      )}

      {/* In-Browser Deep-Link PDF Reader Modal */}
      <PdfViewerModal />
    </div>
  )
}
