/**
 * DocumentNode.jsx
 *
 * Single draggable document node on the Konva canvas.
 *
 * Visual states
 * -------------
 *   default      — filled circle, cluster colour
 *   boundary     — dashed outer ring in same colour
 *   noise/outlier— dashed grey border ring + outlier badge
 *   anchored     — gold pin icon
 *   constrained  — gold pin icon overlay
 *   selected     — glow ring + boosted shadow
 *   hover        — scale up + shadow bloom
 *   dragging     — lifted shadow, cursor grabbing
 *
 * Props
 * -----
 *   node         Node       position + metadata from /api/organize
 *   scale        number     logical→pixel scale factor
 *   isSelected   boolean
 *   isDimmed     boolean    true when another node is selected and this one is not a peer
 *   isPinned     boolean    this doc has an active user constraint
 *   onSelect     (doc_id) => void
 *   onHover      (node, x, y) | null => void
 *   onDragMove   (doc_id, logicalX, logicalY, isShiftKey) => void
 *   onDragEnd    (doc_id, logicalX, logicalY, isShiftKey) => void
 */
import React, { useRef, useState, useEffect, memo } from 'react'
import { Group, Circle, Ring, Text, Rect } from 'react-konva'
import Konva from 'konva'
import { clusterColor } from './clusterColor'

const BASE_RADIUS    = 12
const BOUNDARY_OUTER = 17
const HOVER_SCALE    = 1.05
const DRAG_SCALE     = 1.18

/** Truncate filename: "doc-paper1.pdf" → "paper1" */
function shortLabel(doc_id) {
  return doc_id
    .replace(/^doc-/, '')
    .replace(/\.pdf$/i, '')
    .slice(0, 12)
}

function DocumentNode({
  node,
  scale,
  isSelected,
  isDimmed,
  isPinned,
  isDark = true,
  searchActive,
  searchResult,
  onSelect,
  onOpenPdf,
  onHover,
  onDragMove,
  onDragEnd,
}) {
  const [hovered, setHovered]   = useState(false)
  const [dragging, setDragging] = useState(false)
  const groupRef = useRef(null)
  // Manual dblclick detection — bypasses Konva hit-buffer race after SELECT_NODE re-render
  const lastClickTimeRef = useRef(0)

  const px = node.x * scale
  const py = node.y * scale

  const isNoise   = node.cluster_id.startsWith('noise-')
  const color     = clusterColor(node.cluster_id)
  const nodeColor = isNoise ? (isDark ? '#6e7681' : '#64748b') : color

  // Search relevance calculations (Phase 6)
  const sim = searchResult ? searchResult.similarity_score : 0
  const isMatch = Boolean(searchActive && searchResult && sim > 0.15)
  const isTopMatch = Boolean(searchActive && searchResult && searchResult.rank <= 3)
  const relevancePct = Math.round(Math.max(0, sim) * 100)

  // Dynamic opacity
  let opacity = 1.0
  if (searchActive) {
    opacity = isMatch ? Math.min(1.0, 0.4 + sim * 0.6) : 0.18
  } else if (isDimmed) {
    opacity = 0.22
  }

  // Shadow config
  const shadowBlur  = dragging ? 28 : (isTopMatch ? 24 : hovered ? 18 : isSelected ? 14 : isMatch ? 12 : 0)
  const shadowColor = isMatch ? '#58a6ff' : nodeColor
  const searchScaleBoost = isTopMatch ? 1.22 : isMatch ? 1.08 + sim * 0.12 : 1.0
  const curScale    = dragging ? DRAG_SCALE : (hovered ? HOVER_SCALE : 1.0) * searchScaleBoost

  const isFirstRenderRef = useRef(true)
  const prevPosRef = useRef({ x: px, y: py })

  // Sync position with props via smooth tween only on subsequent updates (skip initial mount to avoid hit-canvas desync)
  useEffect(() => {
    if (groupRef.current && !dragging) {
      if (isFirstRenderRef.current) {
        isFirstRenderRef.current = false
        groupRef.current.position({ x: px, y: py })
        prevPosRef.current = { x: px, y: py }
        const layer = groupRef.current.getLayer()
        if (layer) {
          layer.batchDraw()
          layer.drawHit()
        }
        return
      }

      const prev = prevPosRef.current
      if (Math.abs(prev.x - px) > 0.5 || Math.abs(prev.y - py) > 0.5) {
        groupRef.current.to({
          x: px,
          y: py,
          duration: 0.28,
          easing: Konva.Easings.EaseOut,
          onFinish: () => {
            const layer = groupRef.current?.getLayer()
            if (layer) {
              layer.batchDraw()
              layer.drawHit()
            }
          }
        })
        prevPosRef.current = { x: px, y: py }
      }
    }
  }, [px, py, dragging])

  return (
    <Group
      ref={groupRef}
      x={px}
      y={py}
      opacity={opacity}
      scaleX={curScale}
      scaleY={curScale}
      draggable
      dragDistance={8}
      onMouseDown={e => {
        e.cancelBubble = true
      }}
      onTouchStart={e => {
        e.cancelBubble = true
      }}
      onMouseEnter={e => {
        e.cancelBubble = true
        setHovered(true)
        e.target.getStage().container().style.cursor = 'grab'
        if (onHover) {
          onHover(node, e.evt.clientX, e.evt.clientY)
        }
      }}
      onMouseLeave={e => {
        e.cancelBubble = true
        setHovered(false)
        e.target.getStage().container().style.cursor = 'default'
        if (onHover) onHover(null, 0, 0)
      }}
      onMouseMove={e => {
        e.cancelBubble = true
        if (onHover) {
          onHover(node, e.evt.clientX, e.evt.clientY)
        }
      }}
      onClick={e => {
        e.cancelBubble = true
        const now = Date.now()
        const delta = now - lastClickTimeRef.current
        if (delta < 450) {
          // Two clicks within 450 ms on the same node → open PDF
          lastClickTimeRef.current = 0
          if (onOpenPdf) onOpenPdf(node.doc_id)
        } else {
          // First click → select node
          lastClickTimeRef.current = now
          if (onSelect) onSelect(node.doc_id)
        }
      }}
      onTap={e => {
        e.cancelBubble = true
        const now = Date.now()
        const delta = now - lastClickTimeRef.current
        if (delta < 450) {
          lastClickTimeRef.current = 0
          if (onOpenPdf) onOpenPdf(node.doc_id)
        } else {
          lastClickTimeRef.current = now
          if (onSelect) onSelect(node.doc_id)
        }
      }}
      onDblClick={e => {
        // Native fallback — reset timer to avoid triple-click issues
        e.cancelBubble = true
        lastClickTimeRef.current = 0
        if (onOpenPdf) onOpenPdf(node.doc_id)
      }}
      onDblTap={e => {
        e.cancelBubble = true
        lastClickTimeRef.current = 0
        if (onOpenPdf) onOpenPdf(node.doc_id)
      }}
      onDragStart={e => {
        e.cancelBubble = true
        setDragging(true)
        lastClickTimeRef.current = 0   // reset dblclick timer — drag ≠ click
        e.target.getStage().container().style.cursor = 'grabbing'
        if (groupRef.current) groupRef.current.moveToTop()
      }}
      onDragMove={e => {
        e.cancelBubble = true
        if (onDragMove) {
          const logX = e.target.x() / scale
          const logY = e.target.y() / scale
          onDragMove(node.doc_id, logX, logY, e.evt?.shiftKey ?? false)
        }
      }}
      onDragEnd={e => {
        e.cancelBubble = true
        setDragging(false)
        e.target.getStage().container().style.cursor = 'grab'
        const logX = e.target.x() / scale
        const logY = e.target.y() / scale
        const isShiftKey = e.evt?.shiftKey ?? false

        if (onDragEnd) {
          onDragEnd(node.doc_id, logX, logY, isShiftKey, () => {
            // Callback to snap back immediately if rejected or non-constraint drag
            if (groupRef.current) {
              groupRef.current.to({
                x: px,
                y: py,
                duration: 0.25,
                easing: Konva.Easings.EaseInOut,
                onFinish: () => {
                  const layer = groupRef.current?.getLayer()
                  if (layer) {
                    layer.batchDraw()
                    layer.drawHit()
                  }
                }
              })
            }
          })
        }
      }}
    >
      {/* Semantic Search Heatmap Aura / Halo (Phase 6) */}
      {isMatch && (
        <Group listening={false}>
          {/* Outer diffuse glow */}
          <Circle
            radius={BASE_RADIUS + 7 + sim * 7}
            fill="#58a6ff"
            opacity={0.15 + sim * 0.25}
            shadowColor="#58a6ff"
            shadowBlur={16 + sim * 12}
            shadowOpacity={0.8}
            listening={false}
          />
          {/* Radiant pulse ring */}
          <Ring
            innerRadius={BASE_RADIUS + 3}
            outerRadius={BASE_RADIUS + 5 + sim * 4}
            fill="#58a6ff"
            opacity={0.5 + sim * 0.4}
            listening={false}
          />
        </Group>
      )}

      {/* Noise / Outlier ring */}
      {isNoise && (
        <Ring
          innerRadius={BASE_RADIUS + 2}
          outerRadius={BOUNDARY_OUTER + 1}
          stroke="#8b949e"
          strokeWidth={1}
          dash={[3, 3]}
          opacity={0.65}
          listening={false}
        />
      )}

      {/* Boundary ring — dashed outer circle */}
      {node.is_boundary_document && !isNoise && (
        <Ring
          innerRadius={BASE_RADIUS + 2}
          outerRadius={BOUNDARY_OUTER}
          fill={nodeColor}
          opacity={0.35}
          dash={[4, 3]}
          listening={false}
        />
      )}

      {/* Main filled circle — precise primary hit target */}
      <Circle
        radius={BASE_RADIUS}
        fill={nodeColor}
        shadowColor={shadowColor}
        shadowBlur={shadowBlur}
        shadowOpacity={0.7}
        shadowOffsetX={0}
        shadowOffsetY={dragging ? 4 : 0}
        listening={true}
      />

      {/* Match Score Badge for Semantic Search */}
      {isMatch && (
        <Group y={-BASE_RADIUS - 13} listening={false}>
          <Rect
            x={-14}
            y={0}
            width={28}
            height={11}
            cornerRadius={4}
            fill="rgba(88, 166, 255, 0.92)"
            stroke="#1f6feb"
            strokeWidth={0.5}
            shadowColor="#58a6ff"
            shadowBlur={6}
            shadowOpacity={0.5}
            listening={false}
          />
          <Text
            text={`${relevancePct}%`}
            fontSize={7}
            fontFamily="Inter, system-ui, sans-serif"
            fontStyle="bold"
            fill="#ffffff"
            align="center"
            width={28}
            x={-14}
            y={1.5}
            listening={false}
          />
        </Group>
      )}

      {/* Selected ring */}
      {isSelected && (
        <Circle
          radius={BASE_RADIUS + 4}
          stroke={nodeColor}
          strokeWidth={1.8}
          fill="transparent"
          opacity={0.9}
          listening={false}
        />
      )}

      {/* Anchored / pinned indicator */}
      {isPinned && (
        <Text
          text="📌"
          fontSize={10}
          x={-5}
          y={-BASE_RADIUS - 12}
          listening={false}
        />
      )}

      {/* Outlier pill for noise nodes */}
      {isNoise && (
        <Group y={BASE_RADIUS + 13}>
          <Rect
            x={-16}
            y={0}
            width={32}
            height={11}
            cornerRadius={3}
            fill={isDark ? "rgba(110, 118, 129, 0.25)" : "rgba(100, 116, 139, 0.18)"}
            stroke={isDark ? "#6e7681" : "#64748b"}
            strokeWidth={0.6}
            listening={false}
          />
          <Text
            text="outlier"
            fontSize={7}
            fill={isDark ? "#8b949e" : "#334155"}
            align="center"
            width={32}
            x={-16}
            y={1.5}
            listening={false}
          />
        </Group>
      )}

      {/* Unified node + label hit target */}
      <Rect
        x={-18}
        y={-BASE_RADIUS - 2}
        width={36}
        height={BASE_RADIUS * 2 + 18}
        fill="rgba(0,0,0,0.001)"
        cornerRadius={8}
        listening={true}
      />

      {/* Label */}
      <Text
        text={shortLabel(node.doc_id)}
        fontSize={8.5}
        fontFamily="Inter, system-ui, -apple-system, sans-serif"
        fontStyle="500"
        fill={isDark ? "#e6edf3" : "#0f172a"}
        opacity={0.95}
        align="center"
        width={74}
        x={-37}
        y={BASE_RADIUS + 3}
        listening={true}
      />
    </Group>
  )
}

function areDocumentNodePropsEqual(prev, next) {
  return (
    prev.node.doc_id === next.node.doc_id &&
    prev.node.x === next.node.x &&
    prev.node.y === next.node.y &&
    prev.node.cluster_id === next.node.cluster_id &&
    prev.node.is_boundary_document === next.node.is_boundary_document &&
    prev.scale === next.scale &&
    prev.isSelected === next.isSelected &&
    prev.isDimmed === next.isDimmed &&
    prev.isPinned === next.isPinned &&
    prev.isDark === next.isDark &&
    prev.searchActive === next.searchActive &&
    prev.searchResult === next.searchResult &&
    prev.onSelect === next.onSelect &&
    prev.onOpenPdf === next.onOpenPdf &&
    prev.onHover === next.onHover &&
    prev.onDragMove === next.onDragMove &&
    prev.onDragEnd === next.onDragEnd
  )
}

export default memo(DocumentNode, areDocumentNodePropsEqual)
