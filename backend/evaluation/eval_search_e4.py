"""
backend/evaluation/eval_search_e4.py

Experiment E4: Semantic Search Retrieval Evaluation.
Evaluates retrieval effectiveness of the production search_corpus() engine
against explicit ground-truth document IDs for 5 research queries on the real 34-paper corpus.
"""

import json
from pathlib import Path
from backend.search.semantic_search import search_corpus


def load_ground_truth_queries() -> list[dict]:
    gt_file = Path(__file__).resolve().parent / "ground_truth_search.json"
    with open(gt_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["queries"]


def evaluate_query_retrieval(query_meta: dict, corpus_dir: Path, model=None) -> dict:
    query_text = query_meta["query_text"]
    ground_truth = set(query_meta["relevant_doc_ids"])

    # Call production search engine
    res = search_corpus(query=query_text, corpus_dir=corpus_dir, model=model, top_k=34)
    ranked_results = res.get("results", [])

    retrieved_filenames = [r["filename"] for r in ranked_results]

    # Precision@3
    top3 = set(retrieved_filenames[:3])
    p3 = len(top3 & ground_truth) / 3.0

    # Precision@5
    top5 = set(retrieved_filenames[:5])
    p5 = len(top5 & ground_truth) / 5.0

    # Recall@5
    r5 = len(top5 & ground_truth) / float(len(ground_truth)) if len(ground_truth) > 0 else 0.0

    # Reciprocal Rank (RR) of first relevant doc
    rr = 0.0
    first_rank = None
    for idx, fn in enumerate(retrieved_filenames):
        if fn in ground_truth:
            rr = 1.0 / (idx + 1)
            first_rank = idx + 1
            break

    # Find rank of culinary outlier paper34.pdf
    paper34_rank = None
    paper34_score = None
    for idx, r in enumerate(ranked_results):
        if r["filename"] == "paper34.pdf":
            paper34_rank = idx + 1
            paper34_score = round(r["similarity_score"], 4)
            break

    return {
        "query_id": query_meta["query_id"],
        "query_text": query_text,
        "topic": query_meta["topic"],
        "ground_truth_count": len(ground_truth),
        "ground_truth_docs": sorted(list(ground_truth)),
        "retrieved_top_5": retrieved_filenames[:5],
        "precision_at_3": round(p3, 4),
        "precision_at_5": round(p5, 4),
        "recall_at_5": round(r5, 4),
        "reciprocal_rank": round(rr, 4),
        "first_relevant_rank": first_rank,
        "paper34_rank": paper34_rank,
        "paper34_similarity_score": paper34_score,
    }


def run_e4_search_evaluation() -> dict:
    """Run full E4 semantic search evaluation on 34-paper corpus."""
    print("--- Running Experiment E4: Semantic Search Retrieval Evaluation ---")

    from backend.embeddings.pipeline import load_model
    shared_model = load_model()

    corpus_dir = Path(__file__).resolve().parent.parent.parent / "data" / "sample_docs"
    queries = load_ground_truth_queries()

    eval_results = []
    p3_scores = []
    p5_scores = []
    r5_scores = []
    rr_scores = []

    for q in queries:
        q_res = evaluate_query_retrieval(q, corpus_dir, model=shared_model)
        eval_results.append(q_res)
        p3_scores.append(q_res["precision_at_3"])
        p5_scores.append(q_res["precision_at_5"])
        r5_scores.append(q_res["recall_at_5"])
        rr_scores.append(q_res["reciprocal_rank"])

    mean_p3 = float(sum(p3_scores) / len(p3_scores))
    mean_p5 = float(sum(p5_scores) / len(p5_scores))
    mean_r5 = float(sum(r5_scores) / len(r5_scores))
    mrr = float(sum(rr_scores) / len(rr_scores))

    return {
        "experiment": "E4_Semantic_Search_Retrieval",
        "total_queries_evaluated": len(queries),
        "aggregate_metrics": {
            "mean_precision_at_3": round(mean_p3, 4),
            "mean_precision_at_5": round(mean_p5, 4),
            "mean_recall_at_5": round(mean_r5, 4),
            "mean_reciprocal_rank_MRR": round(mrr, 4),
        },
        "query_level_evaluations": eval_results,
    }


if __name__ == "__main__":
    res = run_e4_search_evaluation()
    import json
    print(json.dumps(res, indent=2))
