"""Map the customer form to the agent without exposing internal traces."""

from __future__ import annotations

from app.agent.prompts import ScopeDecision
from app.agent.state import AgentState
from app.models.output import DesignPlan, SelectedProduct
from app.ui.results import UiResult, UiResultKind
from app.validation.output_validator import OutputValidator

__all__ = [
    "DIMENSION_UNITS",
    "PREFERRED_STYLES",
    "UiResult",
    "UiResultKind",
    "build_form_payload",
    "classify_agent_state",
    "customer_limitations",
    "customer_message",
    "customer_tradeoffs",
    "design_from_form",
    "format_inr",
    "product_name",
    "product_price",
]

PREFERRED_STYLES = (
    "Scandinavian",
    "Mid-Century",
    "Contemporary",
    "Bohemian",
    "Coastal",
    "Industrial",
    "Minimalist",
    "Traditional",
)

DIMENSION_UNITS = ("cm", "ft", "m")

_CUSTOMER_ERRORS = {
    "missing:length": "Please enter the room length.",
    "missing:width": "Please enter the room width.",
    "missing:ceiling": "Please enter the ceiling height.",
    "missing:budget": "Please enter a budget in Indian rupees.",
    "missing:style_preference": "Please choose a preferred style.",
    "missing:must_haves": "Please describe what the living room must include.",
    "missing:room_type": "We currently furnish Living Rooms only.",
    "invalid:length": "Room length must be a positive number.",
    "invalid:width": "Room width must be a positive number.",
    "invalid:ceiling": "Ceiling height must be a positive number.",
    "invalid:budget": "Budget must be a positive amount in Indian rupees.",
    "unsupported_room_type": "We currently furnish Living Rooms only.",
    "scope:unsupported_room_type": "We currently furnish Living Rooms only.",
    "scope:structural_construction": (
        "We can furnish a living room from our catalogue, but we cannot advise on "
        "knocking down walls or structural work."
    ),
    "scope:unsupported_guarantee": (
        "We can recommend in-stock living room pieces and share listed lead times, "
        "but we cannot promise delivery dates or a locked final price."
    ),
    "scope:ambiguous": "Please describe a Living Room furniture request.",
}


def build_form_payload(
    *,
    length: float | int | str,
    width: float | int | str,
    ceiling: float | int | str,
    unit: str,
    budget: float | int | str,
    style_preference: str,
    must_haves: str,
    constraints: str,
    customer_note: str,
) -> dict:
    return {
        "room_type": "Living Room",
        "length": length,
        "width": width,
        "ceiling": ceiling,
        "unit": unit,
        "budget": budget,
        "style_preference": style_preference,
        "must_haves": must_haves,
        "constraints": constraints,
        "customer_note": customer_note,
    }


def customer_message(token: str) -> str | None:
    """Turn a validation token into a short customer sentence. Drops internals."""
    if token.startswith(("tool:", "replan:", "exclude:", "output_validation", "product_selection")):
        return None
    if token in _CUSTOMER_ERRORS:
        return _CUSTOMER_ERRORS[token]
    for prefix, message in _CUSTOMER_ERRORS.items():
        if token.startswith(prefix):
            return message
    if token.startswith("missing_unit:"):
        return "Please choose a unit for the room dimensions (cm, ft, or m)."
    if token.startswith("unsupported_unit:"):
        return "Please use centimetres, feet, or metres."
    if token.startswith(("catalogue:", "stock:", "price:", "budget:", "layout:", "schema:", "living_room:")):
        return None
    if token.startswith("scope:"):
        return "This request is outside what the Living Room designer can do."
    return None


def _customer_line(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.startswith(
        ("tool:", "replan:", "exclude:", "output_validation", "product_selection", "finalize:")
    ):
        return None
    if stripped.startswith("Re-planned"):
        return (
            "The recommendation was revised so it could stay within budget and fit the room."
        )
    if "Stopped after MAX_REPLANS" in stripped:
        return (
            "We couldn't find a complete living room that fits this budget and space."
        )
    if any(
        marker in stripped
        for marker in (
            "budget:",
            "layout:",
            "catalogue:",
            "stock:",
            "price:",
            "schema:",
            "living_room:",
        )
    ):
        return None
    return stripped


def format_inr(amount: int | None) -> str:
    if amount is None:
        return "Price not available"
    return f"₹{amount:,}"


def product_price(product: SelectedProduct) -> str:
    if product.catalog_item is None:
        return "Price not available"
    return format_inr(product.catalog_item.price_inr)


def product_name(product: SelectedProduct) -> str:
    if product.catalog_item is not None:
        return product.catalog_item.name
    return product.item_id


def _unique(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in lines:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _scope_rejected(state: AgentState) -> ScopeDecision | None:
    decision = state.get("scope_decision")
    if isinstance(decision, ScopeDecision) and not decision.proceed:
        return decision
    return None


def _is_unsupported_room_error(errors: list[str]) -> bool:
    return any("unsupported_room_type" in err for err in errors)


def _tools_ran(state: AgentState) -> bool:
    return any(
        msg.startswith("tool:catalog_search") for msg in state.get("messages") or []
    )


def _plan_is_fully_valid(state: AgentState, plan: DesignPlan) -> bool:
    if not plan.selected_products:
        return False
    if plan.budget.over_budget or not plan.fit.fits:
        return False
    brief = state.get("normalized_brief")
    if brief is None:
        return False
    report = OutputValidator().validate(
        brief=brief,
        selected=plan.selected_products,
        claimed_budget=plan.budget,
        claimed_fit=plan.fit,
        plan=plan,
    )
    return report.ok


def classify_agent_state(state: AgentState) -> UiResult:
    """Map graph state to a UI outcome. Dummy ₹0 DesignPlans are not success."""
    errors = list(state.get("validation_errors") or [])
    plan = state.get("final_plan")
    decision = _scope_rejected(state)

    if decision is not None or _is_unsupported_room_error(errors):
        details: list[str] = []
        if decision is not None:
            details.extend([decision.explanation, decision.redirect])
        for token in errors:
            message = customer_message(token)
            if message:
                details.append(message)
        if plan is not None:
            details.extend(customer_limitations(plan))
        return UiResult(
            kind=UiResultKind.NOT_SUPPORTED,
            headline="This request is not supported",
            details=_unique(details),
            plan=None,
        )

    if state.get("normalized_brief") is None or plan is None:
        details = []
        for token in errors:
            message = customer_message(token)
            if message:
                details.append(message)
        if not details:
            details = ["Please complete the Living Room brief and try again."]
        return UiResult(
            kind=UiResultKind.INPUT_INVALID,
            headline="The Living Room brief is incomplete or invalid",
            details=_unique(details),
            plan=None,
        )

    if not _tools_ran(state) or not _plan_is_fully_valid(state, plan):
        details = []
        if plan is not None:
            details.extend(customer_limitations(plan))
            summary_line = _customer_line(plan.summary)
            if summary_line:
                details.insert(0, summary_line)
        if not details:
            details = [
                "Nothing in the current catalogue fits this budget and room size together."
            ]
        return UiResult(
            kind=UiResultKind.NO_VALID_SOLUTION,
            headline="No valid design was found",
            details=_unique(details),
            plan=None,
        )

    return UiResult(
        kind=UiResultKind.SUCCESS,
        headline=plan.summary,
        details=[],
        plan=plan,
    )


def design_from_form(payload: dict, *, max_replans: int = 3) -> UiResult:
    from app.agent.graph import run_design

    return classify_agent_state(run_design(payload, max_replans=max_replans))


def customer_tradeoffs(plan: DesignPlan) -> list[str]:
    lines: list[str] = []
    for item in plan.tradeoffs:
        cleaned = _customer_line(item)
        if cleaned is None:
            continue
        if cleaned.startswith("The recommendation was revised"):
            if cleaned not in lines:
                lines.append(cleaned)
            continue
        lines.append(cleaned)
    return lines


def customer_limitations(plan: DesignPlan) -> list[str]:
    lines: list[str] = []
    for item in plan.limitations:
        cleaned = _customer_line(item)
        if cleaned:
            lines.append(cleaned)
    return lines
