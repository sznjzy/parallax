/**
 * useCanvasSize.js
 *
 * Returns { width, height } of a given ref'd container element.
 * Updates automatically on window resize via ResizeObserver.
 *
 * Used by ResearchCanvas to calculate the Konva Stage scale:
 *   scale = min(containerWidth / LOGICAL_W, containerHeight / LOGICAL_H)
 */
import { useState, useEffect } from 'react'

export function useCanvasSize(containerRef) {
  const [size, setSize] = useState({ width: 800, height: 600 })

  useEffect(() => {
    if (!containerRef.current) return

    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) {
          setSize({ width, height })
        }
      }
    })

    observer.observe(containerRef.current)

    // Set immediately without waiting for first resize event.
    const rect = containerRef.current.getBoundingClientRect()
    if (rect.width > 0 && rect.height > 0) {
      setSize({ width: rect.width, height: rect.height })
    }

    return () => observer.disconnect()
  }, [containerRef])

  return size
}
