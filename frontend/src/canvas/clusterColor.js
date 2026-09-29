/**
 * clusterColor.js
 *
 * Deterministically maps a cluster_id string to one of 7 CSS
 * custom-property colour names.  Uses a simple djb2-style hash so the
 * same cluster always gets the same hue, regardless of render order.
 *
 * Noise nodes (cluster_id starts with "noise-") are always grey.
 */

const NUM_COLOURS = 12

function hashString(s) {
  let h = 5381
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(33, h) ^ s.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

/**
 * Returns a CSS variable name like "--color-cluster-3"
 * for use with `getComputedStyle(document.documentElement).getPropertyValue(...)`.
 */
export function clusterColorVar(cluster_id) {
  if (!cluster_id || cluster_id.startsWith('noise-')) return '--color-text-subtle'
  const idx = hashString(cluster_id) % NUM_COLOURS
  return `--color-cluster-${idx}`
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
