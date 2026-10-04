/**
 * CommandBar.jsx
 *
 * Floating search and command interface for Parallax.
 * Minimal, unified research search box with keyboard hint (/) and clean status indicators.
 */
import React, { useState, useEffect, useRef } from 'react'
import { useSearch } from '../hooks/useSearch'
import { useApp } from '../state/AppContext'

export default function CommandBar() {
  const { state, dispatch } = useApp()
  const { search, clearSearch, isSearching, searchActive, searchResults } = useSearch()
  const [localQuery, setLocalQuery] = useState(state.searchQuery || '')
  const inputRef = useRef(null)

  useEffect(() => {
    setLocalQuery(state.searchQuery || '')
  }, [state.searchQuery])

  // Global hotkeys: "/" to focus, "Escape" to clear/blur
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) && document.activeElement !== inputRef.current) {
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName) || document.activeElement?.isContentEditable) {
          return
        }
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      } else if (e.key === 'Escape' && document.activeElement === inputRef.current) {
        if (localQuery) {
          setLocalQuery('')
          clearSearch()
        }
        inputRef.current?.blur()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [localQuery, clearSearch])

  const handleSubmit = (e) => {
    e.preventDefault()
    const q = localQuery.trim()
    if (!q) {
      clearSearch()
      return
    }
    search(q)
    dispatch({ type: 'SET_WORKSPACE_MODE', mode: 'search' })
  }

  const handleClear = () => {
    setLocalQuery('')
    clearSearch()
    inputRef.current?.focus()
  }

  const matchCount = searchResults?.results?.length ?? 0
  const isRunning = state.status === 'running' || state.status === 'loading'
  const isError = state.status === 'error'

  return (
    <div className="command-bar-wrapper" role="region" aria-label="Command & Search Bar">
      <form className="command-bar-form" onSubmit={handleSubmit} role="search">
        <div className={`command-bar-box ${searchActive ? 'active' : ''} ${isSearching ? 'loading' : ''}`}>
          {/* Search SVG Icon / Spinner */}
          <span className="command-bar-icon" aria-hidden="true">
            {isSearching ? (
              <span className="command-spinner" />
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.35-4.35" />
              </svg>
            )}
          </span>

          {/* Search Input */}
          <input
            ref={inputRef}
            type="text"
            id="command-search-input"
            className="command-bar-input"
            placeholder="Search research concepts or keywords…"
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            onFocus={() => {
              if (searchActive && state.workspaceMode !== 'search') {
                dispatch({ type: 'SET_WORKSPACE_MODE', mode: 'search' })
              }
            }}
            aria-label="Search research concepts"
          />

          {/* Active Matches Count Pill */}
          {searchActive && !isSearching && (
            <span className="command-matches-tag" title={`${matchCount} documents matched`}>
              {matchCount} {matchCount === 1 ? 'doc' : 'docs'}
            </span>
          )}

          {/* Clear Button */}
          {localQuery ? (
            <button
              type="button"
              className="command-icon-btn"
              onClick={handleClear}
              title="Clear search (Esc)"
              aria-label="Clear query"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 6 6 18" />
                <path d="m6 6 12 12" />
              </svg>
            </button>
          ) : (
            <kbd className="command-hotkey-hint" title="Press / to focus search">/</kbd>
          )}
        </div>
      </form>

      {/* Floating Quiet Status Pill */}
      {(isRunning || isError) && (
        <div className={`command-status-pill ${isError ? 'error' : 'running'}`}>
          <span className={`status-dot ${isRunning ? 'pulse' : ''}`} />
          <span>{state.statusMessage || (isRunning ? 'Processing pipeline…' : 'An error occurred')}</span>
        </div>
      )}
    </div>
  )
}
