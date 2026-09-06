"""Evaluation runner: deterministic checks plus optional LLM judge.

Usage:
    python -m app.evaluation.runner
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.agent.graph import InteriorDesignAgent
from app.config import PROJECT_ROOT
from app.db.catalog_repository import CatalogRepository
from app.evaluation.cases import load_golden_set
from app.evaluation.deterministic import aggregate, score_case
from app.evaluation.judge import aggregate_judge_scores, judge_case, make_openai_judge
from app.tools.budget import BudgetCalculator
from app.tools.layout import LayoutChecker
from app.validation.output_validator import OutputValidator

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"


def _pct(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{100.0 * rate:.1f}%"


def run_suite(golden_path: Path | None = None, *, with_judge: bool = True) -> dict:
    payload = load_golden_set(golden_path)
    repo = CatalogRepository()
    validator = OutputValidator(repository=repo)
    budget = BudgetCalculator(repository=repo)
    layout = LayoutChecker(repository=repo)
    agent = InteriorDesignAgent(repository=repo)
    judge_model = None
    judge_error: str | None = None
    if with_judge:
        try:
            judge_model = make_openai_judge()
        except Exception as exc:  # noqa: BLE001 — surface settings/API setup failures
            judge_error = f"Judge unavailable: {exc}"

    results = []
    for case in payload["cases"]:
        state = agent.invoke(case["input"])
        scored = score_case(
            case=case,
            state=state,
            repository=repo,
            validator=validator,
            budget=budget,
            layout=layout,
        )
        if judge_model is not None:
            try:
                scored["judge"] = judge_case(
                    case=case,
                    scored=scored,
                    state=state,
                    repository=repo,
                    structured_model=judge_model,
                )
            except Exception as exc:  # noqa: BLE001
                scored["judge"] = {"error": str(exc)}
        elif judge_error:
            scored["judge"] = {"error": judge_error}
        results.append(scored)

    metrics = aggregate(results)
    judge_metrics = aggregate_judge_scores(results)
    failures = [row for row in results if not row["passed"]]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "metrics": metrics,
        "judge_metrics": judge_metrics,
        "failures": [
            {"id": row["id"], "title": row["title"], "reasons": row["failures"]}
            for row in failures
        ],
        "cases": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = RESULTS_DIR / f"eval_{stamp}.json"
    latest = RESULTS_DIR / "latest.json"
    summary = RESULTS_DIR / "latest_summary.txt"
    text = _format_summary(report)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nWrote {out_json}")
    print(f"Wrote {latest}")
    return report


def _format_summary(report: dict) -> str:
    metrics = report["metrics"]
    judge = report.get("judge_metrics") or {}
    by_dim = judge.get("by_dimension") or {}
    lines = [
        "Evaluation (deterministic + LLM judge)",
        f"Cases: {report['case_count']}",
        "",
        "Deterministic metrics (authoritative)",
        f"  catalogue_validity     {_pct(metrics['catalogue_validity']['rate'])}  "
        f"({metrics['catalogue_validity']['passed']}/{metrics['catalogue_validity']['applicable']})  target 100%",
        f"  stock_compliance       {_pct(metrics['stock_compliance']['rate'])}  "
        f"({metrics['stock_compliance']['passed']}/{metrics['stock_compliance']['applicable']})  target 100%",
        f"  budget_compliance      {_pct(metrics['budget_compliance']['rate'])}  "
        f"({metrics['budget_compliance']['passed']}/{metrics['budget_compliance']['applicable']})  target 100%",
        f"  fit_correctness        {_pct(metrics['fit_correctness']['rate'])}  "
        f"({metrics['fit_correctness']['passed']}/{metrics['fit_correctness']['applicable']})  target >=95%",
        f"  must_have_coverage     {_pct(metrics['must_have_coverage']['rate'])}  "
        f"({metrics['must_have_coverage']['passed']}/{metrics['must_have_coverage']['applicable']})  target >=90%",
        f"  tool_use_compliance    {_pct(metrics['tool_use_compliance']['rate'])}  "
        f"({metrics['tool_use_compliance']['passed']}/{metrics['tool_use_compliance']['applicable']})  target 100%",
        f"  guardrail_compliance   {_pct(metrics['guardrail_compliance']['rate'])}  "
        f"({metrics['guardrail_compliance']['passed']}/{metrics['guardrail_compliance']['applicable']})  target 100%",
        f"  cases passed           {_pct(metrics['cases']['rate'])}  "
        f"({metrics['cases']['passed']}/{metrics['cases']['applicable']})",
        "",
        "LLM judge (qualitative; cannot override facts)",
    ]
    if judge.get("mean") is None:
        lines.append("  no judge scores")
    else:
        lines.append(f"  overall mean           {judge['mean']:.2f} / 5  (n={judge['applicable']})")
        for dim, value in by_dim.items():
            lines.append(f"  {dim:22} {value:.2f}")
        if judge.get("contradicted_facts"):
            lines.append(f"  fact contradictions    {judge['contradicted_facts']}")
        if judge.get("low_scores"):
            lines.append("  notable low scores")
            for item in judge["low_scores"]:
                lines.append(f"    - {item['id']}: mean={item['mean']:.2f}")
        else:
            lines.append("  notable low scores     none (< 3.0)")
    lines.append("")
    if report["failures"]:
        lines.append("Deterministic failures")
        for item in report["failures"]:
            reasons = "; ".join(item["reasons"]) or "(no reason recorded)"
            lines.append(f"  - {item['id']}: {reasons}")
    else:
        lines.append("Deterministic failures: none")
    lines.append("")
    lines.append("Per-case")
    for row in report["cases"]:
        mark = "PASS" if row["passed"] else "FAIL"
        ids = ",".join(row["selected_ids"]) or "-"
        judge_row = row.get("judge") or {}
        mean = judge_row.get("mean")
        mean_txt = f" judge={mean:.2f}" if isinstance(mean, (int, float)) else ""
        err = judge_row.get("error")
        extra = f" judge_error={err}" if err else mean_txt
        lines.append(f"  [{mark}] {row['id']:28} products={ids}{extra}")
    return "\n".join(lines)


def main() -> None:
    run_suite(with_judge=True)


if __name__ == "__main__":
    main()
