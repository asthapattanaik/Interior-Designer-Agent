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
- living_room_design: furniture/styling a living room.
- unsupported_room_type: bedroom, kitchen, dining-only, kids room, study as the requested room, etc.
- structural_construction: knocking down walls, load-bearing questions, demolition, moving plumbing.
- unsupported_guarantee: promising delivery dates, locking discounts, guaranteeing tomorrow arrival or a final price.
- ambiguous: cannot tell if this is a Living Room furniture brief.

Do NOT recommend products, prices, stock, dimensions, or whether furniture fits.
Do NOT decide if a wall is load-bearing.
"""
