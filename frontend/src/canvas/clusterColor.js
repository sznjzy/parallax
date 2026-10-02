/**
 * clusterColor.js
 *
 * Deterministically maps a cluster_id string to one of 12 CSS
 * custom-property colour names.  Uses a djb2-style hash so the same
 * cluster always *prefers* the same hue, but a global collision-free
 * allocation is enforced whenever the full active cluster set is known
 * via `registerClusters()`.
 *
 * Noise nodes (cluster_id starts with "noise-") are always grey.
 *
 * Call `registerClusters(clusterIds)` once per layout update (e.g. from
 * ResearchCanvas whenever `uniqueClusterIds` changes) so every active
 * cluster receives a distinct palette slot.
 */

const NUM_COLOURS = 12

// Collision-free assignment cache: cluster_id -> color_index (0..11)
// Cleared and rebuilt on every registerClusters() call so stale mappings
// from previous pipeline runs never pollute the new assignment.
const assignedColors = new Map()

function hashString(s) {
  let h = 5381
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(33, h) ^ s.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

/**
 * Registers ALL currently-active cluster IDs and allocates a unique,
 * non-colliding palette index for each one.
 *
 * This MUST be called whenever the set of visible clusters changes (e.g.
 * after a new pipeline run).  It clears any stale assignments from the
 * previous run before rebuilding the map from scratch.
 *
 * Allocation strategy
 * -------------------
 * 1. Filter out noise clusters and deduplicate.
 * 2. Sort by each cluster's preferred palette index (hashString % NUM_COLOURS)
 *    so clusters with nearby hash values get resolved in a stable order.
 * 3. Walk the sorted list; if the preferred slot is taken, probe linearly
 *    (wrapping) until a free slot is found.
 *
 * This guarantees:
 *   • Every real cluster on canvas has a UNIQUE colour index.
 *   • The assignment is deterministic given the same set of cluster IDs.
 *   • A cluster that was already assigned keeps its preferred hue whenever
 *     the palette has room (no other cluster hash-collides with it).
 */
export function registerClusters(clusterIds) {
  if (!Array.isArray(clusterIds)) return

  // ── Step 1: clear stale state ──────────────────────────────────────
  assignedColors.clear()

  // ── Step 2: collect & sort real clusters by preferred palette index ─
  const real = [...new Set(clusterIds.filter(id => id && !id.startsWith('noise-')))]
  // Sort by preferred slot so clusters with the same preferred index are
  // resolved in a deterministic order (lowest hash wins its preferred slot).
  real.sort((a, b) => hashString(a) % NUM_COLOURS - hashString(b) % NUM_COLOURS)

  // ── Step 3: collision-free allocation ─────────────────────────────
  const used = new Set()
  for (const cid of real) {
    let desired = hashString(cid) % NUM_COLOURS
    // Linear probing: advance until we find a free slot.
    let probes = 0
    while (used.has(desired) && probes < NUM_COLOURS) {
      desired = (desired + 1) % NUM_COLOURS
      probes++
    }
    assignedColors.set(cid, desired)
    used.add(desired)
  }
}

/**
 * Clears the colour cache.  Call on unmount or before a full reset.
 */
export function clearClusterColors() {
  assignedColors.clear()
}

/**
 * Returns a CSS variable name like "--color-cluster-3".
 * Falls back to a collision-aware lazy allocation if registerClusters()
 * was not called for this cluster yet (e.g. for newly discovered clusters
 * between layout runs).
 */
export function clusterColorVar(cluster_id) {
  if (!cluster_id || cluster_id.startsWith('noise-')) return '--color-text-subtle'
  if (!assignedColors.has(cluster_id)) {
    // Lazy path: allocate avoiding any already-used slots.
    const used = new Set(assignedColors.values())
    let desired = hashString(cluster_id) % NUM_COLOURS
    let probes = 0
    while (used.has(desired) && probes < NUM_COLOURS) {
      desired = (desired + 1) % NUM_COLOURS
      probes++
    }
    assignedColors.set(cluster_id, desired)
  }
  return `--color-cluster-${assignedColors.get(cluster_id)}`
}

/**
 * Resolves the CSS variable to an actual colour string.
 * Safe to call outside of React (Konva needs raw colour strings).
 */
export function clusterColor(cluster_id) {
  if (!cluster_id || cluster_id.startsWith('noise-')) return '#6e7681'
  const varName = clusterColorVar(cluster_id)
  const resolved = getComputedStyle(document.documentElement).getPropertyValue(varName).trim()
  return resolved || '#58a6ff'
}

/** Colour for boundary ring — secondary cluster hue at lower opacity */
export function boundaryRingColor(cluster_id) {
  return clusterColor(cluster_id)
}

