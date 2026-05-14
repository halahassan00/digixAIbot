"""
backend/tests/eval_ragas.py

RAGAS end-to-end evaluation for the DIGIX AI RAG chatbot.

Measures four dimensions of quality using GPT-4o as the judge:
  faithfulness       — are the answer's claims grounded in the retrieved chunks?
  answer_relevancy   — does the answer address the question asked?
  context_precision  — were the retrieved chunks actually needed?
  context_recall     — did the chunks contain enough to answer fully?

Uses the same OPENAI_API_KEY as the chatbot. No extra config needed.

References
----------
Shahul Es et al., "RAGAS: Automated Evaluation of Retrieval Augmented
Generation", arXiv:2309.15217, 2023. https://arxiv.org/abs/2309.15217

Run standalone (prints table, saves JSON):
    python -m backend.tests.eval_ragas

Run as pytest:
    pytest backend/tests/eval_ragas.py -v -m eval
"""

import asyncio
import json
import logging
import math
import time
import warnings
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Paths & thresholds
# ---------------------------------------------------------------------------

EVAL_DATA   = Path(__file__).parent / "eval_data.jsonl"
RESULTS_OUT = Path(__file__).parent / "ragas_results.json"

THRESHOLDS = {
    "faithfulness":       0.80,
    "answer_relevancy":   0.75,
    "context_precision":  0.65,
    "context_recall":     0.70,
}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_eval_data() -> list[dict]:
    if not EVAL_DATA.exists():
        raise FileNotFoundError(
            f"eval_data.jsonl not found at {EVAL_DATA}\n"
            "Populate ChromaDB and curate the file first."
        )
    return [json.loads(l) for l in EVAL_DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def _safe_nanmean(values: list[float]) -> float:
    valid = [v for v in values if not math.isnan(v)]
    if not valid:
        return float("nan")
    return sum(valid) / len(valid)


def _dialect_breakdown(rows: list[dict]) -> dict:
    dialects = sorted({r["dialect"] for r in rows})
    breakdown = {}
    for d in dialects:
        subset = [r for r in rows if r["dialect"] == d]
        breakdown[d] = {
            metric: _safe_nanmean([r[metric] for r in subset])
            for metric in THRESHOLDS
        }
    return breakdown

# ---------------------------------------------------------------------------
# Pipeline invocation
# ---------------------------------------------------------------------------

async def _run_pipeline_all(eval_data: list[dict]) -> list[dict]:
    """
    For every entry: call retrieve() + pipeline.run() to get the real answer.
    Returns a list of dicts with question/answer/contexts/ground_truth/dialect.
    """
    from backend.rag.pipeline import run as pipeline_run
    from backend.rag.retriever import retrieve

    rows = []
    for i, entry in enumerate(eval_data, start=1):
        query        = entry["query"]
        language     = entry["language"]
        dialect      = entry.get("dialect", "unknown")
        ground_truth = entry.get("ground_truth", "")

        # Real retrieval (same call the production pipeline makes)
        chunks   = retrieve(query=query, language=language, n_results=4)
        contexts = [c.text for c in chunks]

        # Real generation — each call costs ~$0.003-0.005 in GPT-4o tokens
        result = await pipeline_run(query=query, language=language)
        answer = result["response"]

        rows.append({
            "question":     query,
            "answer":       answer,
            "contexts":     contexts,
            "ground_truth": ground_truth,
            "dialect":      dialect,
            "language":     language,
        })

        logger.info("[%d/%d] %s query processed", i, len(eval_data), language)

    return rows


# ---------------------------------------------------------------------------
# RAGAS evaluation
# ---------------------------------------------------------------------------

def _build_ragas_llm_and_embeddings():
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o", temperature=0))
    emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))
    return llm, emb


def _run_ragas(pipeline_rows: list[dict]) -> dict:
    """
    Build an EvaluationDataset, run RAGAS evaluate(), return aggregated report.
    """
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="ragas")

    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    llm, emb = _build_ragas_llm_and_embeddings()

    samples = [
        SingleTurnSample(
            user_input=r["question"],
            retrieved_contexts=r["contexts"],
            reference=r["ground_truth"],
            response=r["answer"],
        )
        for r in pipeline_rows
    ]
    dataset = EvaluationDataset(samples=samples)

    print(f"\nRunning RAGAS on {len(samples)} samples (GPT-4o judge)…")
    t0 = time.perf_counter()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=llm,
            embeddings=emb,
            show_progress=True,
        )

    elapsed = time.perf_counter() - t0
    print(f"RAGAS evaluation completed in {elapsed:.1f}s\n")

    # Extract per-row scores; log any NaN rows
    metric_names = list(THRESHOLDS.keys())
    per_row: list[dict] = []
    for i, row in enumerate(pipeline_rows):
        row_scores = {}
        for m in metric_names:
            score_list = result[m]
            val = score_list[i] if i < len(score_list) else float("nan")
            if math.isnan(val):
                logger.warning("NaN for metric=%s row=%d query=%r — skipped", m, i, row["question"][:60])
            row_scores[m] = val
        per_row.append({**row, **row_scores})

    # Aggregate means (NaN-safe)
    aggregate = {m: _safe_nanmean([r[m] for r in per_row]) for m in metric_names}

    # Language-level breakdown
    by_language = {}
    for lang in sorted({r["language"] for r in per_row}):
        subset = [r for r in per_row if r["language"] == lang]
        by_language[lang] = {m: _safe_nanmean([r[m] for r in subset]) for m in metric_names}

    # Dialect breakdown
    by_dialect = _dialect_breakdown(per_row)

    return {
        "aggregate":   aggregate,
        "by_language": by_language,
        "by_dialect":  by_dialect,
        "per_row":     per_row,
    }


# ---------------------------------------------------------------------------
# Print table
# ---------------------------------------------------------------------------

def _print_table(report: dict) -> None:
    agg = report["aggregate"]

    print("\n" + "=" * 65)
    print("  DIGIX AI RAGAS Evaluation Results")
    print("=" * 65)
    print(f"  {'Metric':<25} {'Score':>7}  {'Threshold':>10}  {'Status':>6}")
    print("-" * 65)
    for metric, threshold in THRESHOLDS.items():
        score = agg[metric]
        if math.isnan(score):
            status = "N/A"
            score_str = "   nan"
        else:
            status = "PASS" if score >= threshold else "FAIL"
            score_str = f"{score:7.3f}"
        print(f"  {metric:<25} {score_str}  {threshold:>10.2f}  [{status}]")
    print("=" * 65)

    # Dialect breakdown
    print("\n  Dialect breakdown:")
    print(f"  {'Dialect':<14}", end="")
    for m in THRESHOLDS:
        print(f"  {m[:12]:>12}", end="")
    print()
    print("  " + "-" * (14 + 14 * len(THRESHOLDS)))
    for dialect, scores in sorted(report["by_dialect"].items()):
        print(f"  {dialect:<14}", end="")
        for m in THRESHOLDS:
            v = scores[m]
            print(f"  {'nan':>12}" if math.isnan(v) else f"  {v:12.3f}", end="")
        print()
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_ragas_evaluation() -> dict:
    """
    Full pipeline: load data → run GPT-4o → run RAGAS → save → print.
    Returns the full report dict.
    """
    eval_data     = _load_eval_data()
    pipeline_rows = asyncio.run(_run_pipeline_all(eval_data))
    report        = _run_ragas(pipeline_rows)

    # Save
    RESULTS_OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Results saved → {RESULTS_OUT}")

    _print_table(report)
    return report


# ---------------------------------------------------------------------------
# Pytest entry points (all share one run via session-scoped fixture)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def ragas_report():
    if not EVAL_DATA.exists():
        pytest.skip("eval_data.jsonl not found — curate the file first")
    return run_ragas_evaluation()


@pytest.mark.eval
def test_faithfulness(ragas_report):
    score = ragas_report["aggregate"]["faithfulness"]
    assert not math.isnan(score), "faithfulness score is NaN — all rows failed"
    assert score >= THRESHOLDS["faithfulness"], (
        f"Faithfulness {score:.3f} < threshold {THRESHOLDS['faithfulness']}"
    )


@pytest.mark.eval
def test_answer_relevancy(ragas_report):
    score = ragas_report["aggregate"]["answer_relevancy"]
    assert not math.isnan(score), "answer_relevancy score is NaN"
    assert score >= THRESHOLDS["answer_relevancy"], (
        f"Answer relevancy {score:.3f} < threshold {THRESHOLDS['answer_relevancy']}"
    )


@pytest.mark.eval
def test_context_precision(ragas_report):
    score = ragas_report["aggregate"]["context_precision"]
    assert not math.isnan(score), "context_precision score is NaN"
    assert score >= THRESHOLDS["context_precision"], (
        f"Context precision {score:.3f} < threshold {THRESHOLDS['context_precision']}"
    )


@pytest.mark.eval
def test_context_recall(ragas_report):
    score = ragas_report["aggregate"]["context_recall"]
    assert not math.isnan(score), "context_recall score is NaN"
    assert score >= THRESHOLDS["context_recall"], (
        f"Context recall {score:.3f} < threshold {THRESHOLDS['context_recall']}"
    )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_ragas_evaluation()
