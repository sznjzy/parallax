/**
 * ClusterInspector.jsx
 *
 * Workspace drawer for inspecting and managing discovered clusters.
 * Renders cluster topic titles, keywords, member documents, and inline Rename/Split/Merge controls.
 */
import React, { useState } from 'react'
import { useApp } from '../state/AppContext'
import { useClusterLifecycle } from '../hooks/useClusterLifecycle'
import { clusterColor } from '../canvas/clusterColor'

export default function ClusterInspector({ onClose }) {
  const { state, dispatch } = useApp()
  const { renameTopic, mergeClusters, splitCluster, isMutating } = useClusterLifecycle()

  const [activeAction, setActiveAction] = useState(null) // { type: 'rename'|'split'|'merge', clusterId }
  const [inputValue, setInputValue] = useState('')
  const [targetMergeId, setTargetMergeId] = useState('')
  const [splitK, setSplitK] = useState(2)

  // Group nodes by cluster
  const clusters = {}
  const noiseDocs = []

  state.nodes.forEach((n) => {
    if (n.cluster_id === 'noise' || n.cluster_id.startsWith('noise-')) {
      noiseDocs.push(n)
    } else {
      if (!clusters[n.cluster_id]) clusters[n.cluster_id] = []
      clusters[n.cluster_id].push(n)
    }
  })

  const clusterIds = Object.keys(clusters)

  const handleStartRename = (cid, currentLabel) => {
    setActiveAction({ type: 'rename', clusterId: cid })
    setInputValue(currentLabel || '')
  }

  const handleStartMerge = (cid) => {
    const otherClusters = clusterIds.filter(id => id !== cid)
    setActiveAction({ type: 'merge', clusterId: cid })
    setTargetMergeId(otherClusters[0] || '')
  }

  const handleStartSplit = (cid) => {
    setActiveAction({ type: 'split', clusterId: cid })
    setSplitK(2)
  }

  const handleSaveRename = async (cid) => {
    if (!inputValue.trim()) return
    await renameTopic(cid, inputValue.trim())
    setActiveAction(null)
  }

  const handleSaveMerge = async (sourceCid) => {
    if (!targetMergeId) return
    await mergeClusters([sourceCid], targetMergeId)
    setActiveAction(null)
  }

  const handleSaveSplit = async (cid) => {
    await splitCluster(cid, parseInt(splitK, 10) || 2)
    setActiveAction(null)
  }

  return (
    <div className="inspector-panel" role="region" aria-label="Clusters Workspace">
      {/* Header */}
      <div className="inspector-header">
        <div>
          <span className="inspector-eyebrow">WORKSPACE</span>
          <h2 className="inspector-title">Clusters & Topics</h2>
        </div>
        <button className="inspector-close-btn" onClick={onClose} title="Close inspector (Esc)" aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </div>

      <div className="inspector-scrollable">
        {clusterIds.length === 0 && noiseDocs.length === 0 ? (
          <div className="inspector-empty">
            <p>Run the semantic pipeline to discover document clusters and extract topics.</p>
          </div>
        ) : (
          <div className="cluster-list">
            {clusterIds.map((cid) => {
              const docs = clusters[cid]
              const topicData = state.topics?.[cid]
              const topicLabel = topicData?.topic_label || `Cluster ${cid.slice(0, 8)}`
              const keywords = topicData?.top_terms || []
              const clr = clusterColor(cid)
              const isActionOpen = activeAction?.clusterId === cid

              return (
                <div key={cid} className="cluster-row">
                  {/* Topic Title & Doc Count */}
                  <div className="cluster-header-row">
                    <div className="cluster-title-group">
                      <span className="cluster-dot" style={{ backgroundColor: clr }} />
                      <span className="cluster-title">{topicLabel}</span>
                    </div>
                    <span className="cluster-count">{docs.length} docs</span>
                  </div>

                  {/* Keywords */}
                  {keywords.length > 0 && (
                    <div className="cluster-keywords-text">
                      {keywords.slice(0, 5).join(' · ')}
                    </div>
                  )}

                  {/* Subtle Action Buttons */}
                  <div className="cluster-action-links">
                    <button
                      className={`cluster-link-btn ${isActionOpen && activeAction.type === 'rename' ? 'active' : ''}`}
                      onClick={() => handleStartRename(cid, topicLabel)}
                      disabled={isMutating}
                    >
                      Rename
                    </button>
                    <span className="cluster-action-dot">·</span>
                    <button
                      className={`cluster-link-btn ${isActionOpen && activeAction.type === 'split' ? 'active' : ''}`}
                      onClick={() => handleStartSplit(cid)}
                      disabled={isMutating || docs.length < 2}
                    >
                      Split
                    </button>
                    <span className="cluster-action-dot">·</span>
                    <button
                      className={`cluster-link-btn ${isActionOpen && activeAction.type === 'merge' ? 'active' : ''}`}
                      onClick={() => handleStartMerge(cid)}
                      disabled={isMutating || clusterIds.length < 2}
                    >
                      Merge
                    </button>
                  </div>

                  {/* Inline Action Form */}
                  {isActionOpen && (
                    <div className="cluster-inline-form">
                      {activeAction.type === 'rename' && (
                        <div>
                          <input
                            type="text"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            className="cluster-inline-input"
                            placeholder="Enter new topic title…"
                            autoFocus
                          />
                          <div className="cluster-inline-buttons">
                            <button className="btn btn-secondary btn-sm" onClick={() => setActiveAction(null)}>Cancel</button>
                            <button className="btn btn-primary btn-sm" onClick={() => handleSaveRename(cid)} disabled={isMutating}>Save</button>
                          </div>
                        </div>
                      )}

                      {activeAction.type === 'split' && (
                        <div>
                          <div className="split-form-row">
                            <label className="split-label">Number of sub-clusters (k):</label>
                            <select
                              value={splitK}
                              onChange={(e) => setSplitK(Number(e.target.value))}
                              className="cluster-select"
                            >
                              <option value="2">2 clusters</option>
                              <option value="3">3 clusters</option>
                              <option value="4">4 clusters</option>
                            </select>
                          </div>
                          <div className="cluster-inline-buttons">
                            <button className="btn btn-secondary btn-sm" onClick={() => setActiveAction(null)}>Cancel</button>
                            <button className="btn btn-primary btn-sm" onClick={() => handleSaveSplit(cid)} disabled={isMutating}>Split</button>
                          </div>
                        </div>
                      )}

                      {activeAction.type === 'merge' && (
                        <div>
                          <div className="split-form-row">
                            <label className="split-label">Merge into target cluster:</label>
                            <select
                              value={targetMergeId}
                              onChange={(e) => setTargetMergeId(e.target.value)}
                              className="cluster-select"
                            >
                              {clusterIds.filter(id => id !== cid).map(targetId => (
                                <option key={targetId} value={targetId}>
                                  {state.topics?.[targetId]?.topic_label || targetId}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="cluster-inline-buttons">
                            <button className="btn btn-secondary btn-sm" onClick={() => setActiveAction(null)}>Cancel</button>
                            <button className="btn btn-primary btn-sm" onClick={() => handleSaveMerge(cid)} disabled={isMutating}>Merge</button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}

            {/* Outliers Quiet Section */}
            {noiseDocs.length > 0 && (
              <div className="outliers-section">
                <div className="outliers-header">
                  <span className="outliers-title">Outliers / Unclustered</span>
                  <span className="outliers-count">{noiseDocs.length} docs</span>
                </div>
                <div className="outliers-doc-list">
                  {noiseDocs.map(d => (
                    <div
                      key={d.doc_id}
                      className="outlier-doc-item truncate"
                      onClick={() => dispatch({ type: 'SELECT_NODE', doc_id: d.doc_id })}
                    >
                      {d.doc_id.replace(/^doc-/, '')}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
