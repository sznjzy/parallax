"""
backend/clustering/constraints.py

Persistent user-driven constraint storage.

A Constraint records that a user has manually assigned a specific document
to a specific cluster (by dragging it on the canvas).  These constraints
are honoured in all future /api/organize calls, ensuring the core
differentiator of the project works correctly.

Public API
----------
    load_constraints()      → list[Constraint]
    save_constraints(list)  → None
    add_constraint(doc_id, cluster_id) → Constraint
    remove_constraint(doc_id)          → bool
    get_constraint(doc_id)             → Constraint | None
    apply_constraints(docs, labels, label_to_uuid)
        Pre-assign constrained docs so HDBSCAN does not cluster them.
        Returns: (unconstrained_docs, unconstrained_idxs, forced_assignments)

Data format (constraints.json)
-------------------------------
[
  {
    "doc_id":            "doc-paper1.pdf",
    "forced_cluster_id": "cluster-3a1b721f",
    "created_at":        "2026-08-14T21:00:00Z",
    "source":            "user"
  }
]
"""

import json
import logging
import numpy as np
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# Stored alongside cluster_mapping.json in the api/ directory.
CONSTRAINTS_FILE = Path(__file__).resolve().parent.parent / "api" / "constraints.json"


@dataclass
class Constraint:
    doc_id: str                         # e.g. "doc-paper1.pdf"
    forced_cluster_id: str              # UUID like "cluster-3a1b721f"
    created_at: str                     # ISO 8601 timestamp
    source: Literal["user"] = "user"   # future: "llm", "import"


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def load_constraints() -> list[Constraint]:
    """
    Load constraints from disk.  Returns an empty list if the file does not
    exist or is malformed — never raises, so a missing file is not an error.
    """
    if not CONSTRAINTS_FILE.exists():
        return []
    try:
        with open(CONSTRAINTS_FILE, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return [Constraint(**entry) for entry in raw]
    except Exception as exc:
        logger.warning("Failed to load constraints.json: %s — returning empty list", exc)
        return []


def save_constraints(constraints: list[Constraint]) -> None:
    """Atomically write constraints to disk."""
    CONSTRAINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(c) for c in constraints]
    # Write to a temp file first, then rename (atomic on POSIX; best-effort on Windows).
    tmp = CONSTRAINTS_FILE.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        tmp.replace(CONSTRAINTS_FILE)
    except Exception as exc:
        logger.error("Failed to save constraints.json: %s", exc)
        tmp.unlink(missing_ok=True)
        raise


def add_constraint(doc_id: str, cluster_id: str) -> Constraint:
    """
    Add or replace the constraint for doc_id.
    If the doc already has a constraint it is overwritten (idempotent PUT
    semantics — the last drag wins).
    """
    constraints = load_constraints()
    # Remove any existing constraint for this doc.
    constraints = [c for c in constraints if c.doc_id != doc_id]
    new = Constraint(
        doc_id=doc_id,
        forced_cluster_id=cluster_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        source="user",
    )
    constraints.append(new)
    save_constraints(constraints)
    logger.info("Constraint added: %s → %s", doc_id, cluster_id)
    return new


def remove_constraint(doc_id: str) -> bool:
    """
    Remove the constraint for doc_id.
    Returns True if a constraint was found and removed, False if not found.
    """
    constraints = load_constraints()
    filtered = [c for c in constraints if c.doc_id != doc_id]
    if len(filtered) == len(constraints):
        return False  # Nothing removed.
    save_constraints(filtered)
    logger.info("Constraint removed: %s", doc_id)
    return True


def clear_all_constraints() -> None:
    """Clear all constraints from disk atomically."""
    save_constraints([])
    logger.info("All constraints cleared.")


def get_constraint(doc_id: str) -> "Constraint | None":
    """Return the constraint for doc_id, or None if unconstrained."""
    for c in load_constraints():
        if c.doc_id == doc_id:
            return c
    return None


# ---------------------------------------------------------------------------
# Pipeline integration helper
# ---------------------------------------------------------------------------

def apply_constraints(
    docs: list[dict],
    embeddings_list: list | np.ndarray,
    constraints_override: list[Constraint] | None = None,
) -> tuple[list[dict], list[int], dict[str, str]]:
    """
    Split the document list into:
      - unconstrained docs (passed to HDBSCAN as normal)
      - forced assignments (doc_id → cluster_uuid, bypassing HDBSCAN)

    Parameters
    ----------
    docs : list[dict]
        All documents, each with at least {"id": "doc-paper1.pdf", ...}.
    embeddings_list : list[np.ndarray] | np.ndarray
        Parallel list/array of embeddings (same length as docs).
    constraints_override : list[Constraint] | None
        Optional explicit constraint list to bypass reading from disk.

    Returns
    -------
    unconstrained_docs    : list[dict]   — docs without active constraints
    unconstrained_indices : list[int]    — original indices into docs/embeddings
    forced_assignments    : dict[str, str] — doc_id → forced_cluster_id
    """
    constraints = constraints_override if constraints_override is not None else load_constraints()
    constraint_map = {c.doc_id: c.forced_cluster_id for c in constraints}

    unconstrained_docs: list[dict] = []
    unconstrained_indices: list[int] = []
    forced_assignments: dict[str, str] = {}

    for i, doc in enumerate(docs):
        doc_id = doc["id"]
        if doc_id in constraint_map:
            forced_assignments[doc_id] = constraint_map[doc_id]
            logger.debug("Pre-assigning constrained doc %s → %s", doc_id, constraint_map[doc_id])
        else:
            unconstrained_docs.append(doc)
            unconstrained_indices.append(i)

    return unconstrained_docs, unconstrained_indices, forced_assignments


def evaluate_constraint_satisfaction(
    nodes: list,  # list of Node dataclass instances, dicts, or objects with doc_id and cluster_id
    forced_assignments: dict[str, str],
) -> tuple[float | None, int, int]:
    """
    Compute constraint_satisfaction_rate for the EvaluationContract.

    Returns (rate, num_applied, num_violated).
    Returns (None, 0, 0) if no constraints were active.
    """
    if not forced_assignments:
        return None, 0, 0

    node_map: dict[str, str] = {}
    for n in nodes:
        if isinstance(n, dict):
            if "doc_id" in n and "cluster_id" in n:
                node_map[n["doc_id"]] = n["cluster_id"]
        elif hasattr(n, "doc_id") and hasattr(n, "cluster_id"):
            node_map[getattr(n, "doc_id")] = getattr(n, "cluster_id")

    applied = 0
    violated = 0

    for doc_id, forced_cluster in forced_assignments.items():
        assigned_cluster = node_map.get(doc_id)
        if assigned_cluster is None:
            continue  # Doc was skipped (empty PDF or not in corpus) — don't count it.
        applied += 1
        if assigned_cluster != forced_cluster:
            violated += 1

    if applied == 0:
        return None, 0, 0

    rate = (applied - violated) / applied
    return rate, applied, violated

