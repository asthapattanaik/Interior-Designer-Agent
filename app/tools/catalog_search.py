"""Deterministic catalogue search. Returns only real SQLite rows."""

from __future__ import annotations

from app.db.catalog_repository import CatalogRepository
from app.models.catalog import CatalogItem

LIVING_ROOM = "Living Room"


class CatalogSearchTool:
    """Living Room-scoped search over the supplied catalogue.

    Does not invent products, prices, stock, or dimensions.
    """

    def __init__(self, repository: CatalogRepository | None = None) -> None:
        self._repository = repository or CatalogRepository()

    def get_item(self, item_id: str) -> CatalogItem | None:
        item = self._repository.get_item(item_id)
        if item is None or not item.is_living_room_applicable():
            return None
        return item

    def search(
        self,
        *,
        category: str | None = None,
        style: str | None = None,
        max_price_inr: int | None = None,
        in_stock_only: bool | None = None,
    ) -> list[CatalogItem]:
        return self._repository.get_living_room_items(
            category=category,
            style=style,
            max_price_inr=max_price_inr,
            in_stock_only=in_stock_only,
        )
