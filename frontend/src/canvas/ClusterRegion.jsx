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

export default function ClusterRegion({ cluster_id, nodes, scale, isSelected, isDragTarget }) {
  // Skip noise pseudo-clusters
  if (cluster_id.startsWith('noise-')) return null

  const clusterNodes = nodes.filter(n => n.cluster_id === cluster_id)
  if (clusterNodes.length === 0) return null

  const pts = clusterNodes.map(n => ({ x: n.x * scale, y: n.y * scale }))
  const cx = pts.reduce((sum, p) => sum + p.x, 0) / pts.length
  const cy = pts.reduce((sum, p) => sum + p.y, 0) / pts.length

  const color = clusterColor(cluster_id)
  const isHighlighted = isSelected || isDragTarget
  const fillOpacity = isDragTarget ? 0.28 : isSelected ? 0.20 : 0.09
  const strokeOpacity = isDragTarget ? 0.90 : isSelected ? 0.65 : 0.35
  const strokeWidth = isDragTarget ? 2.5 : isSelected ? 2 : 1.5

  const shortClusterLabel = cluster_id.replace(/^cluster-/, '').slice(0, 6)
  const labelText = `Topic ${shortClusterLabel} · ${clusterNodes.length}`

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
        <CentroidBadge cx={cx} cy={cy - r - 12} text={labelText} color={color} isHighlighted={isHighlighted} />
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

      {/* Centroid Label Badge */}
      <CentroidBadge cx={cx} cy={minY - 14} text={labelText} color={color} isHighlighted={isHighlighted} />
    </Group>
  )
}

function CentroidBadge({ cx, cy, text, color, isHighlighted }) {
  const badgeWidth = text.length * 6 + 18
  const badgeHeight = 16

  return (
    <Group x={cx - badgeWidth / 2} y={cy} listening={false}>
      <Rect
        width={badgeWidth}
        height={badgeHeight}
        cornerRadius={8}
        fill="rgba(13, 17, 23, 0.85)"
        stroke={color}
        strokeWidth={isHighlighted ? 1.5 : 0.8}
        opacity={isHighlighted ? 1.0 : 0.75}
      />
      <Text
        text={text}
        fontSize={8.5}
        fontFamily="Inter, system-ui, sans-serif"
        fontStyle="bold"
        fill={color}
        width={badgeWidth}
        height={badgeHeight}
        align="center"
        verticalAlign="middle"
        y={1}
      />
    </Group>
  )
}
