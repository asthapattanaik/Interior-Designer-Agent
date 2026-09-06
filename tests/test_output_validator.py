"""Independent OutputValidator tests. Facts come from SQLite, not LLM claims."""

from app.db.catalog_repository import CatalogRepository
from app.models.brief import RoomBrief
from app.models.output import (
    BudgetResult,
    DesignPlan,
    FitResult,
    MustHaveCoverage,
    SelectedProduct,
)
from app.validation.output_validator import OutputValidator


def _brief(**overrides) -> RoomBrief:
    data = {
        "room_type": "Living Room",
        "length_cm": 480,
        "width_cm": 360,
        "ceiling_cm": 300,
        "budget_inr": 250000,
        "style_preference": "Scandinavian",
        "must_haves": "sofa",
        "constraints": "none",
        "customer_note": "test",
    }
    data.update(overrides)
    return RoomBrief(**data)


def _product(item_id: str) -> SelectedProduct:
    item = CatalogRepository().get_item(item_id)
    return SelectedProduct(
        item_id=item_id,
        quantity=1,
        role_in_room=item.category if item else "unknown",
        why_selected="unit test selection",
        catalog_item=item,
    )


def _plan(**overrides) -> DesignPlan:
    data = {
        "summary": "Valid plan",
        "style_rationale": "Catalogue SKUs only",
        "selected_products": [_product("SOF-001")],
        "budget": BudgetResult(
            subtotal=58000, budget=250000, remaining=192000, over_budget=False
        ),
        "fit": FitResult(fits=True, explanation="Fits the room rectangle."),
        "fit_status_customer": "These pieces fit the room size and height.",
        "fit_status_technical": "Fits the room rectangle; occupancy derived from cm².",
        "must_have_coverage": MustHaveCoverage(
            requested=["sofa"], covered=["sofa"], missing=[]
        ),
        "tradeoffs": [],
        "tradeoffs_technical": [],
        "limitations": ["test"],
        "limitations_technical": ["test technical"],
    }
    data.update(overrides)
    return DesignPlan(**data)


def test_unknown_id_fails_catalogue_check():
    report = OutputValidator().validate(brief=_brief(), selected=[_product("NO-SUCH-SKU")])
    assert report.ok is False
    assert any(err.code == "catalogue" and err.item_id == "NO-SUCH-SKU" for err in report.errors)
    assert report.tokens()


def test_dining_sku_fails_living_room_applicability():
    report = OutputValidator().validate(brief=_brief(), selected=[_product("DNT-001")])
    assert report.ok is False
    assert any(err.code == "living_room" and err.item_id == "DNT-001" for err in report.errors)


def test_out_of_stock_fails_where_stock_exists():
    report = OutputValidator().validate(brief=_brief(), selected=[_product("SOF-006")])
    assert report.ok is False
    assert any(err.code == "stock" and err.item_id == "SOF-006" for err in report.errors)


def test_null_price_fails():
    report = OutputValidator().validate(brief=_brief(), selected=[_product("CFT-004")])
    assert report.ok is False
    assert any(err.code == "price" and err.item_id == "CFT-004" for err in report.errors)


def test_budget_recomputed_from_sqlite_not_claimed_total():
    claimed = BudgetResult(subtotal=1, budget=250000, remaining=249999, over_budget=False)
    report = OutputValidator().validate(
        brief=_brief(),
        selected=[_product("SOF-001")],
        claimed_budget=claimed,
    )
    assert report.ok is False
    assert report.recomputed_budget is not None
    assert report.recomputed_budget.subtotal == 58000
    assert any(err.code == "budget" for err in report.errors)


def test_over_budget_fails():
    report = OutputValidator().validate(
        brief=_brief(budget_inr=20000),
        selected=[_product("SOF-001")],
    )
    assert report.ok is False
    assert report.recomputed_budget is not None
    assert report.recomputed_budget.over_budget is True
    assert any(err.code == "budget" for err in report.errors)


def test_layout_failure_where_supported():
    report = OutputValidator().validate(
        brief=_brief(length_cm=240, width_cm=210, ceiling_cm=270),
        selected=[_product("SOF-004")],
    )
    assert report.ok is False
    assert report.recomputed_fit is not None
    assert report.recomputed_fit.fits is False
    assert any(err.code == "layout" and err.item_id == "SOF-004" for err in report.errors)


def test_schema_missing_required_field():
    plan = DesignPlan.model_construct(
        summary="",
        style_rationale="x",
        selected_products=[],
        budget=None,
        fit=None,
        must_have_coverage=None,
        tradeoffs=[],
        limitations=[],
    )
    report = OutputValidator().validate(brief=_brief(), selected=[], plan=plan)
    assert report.ok is False
    assert any(err.code == "schema" for err in report.errors)


def test_valid_living_room_selection_passes():
    selected = [_product("SOF-001")]
    plan = _plan()
    report = OutputValidator().validate(
        brief=_brief(),
        selected=selected,
        claimed_budget=plan.budget,
        claimed_fit=FitResult(fits=True, explanation="placeholder"),
        plan=plan,
    )
    assert report.ok is True
    assert report.recomputed_budget.subtotal == 58000
    assert report.recomputed_fit.fits is True
