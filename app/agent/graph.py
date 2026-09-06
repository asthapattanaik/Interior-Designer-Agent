"""LangGraph Living Room designer. Catalogue, budget and layout use real tools."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.guardrails import ScopeGuardrail
from app.agent.llm import build_structured_model, invoke_structured
from app.agent.prompts import ScopeDecision
from app.agent.requirements import (
    CATALOG_CATEGORIES,
    REQUIREMENTS_SYSTEM_PROMPT,
    UnderstoodRequirements,
)
from app.agent.schemas import (
    EXPLANATION_SYSTEM_PROMPT,
    SELECTION_SYSTEM_PROMPT,
    PlanExplanation,
    ProductSelectionResult,
)
from app.agent.state import AgentState, empty_agent_state
from app.config import load_settings
from app.db.catalog_repository import CatalogRepository
from app.models.brief import RoomBrief
from app.models.catalog import CatalogItem
from app.models.output import BudgetResult, DesignPlan, FitResult, MustHaveCoverage, SelectedProduct
from app.tools.budget import BudgetCalculator
from app.tools.catalog_search import CatalogSearchTool
from app.tools.layout import LayoutChecker
from app.validation.normalize import NormalizationError, normalize_customer_input
from app.validation.output_validator import OutputValidator, ValidationReport

RequirementsRunner = Callable[[RoomBrief], UnderstoodRequirements]
SelectionRunner = Callable[[dict[str, Any]], ProductSelectionResult]
ExplanationRunner = Callable[[dict[str, Any]], PlanExplanation]


def _excluded_ids(messages: list[str]) -> set[str]:
    found: set[str] = set()
    for message in messages:
        if message.startswith("exclude:"):
            found.add(message.split(":", 1)[1].strip())
    return found


def _usable(item: CatalogItem) -> bool:
    return (
        item.is_living_room_applicable()
        and item.in_stock == 1
        and item.has_usable_price()
    )


def _candidate_payload(item: CatalogItem) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "name": item.name,
        "category": item.category,
        "style_tags": item.style_tag_list(),
        "price_inr": item.price_inr,
        "width_cm": item.width_cm,
        "depth_cm": item.depth_cm,
        "height_cm": item.height_cm,
        "color_finish": item.color_finish,
    }


def _filter_categories(raw: list[str]) -> list[str]:
    allowed = set(CATALOG_CATEGORIES)
    out: list[str] = []
    for category in raw:
        if category in allowed and category not in out:
            out.append(category)
    return out


def default_requirements_runner() -> RequirementsRunner:
    model = build_structured_model(UnderstoodRequirements)

    def _run(brief: RoomBrief) -> UnderstoodRequirements:
        user = (
            f"style_preference={brief.style_preference}\n"
            f"must_haves={brief.must_haves}\n"
            f"constraints={brief.constraints}\n"
            f"customer_note={brief.customer_note}\n"
            f"budget_inr={brief.budget_inr}\n"
            f"room_cm={brief.length_cm}x{brief.width_cm}, ceiling={brief.ceiling_cm}"
        )
        result = invoke_structured(
            model,
            [
                {"role": "system", "content": REQUIREMENTS_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            stage="understand_requirements",
            schema=UnderstoodRequirements,
        )
        cleaned_needs = _filter_categories(result.needed_categories)
        cleaned_must: list = []
        for need in result.must_haves:
            cats = _filter_categories(need.covering_categories)
            cleaned_must.append(need.model_copy(update={"covering_categories": cats}))
        return result.model_copy(
            update={"needed_categories": cleaned_needs, "must_haves": cleaned_must}
        )

    return _run


def default_selection_runner() -> SelectionRunner:
    model = build_structured_model(ProductSelectionResult)

    def _run(payload: dict[str, Any]) -> ProductSelectionResult:
        return invoke_structured(
            model,
            [
                {"role": "system", "content": SELECTION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
            stage="product_selection",
            schema=ProductSelectionResult,
        )

    return _run


def default_explanation_runner() -> ExplanationRunner:
    model = build_structured_model(PlanExplanation)

    def _run(payload: dict[str, Any]) -> PlanExplanation:
        return invoke_structured(
            model,
            [
                {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
            stage="finalize",
            schema=PlanExplanation,
        )

    return _run


class InteriorDesignAgent:
    def __init__(
        self,
        *,
        repository: CatalogRepository | None = None,
        max_replans: int = 3,
        scope_guardrail: ScopeGuardrail | None = None,
        requirements_runner: RequirementsRunner | None = None,
        selection_runner: SelectionRunner | None = None,
        explanation_runner: ExplanationRunner | None = None,
    ) -> None:
        needs_live_llm = any(
            dep is None
            for dep in (
                scope_guardrail,
                requirements_runner,
                selection_runner,
                explanation_runner,
            )
        )
        if needs_live_llm:
            # Hard-fail before any graph work if the key/config is missing.
            load_settings()

        self.max_replans = max_replans
        repo = repository or CatalogRepository()
        self.catalog = CatalogSearchTool(repository=repo)
        self.budget = BudgetCalculator(repository=repo)
        self.layout = LayoutChecker(repository=repo)
        self.validator = OutputValidator(
            repository=repo, budget=self.budget, layout=self.layout
        )
        self.scope_guardrail = scope_guardrail or ScopeGuardrail()
        self.requirements_runner = requirements_runner or default_requirements_runner()
        self.selection_runner = selection_runner or default_selection_runner()
        self.explanation_runner = explanation_runner or default_explanation_runner()
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("validate_and_normalize", self._validate_and_normalize)
        graph.add_node("scope_check", self._scope_check)
        graph.add_node("understand_requirements", self._understand_requirements)
        graph.add_node("catalog_search", self._catalog_search)
        graph.add_node("product_selection", self._product_selection)
        graph.add_node("budget_check", self._budget_check)
        graph.add_node("layout_check", self._layout_check)
        graph.add_node("output_validation", self._output_validation)
        graph.add_node("replan", self._replan)
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "validate_and_normalize")
        graph.add_conditional_edges(
            "validate_and_normalize",
            self._route_after_validate,
            {"scope_check": "scope_check", "finalize": "finalize"},
        )
        graph.add_conditional_edges(
            "scope_check",
            self._route_after_scope,
            {"understand_requirements": "understand_requirements", "finalize": "finalize"},
        )
        graph.add_edge("understand_requirements", "catalog_search")
        graph.add_edge("catalog_search", "product_selection")
        graph.add_edge("product_selection", "budget_check")
        graph.add_edge("budget_check", "layout_check")
        graph.add_edge("layout_check", "output_validation")
        graph.add_conditional_edges(
            "output_validation",
            self._route_after_output,
            {"finalize": "finalize", "replan": "replan"},
        )
        graph.add_edge("replan", "catalog_search")
        graph.add_edge("finalize", END)
        return graph.compile()

    def invoke(self, brief: RoomBrief | dict) -> AgentState:
        state = empty_agent_state()
        if isinstance(brief, RoomBrief):
            state["brief"] = brief
            state["raw_input"] = brief.model_dump()
        else:
            state["raw_input"] = dict(brief)
        return self._graph.invoke(state)

    def _route_after_validate(self, state: AgentState) -> str:
        return "finalize" if state.get("validation_errors") else "scope_check"

    def _route_after_scope(self, state: AgentState) -> str:
        blocking = [
            err
            for err in state.get("validation_errors") or []
            if err.startswith("scope:")
        ]
        return "finalize" if blocking else "understand_requirements"

    def _route_after_output(self, state: AgentState) -> str:
        errors = state.get("validation_errors") or []
        if not errors:
            return "finalize"
        if int(state.get("replan_count") or 0) >= self.max_replans:
            return "finalize"
        return "replan"

    def _validate_and_normalize(self, state: AgentState) -> dict:
        existing = state.get("brief")
        if isinstance(existing, RoomBrief):
            return {
                "brief": existing,
                "normalized_brief": existing,
                "validation_errors": [],
                "messages": ["validate_and_normalize: ok"],
            }
        raw = state.get("raw_input") or {}
        try:
            brief = normalize_customer_input(raw)
        except NormalizationError as exc:
            return {
                "normalized_brief": None,
                "validation_errors": list(exc.errors),
                "messages": ["validate_and_normalize: failed"] + list(exc.errors),
            }
        return {
            "brief": brief,
            "normalized_brief": brief,
            "validation_errors": [],
            "messages": ["validate_and_normalize: ok"],
        }

    def _scope_check(self, state: AgentState) -> dict:
        brief = state.get("normalized_brief")
        extra = ""
        raw = state.get("raw_input") or {}
        if isinstance(raw, dict):
            extra = " ".join(
                str(raw.get(k, ""))
                for k in ("must_haves", "constraints", "customer_note", "room_type")
            )
        decision = self.scope_guardrail.evaluate(brief, extra_text=extra)
        messages = [
            f"scope_check:{decision.label.value}",
            f"limitation:{decision.explanation}",
            f"redirect:{decision.redirect}",
        ]
        if not decision.proceed:
            return {
                "scope_decision": decision,
                "validation_errors": [f"scope:{decision.label.value}"],
                "messages": messages,
            }
        return {
            "scope_decision": decision,
            "validation_errors": [],
            "messages": messages,
        }

    def _understand_requirements(self, state: AgentState) -> dict:
        brief = state["normalized_brief"]
        understood = self.requirements_runner(brief)
        phrases = [need.phrase for need in understood.must_haves]
        coverage = MustHaveCoverage(
            requested=phrases,
            covered=[],
            missing=list(phrases),
        )
        return {
            "understood_requirements": understood,
            "must_have_coverage": coverage,
            "messages": [
                "understand_requirements: "
                + ",".join(understood.needed_categories or ["none"])
            ],
        }

    def _catalog_search(self, state: AgentState) -> dict:
        brief = state["normalized_brief"]
        understood = state.get("understood_requirements")
        categories = list(understood.needed_categories) if understood else []
        style = brief.style_preference
        seen: dict[str, CatalogItem] = {}

        def _add(items: list[CatalogItem]) -> None:
            for item in items:
                if _usable(item):
                    seen[item.item_id] = item

        if categories:
            for category in categories:
                _add(self.catalog.search(category=category, in_stock_only=True))
                _add(
                    self.catalog.search(
                        category=category, style=style, in_stock_only=True
                    )
                )
        _add(self.catalog.search(style=style, in_stock_only=True))
        _add(self.catalog.search(in_stock_only=True))
        candidates = list(seen.values())
        return {
            "candidate_products": candidates,
            "messages": [f"tool:catalog_search:{len(candidates)}"],
        }

    def _product_selection(self, state: AgentState) -> dict:
        brief = state["normalized_brief"]
        understood = state.get("understood_requirements")
        excluded = _excluded_ids(state.get("messages") or [])
        candidates = [
            item
            for item in state.get("candidate_products") or []
            if item.item_id not in excluded and _usable(item)
        ]
        categories = (
            list(understood.needed_categories)
            if understood and understood.needed_categories
            else ["Sofa", "Coffee Table", "Rug"]
        )
        remaining = brief.budget_inr
        respect_budget = int(state.get("replan_count") or 0) > 0
        payload = {
            "brief": {
                "style_preference": brief.style_preference,
                "must_haves": brief.must_haves,
                "constraints": brief.constraints,
                "customer_note": brief.customer_note,
                "budget_inr": brief.budget_inr,
                "room_cm": {
                    "length": brief.length_cm,
                    "width": brief.width_cm,
                    "ceiling": brief.ceiling_cm,
                },
            },
            "needed_categories": categories,
            "preferences": list(understood.preferences) if understood else [],
            "extracted_constraints": list(understood.constraints) if understood else [],
            "prefer_large_sofa": bool(understood.prefer_large_sofa) if understood else False,
            "prefer_higher_spend": bool(understood.prefer_higher_spend) if understood else False,
            "respect_remaining_budget": respect_budget,
            "remaining_budget_inr": remaining if respect_budget else brief.budget_inr,
            "replan_reason": state.get("replan_reason") or "",
            "excluded_item_ids": sorted(excluded),
            "candidates": [_candidate_payload(item) for item in candidates],
        }
        result = self.selection_runner(payload)

        by_id = {item.item_id: item for item in candidates}
        selected: list[SelectedProduct] = []
        seen_categories: set[str] = set()
        spend = 0
        for choice in result.selections:
            item = by_id.get(choice.item_id)
            if item is None:
                continue
            if item.category in seen_categories:
                continue
            price = item.price_inr or 0
            if respect_budget and spend + price > remaining:
                continue
            role = choice.role_in_room or item.category
            selected.append(
                SelectedProduct(
                    item_id=item.item_id,
                    quantity=1,
                    role_in_room=role,
                    why_selected=choice.why_selected,
                    catalog_item=item,
                )
            )
            seen_categories.add(item.category)
            spend += price

        coverage = self._coverage(brief, selected, understood)
        return {
            "selected_products": selected,
            "must_have_coverage": coverage,
            "messages": [f"product_selection:{[p.item_id for p in selected]}"],
        }

    def _coverage(
        self,
        brief: RoomBrief,
        selected: list[SelectedProduct],
        understood: UnderstoodRequirements | None,
    ) -> MustHaveCoverage:
        selected_categories = {
            (item.catalog_item.category if item.catalog_item else item.role_in_room)
            for item in selected
        }
        if understood and understood.must_haves:
            requested = [need.phrase for need in understood.must_haves]
            covered: list[str] = []
            missing: list[str] = []
            for need in understood.must_haves:
                cats = need.covering_categories
                if not cats:
                    if "no tv" in need.phrase.lower():
                        covered.append(need.phrase)
                    else:
                        missing.append(need.phrase)
                    continue
                if any(cat in selected_categories for cat in cats):
                    covered.append(need.phrase)
                else:
                    missing.append(need.phrase)
            return MustHaveCoverage(requested=requested, covered=covered, missing=missing)

        # Fallback if understand_requirements produced no must-have list.
        requested = [brief.must_haves] if brief.must_haves.strip() else []
        if not requested:
            return MustHaveCoverage()
        if selected:
            return MustHaveCoverage(requested=requested, covered=requested, missing=[])
        return MustHaveCoverage(requested=requested, covered=[], missing=requested)

    def _budget_check(self, state: AgentState) -> dict:
        brief = state["normalized_brief"]
        selected = state.get("selected_products") or []
        result = self.budget.calculate(
            [(item.item_id, item.quantity) for item in selected],
            brief.budget_inr,
        )
        return {
            "budget_result": result,
            "messages": [
                f"tool:budget:subtotal={result.subtotal}:over={result.over_budget}"
            ],
        }

    def _layout_check(self, state: AgentState) -> dict:
        brief = state["normalized_brief"]
        selected = state.get("selected_products") or []
        result = self.layout.check(
            length_cm=brief.length_cm,
            width_cm=brief.width_cm,
            ceiling_cm=brief.ceiling_cm,
            selections=[(item.item_id, item.quantity) for item in selected],
        )
        return {
            "layout_result": result,
            "messages": [
                f"tool:layout:fits={result.fits}:blocking={result.blocking_items}"
            ],
        }

    def _output_validation(self, state: AgentState) -> dict:
        brief = state["normalized_brief"]
        selected = state.get("selected_products") or []
        report = self.validator.validate(
            brief=brief,
            selected=selected,
            claimed_budget=state.get("budget_result"),
            claimed_fit=state.get("layout_result"),
        )
        return {
            "budget_result": report.recomputed_budget or state.get("budget_result"),
            "layout_result": report.recomputed_fit or state.get("layout_result"),
            "validation_errors": report.tokens(),
            "validation_report": report,
            "messages": [
                "output_validation:pass"
                if report.ok
                else f"output_validation:fail:{report.tokens()}"
            ],
        }

    def _replan(self, state: AgentState) -> dict:
        count = int(state.get("replan_count") or 0) + 1
        errors = state.get("validation_errors") or []
        reason = "; ".join(errors) or "unspecified"
        extra: list[str] = [f"replan:{count}:{reason}", f"replan_reason:{reason}"]
        report = state.get("validation_report")
        ids: list[str] = []
        if isinstance(report, ValidationReport):
            ids.extend(report.item_ids())
        layout = state.get("layout_result")
        if layout:
            ids.extend(layout.blocking_items)
        selected = state.get("selected_products") or []
        if any(token.startswith("budget:") for token in errors) and selected:
            priced = []
            for item in selected:
                price = item.catalog_item.price_inr if item.catalog_item else 0
                priced.append((price or 0, item.item_id))
            priced.sort(reverse=True)
            ids.append(priced[0][1])
        for item_id in ids:
            extra.append(f"exclude:{item_id}")
        return {
            "replan_count": count,
            "replan_reason": reason,
            "selected_products": [],
            "validation_errors": [],
            "messages": extra,
        }

    def _finalize(self, state: AgentState) -> dict:
        brief = state.get("normalized_brief")
        selected = list(state.get("selected_products") or [])
        coverage = state.get("must_have_coverage") or MustHaveCoverage()
        errors = state.get("validation_errors") or []
        replans = int(state.get("replan_count") or 0)
        messages = state.get("messages") or []
        tools_ran = any(msg.startswith("tool:catalog_search") for msg in messages)
        limitations = [
            msg.split(":", 1)[1]
            for msg in messages
            if msg.startswith("limitation:")
        ]

        if brief is None:
            return {
                "final_plan": None,
                "messages": ["finalize: rejected before design"],
            }

        if not tools_ran:
            budget = BudgetResult(
                subtotal=0,
                budget=brief.budget_inr,
                remaining=brief.budget_inr,
                over_budget=False,
            )
            layout = FitResult(
                fits=True,
                explanation=(
                    "No furniture was selected because the request was stopped before "
                    "catalogue, budget, or layout tools ran."
                ),
                occupancy_ratio=0,
                room_area_cm2=brief.length_cm * brief.width_cm,
                furniture_footprint_cm2=0,
            )
            selected = []
        else:
            original_ids = [item.item_id for item in selected]
            selected, report = self.validator.feasible_selection(
                brief=brief, selected=selected
            )
            budget = report.recomputed_budget
            layout = report.recomputed_fit
            coverage = self._coverage(
                brief, selected, state.get("understood_requirements")
            )
            if original_ids != [item.item_id for item in selected]:
                limitations.append(
                    "Invalid SKUs were removed rather than returned as a successful plan."
                )
            if errors and replans >= self.max_replans:
                limitations.append(
                    "The catalogue could not complete every requested piece within "
                    "this budget and room size."
                )
            if not selected:
                limitations.append(
                    "No valid in-stock Living Room combination was found within "
                    "budget, fit, and re-plan limits. This is a catalogue/constraint "
                    "limitation, not a completed design."
                )

        if coverage.missing:
            limitations.append(
                "Uncovered must-haves: " + ", ".join(coverage.missing)
            )
        limitations.append(
            "Fit is a rectangle/height check, not a furnished floor-plan guarantee."
        )

        decision = state.get("scope_decision")
        if isinstance(decision, ScopeDecision) and not decision.proceed:
            limitations.append(decision.explanation)
            limitations.append(decision.redirect)

        facts = {
            "style_preference": brief.style_preference,
            "selected_products": [
                {
                    "item_id": item.item_id,
                    "name": item.catalog_item.name if item.catalog_item else item.item_id,
                    "category": (
                        item.catalog_item.category if item.catalog_item else item.role_in_room
                    ),
                    "price_inr": item.catalog_item.price_inr if item.catalog_item else None,
                    "why_selected": item.why_selected,
                    "role_in_room": item.role_in_room,
                }
                for item in selected
            ],
            "budget": budget.model_dump(),
            "fit": layout.model_dump(),
            "must_have_coverage": coverage.model_dump(),
            "replan_count": replans,
            "known_limitations": limitations,
            "tools_ran": tools_ran,
        }
        explanation = self.explanation_runner(facts)

        customer_limitations = [
            line for line in explanation.limitations if line.strip()
        ]
        technical_limitations = [
            line for line in explanation.limitations_technical if line.strip()
        ]
        if not technical_limitations:
            technical_limitations = list(limitations)
            if layout.explanation:
                technical_limitations.insert(0, layout.explanation)

        fit_customer = explanation.fit_status_customer.strip()
        fit_technical = explanation.fit_status_technical.strip() or layout.explanation

        plan = DesignPlan(
            summary=explanation.summary,
            style_rationale=explanation.style_rationale,
            selected_products=selected,
            budget=budget,
            fit=layout,
            fit_status_customer=fit_customer
            or (
                "Selected pieces fit the room size and height."
                if layout.fits
                else "The current mix does not fit the room size or height."
            ),
            fit_status_technical=fit_technical,
            must_have_coverage=coverage,
            tradeoffs=list(explanation.tradeoffs),
            tradeoffs_technical=list(explanation.tradeoffs_technical),
            limitations=customer_limitations
            or [
                "This checks that your furniture fits the room's overall size and "
                "height — it isn't a full floor plan or a guarantee of exact placement."
            ],
            limitations_technical=technical_limitations,
        )
        return {
            "final_plan": plan,
            "selected_products": selected,
            "budget_result": budget,
            "layout_result": layout,
            "must_have_coverage": coverage,
            "messages": ["finalize: done"],
        }


def run_design(brief: RoomBrief | dict, *, max_replans: int = 3) -> AgentState:
    return InteriorDesignAgent(max_replans=max_replans).invoke(brief)
