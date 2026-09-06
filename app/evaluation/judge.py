"""LLM-as-judge for qualitative Living Room plan quality.

Deterministic catalogue, stock, budget, fit, and guardrail checks remain
authoritative. This module must not flip a deterministic failure to a pass.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.catalog_repository import CatalogRepository
from app.models.output import DesignPlan
from app.ui.service import classify_agent_state

JUDGE_DIMENSIONS = (
    "relevance",
    "style_coherence",
    "explanation_quality",
    "tradeoff_quality",
    "customer_usefulness",
)

JUDGE_SYSTEM_PROMPT = """You are a strict interior-design quality rater for a Living Room furniture catalogue MVP.

Score each dimension from 1 (poor) to 5 (excellent):
- relevance: does the response address the customer's brief (design or an honest refusal)?
- style_coherence: do selected catalogue pieces make sense together for the stated style? Score 3 if no products were selected because constraints blocked a design.
- explanation_quality: are reasons and limitations understandable to a customer (no jargon about internals)?
- tradeoff_quality: were budget, size, stock, and must-haves prioritised sensibly? For refusals, is the limitation the right one?
- customer_usefulness: would a customer know what to do next?

You are given DETERMINISTIC FACTS from SQLite and layout/budget tools. Those facts are authoritative.
You MUST set honours_deterministic_facts=true only if your rationale does not contradict them.
Never claim a product exists, is in stock, has a price, or fits the room if the facts say otherwise.
Never treat a blocked structural, bedroom, or guarantee request as a successful furniture design.
Never invent SKUs, prices, or dimensions.

Return only the structured fields.
"""


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevance: int = Field(..., ge=1, le=5)
    style_coherence: int = Field(..., ge=1, le=5)
    explanation_quality: int = Field(..., ge=1, le=5)
    tradeoff_quality: int = Field(..., ge=1, le=5)
    customer_usefulness: int = Field(..., ge=1, le=5)
    rationale: str = Field(..., min_length=1)
    honours_deterministic_facts: bool

    @field_validator(
        "relevance",
        "style_coherence",
        "explanation_quality",
        "tradeoff_quality",
        "customer_usefulness",
    )
    @classmethod
    def score_is_int(cls, value: int) -> int:
        return int(value)

    def mean(self) -> float:
        return (
            self.relevance
            + self.style_coherence
            + self.explanation_quality
            + self.tradeoff_quality
            + self.customer_usefulness
        ) / 5.0


class SupportsStructuredJudge(Protocol):
    def invoke(self, input: dict | list | str) -> JudgeVerdict | dict: ...


def _catalogue_facts(plan: DesignPlan | None, repository: CatalogRepository) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    if plan is None:
        return facts
    for product in plan.selected_products:
        item = repository.get_item(product.item_id)
        if item is None:
            facts.append({"item_id": product.item_id, "exists": False})
            continue
        facts.append(
            {
                "item_id": item.item_id,
                "name": item.name,
                "category": item.category,
                "style_tags": item.style_tags,
                "price_inr": item.price_inr,
                "width_cm": item.width_cm,
                "depth_cm": item.depth_cm,
                "height_cm": item.height_cm,
                "in_stock": item.in_stock,
                "room_types": item.room_types,
            }
        )
    return facts


def customer_facing_response(state: dict[str, Any]) -> str:
    """Assemble only genuine customer-facing copy for the judge.

    Uses fit_status_customer / customer tradeoffs / customer limitations — never
    plan.fit.explanation or other technical audit fields.
    """
    result = classify_agent_state(state)
    lines = [result.headline, *result.details]
    # Prefer the agent DesignPlan even when the UI maps the outcome to a non-SUCCESS
    # kind (judge still needs the customer-facing explanation text).
    plan: DesignPlan | None = state.get("final_plan")
    if plan is not None:
        lines.append(plan.summary)
        lines.append(plan.style_rationale)
        for product in plan.selected_products:
            name = product.catalog_item.name if product.catalog_item else product.item_id
            price = (
                product.catalog_item.price_inr if product.catalog_item else None
            )
            lines.append(
                f"{product.item_id} {name} qty={product.quantity} "
                f"role={product.role_in_room} price={price}: {product.why_selected}"
            )
        lines.append(
            f"budget subtotal={plan.budget.subtotal} remaining={plan.budget.remaining} "
            f"over={plan.budget.over_budget}"
        )
        lines.append(f"fit={plan.fit.fits}: {plan.fit_status_customer}")
        covered = ", ".join(plan.must_have_coverage.covered) or "none"
        missing = ", ".join(plan.must_have_coverage.missing) or "none"
        lines.append(f"must-haves covered: {covered}")
        lines.append(f"must-haves still open: {missing}")
        if plan.tradeoffs:
            lines.append("trade-offs:")
            lines.extend(plan.tradeoffs)
        if plan.limitations:
            lines.append("limitations:")
            lines.extend(plan.limitations)
    return "\n".join(line for line in lines if line)


def technical_audit_context(plan: DesignPlan | None) -> str:
    """Optional technical/audit text for judge context — not customer-facing."""
    if plan is None:
        return ""
    lines: list[str] = []
    if plan.fit_status_technical:
        lines.append(f"fit_technical: {plan.fit_status_technical}")
    if plan.fit.explanation:
        lines.append(f"layout_tool_explanation: {plan.fit.explanation}")
    if plan.tradeoffs_technical:
        lines.append("tradeoffs_technical:")
        lines.extend(plan.tradeoffs_technical)
    if plan.limitations_technical:
        lines.append("limitations_technical:")
        lines.extend(plan.limitations_technical)
    return "\n".join(lines)


def build_judge_prompt(
    *,
    case: dict[str, Any],
    scored: dict[str, Any],
    state: dict[str, Any],
    repository: CatalogRepository,
) -> str:
    plan: DesignPlan | None = state.get("final_plan")
    facts = _catalogue_facts(plan, repository)
    technical = technical_audit_context(plan)
    technical_block = (
        f"\nTECHNICAL / AUDIT DETAIL (not customer-facing; for context only)\n{technical}\n"
        if technical
        else ""
    )
    return (
        "ORIGINAL BRIEF\n"
        f"{case.get('input')}\n\n"
        "DETERMINISTIC VALIDATION (authoritative; do not contradict)\n"
        f"case_passed={scored.get('passed')}\n"
        f"failures={scored.get('failures')}\n"
        f"checks={scored.get('checks')}\n"
        f"selected_ids={scored.get('selected_ids')}\n"
        f"guardrail_label={scored.get('guardrail_label')}\n\n"
        "FACTUAL CATALOGUE ROWS FOR SELECTED IDS\n"
        f"{facts}\n\n"
        "CUSTOMER-FACING RESPONSE\n"
        f"{customer_facing_response(state)}\n"
        f"{technical_block}"
    )


def apply_authoritative_facts(verdict: JudgeVerdict, deterministic_passed: bool) -> dict[str, Any]:
    """Keep deterministic failures as failures. Attach judge scores only."""
    payload = verdict.model_dump()
    payload["mean"] = verdict.mean()
    payload["deterministic_passed"] = deterministic_passed
    payload["quality_does_not_override_facts"] = True
    if not deterministic_passed:
        payload["note"] = (
            "Deterministic checks failed or the request was blocked; "
            "quality scores describe the response only and do not mark the case as factually correct."
        )
    return payload


def judge_case(
    *,
    case: dict[str, Any],
    scored: dict[str, Any],
    state: dict[str, Any],
    repository: CatalogRepository,
    structured_model: SupportsStructuredJudge,
) -> dict[str, Any]:
    prompt = build_judge_prompt(
        case=case, scored=scored, state=state, repository=repository
    )
    raw = structured_model.invoke(
        [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    verdict = raw if isinstance(raw, JudgeVerdict) else JudgeVerdict.model_validate(raw)
    return apply_authoritative_facts(verdict, bool(scored.get("passed")))


def aggregate_judge_scores(results: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row.get("judge") for row in results if isinstance(row.get("judge"), dict) and "relevance" in row["judge"]]
    if not scored:
        return {"applicable": 0, "mean": None, "by_dimension": {}}
    by_dim: dict[str, float] = {}
    for dim in JUDGE_DIMENSIONS:
        by_dim[dim] = sum(item[dim] for item in scored) / len(scored)
    overall = sum(by_dim.values()) / len(by_dim)
    low = [
        {"id": row["id"], "mean": row["judge"]["mean"], "rationale": row["judge"].get("rationale")}
        for row in results
        if isinstance(row.get("judge"), dict)
        and row["judge"].get("mean") is not None
        and row["judge"]["mean"] < 3.0
    ]
    fact_breaks = [
        row["id"]
        for row in results
        if isinstance(row.get("judge"), dict)
        and row["judge"].get("honours_deterministic_facts") is False
    ]
    return {
        "applicable": len(scored),
        "mean": overall,
        "by_dimension": by_dim,
        "low_scores": low,
        "contradicted_facts": fact_breaks,
    }


def make_openai_judge() -> SupportsStructuredJudge:
    from langchain_openai import ChatOpenAI

    from app.config import load_settings

    settings = load_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
    return llm.with_structured_output(JudgeVerdict)
