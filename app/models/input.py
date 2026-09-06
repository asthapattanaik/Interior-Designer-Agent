"""Loose customer input before unit and budget normalization."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CustomerInput(BaseModel):
    """Raw form/API payload. Missing critical fields stay missing; we do not guess."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    room_type: str | None = None
    length: Any = None
    width: Any = None
    ceiling: Any = None
    length_cm: Any = None
    width_cm: Any = None
    ceiling_cm: Any = None
    unit: str | None = None
    budget: Any = None
    budget_inr: Any = None
    style_preference: str | None = None
    must_haves: str | None = None
    constraints: str | None = ""
    customer_note: str | None = ""
