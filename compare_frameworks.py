"""Compare RAGAS and DeepEval on the saved OrbitTech benchmark artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from types import ModuleType
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from evaluate_answers import load_evaluation_inputs

ROOT = Path(__file__).resolve().parent


def _quota_limited(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "resource_exhausted" in message or "rate limit" in message


def _ragas_scores(
    pairs: list[Any], scores: dict[str, dict[str, float]], save: Any
) -> dict[str, dict[str, float]]:
    try:
        # Ragas 0.4 imports a LangChain Vertex type during startup even for
        # Gemini runs; recent langchain-community releases removed that module.
        try:
            from langchain_community.chat_models.vertexai import ChatVertexAI  # noqa: F401
        except ImportError:
            legacy_vertex = ModuleType("langchain_community.chat_models.vertexai")
            legacy_vertex.ChatVertexAI = type("ChatVertexAI", (), {})
            sys.modules[legacy_vertex.__name__] = legacy_vertex
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
        from ragas.metrics.collections import ContextPrecision, ContextRecall
        from ragas.run_config import RunConfig
    except ImportError as exc:
        raise RuntimeError(
            "Install comparison dependencies with: "
            "pip install -r requirements-frameworks.txt"
        ) from exc

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required (load it from .env or the environment)")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=45,
        max_retries=0,
    )
    llm = llm_factory(
        model_name,
        client=client,
    )
    llm.run_config = RunConfig(timeout=45, max_retries=1, max_wait=1)
    metrics = {
        "context_precision": ContextPrecision(llm=llm),
        "context_recall": ContextRecall(llm=llm),
    }

    async def score_all() -> dict[str, dict[str, float]]:
        results = {}
        for pair in pairs:
            case_id = pair.metadata["id"]
            values = scores.setdefault(case_id, {})
            for name, metric in metrics.items():
                if name not in values:
                    for attempt in range(6):
                        try:
                            result = await metric.ascore(
                                user_input=pair.question,
                                reference=pair.expected_answer,
                                retrieved_contexts=pair.retrieved_contexts,
                            )
                            values[name] = float(result.value)
                            save()
                            break
                        except Exception as exc:
                            if not _quota_limited(exc) or attempt == 5:
                                raise
                            print("RAGAS rate limited; retrying in 45 seconds", flush=True)
                            await asyncio.sleep(45)
                print(f"RAGAS: {pair.metadata['id']} {name}", flush=True)
            results[case_id] = values
        await client.close()
        return results

    return asyncio.run(score_all())


def _deepeval_scores(
    pairs: list[Any], answers: dict[str, str], threshold: float,
    scores: dict[str, dict[str, Any]], save: Any
) -> dict[str, dict[str, Any]]:
    try:
        from deepeval.metrics import ContextualPrecisionMetric, ContextualRecallMetric
        from deepeval.models import GeminiModel
        from deepeval.test_case import LLMTestCase
    except ImportError as exc:
        raise RuntimeError(
            "Install comparison dependencies with: "
            "pip install -r requirements-frameworks.txt"
        ) from exc

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required (load it from .env or the environment)")
    judge = GeminiModel(model=model_name, api_key=api_key, temperature=0)
    metrics = {
        "context_precision": ContextualPrecisionMetric(
            threshold=threshold, model=judge, include_reason=True
        ),
        "context_recall": ContextualRecallMetric(
            threshold=threshold, model=judge, include_reason=True
        ),
    }

    results = {}
    for pair in pairs:
        case_id = pair.metadata["id"]
        test_case = LLMTestCase(
            input=pair.question,
            actual_output=answers[pair.question],
            expected_output=pair.expected_answer,
            retrieval_context=pair.retrieved_contexts,
        )
        case_scores = scores.setdefault(case_id, {})

        async def measure(name: str, metric: Any) -> None:
            if name in case_scores:
                return
            for attempt in range(6):
                try:
                    await metric.a_measure(test_case)
                    case_scores[name] = {
                        "score": float(metric.score),
                        "passed": bool(metric.success),
                        "reason": str(metric.reason or ""),
                    }
                    save()
                    print(f"DeepEval: {case_id} {name}", flush=True)
                    return
                except Exception as exc:
                    if not _quota_limited(exc) or attempt == 5:
                        raise
                    print("DeepEval rate limited; retrying in 45 seconds", flush=True)
                    await asyncio.sleep(45)

        async def measure_pair() -> None:
            await asyncio.gather(*(measure(name, metric) for name, metric in metrics.items()))

        asyncio.run(measure_pair())
        results[case_id] = case_scores
    return results


def _summarize(
    ragas: dict[str, dict[str, float]],
    deepeval: dict[str, dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    ids = sorted(set(ragas) & set(deepeval))
    summary = {}
    for framework, scores in (("ragas", ragas), ("deepeval", deepeval)):
        averages = {
            metric: sum(
                scores[case_id][metric]
                if framework == "ragas"
                else scores[case_id][metric]["score"]
                for case_id in ids
            ) / len(ids)
            for metric in ("context_precision", "context_recall")
        }
        failures = {
            case_id for case_id in ids
            if any(
                (scores[case_id][metric] if framework == "ragas"
                 else scores[case_id][metric]["score"]) < threshold
                for metric in ("context_precision", "context_recall")
            )
        }
        summary[framework] = {
            "averages": averages,
            "failed_ids": sorted(failures),
        }
    ragas_failed = set(summary["ragas"]["failed_ids"])
    deepeval_failed = set(summary["deepeval"]["failed_ids"])
    union = ragas_failed | deepeval_failed
    summary["comparison"] = {
        "case_ids": ids,
        "same_cases": len(ids),
        "threshold": threshold,
        "context_precision_mae": sum(
            abs(ragas[case_id]["context_precision"] - deepeval[case_id]["context_precision"]["score"])
            for case_id in ids
        ) / len(ids),
        "context_recall_mae": sum(
            abs(ragas[case_id]["context_recall"] - deepeval[case_id]["context_recall"]["score"])
            for case_id in ids
        ) / len(ids),
        "score_disagreement_ids": [
            case_id for case_id in ids
            if any(
                abs(ragas[case_id][metric] - deepeval[case_id][metric]["score"]) > 0.1
                for metric in ("context_precision", "context_recall")
            )
        ],
        "shared_failed_ids": sorted(ragas_failed & deepeval_failed),
        "ragas_only_failed_ids": sorted(ragas_failed - deepeval_failed),
        "deepeval_only_failed_ids": sorted(deepeval_failed - ragas_failed),
        "failure_jaccard": len(ragas_failed & deepeval_failed) / len(union) if union else 1.0,
    }
    return summary


def _update_exercise(
    summary: dict[str, Any], path: Path, model_name: str
) -> None:
    text = path.read_text(encoding="utf-8")
    marker = "| Kết quả trên cùng dataset |"
    start = text.index(marker)
    end = text.index("\n", start)
    row = (
        "| Kết quả trên cùng dataset | "
        + _markdown_table_for_framework(summary, "ragas")
        + " | "
        + _markdown_table_for_framework(summary, "deepeval")
        + " |"
    )
    text = text[:start] + row + text[end:]

    shared = summary["comparison"]["shared_failed_ids"]
    ragas_only = summary["comparison"]["ragas_only_failed_ids"]
    deepeval_only = summary["comparison"]["deepeval_only_failed_ids"]
    analysis = (
        f"> *Phân tích:* Chạy {summary['comparison']['same_cases']} cases bằng cùng "
        f"Gemini judge ({model_name}), cùng "
        f"Context Precision/Recall và ngưỡng {summary['comparison']['threshold']:.2f}. "
        f"Cả hai cùng fail: {', '.join(shared) or 'không có'}; chỉ RAGAS: "
        f"{', '.join(ragas_only) or 'không có'}; chỉ DeepEval: "
        f"{', '.join(deepeval_only) or 'không có'}. Failure Jaccard: "
        f"{summary['comparison']['failure_jaccard']:.3f}. Case IDs: "
        f"{', '.join(summary['comparison']['case_ids'])}. Score là judge-based và có thể "
        "dao động; xem per-case scores và DeepEval judge reasons tại "
        "[`artifacts/framework_comparison.json`](artifacts/framework_comparison.json)."
    )
    begin = text.index("> *Phân tích:* ")
    finish = text.index("\n", begin)
    text = text[:begin] + analysis + text[finish:]

    comparison = summary["comparison"]
    ragas_fail_count = len(summary["ragas"]["failed_ids"])
    deepeval_fail_count = len(summary["deepeval"]["failed_ids"])
    stricter = "RAGAS" if ragas_fail_count > deepeval_fail_count else "DeepEval"
    answers = (
        "- **Scores có nhất quán không?** "
        f"Context Precision: MAE {comparison['context_precision_mae']:.3f}; "
        f"Context Recall: MAE {comparison['context_recall_mae']:.3f}. "
        f"Case lệch trên 0.10 ở ít nhất một metric: "
        f"{', '.join(comparison['score_disagreement_ids']) or 'không có'}. "
        "Cần đọc judge reasons và đối chiếu human labels cho các case lệch."
    )
    strictness = (
        "- **Framework nào strict hơn và vì sao?** "
        f"Trong lần chạy {comparison['same_cases']} case này, {stricter} strict hơn "
        f"theo gate {comparison['threshold']:.2f}: RAGAS fail {ragas_fail_count}, "
        f"DeepEval fail {deepeval_fail_count}. Điểm Context Precision trung bình là "
        f"{summary['ragas']['averages']['context_precision']:.3f} (RAGAS) và "
        f"{summary['deepeval']['averages']['context_precision']:.3f} (DeepEval). "
        "Chênh lệch có thể đến từ prompt judge và cách chuyển verdict theo từng chunk "
        "thành score; không nên khái quát ngoài lần chạy này."
    )
    matching = (
        "- **Hai framework có tìm ra cùng failure cases không?** "
        f"Cùng fail: {', '.join(shared) or 'không có'}; RAGAS-only: "
        f"{', '.join(ragas_only) or 'không có'}; DeepEval-only: "
        f"{', '.join(deepeval_only) or 'không có'}. Failure Jaccard "
        f"{comparison['failure_jaccard']:.3f}."
    )
    for prefix, replacement in (
        ("- **Scores có nhất quán không?**", answers),
        ("- **Framework nào strict hơn và vì sao?**", strictness),
        ("- **Hai framework có tìm ra cùng failure cases không?**", matching),
    ):
        begin = text.index(prefix)
        finish = text.index("\n", begin)
        text = text[:begin] + replacement + text[finish:]
    path.write_text(text, encoding="utf-8")


def _markdown_table_for_framework(summary: dict[str, Any], framework: str) -> str:
    averages = summary[framework]["averages"]
    failures = summary[framework]["failed_ids"]
    return (
        f"n={summary['comparison']['same_cases']}; "
        f"Precision {averages['context_precision']:.3f}, "
        f"Recall {averages['context_recall']:.3f}; fail="
        f"{', '.join(failures) or 'none'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", default=ROOT / "golden_dataset.json")
    parser.add_argument("--actual", default=ROOT / "artifacts/actual_answers.json")
    parser.add_argument("--output", default=ROOT / "artifacts/framework_comparison.json")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--limit", type=int, help="Score only the first N cases (debug/smoke run)")
    parser.add_argument("--ids", nargs="+", help="Score an explicit shared subset of case IDs")
    parser.add_argument("--no-markdown", action="store_true")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    pairs, answers = load_evaluation_inputs(args.golden, args.actual)
    source_dataset_size = len(pairs)
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")
    if args.ids:
        requested_ids = set(args.ids)
        pair_by_id = {pair.metadata["id"]: pair for pair in pairs}
        missing_ids = requested_ids - pair_by_id.keys()
        if missing_ids:
            parser.error("Unknown case IDs: " + ", ".join(sorted(missing_ids)))
        pairs = [pair for pair in pairs if pair.metadata["id"] in requested_ids]
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be greater than zero")
        pairs = pairs[:args.limit]
    case_ids = [pair.metadata["id"] for pair in pairs]
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    output = Path(args.output)
    checkpoint_path = output.with_name("framework_comparison.partial.json")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("model") != model_name or checkpoint.get("case_ids") != case_ids:
            parser.error(
                f"{checkpoint_path} belongs to a different model or case selection; "
                "remove it before starting a new comparison"
            )
    else:
        checkpoint = {
            "model": model_name,
            "case_ids": case_ids,
            "ragas": {},
            "deepeval": {},
        }

    def save_checkpoint() -> None:
        checkpoint_path.write_text(
            json.dumps(checkpoint, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    ragas_scores = _ragas_scores(pairs, checkpoint["ragas"], save_checkpoint)
    deepeval_scores = _deepeval_scores(
        pairs, answers, args.threshold, checkpoint["deepeval"], save_checkpoint
    )
    summary = _summarize(ragas_scores, deepeval_scores, args.threshold)
    artifact = {
        "judge_model": model_name,
        "dataset_size": len(pairs),
        "source_dataset_size": source_dataset_size,
        "threshold": args.threshold,
        "summary": summary,
        "per_case": {
            case_id: {"ragas": ragas_scores[case_id], "deepeval": deepeval_scores[case_id]}
            for case_id in sorted(ragas_scores)
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    checkpoint_path.unlink(missing_ok=True)
    if not args.no_markdown:
        _update_exercise(summary, ROOT / "exercises.md", model_name)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Saved per-case comparison to {output}")


if __name__ == "__main__":
    main()
