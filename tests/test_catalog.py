"""Tests for the read-only catalogue repository and search tool."""

from __future__ import annotations

import sqlite3

import pytest

from app.db.catalog_repository import CatalogRepository, connect_readonly
from app.tools.catalog_search import CatalogSearchTool

NULL_PRICE_LIVING_ROOM_IDS = {"CFT-004", "RUG-003", "ART-003"}


@pytest.fixture(scope="module")
def repo() -> CatalogRepository:
    return CatalogRepository()


@pytest.fixture(scope="module")
def tool(repo: CatalogRepository) -> CatalogSearchTool:
    return CatalogSearchTool(repository=repo)


def test_get_item_exact_product(repo: CatalogRepository):
    item = repo.get_item("SOF-001")
    assert item is not None
    assert item.item_id == "SOF-001"
    assert item.name == "Nordby 3-Seater Fabric Sofa"
    assert item.category == "Sofa"
    assert item.price_inr == 58000
    assert item.in_stock == 1
    assert item.is_living_room_applicable() is True


def test_get_item_missing_returns_none(repo: CatalogRepository):
    assert repo.get_item("NOT-A-REAL-SKU") is None


def test_null_price_is_preserved(repo: CatalogRepository):
    item = repo.get_item("CFT-004")
    assert item is not None
    assert item.price_inr is None
    assert item.has_usable_price() is False
    assert item.in_stock == 1


def test_category_filter(repo: CatalogRepository):
    items = repo.get_living_room_items(category="Sofa")
    assert items
    assert {item.category for item in items} == {"Sofa"}
    assert {item.item_id for item in items} >= {"SOF-001", "SOF-002"}
    assert all(item.is_living_room_applicable() for item in items)


def test_style_filter(repo: CatalogRepository):
    items = repo.get_living_room_items(style="Scandinavian")
    assert items
    assert all("Scandinavian" in item.style_tag_list() for item in items)
    assert any(item.item_id == "SOF-001" for item in items)
    assert all(item.is_living_room_applicable() for item in items)


def test_stock_filter(repo: CatalogRepository):
    in_stock = repo.get_living_room_items(in_stock_only=True)
    out_of_stock = repo.get_living_room_items(in_stock_only=False)
    assert in_stock
    assert all(item.in_stock == 1 for item in in_stock)
    assert {item.item_id for item in out_of_stock} == {"CON-002", "SOF-006"}
    assert all(item.in_stock == 0 for item in out_of_stock)


def test_max_price_excludes_null_and_over_budget(repo: CatalogRepository):
    items = repo.get_living_room_items(max_price_inr=10000)
    assert items
    assert all(item.price_inr is not None and item.price_inr <= 10000 for item in items)
    ids = {item.item_id for item in items}
    assert ids.isdisjoint(NULL_PRICE_LIVING_ROOM_IDS)


def test_living_room_scope_excludes_dining_only(repo: CatalogRepository):
    dining = repo.get_item("DNT-001")
    assert dining is not None
    assert dining.is_living_room_applicable() is False
    lr_ids = {item.item_id for item in repo.get_living_room_items()}
    assert "DNT-001" not in lr_ids
    assert len(lr_ids) == 44


def test_empty_result(repo: CatalogRepository):
    assert repo.get_living_room_items(category="Spaceship") == []
    assert repo.search_items(category="Sofa", style="NoSuchStyle") == []


def test_tool_exact_retrieval_living_room_only(tool: CatalogSearchTool):
    sofa = tool.get_item("SOF-001")
    assert sofa is not None
    assert sofa.item_id == "SOF-001"
    assert tool.get_item("DNT-001") is None
    assert tool.get_item("MISSING") is None


def test_tool_search_filters(tool: CatalogSearchTool):
    sofas = tool.search(category="Sofa")
    assert all(item.category == "Sofa" for item in sofas)
    scandi = tool.search(style="Mid-Century")
    assert scandi
    assert all("Mid-Century" in item.style_tag_list() for item in scandi)
    oos = tool.search(in_stock_only=False)
    assert {item.item_id for item in oos} == {"CON-002", "SOF-006"}
    empty = tool.search(category="Dining Table")
    assert empty == []


def test_tool_null_price_included_without_max_price(tool: CatalogSearchTool):
    coffee = tool.search(category="Coffee Table")
    by_id = {item.item_id: item for item in coffee}
    assert "CFT-004" in by_id
    assert by_id["CFT-004"].price_inr is None
    priced_only = tool.search(category="Coffee Table", max_price_inr=200000)
    assert "CFT-004" not in {item.item_id for item in priced_only}


def test_repository_is_read_only():
    conn = connect_readonly()
    with pytest.raises(sqlite3.OperationalError) as exc:
        conn.execute("UPDATE catalog SET name = name WHERE item_id = 'SOF-001'")
        conn.commit()
    conn.close()
    assert "readonly" in str(exc.value).lower()
