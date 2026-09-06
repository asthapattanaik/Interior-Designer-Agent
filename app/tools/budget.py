"""Deterministic budget calculator. Prices come only from SQLite."""

from __future__ import annotations

from collections.abc import Sequence

from app.db.catalog_repository import CatalogRepository
from app.models.output import BudgetResult


class BudgetError(ValueError):
    """Raised when a selection cannot be priced from the catalogue."""


class UnknownCatalogItemError(BudgetError):
    def __init__(self, item_id: str) -> None:
        self.item_id = item_id
        super().__init__(f"Unknown catalogue item_id: {item_id}")


class NullPriceError(BudgetError):
    def __init__(self, item_id: str) -> None:
        self.item_id = item_id
        super().__init__(
            f"Catalogue item {item_id} has a NULL price and cannot be included as a purchasable selection"
        )


class InvalidQuantityError(BudgetError):
    def __init__(self, item_id: str, quantity: int) -> None:
        self.item_id = item_id
        self.quantity = quantity
        super().__init__(f"Quantity for {item_id} must be a positive integer, got {quantity}")


class InvalidBudgetError(BudgetError):
    def __init__(self, budget_inr: int) -> None:
        self.budget_inr = budget_inr
        super().__init__(f"Budget must be a positive integer, got {budget_inr}")


class BudgetCalculator:
    def __init__(self, repository: CatalogRepository | None = None) -> None:
        self._repository = repository or CatalogRepository()

    def calculate(
        self,
        selections: Sequence[tuple[str, int]],
        budget_inr: int,
    ) -> BudgetResult:
        """Sum SQLite prices × quantities. Does not accept an LLM-provided total."""
        if budget_inr <= 0:
            raise InvalidBudgetError(budget_inr)

        subtotal = 0
        for item_id, quantity in selections:
            if quantity <= 0:
                raise InvalidQuantityError(item_id, quantity)
            item = self._repository.get_item(item_id)
            if item is None:
                raise UnknownCatalogItemError(item_id)
            if item.price_inr is None:
                raise NullPriceError(item_id)
            subtotal += item.price_inr * quantity

        remaining = budget_inr - subtotal
        return BudgetResult(
            subtotal=subtotal,
            budget=budget_inr,
            remaining=remaining,
            over_budget=subtotal > budget_inr,
        )
