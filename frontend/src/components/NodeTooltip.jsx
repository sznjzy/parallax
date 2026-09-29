/**
 * NodeTooltip.jsx
 *
 * An HTML-layer tooltip (not a Konva shape) that appears on node hover.
 * Rendered as a fixed-position div, positioned near the cursor but
 * automatically flipped if it would overflow the right/bottom edge.
 *
 * Props
 * -----
 *   node      Node     the hovered node (or null to hide)
 *   screenX   number   cursor X in page coordinates
 *   screenY   number   cursor Y in page coordinates
 *   isPinned  boolean  whether this doc has an active constraint
 */
import React, { useRef, useLayoutEffect, useState } from 'react'

const OFFSET = 14  // px from cursor

export default function NodeTooltip({ node, screenX, screenY, isPinned }) {
  const ref = useRef(null)
  const [pos, setPos] = useState({ x: screenX + OFFSET, y: screenY + OFFSET })

  useLayoutEffect(() => {
    if (!ref.current || !node) return
    const { width, height } = ref.current.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight

    let x = screenX + OFFSET
    let y = screenY + OFFSET

    if (x + width > vw - 8)  x = screenX - width - OFFSET
    if (y + height > vh - 8) y = screenY - height - OFFSET

    setPos({ x, y })
  }, [screenX, screenY, node])

  if (!node) return null

  const docLabel     = node.doc_id.replace('doc-', '')
  const clusterShort = node.cluster_id.replace('cluster-', '').replace('noise-', 'noise:')

  return (
    <div
      ref={ref}
      className="node-tooltip"
      style={{ left: pos.x, top: pos.y }}
      role="tooltip"
      aria-label={`Details for ${docLabel}`}
    >
      <div className="tooltip-filename">{docLabel}</div>
      <div className="tooltip-cluster">{node.cluster_id}</div>
      <div className="tooltip-badges">
        {node.is_boundary_document && (
          <span className="badge badge-warning">Boundary</span>
        )}
        {node.is_anchored && (
          <span className="badge badge-accent">Anchored</span>
        )}
        {isPinned && (
          <span className="badge badge-success">📌 Pinned</span>
        )}
        {node.cluster_id.startsWith('noise-') && (
          <span className="badge badge-default">Noise</span>
        )}
      </div>
      <div style={{ fontSize: '0.62rem', color: 'var(--color-text-muted)', marginTop: 5, borderTop: '1px solid var(--color-border)', paddingTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
        <span>📄</span> Click to select & open PDF
      </div>
    </div>
  )
}
