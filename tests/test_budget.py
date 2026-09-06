"""Tests for the deterministic budget calculator using the supplied SQLite catalogue."""

import pytest

from app.db.catalog_repository import CatalogRepository
from app.tools.budget import (
    BudgetCalculator,
    InvalidQuantityError,
    NullPriceError,
    UnknownCatalogItemError,
)

# FACT FROM DATABASE: SOF-001 price_inr = 58000, CFT-001 price_inr = 16000
SOFA_PRICE = 58000
COFFEE_TABLE_PRICE = 16000


@pytest.fixture(scope="module")
def calculator() -> BudgetCalculator:
    return BudgetCalculator(repository=CatalogRepository())


def test_under_budget(calculator: BudgetCalculator):
    result = calculator.calculate([("SOF-001", 1)], budget_inr=250000)
    assert result.subtotal == SOFA_PRICE
    assert result.budget == 250000
    assert result.remaining == 250000 - SOFA_PRICE
    assert result.over_budget is False


def test_exactly_on_budget(calculator: BudgetCalculator):
    result = calculator.calculate([("SOF-001", 1)], budget_inr=SOFA_PRICE)
    assert result.subtotal == SOFA_PRICE
    assert result.remaining == 0
    assert result.over_budget is False


def test_over_budget(calculator: BudgetCalculator):
    result = calculator.calculate([("SOF-001", 1)], budget_inr=20000)
    assert result.subtotal == SOFA_PRICE
    assert result.remaining == 20000 - SOFA_PRICE
    assert result.over_budget is True


def test_null_price_is_rejected(calculator: BudgetCalculator):
    with pytest.raises(NullPriceError) as exc:
        calculator.calculate([("CFT-004", 1)], budget_inr=200000)
    assert exc.value.item_id == "CFT-004"


def test_invalid_item_id_is_rejected(calculator: BudgetCalculator):
    with pytest.raises(UnknownCatalogItemError) as exc:
        calculator.calculate([("NOT-A-REAL-SKU", 1)], budget_inr=200000)
    assert exc.value.item_id == "NOT-A-REAL-SKU"


def test_multiple_quantities(calculator: BudgetCalculator):
    result = calculator.calculate(
        [("SOF-001", 2), ("CFT-001", 1)],
        budget_inr=200000,
    )
    expected = SOFA_PRICE * 2 + COFFEE_TABLE_PRICE
    assert result.subtotal == expected
    assert result.remaining == 200000 - expected
    assert result.over_budget is False


def test_invalid_quantity_is_rejected(calculator: BudgetCalculator):
    with pytest.raises(InvalidQuantityError):
        calculator.calculate([("SOF-001", 0)], budget_inr=200000)
