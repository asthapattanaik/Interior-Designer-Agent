"""Agent state unit tests and LangGraph integration tests."""

from app.agent.state import AgentState, empty_agent_state
from app.models.brief import RoomBrief
from app.models.output import DesignPlan
from app.validation.output_validator import OutputValidator
from tests.fakes import make_test_agent


def run_design(brief, *, max_replans: int = 3):
    return make_test_agent(max_replans=max_replans).invoke(brief)


InteriorDesignAgent = make_test_agent


def _brief(**overrides) -> RoomBrief:
    data = {
        "room_type": "Living Room",
        "length_cm": 480,
        "width_cm": 360,
        "ceiling_cm": 300,
        "budget_inr": 250000,
        "style_preference": "Scandinavian",
        "must_haves": "3-seater sofa, coffee table, TV unit, rug, lighting",
        "constraints": "South-facing, lots of natural light",
        "customer_note": "Calm bright living room",
    }
    data.update(overrides)
    return RoomBrief(**data)


def test_empty_agent_state_has_required_fields():
    state: AgentState = empty_agent_state(_brief())
    assert state["brief"].room_type == "Living Room"
    assert state["normalized_brief"] is None
    assert state["candidate_products"] == []
    assert state["selected_products"] == []
    assert state["budget_result"] is None
    assert state["layout_result"] is None
    assert state["must_have_coverage"] is None
    assert state["replan_count"] == 0
    assert state["replan_reason"] is None
    assert state["validation_errors"] == []
    assert state["final_plan"] is None
    assert state["messages"] == []


def _assert_tools_called(messages: list[str]) -> None:
    joined = "\n".join(messages)
    assert "tool:catalog_search" in joined
    assert "tool:budget" in joined
    assert "tool:layout" in joined


def _assert_plan_never_invalid(plan: DesignPlan | None, brief: RoomBrief) -> None:
    assert plan is not None
    assert plan.budget.over_budget is False
    assert plan.fit.fits is True
    report = OutputValidator().validate(
        brief=brief,
        selected=plan.selected_products,
        claimed_budget=plan.budget,
        claimed_fit=plan.fit,
        plan=plan,
    )
    assert report.ok, report.tokens()


def test_normal_living_room_brief():
    result = run_design(_brief())
    plan = result["final_plan"]
    assert plan is not None
    assert plan.selected_products
    assert all(item.item_id for item in plan.selected_products)
    assert plan.budget.over_budget is False
    assert plan.budget.subtotal <= 250000
    assert plan.fit.fits is True
    sofa_ids = [
        item.item_id
        for item in plan.selected_products
        if item.catalog_item and item.catalog_item.category == "Sofa"
    ]
    assert sofa_ids
    assert sofa_ids[0] == "SOF-001"
    assert "SQLite" not in plan.style_rationale
    _assert_tools_called(result["messages"])
    assert result["replan_count"] <= 3


def test_constrained_budget_brief():
    result = run_design(
        _brief(
            budget_inr=20000,
            style_preference="Contemporary",
            must_haves="Full living room: sofa, coffee table, TV unit, rug, lighting",
            constraints="First apartment, very tight on money",
            customer_note="Can you do the whole living room in this budget?",
        )
    )
    plan = result["final_plan"]
    assert plan is not None
    assert plan.budget.over_budget is False
    assert plan.budget.subtotal <= 20000
    _assert_tools_called(result["messages"])
    ids = {item.item_id for item in plan.selected_products}
    assert "SOF-001" not in ids
    assert any(
        "could not be sourced" in item.lower() or "uncovered" in item.lower()
        for item in plan.limitations
    )


def test_spatially_constrained_brief():
    result = run_design(
        _brief(
            length_cm=240,
            width_cm=210,
            ceiling_cm=270,
            budget_inr=180000,
            must_haves="Large L-sectional",
            constraints="Small studio",
            customer_note="Make it all fit, please.",
        )
    )
    plan = result["final_plan"]
    assert plan is not None
    _assert_tools_called(result["messages"])
    ids = [item.item_id for item in plan.selected_products]
    assert "SOF-004" not in ids
    assert "SOF-006" not in ids
    if plan.selected_products:
        assert plan.fit.fits is True
    assert result["replan_count"] <= 3


def test_max_replans_is_enforced():
    agent = InteriorDesignAgent(max_replans=0)
    result = agent.invoke(
        _brief(
            length_cm=240,
            width_cm=210,
            ceiling_cm=270,
            budget_inr=180000,
            must_haves="Large L-sectional",
        )
    )
    assert result["replan_count"] == 0
    _assert_tools_called(result["messages"])
    assert not any(msg.startswith("replan:") for msg in result["messages"])
    tiny = _brief(
        length_cm=240,
        width_cm=210,
        ceiling_cm=270,
        budget_inr=180000,
        must_haves="Large L-sectional",
    )
    _assert_plan_never_invalid(result["final_plan"], tiny)


def test_budget_failure_triggers_replan():
    brief = _brief(
        budget_inr=20000,
        style_preference="Contemporary",
        must_haves="Full living room: sofa, coffee table, TV unit, rug, lighting",
        constraints="First apartment, very tight on money",
        customer_note="Can you do the whole living room in this budget?",
    )
    result = run_design(brief)
    joined = "\n".join(result["messages"])
    assert "replan:" in joined
    assert result["replan_count"] >= 1
    assert result["replan_count"] <= 3
    assert "tool:budget" in joined
    plan = result["final_plan"]
    assert plan is not None
    assert plan.budget.over_budget is False
    _assert_plan_never_invalid(plan, brief)


def test_fit_failure_triggers_replan_where_supported():
    brief = _brief(
        length_cm=240,
        width_cm=210,
        ceiling_cm=270,
        budget_inr=180000,
        must_haves="Large L-sectional",
        constraints="Small studio",
        customer_note="Make it all fit, please.",
    )
    result = run_design(brief)
    joined = "\n".join(result["messages"])
    assert "replan:" in joined
    assert "layout:" in joined
    assert result["replan_count"] >= 1
    assert "SOF-004" not in {item.item_id for item in result["final_plan"].selected_products}
    _assert_plan_never_invalid(result["final_plan"], brief)


def test_replan_limit_prevents_infinite_loop():
    brief = _brief(
        budget_inr=20000,
        must_haves="Full living room: sofa, coffee table, TV unit, rug, lighting",
    )
    result = InteriorDesignAgent(max_replans=1).invoke(brief)
    assert result["replan_count"] <= 1
    replan_starts = [msg for msg in result["messages"] if msg.startswith("replan:")]
    assert len(replan_starts) <= 1
    _assert_plan_never_invalid(result["final_plan"], brief)


def test_impossible_case_terminates_honestly():
    brief = _brief(
        budget_inr=1,
        must_haves="3-seater sofa, coffee table, TV unit, rug, lighting",
        customer_note="Please furnish the whole room for one rupee.",
    )
    result = run_design(brief)
    plan = result["final_plan"]
    assert plan is not None
    assert result["replan_count"] <= 3
    _assert_plan_never_invalid(plan, brief)
    assert plan.selected_products == []
    blob = " ".join([plan.summary, *plan.limitations]).lower()
    assert "could not" in blob or "no valid" in blob or "max_replans" in blob
    assert "could not be sourced" in blob or "uncovered" in blob or "must-have" in blob


def test_invalid_final_result_never_returned():
    cases = [
        _brief(),
        _brief(budget_inr=20000, must_haves="sofa, coffee table, lighting"),
        _brief(
            length_cm=240,
            width_cm=210,
            ceiling_cm=270,
            budget_inr=180000,
            must_haves="Large L-sectional",
        ),
        _brief(budget_inr=20000, must_haves="sofa and coffee table"),
    ]
    results = [
        run_design(cases[0]),
        run_design(cases[1]),
        run_design(cases[2]),
        InteriorDesignAgent(max_replans=0).invoke(cases[3]),
    ]
    for brief, result in zip(cases, results, strict=True):
        _assert_plan_never_invalid(result["final_plan"], brief)
        assert result["replan_count"] <= 3


def test_agent_customer_copy_omits_internal_fit_terms():
    result = run_design(_brief())
    plan = result["final_plan"]
    assert plan is not None
    customer_blob = " ".join(
        [
            plan.fit_status_customer,
            *plan.tradeoffs,
            *plan.limitations,
            plan.summary,
            plan.style_rationale,
        ]
    ).lower()
    for term in (
        "cm²",
        "cm2",
        "occupancy_ratio",
        "rotated 90",
        "rotation",
    ):
        assert term not in customer_blob, term
    technical_blob = " ".join(
        [
            plan.fit_status_technical,
            *plan.tradeoffs_technical,
            *plan.limitations_technical,
        ]
    ).lower()
    assert plan.fit_status_technical
    assert (
        "cm²" in technical_blob
        or "occupancy" in technical_blob
        or "rotated" in technical_blob
        or "cm2" in technical_blob.replace("²", "2")
    )
