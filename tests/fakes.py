"""Deterministic LLM stand-ins for integration tests (not used in production)."""

from __future__ import annotations

from typing import Any

from app.agent.guardrails import ScopeGuardrail, heuristic_classify, llm_classifier
from app.agent.requirements import (
    MustHaveNeed,
    UnderstoodRequirements,
    categories_for_phrase,
    needed_categories,
    parse_must_have_phrases,
    prefer_large_sofa,
)
from app.agent.schemas import PlanExplanation, ProductChoice, ProductSelectionResult
from app.models.brief import RoomBrief


def fake_scope_guardrail() -> ScopeGuardrail:
    class _Model:
        def invoke(self, messages):
            user = ""
            if isinstance(messages, list):
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        user = str(msg.get("content", ""))
            return heuristic_classify(user)

    return ScopeGuardrail(classifier=llm_classifier(_Model()))


def fake_requirements_runner():
    def _run(brief: RoomBrief) -> UnderstoodRequirements:
        phrases = parse_must_have_phrases(brief.must_haves)
        must_haves = [
            MustHaveNeed(phrase=phrase, covering_categories=categories_for_phrase(phrase))
            for phrase in phrases
        ]
        cats = needed_categories(brief.must_haves) or ["Sofa", "Coffee Table", "Rug"]
        blob = f"{brief.must_haves} {brief.customer_note} {brief.constraints}".lower()
        return UnderstoodRequirements(
            needed_categories=cats,
            must_haves=must_haves,
            preferences=[brief.style_preference] if brief.style_preference else [],
            constraints=[brief.constraints] if brief.constraints.strip() else [],
            prefer_large_sofa=prefer_large_sofa(brief.must_haves),
            prefer_higher_spend=any(
                token in blob
                for token in ("premium", "high-end", "designer sofa", "statement", "impress")
            ),
        )

    return _run


def _style_rank(item: dict, style: str) -> int:
    wanted = style.casefold()
    tags = [str(tag).casefold() for tag in item.get("style_tags") or []]
    if wanted in tags:
        return 0
    if any(wanted in tag or tag in wanted for tag in tags if tag):
        return 1
    return 2


def fake_selection_runner():
    def _run(payload: dict[str, Any]) -> ProductSelectionResult:
        brief = payload.get("brief") or {}
        style = str(brief.get("style_preference") or "")
        categories = list(payload.get("needed_categories") or [])
        candidates = list(payload.get("candidates") or [])
        excluded = set(payload.get("excluded_item_ids") or [])
        respect = bool(payload.get("respect_remaining_budget"))
        remaining = int(payload.get("remaining_budget_inr") or brief.get("budget_inr") or 0)
        large = bool(payload.get("prefer_large_sofa"))
        premium = bool(payload.get("prefer_higher_spend"))
        reason = str(payload.get("replan_reason") or "")
        must = str(brief.get("must_haves") or "").lower()

        selections: list[ProductChoice] = []
        for category in categories:
            options = [
                item
                for item in candidates
                if item.get("category") == category and item.get("item_id") not in excluded
            ]

            def _key(item: dict, cat: str = category) -> tuple:
                style_rank = _style_rank(item, style)
                name = str(item.get("name") or "").lower()
                width = item.get("width_cm") or 0
                seater = 0
                if cat == "Sofa":
                    if "2-seater" in must or "loveseat" in must:
                        seater = (
                            0
                            if "2-seater" in name or "loveseat" in name or width <= 180
                            else 1
                        )
                    elif "3-seater" in must:
                        seater = 0 if "3-seater" in name or width >= 200 else 1
                price = item.get("price_inr") or 0
                if large and cat == "Sofa" and "layout:" not in reason:
                    return (0, -(width or 0), price)
                if premium and style_rank == 0:
                    return (style_rank, seater, -price)
                return (style_rank, seater, price)

            options.sort(key=_key)
            for item in options:
                price = item.get("price_inr") or 0
                if respect and price > remaining:
                    continue
                selections.append(
                    ProductChoice(
                        item_id=str(item["item_id"]),
                        role_in_room=category,
                        why_selected=(
                            f"{item.get('name')} is an in-stock Living Room {category} "
                            f"listed at ₹{price}."
                        ),
                    )
                )
                remaining -= price
                break
        return ProductSelectionResult(selections=selections)

    return _run


def fake_explanation_runner():
    def _run(payload: dict[str, Any]) -> PlanExplanation:
        style = str(payload.get("style_preference") or "Living Room")
        selected = payload.get("selected_products") or []
        coverage = payload.get("must_have_coverage") or {}
        missing = list(coverage.get("missing") or [])
        known = list(payload.get("known_limitations") or [])
        fit = payload.get("fit") or {}
        budget = payload.get("budget") or {}
        replans = int(payload.get("replan_count") or 0)

        ratio = fit.get("occupancy_ratio")
        room_area = fit.get("room_area_cm2")
        footprint = fit.get("furniture_footprint_cm2")
        fits = bool(fit.get("fits", True))
        remaining = int(budget.get("remaining") or 0)

        if ratio is not None:
            pct = int(round(float(ratio) * 100))
            fit_customer = (
                f"Your furniture uses about {pct}% of the floor, leaving open space. "
                "This checks overall room fit, not exact walking paths between pieces."
            )
            fit_technical = (
                f"Selected floor-standing items "
                f"{'fit' if fits else 'do not fit'} the room rectangle and ceiling. "
                f"Furniture footprint {footprint} cm² / room {room_area} cm² "
                f"(occupancy_ratio={float(ratio):.4f}). Circulation was not measured."
            )
        else:
            fit_customer = (
                "This checks overall room fit for size and height, not exact placement."
            )
            fit_technical = str(fit.get("explanation") or "Fit details unavailable.")

        tradeoffs: list[str] = []
        tradeoffs_technical: list[str] = []
        if remaining > 0 and selected:
            tradeoffs.append(
                f"We left ₹{remaining:,} of your budget unused in case you'd like to "
                "add extra pieces later."
            )
        if replans:
            tradeoffs.append(
                "The mix was revised so it could stay within budget and fit the room."
            )
            tradeoffs_technical.append(
                f"Re-planned {replans} time(s) after budget/fit validation failures."
            )
        if missing:
            tradeoffs.append(
                "Some requested pieces were omitted because they are absent from the "
                "catalogue, out of budget, or too large for the room."
            )
            tradeoffs_technical.append(
                "Uncovered must-haves after selection: " + ", ".join(missing)
            )
        if footprint is not None and room_area is not None and ratio is not None:
            tradeoffs_technical.append(
                f"Furniture occupancy {footprint} cm² of {room_area} cm² "
                f"({float(ratio) * 100:.1f}%); rugs/lamps/pendants may be excluded "
                "under fit assumptions."
            )

        limitations = [
            "This checks that your furniture fits the room's overall size and height — "
            "it isn't a full floor plan or a guarantee of exact placement."
        ]
        if missing:
            limitations.append(
                "Some requested pieces could not be sourced from the catalogue as specified."
            )
        limitations_technical = list(known) or [
            "Floor-standing items may be rotated 90 degrees in the fit check. "
            "Rugs, table lamps, and pendants follow accessory/ceiling exclusion rules."
        ]
        # Scope/refusal text is already customer-safe; surface it on the main page.
        if not payload.get("tools_ran") and known:
            limitations = list(known)

        if not selected and payload.get("tools_ran"):
            summary = (
                "No in-stock catalogue combination fitted this budget and room. "
                "A larger budget or fewer must-haves may work."
            )
        elif missing:
            summary = (
                f"A {style} living room from the catalogue. "
                "Some requested pieces could not be sourced as specified."
            )
        else:
            summary = (
                f"A {style} living room using in-stock catalogue "
                "pieces within the stated budget and room size."
            )
        return PlanExplanation(
            summary=summary,
            style_rationale=(
                f"{style} tags were preferred when present. "
                "Only in-stock Living Room products with a listed price were used."
            ),
            fit_status_customer=fit_customer,
            fit_status_technical=fit_technical,
            tradeoffs=tradeoffs,
            tradeoffs_technical=tradeoffs_technical,
            limitations=limitations,
            limitations_technical=limitations_technical,
        )

    return _run


def make_test_agent(**kwargs):
    from app.agent.graph import InteriorDesignAgent as Agent

    kwargs.setdefault("scope_guardrail", fake_scope_guardrail())
    kwargs.setdefault("requirements_runner", fake_requirements_runner())
    kwargs.setdefault("selection_runner", fake_selection_runner())
    kwargs.setdefault("explanation_runner", fake_explanation_runner())
    return Agent(**kwargs)
