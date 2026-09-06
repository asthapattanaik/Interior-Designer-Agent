"""Customer brief contract used by UI input, agent state, and evaluation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LIVING_ROOM = "Living Room"


class RoomBrief(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    room_type: Literal["Living Room"]
    length_cm: int = Field(..., gt=0)
    width_cm: int = Field(..., gt=0)
    ceiling_cm: int = Field(..., gt=0)
    budget_inr: int = Field(..., gt=0)
    style_preference: str = Field(..., min_length=1)
    must_haves: str = Field(..., min_length=1)
    constraints: str
    customer_note: str
