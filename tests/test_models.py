"""Unit tests for STEP 3 Pydantic domain models."""

import pytest
from pydantic import ValidationError

from app.models import (
    BudgetResult,
    CatalogItem,
    DesignPlan,
    FitResult,
    MustHaveCoverage,
    RoomBrief,
    SelectedProduct,
)


def _valid_brief_kwargs(**overrides):
    data = {
        "room_type": "Living Room",
        "length_cm": 480,
        "width_cm": 360,
        "ceiling_cm": 300,
        "budget_inr": 250000,
        "style_preference": "Scandinavian",
        "must_haves": "3-seater sofa, coffee table, TV unit, rug, lighting",
        "constraints": "South-facing, lots of natural light",
        "customer_note": "We want a calm, bright living room.",
    }
    data.update(overrides)
    return data


def _catalog_sofa() -> CatalogItem:
    return CatalogItem(
        item_id="SOF-001",
        category="Sofa",
        name="Nordby 3-Seater Fabric Sofa",
        style_tags="Scandinavian,Minimalist",
        price_inr=58000,
        width_cm=210,
        depth_cm=90,
        height_cm=82,
        color_finish="Oatmeal grey",
        in_stock=1,
        lead_time_days=21,
        room_types="Living Room",
    )


def _selected_sofa() -> SelectedProduct:
    item = _catalog_sofa()
    return SelectedProduct(
        item_id=item.item_id,
        quantity=1,
        role_in_room="Primary seating",
        why_selected="Matches Scandinavian preference and Living Room tagging",
        catalog_item=item,
    )


def _valid_plan_kwargs(**overrides):
    data = {
        "summary": "A calm Scandinavian living room using catalogue seating and tables.",
        "style_rationale": "Light oak and oatmeal finishes follow the brief.",
        "selected_products": [_selected_sofa()],
        "budget": BudgetResult(
            subtotal=58000,
            budget=250000,
            remaining=192000,
            over_budget=False,
        ),
        "fit": FitResult(
            fits=True,
            explanation="Selected sofa dimensions are within the room rectangle.",
        ),
        "must_have_coverage": MustHaveCoverage(
            requested=["3-seater sofa"],
            covered=["3-seater sofa"],
            missing=[],
        ),
        "tradeoffs": ["Rug not included in this fixture plan"],
        "tradeoffs_technical": [
            "Rug omitted from this fixture plan; occupancy math unchanged for seating."
        ],
        "limitations": [
            "This checks overall room size and height — not a full floor plan."
        ],
        "limitations_technical": [
            "Layout is a box-fit check with optional 90-degree rotation; occupancy_ratio uses cm²."
        ],
        "fit_status_customer": (
            "Your sofa fits the room size, leaving open floor space for walking."
        ),
        "fit_status_technical": (
            "Selected sofa dimensions are within the room rectangle "
            "(occupancy_ratio derived from cm² footprints)."
        ),
    }
    data.update(overrides)
    return data


def test_valid_room_brief():
    brief = RoomBrief(**_valid_brief_kwargs())
    assert brief.room_type == "Living Room"
    assert brief.budget_inr == 250000
    assert brief.length_cm == 480


def test_invalid_dimensions():
    with pytest.raises(ValidationError):
        RoomBrief(**_valid_brief_kwargs(length_cm=0))
    with pytest.raises(ValidationError):
        RoomBrief(**_valid_brief_kwargs(width_cm=-10))
    with pytest.raises(ValidationError):
        RoomBrief(**_valid_brief_kwargs(ceiling_cm=0))


def test_invalid_budget():
    with pytest.raises(ValidationError):
        RoomBrief(**_valid_brief_kwargs(budget_inr=0))
    with pytest.raises(ValidationError):
        RoomBrief(**_valid_brief_kwargs(budget_inr=-1))


def test_invalid_room_type():
    with pytest.raises(ValidationError):
        RoomBrief(**_valid_brief_kwargs(room_type="Bedroom"))
    with pytest.raises(ValidationError):
        RoomBrief(**_valid_brief_kwargs(room_type="living room"))


def test_room_brief_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        RoomBrief(**_valid_brief_kwargs(occupancy_threshold=0.55))


def test_catalog_item_allows_null_price():
    item = CatalogItem(
        item_id="CFT-004",
        category="Coffee Table",
        name="Live-Edge Slab Table",
        price_inr=None,
        width_cm=130,
        depth_cm=70,
        height_cm=40,
        in_stock=1,
        lead_time_days=35,
        room_types="Living Room",
    )
    assert item.has_usable_price() is False
    assert item.is_living_room_applicable() is True


def test_selected_product_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        SelectedProduct(
            item_id="SOF-001",
            quantity=0,
            role_in_room="Seating",
            why_selected="Requested sofa",
        )


def test_valid_design_plan():
    plan = DesignPlan(**_valid_plan_kwargs())
    assert len(plan.selected_products) == 1
    assert plan.budget.over_budget is False
    assert plan.fit.fits is True
    assert plan.selected_products[0].item_id == "SOF-001"


def test_invalid_design_plan():
    with pytest.raises(ValidationError):
        DesignPlan(**_valid_plan_kwargs(summary=""))
    with pytest.raises(ValidationError):
        DesignPlan(
            **_valid_plan_kwargs(
                budget=BudgetResult(
                    subtotal=300000,
                    budget=250000,
                    remaining=50000,
                    over_budget=False,
                )
            )
        )
    with pytest.raises(ValidationError):
        DesignPlan(**_valid_plan_kwargs(extra_field="nope"))
