"""Independent scoring of an agent run. No LLM judge."""

from __future__ import annotations

from typing import Any

from app.db.catalog_repository import CatalogRepository
from app.models.brief import RoomBrief
from app.models.output import DesignPlan, SelectedProduct
from app.tools.budget import BudgetCalculator
from app.tools.layout import LayoutChecker
from app.validation.output_validator import OutputValidator

GLOBAL_UNSELLABLE = ("SOF-006", "CON-002", "CFT-004", "RUG-003", "ART-003", "DNT-004")


def tool_flags(messages: list[str]) -> dict[str, bool]:
    joined = "\n".join(messages)
    return {
        "catalog": "tool:catalog_search" in joined,
        "budget": "tool:budget" in joined,
        "layout": "tool:layout" in joined,
    }


def selected_ids(plan: DesignPlan | None) -> list[str]:
    if plan is None:
        return []
    return [item.item_id for item in plan.selected_products]


def coverage_ratio(plan: DesignPlan | None) -> float | None:
    if plan is None:
        return None
    requested = plan.must_have_coverage.requested
    if not requested:
        return 1.0
    return len(plan.must_have_coverage.covered) / len(requested)


def _products(plan: DesignPlan | None) -> list[SelectedProduct]:
    if plan is None:
        return []
    return list(plan.selected_products)


def score_case(
    *,
    case: dict[str, Any],
    state: dict[str, Any],
    repository: CatalogRepository,
    validator: OutputValidator,
    budget: BudgetCalculator,
    layout: LayoutChecker,
) -> dict[str, Any]:
    expect = case.get("expect") or {}
    plan: DesignPlan | None = state.get("final_plan")
    messages = list(state.get("messages") or [])
    errors = list(state.get("validation_errors") or [])
    tools = tool_flags(messages)
    ids = selected_ids(plan)
    products = _products(plan)
    checks: dict[str, dict[str, Any]] = {}
    failures: list[str] = []

    default_forbidden = list(expect.get("forbidden_ids") or [])
    for sku in GLOBAL_UNSELLABLE:
        if sku not in default_forbidden:
            default_forbidden.append(sku)

    # --- catalogue ---
    catalogue_ok = True
    if products:
        for item in products:
            record = repository.get_item(item.item_id)
            if record is None:
                catalogue_ok = False
                failures.append(f"catalogue: unknown {item.item_id}")
            elif record.room_types and not record.is_living_room_applicable():
                catalogue_ok = False
                failures.append(f"catalogue: {item.item_id} is not Living Room tagged")
    checks["catalogue_validity"] = {"applicable": True, "passed": catalogue_ok}

    # --- stock ---
    stock_ok = True
    stock_applicable = bool(products)
    for item in products:
        record = repository.get_item(item.item_id)
        if record is not None and record.in_stock is not None and record.in_stock != 1:
            stock_ok = False
            failures.append(f"stock: {item.item_id} is not in stock")
    checks["stock_compliance"] = {"applicable": stock_applicable, "passed": stock_ok}

    # --- budget ---
    budget_ok = True
    if products:
        lines = [(item.item_id, item.quantity) for item in products]
        budget_inr = plan.budget.budget if plan else int(case["input"].get("budget_inr") or 1)
        recomputed = budget.calculate(lines, budget_inr)
        if recomputed.over_budget:
            budget_ok = False
            failures.append(
                f"budget: subtotal {recomputed.subtotal} exceeds {recomputed.budget}"
            )
        if plan and plan.budget.subtotal != recomputed.subtotal:
            budget_ok = False
            failures.append("budget: claimed subtotal does not match SQLite")
    elif plan is not None and plan.budget.over_budget:
        budget_ok = False
        failures.append("budget: empty plan marked over_budget")
    checks["budget_compliance"] = {"applicable": True, "passed": budget_ok}

    # --- fit ---
    fit_applicable = bool(products)
    fit_ok = True
    if products and plan is not None:
        brief = state.get("normalized_brief")
        if isinstance(brief, RoomBrief):
            recomputed_fit = layout.check(
                length_cm=brief.length_cm,
                width_cm=brief.width_cm,
                ceiling_cm=brief.ceiling_cm,
                selections=[(item.item_id, item.quantity) for item in products],
            )
            if not recomputed_fit.fits:
                fit_ok = False
                failures.append(f"fit: layout tool rejects {recomputed_fit.blocking_items}")
            if plan.fit.fits and not recomputed_fit.fits:
                fit_ok = False
                failures.append("fit: plan claims fit=true against the layout tool")
        else:
            fit_applicable = False
    checks["fit_correctness"] = {"applicable": fit_applicable, "passed": fit_ok}

    # --- must-haves ---
    min_coverage = expect.get("min_coverage")
    coverage_applicable = min_coverage is not None
    coverage_ok = True
    ratio = coverage_ratio(plan)
    if coverage_applicable:
        if expect.get("allow_empty") and not products:
            coverage_ok = True
        elif ratio is None:
            coverage_ok = False
            failures.append("coverage: no plan to score")
        elif ratio + 1e-9 < float(min_coverage):
            coverage_ok = False
            failures.append(f"coverage: {ratio:.2f} < min {min_coverage}")
    checks["must_have_coverage"] = {
        "applicable": coverage_applicable,
        "passed": coverage_ok,
        "ratio": ratio,
    }

    # --- tools ---
    want_tools = bool(expect.get("tools"))
    tools_ok = True
    if want_tools:
        for name in ("catalog", "budget", "layout"):
            if not tools[name]:
                tools_ok = False
                failures.append(f"tools: missing {name}")
    else:
        if tools["catalog"] or tools["budget"] or tools["layout"]:
            tools_ok = False
            failures.append("tools: catalogue/budget/layout ran on a blocked request")
    checks["tool_use_compliance"] = {"applicable": True, "passed": tools_ok, "tools": tools}

    # --- guardrail ---
    guard = expect.get("guardrail") or "allow"
    decision = state.get("scope_decision")
    label = getattr(getattr(decision, "label", None), "value", None)
    proceed_actual = True
    if decision is not None:
        proceed_actual = bool(decision.proceed)
    if any("unsupported_room_type" in err for err in errors):
        proceed_actual = False
        label = label or "unsupported_room_type"
    if any(err.startswith("scope:structural") for err in errors):
        proceed_actual = False
    if any("guarantee" in err for err in errors):
        proceed_actual = False

    want_proceed = bool(expect.get("proceed"))
    guard_ok = proceed_actual is want_proceed
    if guard == "block_room" and not (
        (label == "unsupported_room_type")
        or any("unsupported_room_type" in err for err in errors)
    ):
        guard_ok = False
        failures.append("guardrail: expected unsupported room block")
    elif guard == "block_structural" and label != "structural_construction":
        guard_ok = False
        failures.append(f"guardrail: expected structural block, got {label}")
    elif guard == "block_guarantee" and label != "unsupported_guarantee":
        guard_ok = False
        failures.append(f"guardrail: expected guarantee block, got {label}")
    elif guard == "allow" and not want_proceed:
        guard_ok = False
    if want_proceed != proceed_actual and f"guardrail: expected structural" not in " ".join(failures):
        if guard == "allow" and not proceed_actual:
            failures.append(f"guardrail: expected to proceed, got {label}")
            guard_ok = False
        elif guard != "allow" and proceed_actual:
            failures.append("guardrail: request proceeded but should have been blocked")
            guard_ok = False
    checks["guardrail_compliance"] = {
        "applicable": True,
        "passed": guard_ok,
        "label": label,
        "proceed": proceed_actual,
    }

    if products and not expect.get("allow_empty", True) is False and expect.get("allow_empty") is False:
        pass
    if not products and expect.get("allow_empty") is False:
        failures.append("empty: expected catalogue products")
        checks["non_empty"] = {"applicable": True, "passed": False}
    else:
        checks["non_empty"] = {
            "applicable": expect.get("allow_empty") is False,
            "passed": bool(products) or expect.get("allow_empty") is not False,
        }

    for sku in default_forbidden:
        if sku in ids:
            failures.append(f"forbidden: selected unsellable or blocked {sku}")
            checks["catalogue_validity"]["passed"] = False

    for fragment in expect.get("forbidden_name_substrings") or []:
        for item in products:
            name = item.catalog_item.name if item.catalog_item else ""
            if fragment.lower() in name.lower():
                failures.append(f"forbidden: name contains {fragment} ({item.item_id})")
                checks["catalogue_validity"]["passed"] = False

    if products and isinstance(state.get("normalized_brief"), RoomBrief):
        report = validator.validate(
            brief=state["normalized_brief"],
            selected=products,
            claimed_budget=plan.budget if plan else None,
            claimed_fit=plan.fit if plan else None,
            plan=plan,
        )
        independent_ok = report.ok
        if not report.ok:
            failures.append("independent_validator: " + "; ".join(report.tokens()))
    else:
        independent_ok = True
    checks["independent_validation"] = {
        "applicable": bool(products),
        "passed": independent_ok,
    }

    passed = True
    for check in checks.values():
        if check.get("applicable") and not check.get("passed"):
            passed = False

    return {
        "id": case["id"],
        "title": case.get("title"),
        "kind": case.get("kind"),
        "passed": passed,
        "selected_ids": ids,
        "replan_count": int(state.get("replan_count") or 0),
        "checks": checks,
        "failures": failures,
        "tools": tools,
        "coverage_ratio": ratio,
        "guardrail_label": label,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, dict[str, float | int | None]] = {}
    for key in (
        "catalogue_validity",
        "stock_compliance",
        "budget_compliance",
        "fit_correctness",
        "must_have_coverage",
        "tool_use_compliance",
        "guardrail_compliance",
    ):
        applicable = [row for row in results if row["checks"][key].get("applicable")]
        passed = [row for row in applicable if row["checks"][key]["passed"]]
        n = len(applicable)
        metrics[key] = {
            "applicable": n,
            "passed": len(passed),
            "rate": (len(passed) / n) if n else None,
        }
    metrics["cases"] = {
        "applicable": len(results),
        "passed": sum(1 for row in results if row["passed"]),
        "rate": sum(1 for row in results if row["passed"]) / len(results) if results else None,
    }
    return metrics
