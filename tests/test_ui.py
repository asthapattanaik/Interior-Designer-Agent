"""Customer UI helpers. Streamlit widgets are not required for these checks."""

from app.models.output import DesignPlan
from app.ui.service import (
    UiResultKind,
    build_form_payload,
    customer_limitations,
    customer_message,
    customer_tradeoffs,
    design_from_form,
    format_inr,
)

_FULL_RESULT_HEADERS = {
    "Recommended products",
    "Budget",
    "Fit",
    "Must-have coverage",
    "Trade-offs",
}


def _normal_payload(**overrides) -> dict:
    data = build_form_payload(
        length=480,
        width=360,
        ceiling=300,
        unit="cm",
        budget=250000,
        style_preference="Scandinavian",
        must_haves="3-seater sofa, coffee table, TV unit, rug, lighting",
        constraints="South-facing, lots of natural light",
        customer_note="Calm bright living room",
    )
    data.update(overrides)
    return data


def test_build_form_payload_is_living_room_only():
    payload = build_form_payload(
        length=480,
        width=360,
        ceiling=300,
        unit="cm",
        budget=250000,
        style_preference="Scandinavian",
        must_haves="sofa, coffee table",
        constraints="south light",
        customer_note="calm room",
    )
    assert payload["room_type"] == "Living Room"
    assert payload["unit"] == "cm"
    assert "messages" not in payload


def test_customer_messages_hide_internal_tokens():
    assert customer_message("tool:catalog_search:12") is None
    assert customer_message("replan:1:budget:over") is None
    assert customer_message("missing:budget") == "Please enter a budget in Indian rupees."
    assert "Living Room" in (customer_message("unsupported_room_type:Bedroom") or "")


def test_ui_result_kind_success_has_validated_plan():
    result = design_from_form(_normal_payload())
    assert result.kind is UiResultKind.SUCCESS
    assert result.show_full_plan is True
    plan = result.plan
    assert isinstance(plan, DesignPlan)
    assert plan.selected_products
    assert plan.budget.over_budget is False
    assert plan.budget.subtotal > 0
    blob = " ".join(
        [plan.summary, *customer_tradeoffs(plan), *customer_limitations(plan), *result.details]
    )
    assert "tool:" not in blob
    assert "replan:" not in blob


def test_ui_result_kind_guardrail_rejection_has_no_plan():
    bedroom = design_from_form(_normal_payload(room_type="Bedroom", must_haves="Queen bed"))
    structural = design_from_form(
        _normal_payload(
            constraints="Want to remove the wall between kitchen and living room",
            customer_note="Should I knock down the kitchen wall? Is it load-bearing?",
        )
    )
    guarantee = design_from_form(
        _normal_payload(
            customer_note="Guarantee everything is delivered before the 25th and lock the final price.",
        )
    )
    kinds = {bedroom.kind, structural.kind, guarantee.kind}
    assert kinds == {UiResultKind.NOT_SUPPORTED}
    for result in (bedroom, structural, guarantee):
        assert result.plan is None
        assert result.show_full_plan is False
        assert result.kind is not UiResultKind.SUCCESS
        blob = " ".join([result.headline, *result.details]).lower()
        assert "₹0" not in blob
        assert "not supported" in result.headline.lower() or "cannot" in blob or "living room" in blob


def test_ui_result_kind_no_valid_solution_has_no_plan():
    result = design_from_form(
        _normal_payload(
            budget=1,
            customer_note="Please furnish the whole room for one rupee.",
        )
    )
    assert result.kind is UiResultKind.NO_VALID_SOLUTION
    assert result.plan is None
    assert result.show_full_plan is False
    blob = " ".join([result.headline, *result.details]).lower()
    assert "no valid" in blob or "could not" in blob
    assert "₹0" not in " ".join(result.details)


def test_ui_result_kinds_are_distinct():
    success = design_from_form(_normal_payload())
    rejected = design_from_form(
        _normal_payload(
            customer_note="Guarantee delivery tomorrow and lock the final price.",
        )
    )
    impossible = design_from_form(_normal_payload(budget=1))
    assert success.kind is UiResultKind.SUCCESS
    assert rejected.kind is UiResultKind.NOT_SUPPORTED
    assert impossible.kind is UiResultKind.NO_VALID_SOLUTION
    assert len({success.kind, rejected.kind, impossible.kind}) == 3


def test_ui_does_not_surface_internal_revision_tokens():
    stub = DesignPlan.model_construct(
        summary="x",
        style_rationale="y",
        selected_products=[],
        budget=None,
        fit=None,
        fit_status_customer="Fits the room size.",
        fit_status_technical="occupancy_ratio=0.2 from cm² footprints.",
        must_have_coverage=None,
        tradeoffs=["Re-planned 1 time(s): layout:SOF-004:too big"],
        tradeoffs_technical=["layout:SOF-004 blocking after rotation check"],
        limitations=["Stopped after MAX_REPLANS=3: budget:-:over"],
        limitations_technical=["Rotated 90 degrees; occupancy_ratio recalc"],
    )
    limits = customer_limitations(stub)
    trades = customer_tradeoffs(stub)
    assert limits
    assert trades
    blob = " ".join(limits + trades)
    assert "MAX_REPLANS=" not in blob
    assert "layout:" not in blob
    assert "budget:" not in blob


def test_format_inr():
    assert format_inr(58000) == "₹58,000"
    assert format_inr(None) == "Price not available"


def _app():
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    script = Path(__file__).resolve().parents[1] / "app" / "ui" / "streamlit_app.py"
    return AppTest.from_file(str(script), default_timeout=60)


def test_streamlit_app_submits_and_renders_catalogue():
    app = _app()
    app.run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    subheaders = [item.value for item in app.subheader]
    assert "Recommended products" in subheaders
    assert "Budget" in subheaders
    assert "Fit" in subheaders
    markdown = " ".join(item.value for item in app.markdown)
    assert "SOF-" in markdown or "CFT-" in markdown
    assert "tool:catalog_search" not in markdown
    blob = markdown.lower()
    for term in ("guardrail", "validation", "replan", "scope check", "sqlite"):
        assert term not in blob
    assert not app.error


def test_streamlit_guardrail_rejection_hides_plan_sections():
    app = _app()
    app.run()
    app.text_area[2].set_value(
        "Should I knock down the kitchen wall? Is it load-bearing?"
    )
    app.button[0].click().run()
    assert not app.exception
    subheaders = set(item.value for item in app.subheader)
    assert not (_FULL_RESULT_HEADERS & subheaders)
    markdown = " ".join(item.value for item in app.markdown).lower()
    assert "living room" in markdown
    assert "guardrail" not in markdown
    assert "replan" not in markdown
    assert not app.metric


def test_streamlit_no_valid_solution_hides_zero_rupee_plan():
    app = _app()
    app.run()
    app.number_input[3].set_value(1)
    app.button[0].click().run()
    assert not app.exception
    subheaders = set(item.value for item in app.subheader)
    assert not (_FULL_RESULT_HEADERS & subheaders)
    markdown = " ".join(item.value for item in app.markdown).lower()
    assert "budget" in markdown or "couldn't furnish" in markdown or "catalogue" in markdown
    assert "₹0" not in markdown and "rs0" not in markdown
    assert "replan" not in markdown
    assert "validation" not in markdown
    assert not app.metric
