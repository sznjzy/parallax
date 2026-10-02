/**
 * useCanvasSize.js
 *
 * Returns { width, height } of a given ref'd container element.
 * Updates automatically on window resize via ResizeObserver.
 *
 * Used by ResearchCanvas to calculate the Konva Stage scale:
 *   scale = min(containerWidth / LOGICAL_W, containerHeight / LOGICAL_H)
 */
import { useState, useEffect, useLayoutEffect } from 'react'

export function useCanvasSize(containerRef) {
  const [size, setSize] = useState(() => {
    if (typeof window !== 'undefined') {
      return {
        width: window.innerWidth || 800,
        height: window.innerHeight || 600,
      }
    }
    return { width: 800, height: 600 }
  })

  useLayoutEffect(() => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      if (rect.width > 0 && rect.height > 0) {
        setSize({ width: rect.width, height: rect.height })
      }
    }
  }, [containerRef])

  useEffect(() => {
    if (!containerRef.current) return

    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) {
          setSize(prev => {
            if (prev.width === width && prev.height === height) return prev
            return { width, height }
          })
        }
      }
    })

    observer.observe(containerRef.current)

    // Immediate rect check in effect
    const rect = containerRef.current.getBoundingClientRect()
    if (rect.width > 0 && rect.height > 0) {
      setSize(prev => {
        if (prev.width === rect.width && prev.height === rect.height) return prev
        return { width: rect.width, height: rect.height }
      })
    }

    return () => observer.disconnect()
  }, [containerRef])

  return size
}
