/**
 * SearchBar.jsx
 *
 * Semantic search input bar for the Parallax topbar / canvas.
 * Allows users to query the corpus via sentence-transformers embeddings.
 */

import React, { useState, useEffect, useRef } from 'react'
import { useSearch } from '../hooks/useSearch'
import { useApp } from '../state/AppContext'

export default function SearchBar() {
  const { state } = useApp()
  const { search, clearSearch, isSearching, searchActive, searchResults } = useSearch()
  const [localQuery, setLocalQuery] = useState(state.searchQuery || '')
  const inputRef = useRef(null)

  // Keep local query in sync if global state changes
  useEffect(() => {
    setLocalQuery(state.searchQuery || '')
  }, [state.searchQuery])

  // Global keyboard shortcuts: "/" to focus search, "Escape" to clear/blur
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        // Prevent typing '/' into another input if already focused
        if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return
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
    if (!localQuery.trim()) {
      clearSearch()
      return
    }
    search(localQuery.trim())
  }

  const handleClear = () => {
    setLocalQuery('')
    clearSearch()
    inputRef.current?.focus()
  }

  const matchCount = searchResults?.results?.length ?? 0

  return (
    <form className="search-bar-form" onSubmit={handleSubmit} role="search" aria-label="Semantic Search">
      <div className={`search-bar-container ${searchActive ? 'active' : ''} ${isSearching ? 'loading' : ''}`}>
        {/* Search icon or spinner */}
        <span className="search-icon" aria-hidden="true">
          {isSearching ? (
            <span className="search-spinner" />
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
          )}
        </span>

        {/* Text Input */}
        <input
          ref={inputRef}
          type="text"
          id="search-input"
          className="search-input"
          placeholder="Semantic search corpus… (/ to focus)"
          value={localQuery}
          onChange={(e) => setLocalQuery(e.target.value)}
          aria-label="Search corpus by semantic concept or keyword"
        />

        {/* Match Count Badge */}
        {searchActive && !isSearching && (
          <span className="search-badge" title={`${matchCount} documents ranked by similarity`}>
            {matchCount} {matchCount === 1 ? 'match' : 'matches'}
          </span>
        )}

        {/* Clear Button */}
        {localQuery && (
          <button
            type="button"
            className="search-clear-btn"
            onClick={handleClear}
            title="Clear search (Esc)"
            aria-label="Clear search query"
          >
            ✕
          </button>
        )}

        {/* Submit action button */}
        <button
          type="submit"
          className="search-submit-btn"
          disabled={isSearching || !localQuery.trim()}
          title="Search"
          aria-label="Execute semantic search"
        >
          Search
        </button>
      </div>
    </form>
  )
}
