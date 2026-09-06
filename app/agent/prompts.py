"""Structured scope/intent labels for the model-based guardrail."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ScopeLabel(str, Enum):
    LIVING_ROOM_DESIGN = "living_room_design"
    UNSUPPORTED_ROOM_TYPE = "unsupported_room_type"
    STRUCTURAL_CONSTRUCTION = "structural_construction"
    UNSUPPORTED_GUARANTEE = "unsupported_guarantee"
    AMBIGUOUS = "ambiguous"


class ScopeDecision(BaseModel):
    """Intent classification only. Never includes products, prices, or fit claims."""

    model_config = ConfigDict(extra="forbid")

    label: ScopeLabel
    proceed: bool
    explanation: str = Field(..., min_length=1)
    redirect: str = Field(..., min_length=1)


SCOPE_SYSTEM_PROMPT = """You classify interior-design requests for an MVP that ONLY designs Living Rooms using a furniture catalogue.

Return structured fields:
- label: one of living_room_design, unsupported_room_type, structural_construction, unsupported_guarantee, ambiguous
- proceed: true ONLY for living_room_design
- explanation: short customer-facing limitation or confirmation
- redirect: how to use the supported Living Room furniture designer

Rules:
- living_room_design: furniture/styling a living room, including normal budget caps, exact spend targets, and preferred delivery/move-in timing stated as constraints or preferences (not as contractual promises).
- unsupported_room_type: bedroom, kitchen, dining-only, kids room, study as the requested room, etc.
- structural_construction: knocking down walls, load-bearing questions, demolition, moving plumbing.
- unsupported_guarantee: ONLY when the customer demands a promise, certainty, contractual commitment, locked quote, or assurance about delivery/price — e.g. "guarantee", "promise", "assure me", "lock the final price", "firm quote that will not change".
- ambiguous: cannot tell if this is a Living Room furniture brief.

Critical distinction — constraints vs guarantees:
- ALLOW (living_room_design): "Spend exactly ₹36,000.", "I want to stay under ₹50,000.", "I need everything delivered before the 25th.", "Please furnish the whole room for one rupee.", "Cheapest acceptable seating only."
- BLOCK (unsupported_guarantee): "Guarantee that the final price is exactly ₹36,000.", "Guarantee everything will be delivered before the 25th.", "Guarantee I will stay under ₹50,000.", "Lock the final discounted price now."

Do NOT treat exact budgets, tight budgets, or delivery preferences alone as unsupported_guarantee.
Do NOT recommend products, prices, stock, dimensions, or whether furniture fits.
Do NOT decide if a wall is load-bearing.
"""
