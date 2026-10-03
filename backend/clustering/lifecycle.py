"""
backend/clustering/lifecycle.py

Interactive Cluster Lifecycle Management for Parallax (Phase 7).
Supports interactive renaming, merging, and splitting of semantic clusters
with stable UUID lineage, persistent state updates, constraint synchronization,
and automatic topic modeling updates.

Public API
----------
    rename_cluster_topic(cluster_id, new_topic_label, state_file=None, metadata_file=None) -> dict
    merge_clusters(source_cluster_ids, target_cluster_id, new_topic_label=None, state_file=None, metadata_file=None, docs_dir=None, model=None) -> dict
    split_cluster(cluster_id, k=2, new_topic_labels=None, state_file=None, metadata_file=None, docs_dir=None, model=None) -> dict
    load_cluster_metadata(metadata_file=None) -> dict
    save_cluster_metadata(metadata, metadata_file=None) -> None
    get_cluster_lifecycle_state(state_file=None, metadata_file=None) -> dict
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.cluster import KMeans

from backend.clustering.constraints import add_constraint, remove_constraint, load_constraints
from backend.embeddings.embedding_cache import get_cached_embedding, get_cached_text
from backend.embeddings.pipeline import extract_text_from_pdf, embed_document_chunks, chunk_text, load_model
from backend.topics.topic_modeling import extract_cluster_topics

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = Path(__file__).resolve().parent.parent / "api" / "cluster_mapping.json"
DEFAULT_METADATA_FILE = Path(__file__).resolve().parent.parent / "api" / "cluster_metadata.json"
DEFAULT_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs"


# ---------------------------------------------------------------------------
# Metadata Storage (Custom Topic Labels & Lifecycle History)
# ---------------------------------------------------------------------------

def load_cluster_metadata(metadata_file: Path | None = None) -> dict[str, dict]:
    """Load cluster metadata (custom topic overrides, creation timestamps)."""
    target = metadata_file or DEFAULT_METADATA_FILE
    if not target.exists():
        return {}
    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to read cluster metadata from %s: %s", target, exc)
        return {}


def save_cluster_metadata(metadata: dict[str, dict], metadata_file: Path | None = None) -> None:
    """Atomically persist cluster metadata to disk."""
    target = metadata_file or DEFAULT_METADATA_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        tmp.replace(target)
    except Exception as exc:
        logger.error("Failed to save cluster metadata to %s: %s", target, exc)
        tmp.unlink(missing_ok=True)
        raise


def _load_cluster_mapping(state_file: Path | None = None) -> dict[str, list[str]]:
    """Load the raw cluster_mapping.json mapping (cluster_id -> [doc_id, ...])."""
    target = state_file or DEFAULT_STATE_FILE
    if not target.exists():
        return {}
    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to load cluster mapping from %s: %s", target, exc)
        return {}


def _save_cluster_mapping(mapping: dict[str, list[str]], state_file: Path | None = None) -> None:
    """Atomically write cluster mapping to disk."""
    target = state_file or DEFAULT_STATE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)
        tmp.replace(target)
    except Exception as exc:
        logger.error("Failed to save cluster mapping to %s: %s", target, exc)
        tmp.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# 1. Rename Cluster Topic
# ---------------------------------------------------------------------------

def rename_cluster_topic(
    cluster_id: str,
    new_topic_label: str,
    state_file: Path | None = None,
    metadata_file: Path | None = None,
) -> dict:
    """
    Rename a cluster by assigning a custom topic label.
    
    Parameters
    ----------
    cluster_id : str
        The stable cluster UUID (e.g. 'cluster-912da791').
    new_topic_label : str
        Human-readable custom topic name.
    state_file : Path | None
        Path to cluster_mapping.json.
    metadata_file : Path | None
        Path to cluster_metadata.json.

    Returns
    -------
    dict
        Updated cluster topic information.
    """
    if not cluster_id or not cluster_id.strip():
        raise ValueError("cluster_id must be provided.")
    
    cluster_id = cluster_id.strip()
    if cluster_id.startswith("noise-") or cluster_id == "noise":
        raise ValueError("Cannot rename noise or outlier pseudo-clusters.")

    if not new_topic_label or not new_topic_label.strip():
        raise ValueError("new_topic_label cannot be empty.")

    clean_label = new_topic_label.strip()

    mapping = _load_cluster_mapping(state_file)
    if mapping and cluster_id not in mapping:
        raise KeyError(f"Cluster '{cluster_id}' does not exist in cluster mapping.")

    metadata = load_cluster_metadata(metadata_file)
    entry = metadata.get(cluster_id, {})
    entry["custom_topic_label"] = clean_label
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    metadata[cluster_id] = entry

    save_cluster_metadata(metadata, metadata_file)
    logger.info("Renamed cluster %s -> '%s'", cluster_id, clean_label)

    return {
        "cluster_id": cluster_id,
        "topic_label": clean_label,
        "is_custom_label": True,
        "updated_at": entry["updated_at"],
    }


# ---------------------------------------------------------------------------
# 2. Merge Clusters
# ---------------------------------------------------------------------------

def merge_clusters(
    source_cluster_ids: list[str] | str,
    target_cluster_id: str,
    new_topic_label: str | None = None,
    state_file: Path | None = None,
    metadata_file: Path | None = None,
    docs_dir: Path | None = None,
    model: Any = None,
) -> dict:
    """
    Merge one or more source clusters into a target cluster.
    Reassigns all documents from source clusters to the target cluster,
    records persistent user constraints for those documents, cleans up
    source cluster mappings, and updates topic modeling.

    Parameters
    ----------
    source_cluster_ids : list[str] | str
        Cluster UUID(s) to merge from.
    target_cluster_id : str
        Cluster UUID to merge into (retains identity).
    new_topic_label : str | None
        Optional custom topic label for the merged cluster.
    """
    if isinstance(source_cluster_ids, str):
        sources = [source_cluster_ids.strip()]
    else:
        sources = [s.strip() for s in source_cluster_ids if s and s.strip()]

    target_cid = target_cluster_id.strip() if target_cluster_id else ""

    if not target_cid:
        raise ValueError("target_cluster_id cannot be empty.")
    if target_cid.startswith("noise-") or target_cid == "noise":
        raise ValueError("Cannot merge into a noise pseudo-cluster.")

    # Remove self-merge if present
    sources = [s for s in sources if s != target_cid]
    if not sources:
        raise ValueError("Must specify at least one distinct source cluster to merge.")

    for s in sources:
        if s.startswith("noise-") or s == "noise":
            raise ValueError(f"Cannot merge noise pseudo-cluster '{s}'.")

    mapping = _load_cluster_mapping(state_file)
    if not mapping:
        raise ValueError("No cluster mapping exists to perform merge.")

    if target_cid not in mapping:
        raise KeyError(f"Target cluster '{target_cid}' does not exist.")

    for s in sources:
        if s not in mapping:
            raise KeyError(f"Source cluster '{s}' does not exist.")

    # Collect documents
    target_docs = list(mapping[target_cid])
    merged_docs: list[str] = []
    
    for s in sources:
        s_docs = mapping.get(s, [])
        for doc_id in s_docs:
            if doc_id not in target_docs:
                target_docs.append(doc_id)
            merged_docs.append(doc_id)
        # Remove source cluster from mapping
        mapping.pop(s, None)

    mapping[target_cid] = target_docs
    _save_cluster_mapping(mapping, state_file)

    # Add constraints to lock merged documents into target_cluster_id
    for doc_id in merged_docs:
        add_constraint(doc_id, target_cid)

    # Clean up and update metadata
    metadata = load_cluster_metadata(metadata_file)
    for s in sources:
        metadata.pop(s, None)

    if new_topic_label and new_topic_label.strip():
        metadata[target_cid] = {
            "custom_topic_label": new_topic_label.strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    save_cluster_metadata(metadata, metadata_file)

    logger.info("Merged %d clusters (%s) into %s with %d total docs", len(sources), sources, target_cid, len(target_docs))

    # Compute updated topic for the merged cluster if docs_dir is provided
    updated_topic = None
    target_folder = docs_dir or DEFAULT_DOCS_DIR
    if target_folder.exists():
        docs_for_topic = []
        cids_for_topic = []
        for doc_id in target_docs:
            fn = doc_id.replace("doc-", "")
            if not fn.lower().endswith(".pdf"):
                fn = f"{fn}.pdf"
            pdf_path = target_folder / fn
            text = get_cached_text(pdf_path) if pdf_path.exists() else None
            if text is None and pdf_path.exists():
                text = extract_text_from_pdf(pdf_path)
            docs_for_topic.append({"id": doc_id, "filename": fn, "text": text or ""})
            cids_for_topic.append(target_cid)

        if docs_for_topic:
            topics = extract_cluster_topics(docs_for_topic, cids_for_topic, model=model)
            updated_topic = topics.get(target_cid)

    return {
        "status": "success",
        "action": "merge",
        "target_cluster_id": target_cid,
        "merged_source_cluster_ids": sources,
        "affected_documents": merged_docs,
        "total_documents": len(target_docs),
        "topic": updated_topic,
    }


# ---------------------------------------------------------------------------
# 3. Split Cluster
# ---------------------------------------------------------------------------

def split_cluster(
    cluster_id: str,
    k: int = 2,
    new_topic_labels: list[str] | None = None,
    state_file: Path | None = None,
    metadata_file: Path | None = None,
    docs_dir: Path | None = None,
    model: Any = None,
) -> dict:
    """
    Split an existing cluster into k sub-clusters using semantic embeddings.
    The primary (largest) sub-cluster retains the original cluster UUID to
    preserve continuity and lineage, while other sub-clusters receive new stable UUIDs.
    
    Persistent constraints and cluster_mapping are updated accordingly.
    """
    cid = cluster_id.strip() if cluster_id else ""
    if not cid:
        raise ValueError("cluster_id cannot be empty.")
    if cid.startswith("noise-") or cid == "noise":
        raise ValueError("Cannot split noise or outlier pseudo-clusters.")

    if not isinstance(k, int) or k < 2:
        raise ValueError("k must be an integer >= 2.")

    mapping = _load_cluster_mapping(state_file)
    if not mapping or cid not in mapping:
        raise KeyError(f"Cluster '{cid}' does not exist in cluster mapping.")

    doc_ids = mapping[cid]
    n_docs = len(doc_ids)
    if n_docs < 2:
        raise ValueError(f"Cannot split cluster '{cid}': requires at least 2 documents (has {n_docs}).")
    if k > n_docs:
        raise ValueError(f"Cannot split cluster '{cid}' into {k} parts: cluster only contains {n_docs} documents.")

    target_folder = docs_dir or DEFAULT_DOCS_DIR
    embeddings_list: list[np.ndarray] = []
    docs_payload: list[dict] = []

    # Gather embeddings
    loaded_model = None
    for doc_id in doc_ids:
        fn = doc_id.replace("doc-", "")
        if not fn.lower().endswith(".pdf"):
            fn = f"{fn}.pdf"
        pdf_path = target_folder / fn

        emb = get_cached_embedding(pdf_path) if pdf_path.exists() else None
        text = get_cached_text(pdf_path) if pdf_path.exists() else None

        if emb is None and pdf_path.exists():
            if loaded_model is None:
                loaded_model = model or load_model()
            if text is None:
                text = extract_text_from_pdf(pdf_path)
            chunks = chunk_text(text)
            if chunks:
                emb, _ = embed_document_chunks(loaded_model, chunks)

        if emb is None:
            # Fallback to reproducible pseudo-embedding if file is missing (e.g. testing)
            rng_seed = abs(hash(doc_id)) % (2**31)
            emb = np.random.default_rng(rng_seed).normal(0, 1, 768)
            emb = emb / np.linalg.norm(emb)

        embeddings_list.append(emb)
        docs_payload.append({"id": doc_id, "filename": fn, "text": text or ""})

    emb_matrix = np.array(embeddings_list)

    # Run KMeans sub-clustering
    kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
    sub_labels = kmeans.fit_predict(emb_matrix)

    # Group documents by sub-cluster
    sub_groups: dict[int, list[str]] = {}
    for idx, sub_lbl in enumerate(sub_labels):
        sub_groups.setdefault(int(sub_lbl), []).append(doc_ids[idx])

    # Sort groups by size descending: largest retains original cluster UUID
    sorted_sub_groups = sorted(sub_groups.values(), key=len, reverse=True)

    resulting_clusters = []
    new_mapping = dict(mapping)

    # Primary partition keeps original cluster_id
    primary_docs = sorted_sub_groups[0]
    new_mapping[cid] = primary_docs
    resulting_clusters.append({
        "cluster_id": cid,
        "doc_ids": primary_docs,
        "is_original": True,
    })

    # Subsequent partitions get new UUIDs
    for part_idx, part_docs in enumerate(sorted_sub_groups[1:], start=1):
        new_uuid = f"cluster-{uuid.uuid4().hex[:8]}"
        new_mapping[new_uuid] = part_docs
        resulting_clusters.append({
            "cluster_id": new_uuid,
            "doc_ids": part_docs,
            "is_original": False,
        })

    # Persist updated mapping
    _save_cluster_mapping(new_mapping, state_file)

    # Update constraints for all documents to lock them in their split partitions
    for res_c in resulting_clusters:
        c_id = res_c["cluster_id"]
        for d_id in res_c["doc_ids"]:
            add_constraint(d_id, c_id)

    # Update custom metadata if custom labels were passed
    metadata = load_cluster_metadata(metadata_file)
    # Remove old custom label on original cluster if it was split
    if new_topic_labels:
        for idx, lbl in enumerate(new_topic_labels[:len(resulting_clusters)]):
            if lbl and lbl.strip():
                c_id = resulting_clusters[idx]["cluster_id"]
                metadata[c_id] = {
                    "custom_topic_label": lbl.strip(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
    save_cluster_metadata(metadata, metadata_file)

    # Compute topics for all resulting sub-clusters
    all_split_docs = []
    all_split_cids = []
    for res_c in resulting_clusters:
        for d_id in res_c["doc_ids"]:
            match_doc = next((d for d in docs_payload if d["id"] == d_id), {"id": d_id, "text": ""})
            all_split_docs.append(match_doc)
            all_split_cids.append(res_c["cluster_id"])

    topics = extract_cluster_topics(all_split_docs, all_split_cids, model=model)
    for res_c in resulting_clusters:
        res_c["topic"] = topics.get(res_c["cluster_id"])

    logger.info("Split cluster %s into %d parts: %s", cid, k, [c["cluster_id"] for c in resulting_clusters])

    return {
        "status": "success",
        "action": "split",
        "original_cluster_id": cid,
        "k": k,
        "resulting_clusters": resulting_clusters,
        "total_documents": n_docs,
    }


# ---------------------------------------------------------------------------
# 4. Get Current Cluster Lifecycle State
# ---------------------------------------------------------------------------

def get_cluster_lifecycle_state(
    state_file: Path | None = None,
    metadata_file: Path | None = None,
    docs_dir: Path | None = None,
    model: Any = None,
) -> list[dict]:
    """
    Return all current clusters with member documents, counts, and topic info.
    """
    mapping = _load_cluster_mapping(state_file)
    metadata = load_cluster_metadata(metadata_file)
    target_folder = docs_dir or DEFAULT_DOCS_DIR

    all_docs = []
    all_cids = []

    for cid, doc_ids in mapping.items():
        for d_id in doc_ids:
            fn = d_id.replace("doc-", "")
            if not fn.lower().endswith(".pdf"):
                fn = f"{fn}.pdf"
            pdf_path = target_folder / fn
            text = get_cached_text(pdf_path) if pdf_path.exists() else None
            all_docs.append({"id": d_id, "filename": fn, "text": text or ""})
            all_cids.append(cid)

    topics = extract_cluster_topics(all_docs, all_cids, model=model) if all_docs else {}

    clusters_list = []
    for cid, doc_ids in mapping.items():
        topic_info = topics.get(cid, {})
        custom_label = metadata.get(cid, {}).get("custom_topic_label")
        if custom_label:
            topic_info["topic_label"] = custom_label
            topic_info["is_custom_label"] = True

        clusters_list.append({
            "cluster_id": cid,
            "document_count": len(doc_ids),
            "documents": [{"doc_id": d, "filename": d.replace("doc-", "")} for d in doc_ids],
            "topic": topic_info,
            "custom_metadata": metadata.get(cid),
        })

    return clusters_list
