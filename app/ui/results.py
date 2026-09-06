"""Customer-facing UI result types. No agent imports, so Streamlit can load this first."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.models.output import DesignPlan


class UiResultKind(str, Enum):
    """Customer-facing outcome. Not the same as a dummy DesignPlan from finalize."""

    SUCCESS = "success"
    INPUT_INVALID = "input_invalid"
    NOT_SUPPORTED = "not_supported"
    NO_VALID_SOLUTION = "no_valid_solution"


@dataclass(frozen=True)
class UiResult:
    kind: UiResultKind
    headline: str
    details: list[str]
    plan: DesignPlan | None = None

    @property
    def notices(self) -> list[str]:
        return list(self.details)

    @property
    def show_full_plan(self) -> bool:
        return self.kind is UiResultKind.SUCCESS and self.plan is not None
