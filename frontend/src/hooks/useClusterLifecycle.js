/**
 * useClusterLifecycle.js
 *
 * Provides interactive cluster lifecycle actions:
 *   - renameCluster(clusterId, newTopicLabel)
 *   - mergeClusters(sourceClusterIds, targetClusterId, newTopicLabel)
 *   - splitCluster(clusterId, k, newTopicLabels)
 */
import { useState, useCallback } from 'react'
import { useApp } from '../state/AppContext'
import { useOrganize } from './useOrganize'

export function useClusterLifecycle() {
  const { state, dispatch } = useApp()
  const { run: triggerOrganize } = useOrganize()
  const [isProcessing, setIsProcessing] = useState(false)
  const [lifecycleError, setLifecycleError] = useState(null)
  const [lifecycleSuccess, setLifecycleSuccess] = useState(null)

  const clearMessages = useCallback(() => {
    setLifecycleError(null)
    setLifecycleSuccess(null)
  }, [])

  /**
   * Rename a cluster topic.
   */
  const renameCluster = useCallback(async (clusterId, newTopicLabel) => {
    if (!clusterId || !newTopicLabel || !newTopicLabel.trim()) return false
    setIsProcessing(true)
    clearMessages()

    try {
      if (state.mockMode) {
        dispatch({
          type: 'SET_TOPICS',
          topics: {
            ...state.topics,
            [clusterId]: {
              ...(state.topics?.[clusterId] || {}),
              topic_label: newTopicLabel.trim(),
              is_custom_label: true,
            },
          },
        })
        setLifecycleSuccess(`Cluster renamed to "${newTopicLabel.trim()}"`)
        return true
      }

      const res = await fetch(`/api/clusters/${encodeURIComponent(clusterId)}/topic`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_label: newTopicLabel.trim() }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      
      // Update topic immediately in state
      dispatch({
        type: 'SET_TOPICS',
        topics: {
          ...state.topics,
          [clusterId]: {
            ...(state.topics?.[clusterId] || {}),
            topic_label: data.topic_label,
            is_custom_label: true,
          },
        },
      })
      setLifecycleSuccess(`Cluster renamed to "${data.topic_label}"`)
      return true
    } catch (err) {
      setLifecycleError(err.message || 'Failed to rename cluster')
      return false
    } finally {
      setIsProcessing(false)
    }
  }, [state.mockMode, state.topics, dispatch, clearMessages])

  /**
   * Merge one or more clusters into a target cluster.
   */
  const mergeClusters = useCallback(async (sourceClusterIds, targetClusterId, newTopicLabel = null) => {
    if (!targetClusterId) return false
    const sources = Array.isArray(sourceClusterIds) ? sourceClusterIds : [sourceClusterIds]
    if (sources.length === 0) return false

    setIsProcessing(true)
    clearMessages()
    dispatch({ type: 'SET_STATUS', status: 'running', message: 'Merging clusters…' })

    try {
      if (state.mockMode) {
        // Mock mode merge simulation
        const targetDocs = state.nodes.filter(n => n.cluster_id === targetClusterId).map(n => n.doc_id)
        const sourceDocs = state.nodes.filter(n => sources.includes(n.cluster_id)).map(n => n.doc_id)
        const allDocs = [...targetDocs, ...sourceDocs]

        const nextNodes = state.nodes.map(n => {
          if (sources.includes(n.cluster_id)) {
            return { ...n, cluster_id: targetClusterId, is_anchored: true }
          }
          return n
        })

        const nextTopics = { ...state.topics }
        for (const s of sources) delete nextTopics[s]
        if (newTopicLabel) {
          nextTopics[targetClusterId] = {
            ...(nextTopics[targetClusterId] || {}),
            topic_label: newTopicLabel.trim(),
            is_custom_label: true,
          }
        }

        dispatch({ type: 'SET_NODES', nodes: nextNodes })
        dispatch({ type: 'SET_TOPICS', topics: nextTopics })
        dispatch({ type: 'SET_STATUS', status: 'ready', message: null })
        setLifecycleSuccess(`Merged ${sources.length} cluster(s) into ${targetClusterId}`)
        return true
      }

      const res = await fetch('/api/clusters/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_cluster_ids: sources,
          target_cluster_id: targetClusterId,
          new_topic_label: newTopicLabel ? newTopicLabel.trim() : null,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setLifecycleSuccess(`Successfully merged into ${targetClusterId} (${data.total_documents} total papers)`)
      
      // Re-run organize to recalculate layout & topic models seamlessly
      await triggerOrganize()
      return true
    } catch (err) {
      const msg = err.message || 'Failed to merge clusters'
      setLifecycleError(msg)
      dispatch({ type: 'SET_STATUS', status: 'error', message: msg })
      return false
    } finally {
      setIsProcessing(false)
    }
  }, [state.mockMode, state.nodes, state.topics, dispatch, triggerOrganize, clearMessages])

  /**
   * Split a cluster into k sub-clusters.
   */
  const splitCluster = useCallback(async (clusterId, k = 2, newTopicLabels = null) => {
    if (!clusterId) return false
    setIsProcessing(true)
    clearMessages()
    dispatch({ type: 'SET_STATUS', status: 'running', message: `Splitting cluster into ${k} sub-clusters…` })

    try {
      if (state.mockMode) {
        setLifecycleSuccess(`Split cluster ${clusterId} into ${k} parts`)
        dispatch({ type: 'SET_STATUS', status: 'ready', message: null })
        return true
      }

      const res = await fetch(`/api/clusters/${encodeURIComponent(clusterId)}/split`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          k: parseInt(k, 10) || 2,
          new_topic_labels: newTopicLabels,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setLifecycleSuccess(`Split cluster into ${data.resulting_clusters.length} sub-clusters`)
      
      // Re-run organize to smoothly update node positions & topics
      await triggerOrganize()
      return true
    } catch (err) {
      const msg = err.message || 'Failed to split cluster'
      setLifecycleError(msg)
      dispatch({ type: 'SET_STATUS', status: 'error', message: msg })
      return false
    } finally {
      setIsProcessing(false)
    }
  }, [state.mockMode, dispatch, triggerOrganize, clearMessages])

  return {
    renameCluster,
    mergeClusters,
    splitCluster,
    isProcessing,
    lifecycleError,
    lifecycleSuccess,
    clearMessages,
  }
}
