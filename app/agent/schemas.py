"""Structured LLM schemas for product selection and final explanation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

SELECTION_SYSTEM_PROMPT = """You select Living Room furniture from a provided candidate catalogue list.

Rules:
- Choose ONLY item_id values that appear in the candidate list. Never invent SKUs.
- Prefer style fit and requirement match.
- Select at most one product per needed category unless the brief clearly needs more.
- Respect excluded item_ids and any remaining-budget guidance in the user message.
- why_selected must refer only to facts present in the candidate rows and brief.
- If no suitable candidate exists for a category, omit that category.
"""

EXPLANATION_SYSTEM_PROMPT = """You write TWO layers of explanation for a Living Room furniture plan:
1) customer-facing copy (short, plain language for the results page)
2) technical/audit copy (detailed, for evaluators — not shown to customers by default)

You receive ONLY factual inputs: selected products, budget result, layout/fit result,
must-have coverage, and known limitation strings. Ground every claim in those facts.
Do not invent products, prices, stock, dimensions, or fit outcomes.

Return structured fields:
- summary, style_rationale (customer-facing; 1-3 short sentences)
- fit_status_customer, fit_status_technical
- tradeoffs, tradeoffs_technical (lists; may be empty)
- limitations, limitations_technical (lists; keep customer list short)

=== Tone rules ===

Customer-facing (fit_status_customer, tradeoffs, limitations, summary, style_rationale):
- 1-2 plain sentences each item where possible.
- No formulas, no cm², no occupancy_ratio, no variable names, no algorithm mechanics.
- Never mention rotation, 90 degrees, rug/lamp/pendant exclusion rules, or occupancy math.
- Collapse multiple internal exclusion rules into at most one plain limitation sentence.

Technical (fit_status_technical, tradeoffs_technical, limitations_technical):
- Keep accurate audit detail derived from the provided budget and fit numbers.
- May include cm², occupancy_ratio, rotation assumptions, and accessory exclusion rules
  when those facts are present in the inputs / known limitations.

=== Few-shot examples (learn this split) ===

FIT:
- Technical (audit, not shown by default):
  "Selected floor-standing items fit the room rectangle and ceiling. Furniture footprint
  35245 cm² / room 172800 cm² (occupancy_ratio=0.2040). Circulation was not measured."
- Customer-facing (shown):
  "Your furniture uses about 20% of the floor, leaving plenty of open space. This checks
  overall room fit, not exact walking paths between pieces."

TRADE-OFFS:
- Technical (not shown):
  "The furniture occupancy calculation is 35,245 cm² out of 172,800 cm² room area, or
  20.4%, but this figure excludes the rug, table lamp, and pendant under the stated fit
  assumptions."
- Customer-facing (shown):
  "We left ₹106,000 of your budget unused in case you'd like to add extra pieces later."
- Only include a customer trade-off if a real choice was made (cheaper vs pricier item,
  or something skipped for budget/fit). Do not restate the product list or explain
  internal calculation exclusions in the customer trade-offs.

LIMITATIONS:
- Technical (not shown):
  "Floor-standing items may be rotated 90 degrees in the fit check. The rug is excluded
  from furniture occupancy because the check assumes rugs sit beneath furniture. The
  table lamp is treated as an accessory without an independent floor footprint. The
  pendant is treated as a ceiling fixture."
- Customer-facing (shown):
  "This checks that your furniture fits the room's overall size and height — it isn't a
  full floor plan or a guarantee of exact placement."

If no products were selected, say so honestly in both layers using the provided facts.
"""


class ProductChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_id: str = Field(..., min_length=1)
    role_in_room: str = Field(..., min_length=1)
    why_selected: str = Field(..., min_length=1)


class ProductSelectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selections: list[ProductChoice] = Field(default_factory=list)


class PlanExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(..., min_length=1)
    style_rationale: str = Field(..., min_length=1)
    fit_status_customer: str = Field(..., min_length=1)
    fit_status_technical: str = Field(..., min_length=1)
    tradeoffs: list[str] = Field(
        default_factory=list,
        description="Customer-facing trade-offs shown on the results page.",
    )
    tradeoffs_technical: list[str] = Field(
        default_factory=list,
        description="Audit trade-offs with formulas/assumptions; not shown by default.",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Customer-facing limitations shown on the results page.",
    )
    limitations_technical: list[str] = Field(
        default_factory=list,
        description="Audit limitations with fit mechanics; not shown by default.",
    )
