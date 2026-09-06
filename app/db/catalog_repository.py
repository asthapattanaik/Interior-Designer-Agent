"""Read-only SQLite access to interior_company_catalog.db."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from app.models.catalog import CatalogItem

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "interior_company_catalog.db"

_CATALOG_COLUMNS = (
    "item_id",
    "category",
    "name",
    "style_tags",
    "price_inr",
    "width_cm",
    "depth_cm",
    "height_cm",
    "color_finish",
    "in_stock",
    "lead_time_days",
    "room_types",
)
_SELECT_CATALOG = "SELECT " + ", ".join(_CATALOG_COLUMNS) + " FROM catalog"


def resolve_catalog_db_path(db_path: str | Path | None = None) -> Path:
    raw = (
        db_path
        if db_path is not None
        else os.environ.get("CATALOG_DB_PATH", str(DEFAULT_DB_PATH))
    )
    path = Path(raw)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    else:
        path = path.resolve()
    return path


def connect_readonly(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = resolve_catalog_db_path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"Catalogue database not found: {path}")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _csv_token_sql(column: str) -> str:
    """Match a comma-separated token without treating the column as free text."""
    return (
        "',' || REPLACE(REPLACE(COALESCE("
        f"{column}"
        ", ''), ', ', ','), ' ,', ',') || ',' LIKE '%,' || ? || ',%'"
    )


def row_to_catalog_item(row: sqlite3.Row) -> CatalogItem:
    payload: dict[str, Any] = {name: row[name] for name in _CATALOG_COLUMNS}
    return CatalogItem.model_validate(payload)


class CatalogRepository:
    """Parameterized, read-only catalogue queries. No LLM calls."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = resolve_catalog_db_path(db_path)

    def _connect(self) -> sqlite3.Connection:
        return connect_readonly(self.db_path)

    def get_item(self, item_id: str) -> CatalogItem | None:
        sql = _SELECT_CATALOG + " WHERE item_id = ?"
        with self._connect() as conn:
            row = conn.execute(sql, (item_id,)).fetchone()
        if row is None:
            return None
        return row_to_catalog_item(row)

    def search_items(
        self,
        *,
        category: str | None = None,
        style: str | None = None,
        max_price_inr: int | None = None,
        in_stock_only: bool | None = None,
        room_type: str | None = None,
    ) -> list[CatalogItem]:
        clauses: list[str] = []
        params: list[Any] = []

        if category is not None and category.strip():
            clauses.append("category = ?")
            params.append(category.strip())

        if style is not None and style.strip():
            clauses.append(_csv_token_sql("style_tags"))
            params.append(style.strip())

        if max_price_inr is not None:
            # NULL price cannot be compared to a maximum; exclude those rows.
            clauses.append("price_inr IS NOT NULL AND price_inr <= ?")
            params.append(max_price_inr)

        if in_stock_only is True:
            clauses.append("in_stock = 1")
        elif in_stock_only is False:
            clauses.append("in_stock = 0")

        if room_type is not None and room_type.strip():
            clauses.append(_csv_token_sql("room_types"))
            params.append(room_type.strip())

        sql = _SELECT_CATALOG
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY category, item_id"

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [row_to_catalog_item(row) for row in rows]

    def get_living_room_items(
        self,
        *,
        category: str | None = None,
        style: str | None = None,
        max_price_inr: int | None = None,
        in_stock_only: bool | None = None,
    ) -> list[CatalogItem]:
        return self.search_items(
            category=category,
            style=style,
            max_price_inr=max_price_inr,
            in_stock_only=in_stock_only,
            room_type="Living Room",
        )
