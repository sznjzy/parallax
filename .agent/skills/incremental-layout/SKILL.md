---
name: incremental-layout
description: Use this skill whenever implementing or modifying the canvas's force-directed layout engine, positioning nodes/clusters, handling new document insertion, animating node movement, or addressing layout stability across updates. Trigger on tasks involving "force-directed", "layout", "canvas physics", "node position", "clustering visualization", "layout stability".
---

# Incremental Layout Skill

## Purpose
Defines how Parallax renders clustering results as a stable, physically animated spatial layout — critically, ensuring that adding new documents does NOT disrupt the user's spatial memory of the existing map. This is the project's core technical differentiator; do not implement a naive full-recompute layout.

## Core Rules

1. **Never fully recompute layout from scratch on update.**
   - On initial load: run the full force-directed simulation (spring attraction within clusters, repulsion between clusters) until convergence.
   - On incremental update (new documents added): treat all EXISTING nodes as high-mass, low-mobility anchors. Only new nodes (and, optionally, their immediate cluster neighbors) should be significantly mobile in the simulation.
   - Cap per-frame displacement for existing nodes (e.g., max N pixels/frame) so nothing "teleports" or jumps abruptly, even if clustering assignment technically shifted slightly.

2. **Physics parameters (starting defaults — tune empirically).**
   - Attraction force: proportional to cosine similarity between connected documents' embeddings (stronger pull = higher similarity).
   - Repulsion force: standard inverse-distance repulsion between all node pairs (prevents overlap), weaker than intra-cluster attraction.
   - Damping factor: apply velocity damping (~0.85-0.9) to avoid oscillation/jitter — layout should visibly settle, not vibrate indefinitely.
   - Convergence threshold: stop simulation when total system kinetic energy (sum of node velocities) drops below a small threshold, not after a fixed iteration count — avoids stopping too early or running needlessly long.

3. **Boundary/multi-membership documents.**
   - A document flagged `is_boundary_document` (from the constrained-clustering skill output) should have attraction forces toward BOTH its primary and secondary cluster centroids, weighted by relative similarity — this is what makes it visually settle between clusters rather than being forced fully into one.

4. **Rendering.**
   - Decouple physics simulation (runs on a fixed timestep, independent of frame rate) from rendering (interpolate node positions for smooth visual animation regardless of simulation step rate).
   - Animate position changes with easing (not instant snapping) whenever a node's target position changes, including after constraint-driven re-clustering.

5. **Stability measurement (for evaluation).**
   - After every incremental update, compute and log the average displacement of pre-existing nodes (Euclidean distance between position before and after the update). This is the project's "layout stability" evaluation metric — lower is better, and this number should be reported, not just visually assessed.

## Failure Modes to Avoid
- Recomputing the entire layout from random initial positions on every update (causes jarring full-map rearrangement — defeats the core "persistent spatial memory" pitch).
- Letting the simulation run indefinitely without a convergence/energy threshold (wastes compute, delays interactivity).
- Ignoring the `is_boundary_document` flag and forcing every node to have exactly one attraction target (loses the multi-membership visualization that differentiates this project from a simple hierarchical tree).
- Tightly coupling physics tick rate to browser frame rate (causes inconsistent behavior across devices — always use a fixed timestep for the simulation loop).

## Output Contract
```json
{
  "doc_id": "string",
  "x": float,
  "y": float,
  "velocity_x": float,
  "velocity_y": float,
  "is_anchored": bool
}
```

## Evaluation Contract
```json
{
  "update_id": "string",
  "avg_displacement_existing_nodes": float,
  "max_displacement_existing_nodes": float,
  "convergence_iterations": int,
  "convergence_time_ms": float
}
```
Log this on every incremental update — it directly supports the project's evaluation plan.