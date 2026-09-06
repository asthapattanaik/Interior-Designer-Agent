"""Selected products and final DesignPlan output contract."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.catalog import CatalogItem


class SelectedProduct(BaseModel):
    """A plan line item. Factual catalogue fields come from CatalogItem, not guesses."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    item_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    role_in_room: str = Field(..., min_length=1)
    why_selected: str = Field(..., min_length=1)
    catalog_item: CatalogItem | None = None

    @model_validator(mode="after")
    def catalog_item_id_must_match(self) -> SelectedProduct:
        if self.catalog_item is not None and self.catalog_item.item_id != self.item_id:
            raise ValueError("catalog_item.item_id must match item_id")
        return self


class BudgetResult(BaseModel):
    """Deterministic budget arithmetic result. Totals must come from tools, not the LLM."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subtotal: int = Field(..., ge=0)
    budget: int = Field(..., gt=0)
    remaining: int
    over_budget: bool

    @model_validator(mode="after")
    def remaining_must_match_arithmetic(self) -> BudgetResult:
        expected_remaining = self.budget - self.subtotal
        if self.remaining != expected_remaining:
            raise ValueError("remaining must equal budget - subtotal")
        if self.over_budget != (self.subtotal > self.budget):
            raise ValueError("over_budget must be true only when subtotal > budget")
        return self


class FitResult(BaseModel):
    """Spatial check result. Thresholds are MVP assumptions on the checker, not DB facts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    fits: bool
    explanation: str = Field(..., min_length=1)
    warnings: list[str] = Field(default_factory=list)
    blocking_items: list[str] = Field(default_factory=list)
    occupancy_ratio: float | None = Field(default=None, ge=0)
    room_area_cm2: int | None = Field(default=None, ge=0)
    furniture_footprint_cm2: int | None = Field(default=None, ge=0)


class MustHaveCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    requested: list[str] = Field(default_factory=list)
    covered: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def coverage_sets_must_be_consistent(self) -> MustHaveCoverage:
        requested = set(self.requested)
        covered = set(self.covered)
        missing = set(self.missing)
        if covered - requested:
            raise ValueError("covered items must be a subset of requested")
        if missing - requested:
            raise ValueError("missing items must be a subset of requested")
        if covered & missing:
            raise ValueError("an item cannot be both covered and missing")
        return self


class DesignPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    summary: str = Field(..., min_length=1)
    style_rationale: str = Field(..., min_length=1)
    selected_products: list[SelectedProduct]
    budget: BudgetResult
    fit: FitResult
    fit_status_customer: str = Field(
        ...,
        min_length=1,
        description="Short customer-facing fit status shown on the results page.",
    )
    fit_status_technical: str = Field(
        ...,
        min_length=1,
        description="Detailed fit/audit text for evaluators; not shown by default.",
    )
    must_have_coverage: MustHaveCoverage
    tradeoffs: list[str] = Field(
        default_factory=list,
        description="Customer-facing trade-offs shown on the results page.",
    )
    tradeoffs_technical: list[str] = Field(
        default_factory=list,
        description="Technical/audit trade-offs; not shown by default.",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Customer-facing limitations shown on the results page.",
    )
    limitations_technical: list[str] = Field(
        default_factory=list,
        description="Technical/audit limitations; not shown by default.",
    )
