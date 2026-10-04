/**
 * ClusterRegion.jsx
 *
 * Renders a smooth convex hull polygon behind all nodes belonging to one cluster.
 * Replaces axis-aligned ellipses to eliminate severe overlap and accurately enclose
 * cluster members with a smooth spline boundary (Konva Line tension=0.35).
 *
 * Props
 * -----
 *   cluster_id    string     cluster UUID
 *   nodes         Node[]     ALL nodes on canvas — filtered here to the cluster
 *   scale         number     logical→pixel scale factor
 *   isSelected    boolean    highlight when a sibling node is selected
 *   isDragTarget  boolean    pulsing/bold highlight when user is dragging a node over this cluster
 */
import React from 'react'
import { Group, Line, Circle, Rect, Text } from 'react-konva'
import { useApp } from '../state/AppContext'
import { clusterColor } from './clusterColor'

const PADDING = 24 // outward offset in px

/**
 * 2D Cross product of OA and OB vectors.
 * Returns > 0 for counter-clockwise turn, < 0 for clockwise, 0 for collinear.
 */
function cross(o, a, b) {
  return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)
}

/**
 * Monotone Chain Convex Hull algorithm (Andrew's algorithm)
 * Returns array of {x, y} vertices in CCW order.
 */
function convexHull(points) {
  if (points.length <= 2) return points

  const sorted = [...points].sort((a, b) => (a.x === b.x ? a.y - b.y : a.x - b.x))

  const lower = []
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
      lower.pop()
    }
    lower.push(p)
  }

  const upper = []
  for (let i = sorted.length - 1; i >= 0; i--) {
    const p = sorted[i]
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
      upper.pop()
    }
    upper.push(p)
  }

  lower.pop()
  upper.pop()
  return lower.concat(upper)
}

/**
 * Offset hull outward from centroid by padding distance.
 */
function expandHull(hull, cx, cy, padding = PADDING) {
  if (hull.length === 0) return []
  if (hull.length === 1) return hull

  if (hull.length === 2) {
    const [p1, p2] = hull
    const dx = p2.x - p1.x
    const dy = p2.y - p1.y
    const len = Math.hypot(dx, dy) || 1
    const latPad = Math.min(padding, 18)
    const endPad = Math.min(padding, 16)
    const nx = (-dy / len) * latPad
    const ny = (dx / len) * latPad
    const ex = (dx / len) * endPad
    const ey = (dy / len) * endPad

    return [
      { x: p1.x - ex + nx, y: p1.y - ey + ny },
      { x: p2.x + ex + nx, y: p2.y + ey + ny },
      { x: p2.x + ex - nx, y: p2.y + ey - ny },
      { x: p1.x - ex - nx, y: p1.y - ey - ny },
    ]
  }

  return hull.map(p => {
    const vx = p.x - cx
    const vy = p.y - cy
    const dist = Math.hypot(vx, vy)
    if (dist < 1e-4) {
      return { x: p.x + padding, y: p.y }
    }
    const ux = vx / dist
    const uy = vy / dist
    return {
      x: p.x + ux * padding,
      y: p.y + uy * padding,
    }
  })
}

export default function ClusterRegion({
  cluster_id,
  nodes,
  scale,
  isSelected,
  isDragTarget,
  searchActive,
  clusterRelevance,
}) {
  const { state } = useApp()

  // Skip noise pseudo-clusters
  if (cluster_id.startsWith('noise-')) return null

  const clusterNodes = nodes.filter(n => n.cluster_id === cluster_id)
  if (clusterNodes.length === 0) return null

  const pts = clusterNodes.map(n => ({ x: n.x * scale, y: n.y * scale }))
  const cx = pts.reduce((sum, p) => sum + p.x, 0) / pts.length
  const cy = pts.reduce((sum, p) => sum + p.y, 0) / pts.length

  const color = clusterColor(cluster_id)

  // Search relevance calculations (Phase 6)
  const maxSim = clusterRelevance ? clusterRelevance.max_similarity : 0
  const isRelevantCluster = Boolean(searchActive && clusterRelevance && maxSim >= 0.35)

  let fillOpacity = 0.09
  let strokeOpacity = 0.35
  let strokeWidth = 1.5

  if (isDragTarget) {
    fillOpacity = 0.28
    strokeOpacity = 0.90
    strokeWidth = 2.5
  } else if (isSelected) {
    fillOpacity = 0.20
    strokeOpacity = 0.65
    strokeWidth = 2.0
  } else if (searchActive) {
    fillOpacity = isRelevantCluster ? Math.min(0.32, 0.12 + maxSim * 0.22) : 0.03
    strokeOpacity = isRelevantCluster ? 0.85 : 0.15
    strokeWidth = isRelevantCluster ? 2.2 : 1.0
  }

  const isHighlighted = isSelected || isDragTarget || isRelevantCluster

  const shortClusterLabel = cluster_id.replace(/^cluster-/, '').slice(0, 6)
  const topicMeta = state?.topics?.[cluster_id]
  const displayTitle = topicMeta?.topic_label || `Topic ${shortClusterLabel}`
  const countSubtitle = searchActive && isRelevantCluster
    ? `${Math.round(maxSim * 100)}% relevance`
    : `${clusterNodes.length} ${clusterNodes.length === 1 ? 'document' : 'documents'}`

  const isDark = state.theme !== 'light'

  // 1 Node special case: circle
  if (pts.length === 1) {
    const r = 32
    return (
      <Group listening={false}>
        <Circle
          x={cx}
          y={cy}
          radius={r}
          fill={color}
          opacity={fillOpacity}
          listening={false}
        />
        <Circle
          x={cx}
          y={cy}
          radius={r}
          stroke={color}
          strokeWidth={strokeWidth}
          opacity={strokeOpacity}
          dash={isDragTarget ? [4, 2] : [6, 4]}
          listening={false}
        />
        <ScientificClusterAnnotation
          cx={cx}
          cy={cy - r - 20}
          title={displayTitle}
          subtitle={countSubtitle}
          color={color}
          isHighlighted={isHighlighted}
          isDark={isDark}
        />
      </Group>
    )
  }

  // 2+ Nodes: Convex hull
  const rawHull = pts.length === 2 ? pts : convexHull(pts)
  const expanded = expandHull(rawHull, cx, cy, PADDING)
  const flatPoints = expanded.flatMap(p => [p.x, p.y])

  // Compute top-most point for badge position
  const minY = Math.min(...expanded.map(p => p.y))

  return (
    <Group listening={false}>
      {/* Smooth Hull Region Fill & Stroke */}
      <Line
        points={flatPoints}
        closed
        tension={0.35}
        fill={color}
        opacity={fillOpacity}
        stroke={color}
        strokeWidth={strokeWidth}
        dash={isDragTarget ? [4, 2] : [6, 4]}
        listening={false}
      />

      {/* Scientific Floating Cluster Annotation */}
      <ScientificClusterAnnotation
        cx={cx}
        cy={minY - 24}
        title={displayTitle}
        subtitle={countSubtitle}
        color={color}
        isHighlighted={isHighlighted}
        isDark={isDark}
      />
    </Group>
  )
}

function ScientificClusterAnnotation({ cx, cy, title, subtitle, color, isHighlighted, isDark }) {
  const maxLen = Math.max(title.length, subtitle.length)
  const boxWidth = Math.max(100, maxLen * 6.5 + 20)
  const boxHeight = 26

  const bgFill = isDark ? "rgba(11, 14, 20, 0.78)" : "rgba(255, 255, 255, 0.92)"
  const defaultBorder = isDark ? "rgba(255, 255, 255, 0.08)" : "#cbd5e1"
  const titleFill = isHighlighted ? color : (isDark ? "#f0f6fc" : "#0f172a")
  const subtitleFill = isDark ? "#8b949e" : "#475569"

  return (
    <Group x={cx - boxWidth / 2} y={cy} listening={false}>
      {/* Subtle translucent backdrop */}
      <Rect
        width={boxWidth}
        height={boxHeight}
        cornerRadius={5}
        fill={bgFill}
        stroke={isHighlighted ? color : defaultBorder}
        strokeWidth={isHighlighted ? 1.2 : 0.8}
        shadowColor={isDark ? "#000000" : "#64748b"}
        shadowBlur={isDark ? 8 : 4}
        shadowOpacity={isDark ? 0.4 : 0.12}
      />
      {/* Topic Title */}
      <Text
        text={title}
        fontSize={9.5}
        fontFamily="Inter, system-ui, -apple-system, sans-serif"
        fontStyle="600"
        fill={titleFill}
        width={boxWidth}
        align="center"
        y={4}
      />
      {/* Document Count Subtitle */}
      <Text
        text={subtitle}
        fontSize={8}
        fontFamily="Inter, system-ui, -apple-system, sans-serif"
        fill={subtitleFill}
        width={boxWidth}
        align="center"
        y={15}
      />
    </Group>
  )
}
