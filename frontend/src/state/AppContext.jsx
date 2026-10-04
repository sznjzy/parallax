/**
 * AppContext.jsx
 *
 * Single source of truth for all global UI state.
 *
 * Authoritative Workspace Mode:
 *   workspaceMode: null | 'document' | 'cluster' | 'search' | 'library' | 'evaluation' | 'settings'
 */

import React, { createContext, useContext, useReducer, useEffect } from 'react'

// ─── Initial state ────────────────────────────────────────────────────────────
const initialState = {
  /** List of canvas nodes returned by /api/organize */
  nodes: [],
  /** Cluster topic models extracted by c-TF-IDF / KeyBERT */
  topics: {},
  /** EvaluationContract from /api/organize */
  evaluation: null,
  /** PDFs the pipeline couldn't parse */
  skippedDocuments: [],
  /** Persistent user constraints */
  constraints: [],
  /** Pipeline + API status */
  status: 'idle',   // 'idle' | 'loading' | 'running' | 'ready' | 'error'
  /** Human-readable status message shown in the status pill */
  statusMessage: null,

  /** Single Authoritative Contextual Workspace Mode */
  workspaceMode: null, // null | 'document' | 'cluster' | 'search' | 'library' | 'evaluation' | 'settings'

  /** Currently selected doc_id */
  selectedDocId: null,
  /** Currently selected cluster_id */
  selectedClusterId: null,

  /** Filename of the PDF currently being viewed in the modal viewer, or null */
  viewingDoc: null,
  /** Active page to display in PDF viewer (1-indexed) */
  viewerPage: 1,
  /** Active search highlight phrase/term in PDF viewer */
  viewerHighlight: null,
  /** Active SearchResult object passed to viewer */
  viewerMatch: null,

  /** 'dark' | 'light' — persisted to localStorage */
  theme: localStorage.getItem('parallax-theme') || 'dark',
  /** True when running against static fixture instead of live backend */
  mockMode: typeof __MOCK_API__ !== 'undefined' ? __MOCK_API__ : false,

  /** List of docs returned by GET /api/documents */
  availableDocs: [],   // [{ filename, size_bytes, cached }]
  /** Set of filenames the user has selected to process */
  selectedDocs: new Set(),  // empty = all docs

  /** Active search query string */
  searchQuery: '',
  /** Semantic search response payload from /api/search */
  searchResults: null,
  /** Whether search request is in-flight */
  isSearching: false,
  /** Whether search highlight / heatmap mode is currently active */
  searchActive: false,
}

// ─── Reducer ──────────────────────────────────────────────────────────────────
function reducer(state, action) {
  switch (action.type) {
    case 'SET_WORKSPACE_MODE':
      return {
        ...state,
        workspaceMode: action.mode,
        // If closing inspector or switching away from document, keep or clear selection appropriately
        selectedDocId: action.mode === 'document' ? state.selectedDocId : (action.mode === null ? null : state.selectedDocId),
      }

    case 'SET_NODES':
      return { ...state, nodes: action.nodes }

    case 'SET_TOPICS':
      return { ...state, topics: action.topics }

    case 'SET_EVALUATION':
      return { ...state, evaluation: action.evaluation }

    case 'SET_SKIPPED':
      return { ...state, skippedDocuments: action.skipped }

    case 'SET_CONSTRAINTS':
      return { ...state, constraints: action.constraints }

    case 'ADD_CONSTRAINT': {
      const without = state.constraints.filter(c => c.doc_id !== action.constraint.doc_id)
      const nextConstraints = [...without, action.constraint]
      const nextNodes = state.nodes.map(n => {
        if (n.doc_id === action.constraint.doc_id) {
          return {
            ...n,
            cluster_id: action.constraint.forced_cluster_id,
            is_anchored: true,
            is_boundary_document: false,
          }
        }
        return n
      })
      const applied = nextConstraints.length
      const violated = nextConstraints.filter(c => {
        const node = nextNodes.find(n => n.doc_id === c.doc_id)
        return node && node.cluster_id !== c.forced_cluster_id
      }).length
      const rate = applied > 0 ? (applied - violated) / applied : null
      const nextEval = state.evaluation ? {
        ...state.evaluation,
        constraint_satisfaction_rate: rate,
        num_constraints_applied: applied,
        num_constraints_violated: violated,
      } : {
        silhouette_score: null,
        num_clusters: new Set(nextNodes.map(n => n.cluster_id)).size,
        constraint_satisfaction_rate: rate,
        num_constraints_applied: applied,
        num_constraints_violated: violated,
      }
      return {
        ...state,
        constraints: nextConstraints,
        nodes: nextNodes,
        evaluation: nextEval,
      }
    }

    case 'REMOVE_CONSTRAINT': {
      const nextConstraints = state.constraints.filter(c => c.doc_id !== action.doc_id)
      const applied = nextConstraints.length
      const rate = applied > 0 ? 1.0 : null
      const nextEval = state.evaluation ? {
        ...state.evaluation,
        constraint_satisfaction_rate: rate,
        num_constraints_applied: applied > 0 ? applied : null,
        num_constraints_violated: applied > 0 ? 0 : null,
      } : state.evaluation
      return {
        ...state,
        constraints: nextConstraints,
        evaluation: nextEval,
      }
    }

    case 'UPDATE_NODE_POSITION': {
      return {
        ...state,
        nodes: state.nodes.map(n =>
          n.doc_id === action.doc_id ? { ...n, x: action.x, y: action.y } : n
        ),
      }
    }

    case 'CLEAR_CONSTRAINTS': {
      const nextEval = state.evaluation ? {
        ...state.evaluation,
        constraint_satisfaction_rate: null,
        num_constraints_applied: null,
        num_constraints_violated: null,
      } : state.evaluation
      return {
        ...state,
        constraints: [],
        evaluation: nextEval,
        nodes: state.nodes.map(n => ({ ...n, is_anchored: false })),
      }
    }

    case 'SET_STATUS':
      return { ...state, status: action.status, statusMessage: action.message ?? null }

    case 'SET_THEME': {
      localStorage.setItem('parallax-theme', action.theme)
      return { ...state, theme: action.theme }
    }

    case 'SELECT_NODE': {
      const isDeselecting = state.selectedDocId === action.doc_id || !action.doc_id
      const nextDocId = isDeselecting ? null : action.doc_id
      const nextMode = nextDocId ? 'document' : (state.workspaceMode === 'document' ? null : state.workspaceMode)
      return {
        ...state,
        selectedDocId: nextDocId,
        workspaceMode: nextMode,
      }
    }

    case 'SELECT_CLUSTER': {
      const isDeselecting = state.selectedClusterId === action.cluster_id || !action.cluster_id
      const nextClusterId = isDeselecting ? null : action.cluster_id
      const nextMode = nextClusterId ? 'cluster' : (state.workspaceMode === 'cluster' ? null : state.workspaceMode)
      return {
        ...state,
        selectedClusterId: nextClusterId,
        workspaceMode: nextMode,
      }
    }

    case 'VIEW_DOCUMENT': {
      let filename = action.filename
      if (!filename && action.doc_id) {
        filename = action.doc_id.replace(/^doc-/, '')
        if (!filename.toLowerCase().endsWith('.pdf')) {
          filename += '.pdf'
        }
      }
      return {
        ...state,
        viewingDoc: filename || null,
        selectedDocId: action.doc_id || (filename ? `doc-${filename}` : state.selectedDocId),
        viewerPage: action.page || 1,
        viewerHighlight: action.highlightTerm || null,
        viewerMatch: action.searchMatch || null,
      }
    }

    case 'CLOSE_DOCUMENT_VIEWER':
      return {
        ...state,
        viewingDoc: null,
        viewerPage: 1,
        viewerHighlight: null,
        viewerMatch: null,
      }

    case 'SET_MOCK_MODE':
      return { ...state, mockMode: action.mockMode }

    case 'SET_AVAILABLE_DOCS': {
      const isFirstLoad = state.availableDocs.length === 0
      const nextSelected = isFirstLoad
        ? new Set(action.docs.map(d => d.filename))
        : state.selectedDocs

      return {
        ...state,
        availableDocs: action.docs,
        selectedDocs: nextSelected,
      }
    }

    case 'TOGGLE_DOC': {
      const next = new Set(state.selectedDocs)
      if (next.has(action.filename)) {
        next.delete(action.filename)
      } else {
        next.add(action.filename)
      }
      return { ...state, selectedDocs: next }
    }

    case 'SELECT_ALL_DOCS': {
      return { ...state, selectedDocs: new Set(state.availableDocs.map(d => d.filename)) }
    }

    case 'CLEAR_ALL_DOCS': {
      return { ...state, selectedDocs: new Set() }
    }

    case 'SET_SEARCH_QUERY': {
      return { ...state, searchQuery: action.query }
    }

    case 'SET_SEARCHING': {
      return { ...state, isSearching: action.isSearching }
    }

    case 'SET_SEARCH_RESULTS': {
      const hasResults = Boolean(action.results && action.results.results && action.results.results.length > 0)
      return {
        ...state,
        searchResults: action.results,
        searchActive: hasResults,
        isSearching: false,
        workspaceMode: hasResults ? 'search' : state.workspaceMode,
      }
    }

    case 'CLEAR_SEARCH': {
      return {
        ...state,
        searchQuery: '',
        searchResults: null,
        searchActive: false,
        isSearching: false,
        viewerHighlight: null,
        viewerMatch: null,
        workspaceMode: state.workspaceMode === 'search' ? null : state.workspaceMode,
      }
    }

    default:
      return state
  }
}

// ─── Context ──────────────────────────────────────────────────────────────────
const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  // Sync theme to <html data-theme="...">
  useEffect(() => {
    document.documentElement.dataset.theme = state.theme
  }, [state.theme])

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>')
  return ctx
}
