/**
 * ResearchCanvas.jsx
 *
 * The main Konva Stage. Renders cluster convex hull regions (background)
 * and document nodes (foreground). Handles:
 *   - Logical → pixel coordinate scaling (backend 400×300 → screen px)
 *   - Stage-level drag (pan)
 *   - Mouse-wheel zoom
 *   - Node selection (click to highlight cluster peers)
 *   - Shift+drag intent constraint creation with live drop-zone highlight
 *   - Smooth snap-back on plain drag (prevents accidental constraints)
 *   - PNG and JSON canvas export
 *
 * Props
 * -----
 *   onConstraintAdded   (doc_id, cluster_id, label) => void
 *       Called after a successful drag-to-constrain so the parent can
 *       show the ConstraintToast.
 */
import React, { useRef, useState, useCallback, useEffect, useMemo } from 'react'
import { Stage, Layer } from 'react-konva'
import { useApp } from '../state/AppContext'
import { useCanvasSize } from '../hooks/useCanvasSize'
import { useConstraints } from '../hooks/useConstraints'
import ClusterRegion from './ClusterRegion'
import DocumentNode from './DocumentNode'
import NodeTooltip from '../components/NodeTooltip'
import SelectedNodeBar from '../components/SelectedNodeBar'
import { registerClusters } from './clusterColor'

// Logical canvas dimensions — must match physics.py CANVAS_WIDTH / CANVAS_HEIGHT
const LOGICAL_W = 400
const LOGICAL_H = 300

const MIN_SCALE = 0.4
const MAX_SCALE = 5.0
const ZOOM_FACTOR = 1.05

export default function ResearchCanvas({ onConstraintAdded }) {
  const { state, dispatch } = useApp()
  const { addConstraint } = useConstraints()
  const containerRef = useRef(null)
  const stageRef = useRef(null)
  const nodeLayerRef = useRef(null)
  const { width: containerW, height: containerH } = useCanvasSize(containerRef)

  // ── Coordinate mapping with margin insets ─────────────────────────
  const PADDING_TOP = 28
  const PADDING_BOTTOM = 88  // Space for SelectedNodeBar at bottom
  const PADDING_SIDE = 48
  const availW = Math.max(100, containerW - PADDING_SIDE * 2)
  const availH = Math.max(100, containerH - (PADDING_TOP + PADDING_BOTTOM))
  const baseScale = Math.min(availW / LOGICAL_W, availH / LOGICAL_H)
  const offsetX = (containerW - LOGICAL_W * baseScale) / 2
  const offsetY = PADDING_TOP + (availH - LOGICAL_H * baseScale) / 2

  // ── Stage transform state (pan + zoom) ────────────────────────────
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 })
  const [stageScale, setStageScale] = useState(1.0)

  // ── Live drag target highlight state ──────────────────────────────
  const [dragTargetClusterId, setDragTargetClusterId] = useState(null)

  // Reset transform when new data loads
  useEffect(() => {
    if (state.nodes.length > 0) {
      setStagePos({ x: 0, y: 0 })
      setStageScale(1.0)
    }
  }, [state.nodes])

  // Synchronize Konva hit buffers on dimension / transform changes
  useEffect(() => {
    if (stageRef.current) {
      stageRef.current.batchDraw()
    }
    if (nodeLayerRef.current) {
      nodeLayerRef.current.batchDraw()
      nodeLayerRef.current.drawHit()
    }
  }, [containerW, containerH, baseScale, stageScale, stagePos, state.nodes])

  // Custom events for reset zoom & export
  useEffect(() => {
    const onReset = () => {
      setStagePos({ x: 0, y: 0 })
      setStageScale(1.0)
    }

    const onExportPNG = () => {
      if (!stageRef.current) return
      const dataUrl = stageRef.current.toDataURL({ pixelRatio: 2 })
      const link = document.createElement('a')
      link.download = `parallax-canvas-${Date.now()}.png`
      link.href = dataUrl
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }

    const onExportJSON = () => {
      const exportData = {
        exported_at: new Date().toISOString(),
        num_nodes: state.nodes.length,
        num_clusters: new Set(state.nodes.map(n => n.cluster_id)).size,
        evaluation: state.evaluation,
        constraints: state.constraints,
        nodes: state.nodes,
      }
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.download = `parallax-clusters-${Date.now()}.json`
      link.href = url
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }

    window.addEventListener('parallax-reset-zoom', onReset)
    window.addEventListener('parallax-export-png', onExportPNG)
    window.addEventListener('parallax-export-json', onExportJSON)

    return () => {
      window.removeEventListener('parallax-reset-zoom', onReset)
      window.removeEventListener('parallax-export-png', onExportPNG)
      window.removeEventListener('parallax-export-json', onExportJSON)
    }
  }, [state.nodes, state.evaluation, state.constraints])

  // ── Wheel zoom / pan ────────────────────────────────────────────────
  const handleWheel = useCallback(e => {
    e.evt.preventDefault()

    // Pan if not holding Ctrl (or Meta)
    if (!e.evt.ctrlKey && !e.evt.metaKey) {
      setStagePos(pos => ({
        x: pos.x - e.evt.deltaX,
        y: pos.y - e.evt.deltaY,
      }))
      return
    }

    const stage = stageRef.current
    const pointer = stage.getPointerPosition()
    const oldScale = stageScale
    const direction = e.evt.deltaY < 0 ? 1 : -1
    const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, oldScale * (direction > 0 ? ZOOM_FACTOR : 1 / ZOOM_FACTOR)))

    const mousePointTo = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    }

    setStageScale(newScale)
    setStagePos({
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale,
    })
  }, [stageScale])

  // ── Node selection ─────────────────────────────────────────────────
  const handleSelect = useCallback(doc_id => {
    dispatch({ type: 'SELECT_NODE', doc_id })
  }, [dispatch])

  // ── Tooltip state ─────────────────────────────────────────────────
  const [tooltip, setTooltip] = useState({ node: null, x: 0, y: 0 })
  const handleHover = useCallback((node, x, y) => {
    setTooltip({ node, x, y })
  }, [])

  // ── Cluster centroid lookup ───────────────────────────────────────
  const clusterCentroids = useMemo(() => {
    const clusters = {}
    for (const n of state.nodes) {
      if (!n.cluster_id.startsWith('noise-')) {
        if (!clusters[n.cluster_id]) clusters[n.cluster_id] = { xs: [], ys: [] }
        clusters[n.cluster_id].xs.push(n.x)
        clusters[n.cluster_id].ys.push(n.y)
      }
    }
    const centroids = {}
    for (const [cid, { xs, ys }] of Object.entries(clusters)) {
      centroids[cid] = {
        x: xs.reduce((a, b) => a + b, 0) / xs.length,
        y: ys.reduce((a, b) => a + b, 0) / ys.length,
      }
    }
    return centroids
  }, [state.nodes])

  // ── Drag move tracking for target cluster highlight ───────────────
  const handleDragMove = useCallback((doc_id, logX, logY, isShiftKey) => {
    if (!isShiftKey) {
      if (dragTargetClusterId) setDragTargetClusterId(null)
      return
    }

    const thisNode = state.nodes.find(n => n.doc_id === doc_id)
    const originalCluster = thisNode?.cluster_id

    let nearestCluster = null
    let nearestDist = Infinity

    for (const [cid, centroid] of Object.entries(clusterCentroids)) {
      const d = Math.hypot(logX - centroid.x, logY - centroid.y)
      if (d < nearestDist) {
        nearestDist = d
        nearestCluster = cid
      }
    }

    if (nearestCluster && nearestCluster !== originalCluster) {
      setDragTargetClusterId(nearestCluster)
    } else {
      setDragTargetClusterId(null)
    }
  }, [state.nodes, clusterCentroids, dragTargetClusterId])

  // ── Drag end & constraint handling ────────────────────────────────
  const handleDragEnd = useCallback(async (doc_id, logX, logY, isShiftKey, snapBack) => {
    setDragTargetClusterId(null)

    // Plain drag (no Shift): visual explore only, snap back smoothly
    if (!isShiftKey) {
      snapBack()
      return
    }

    // Shift held: find nearest target cluster
    let nearestCluster = null
    let nearestDist = Infinity

    for (const [cid, centroid] of Object.entries(clusterCentroids)) {
      const d = Math.hypot(logX - centroid.x, logY - centroid.y)
      if (d < nearestDist) {
        nearestDist = d
        nearestCluster = cid
      }
    }

    const thisNode = state.nodes.find(n => n.doc_id === doc_id)
    const originalCluster = thisNode?.cluster_id

    // Only create constraint if dropped into a different cluster
    if (nearestCluster && nearestCluster !== originalCluster) {
      try {
        const targetCentroid = clusterCentroids[nearestCluster]
        await addConstraint(doc_id, nearestCluster)

        // Optimistically snap the node near the centroid with small jitter
        if (targetCentroid) {
          const jitterX = (Math.random() - 0.5) * 12
          const jitterY = (Math.random() - 0.5) * 12
          dispatch({
            type: 'UPDATE_NODE_POSITION',
            doc_id,
            x: targetCentroid.x + jitterX,
            y: targetCentroid.y + jitterY,
          })
        }

        if (onConstraintAdded) onConstraintAdded(doc_id, nearestCluster)
      } catch (err) {
        console.error('[ResearchCanvas] constraint save failed:', err)
        snapBack()
      }
    } else {
      snapBack()
    }
  }, [state.nodes, clusterCentroids, addConstraint, onConstraintAdded, dispatch])

  // ── Derived data ──────────────────────────────────────────────────
  const uniqueClusterIds = useMemo(() =>
    [...new Set(state.nodes.map(n => n.cluster_id))],
    [state.nodes]
  )

  // Register all active clusters as a batch so every cluster gets a unique,
  // collision-free palette colour.  Must run before the first render that
  // consumes clusterColor() — hence the effect fires on uniqueClusterIds.
  useEffect(() => {
    if (uniqueClusterIds.length > 0) {
      registerClusters(uniqueClusterIds)
    }
  }, [uniqueClusterIds])

  const constrainedDocIds = useMemo(() =>
    new Set(state.constraints.map(c => c.doc_id)),
    [state.constraints]
  )

  const selectedClusterId = useMemo(() => {
    if (!state.selectedDocId) return null
    return state.nodes.find(n => n.doc_id === state.selectedDocId)?.cluster_id ?? null
  }, [state.selectedDocId, state.nodes])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}
    >
      {state.nodes.length === 0 ? (
        <EmptyState />
      ) : (
        <Stage
          ref={stageRef}
          width={containerW}
          height={containerH}
          x={stagePos.x + offsetX * stageScale}
          y={stagePos.y + offsetY * stageScale}
          scaleX={stageScale}
          scaleY={stageScale}
          draggable
          onDragEnd={e => {
            if (e.target === stageRef.current || e.target === e.target.getStage()) {
              setStagePos({ x: e.target.x() - offsetX * stageScale, y: e.target.y() - offsetY * stageScale })
            }
          }}
          onWheel={handleWheel}
          onClick={e => { if (e.target === e.target.getStage()) dispatch({ type: 'SELECT_NODE', doc_id: null }) }}
        >
          {/* Background layer: cluster convex hull regions (non-interactive to avoid event capture) */}
          <Layer listening={false}>
            {uniqueClusterIds.map(cid => (
              <ClusterRegion
                key={cid}
                cluster_id={cid}
                nodes={state.nodes}
                scale={baseScale}
                isSelected={cid === selectedClusterId}
                isDragTarget={cid === dragTargetClusterId}
              />
            ))}
          </Layer>

          {/* Foreground layer: document nodes */}
          <Layer ref={nodeLayerRef} listening={true}>
            {state.nodes.map(node => (
              <DocumentNode
                key={node.doc_id}
                node={node}
                scale={baseScale}
                isSelected={node.doc_id === state.selectedDocId}
                isDimmed={
                  selectedClusterId !== null &&
                  node.cluster_id !== selectedClusterId &&
                  node.doc_id !== state.selectedDocId
                }
                isPinned={constrainedDocIds.has(node.doc_id)}
                onSelect={handleSelect}
                onOpenPdf={(doc_id) => dispatch({ type: 'VIEW_DOCUMENT', doc_id })}
                onHover={handleHover}
                onDragMove={handleDragMove}
                onDragEnd={handleDragEnd}
              />
            ))}
          </Layer>
        </Stage>
      )}

      {/* Floating Selected Node Action Bar */}
      <SelectedNodeBar />

      {/* HTML tooltip — rendered outside Konva to use CSS */}
      {tooltip.node && (
        <NodeTooltip
          node={tooltip.node}
          screenX={tooltip.x}
          screenY={tooltip.y}
          isPinned={constrainedDocIds.has(tooltip.node.doc_id)}
        />
      )}
    </div>
  )
}

function EmptyState() {
  return (
    <div style={{
      position: 'absolute', inset: 0,
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      gap: '12px', opacity: 0.45, pointerEvents: 'none',
      userSelect: 'none',
    }}>
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
        <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
      </svg>
      <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', textAlign: 'center', maxWidth: 220 }}>
        Click <strong>Run Pipeline</strong> to organise your documents on the canvas.
      </p>
    </div>
  )
}
