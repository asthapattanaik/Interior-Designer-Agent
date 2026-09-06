"""Independent after-agent validation. SQLite and layout tools are the source of truth."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.db.catalog_repository import CatalogRepository
from app.models.brief import RoomBrief
from app.models.output import BudgetResult, DesignPlan, FitResult, SelectedProduct
from app.tools.budget import BudgetCalculator, BudgetError
from app.tools.layout import LayoutChecker, LayoutError

DESIGN_PLAN_REQUIRED_FIELDS = (
    "summary",
    "style_rationale",
    "selected_products",
    "budget",
    "fit",
    "fit_status_customer",
    "fit_status_technical",
    "must_have_coverage",
    "tradeoffs",
    "tradeoffs_technical",
    "limitations",
    "limitations_technical",
)


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    item_id: str | None = None

    def as_token(self) -> str:
        item = self.item_id or "-"
        return f"{self.code}:{item}:{self.message}"


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    recomputed_budget: BudgetResult | None = None
    recomputed_fit: FitResult | None = None

    def tokens(self) -> list[str]:
        return [error.as_token() for error in self.errors]

    def item_ids(self) -> list[str]:
        return [error.item_id for error in self.errors if error.item_id]


class OutputValidator:
    """Re-checks a selection against the catalogue. Ignores LLM-provided totals."""

    def __init__(
        self,
        repository: CatalogRepository | None = None,
        budget: BudgetCalculator | None = None,
        layout: LayoutChecker | None = None,
    ) -> None:
        repo = repository or CatalogRepository()
        self._repository = repo
        self._budget = budget or BudgetCalculator(repository=repo)
        self._layout = layout or LayoutChecker(repository=repo)

    def validate(
        self,
        *,
        brief: RoomBrief,
        selected: Sequence[SelectedProduct],
        claimed_budget: BudgetResult | None = None,
        claimed_fit: FitResult | None = None,
        plan: DesignPlan | None = None,
    ) -> ValidationReport:
        errors: list[ValidationIssue] = []
        line_items: list[tuple[str, int]] = []

        for product in selected:
            item = self._repository.get_item(product.item_id)
            if item is None:
                errors.append(
                    ValidationIssue(
                        code="catalogue",
                        item_id=product.item_id,
                        message="product ID does not exist in SQLite",
                    )
                )
                continue
            if item.room_types and item.room_types.strip() and not item.is_living_room_applicable():
                errors.append(
                    ValidationIssue(
                        code="living_room",
                        item_id=product.item_id,
                        message="product is not tagged for Living Room",
                    )
                )
            if item.in_stock is not None and item.in_stock != 1:
                errors.append(
                    ValidationIssue(
                        code="stock",
                        item_id=product.item_id,
                        message="product is not in stock",
                    )
                )
            if not item.has_usable_price():
                errors.append(
                    ValidationIssue(
                        code="price",
                        item_id=product.item_id,
                        message="NULL price cannot be sold",
                    )
                )
            line_items.append((product.item_id, product.quantity))

        recomputed_budget: BudgetResult | None = None
        priced_lines = [
            (item_id, qty)
            for item_id, qty in line_items
            if not any(
                error.item_id == item_id and error.code in {"catalogue", "price"}
                for error in errors
            )
        ]
        try:
            recomputed_budget = self._budget.calculate(priced_lines, brief.budget_inr)
        except BudgetError as exc:
            errors.append(
                ValidationIssue(code="budget", message=str(exc), item_id=getattr(exc, "item_id", None))
            )
        else:
            if recomputed_budget.over_budget:
                errors.append(
                    ValidationIssue(
                        code="budget",
                        message=(
                            f"SQLite subtotal {recomputed_budget.subtotal} exceeds "
                            f"budget {recomputed_budget.budget}"
                        ),
                    )
                )
            if (
                claimed_budget is not None
                and claimed_budget.subtotal != recomputed_budget.subtotal
            ):
                errors.append(
                    ValidationIssue(
                        code="budget",
                        message=(
                            "claimed subtotal does not match SQLite recomputation "
                            f"{claimed_budget.subtotal} != {recomputed_budget.subtotal}"
                        ),
                    )
                )

        recomputed_fit: FitResult | None = None
        layout_ids = [
            (item_id, qty)
            for item_id, qty in line_items
            if not any(error.item_id == item_id and error.code == "catalogue" for error in errors)
        ]
        try:
            recomputed_fit = self._layout.check(
                length_cm=brief.length_cm,
                width_cm=brief.width_cm,
                ceiling_cm=brief.ceiling_cm,
                selections=layout_ids,
            )
        except LayoutError as exc:
            errors.append(
                ValidationIssue(
                    code="layout",
                    message=str(exc),
                    item_id=getattr(exc, "item_id", None),
                )
            )
        else:
            if not recomputed_fit.fits:
                for item_id in recomputed_fit.blocking_items:
                    errors.append(
                        ValidationIssue(
                            code="layout",
                            item_id=item_id,
                            message="does not pass deterministic fit check",
                        )
                    )
                if not recomputed_fit.blocking_items:
                    errors.append(
                        ValidationIssue(code="layout", message="deterministic fit check failed")
                    )
            if claimed_fit is not None and claimed_fit.fits and not recomputed_fit.fits:
                errors.append(
                    ValidationIssue(
                        code="layout",
                        message="claimed fit=true is contradicted by the layout tool",
                    )
                )

        if plan is not None:
            dumped = plan.model_dump()
            for field_name in DESIGN_PLAN_REQUIRED_FIELDS:
                if field_name not in dumped or dumped[field_name] in (None, ""):
                    errors.append(
                        ValidationIssue(
                            code="schema",
                            message=f"DesignPlan missing required field {field_name}",
                        )
                    )

        return ValidationReport(
            ok=len(errors) == 0,
            errors=errors,
            recomputed_budget=recomputed_budget,
            recomputed_fit=recomputed_fit,
        )

    def feasible_selection(
        self,
        *,
        brief: RoomBrief,
        selected: Sequence[SelectedProduct],
    ) -> tuple[list[SelectedProduct], ValidationReport]:
        """Drop invalid SKUs until the selection passes, or return empty.

        Used at finalize so an invalid plan is never emitted as success.
        """
        products = list(selected)
        report = self.validate(brief=brief, selected=products)
        if report.ok:
            return products, report

        drop = set(report.item_ids())
        if drop:
            products = [item for item in products if item.item_id not in drop]
            report = self.validate(brief=brief, selected=products)
            if report.ok:
                return products, report

        while products and report.recomputed_budget and report.recomputed_budget.over_budget:
            ranked = sorted(
                products,
                key=lambda item: (
                    item.catalog_item.price_inr if item.catalog_item and item.catalog_item.price_inr else 0
                ),
                reverse=True,
            )
            products = [item for item in products if item.item_id != ranked[0].item_id]
            report = self.validate(brief=brief, selected=products)
            if report.ok:
                return products, report

        while products and report.recomputed_fit and not report.recomputed_fit.fits:
            blocking = set(report.recomputed_fit.blocking_items)
            if blocking:
                next_products = [item for item in products if item.item_id not in blocking]
            else:
                next_products = products[:-1]
            if next_products == products:
                next_products = products[:-1]
            products = next_products
            report = self.validate(brief=brief, selected=products)
            if report.ok:
                return products, report

        empty: list[SelectedProduct] = []
        return empty, self.validate(brief=brief, selected=empty)
