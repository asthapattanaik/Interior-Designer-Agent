"""Normalization and scope-guardrail tests (STEP 10–11)."""

from __future__ import annotations

import pytest

from app.agent.guardrails import (
    ScopeGuardrail,
    heuristic_classify,
    is_unsupported_guarantee_request,
    llm_classifier,
)
from app.agent.prompts import ScopeDecision, ScopeLabel
from app.models.brief import RoomBrief
from app.validation.normalize import (
    CM_PER_FOOT,
    NormalizationError,
    normalize_customer_input,
    parse_budget_inr,
    parse_dimension_cm,
)
from tests.fakes import make_test_agent


def run_design(brief, *, max_replans: int = 3):
    return make_test_agent(max_replans=max_replans).invoke(brief)


InteriorDesignAgent = make_test_agent


def test_feet_to_cm():
    assert parse_dimension_cm("12 ft", field="length", default_unit=None) == int(round(12 * CM_PER_FOOT))
    brief = normalize_customer_input(
        {
            "room_type": "Living Room",
            "length": 12,
            "width": 10,
            "ceiling": 9,
            "unit": "ft",
            "budget": 250000,
            "style_preference": "Scandinavian",
            "must_haves": "sofa",
        }
    )
    assert brief.length_cm == int(round(12 * CM_PER_FOOT))
    assert brief.width_cm == int(round(10 * CM_PER_FOOT))
    assert brief.ceiling_cm == int(round(9 * CM_PER_FOOT))


def test_lakh_to_inr():
    assert parse_budget_inr("2.5 lakh") == 250000
    brief = normalize_customer_input(
        {
            "room_type": "Living Room",
            "length_cm": 480,
            "width_cm": 360,
            "ceiling_cm": 300,
            "budget": "2.5 lakh",
            "style_preference": "Contemporary",
            "must_haves": "sofa",
        }
    )
    assert brief.budget_inr == 250000


def test_invalid_dimensions():
    with pytest.raises(NormalizationError) as exc:
        parse_dimension_cm(0, field="length", default_unit="cm")
    assert "invalid:length" in exc.value.errors
    with pytest.raises(NormalizationError):
        parse_dimension_cm(-4, field="width", default_unit="cm")


def test_missing_budget():
    with pytest.raises(NormalizationError) as exc:
        normalize_customer_input(
            {
                "room_type": "Living Room",
                "length_cm": 480,
                "width_cm": 360,
                "ceiling_cm": 300,
                "style_preference": "Scandinavian",
                "must_haves": "sofa",
            }
        )
    assert "missing:budget" in exc.value.errors


def test_missing_dimensions():
    with pytest.raises(NormalizationError) as exc:
        normalize_customer_input(
            {
                "room_type": "Living Room",
                "budget_inr": 200000,
                "style_preference": "Scandinavian",
                "must_haves": "sofa",
            }
        )
    assert "missing:length" in exc.value.errors
    assert "missing:width" in exc.value.errors
    assert "missing:ceiling" in exc.value.errors


def test_unsupported_room_type_normalization():
    with pytest.raises(NormalizationError) as exc:
        normalize_customer_input(
            {
                "room_type": "Bedroom",
                "length_cm": 420,
                "width_cm": 360,
                "ceiling_cm": 290,
                "budget_inr": 200000,
                "style_preference": "Minimalist",
                "must_haves": "Queen bed",
            }
        )
    assert any(err.startswith("unsupported_room_type") for err in exc.value.errors)


def test_guardrail_unsupported_room_mocked_model():
    class FakeModel:
        def invoke(self, _messages):
            return ScopeDecision(
                label=ScopeLabel.UNSUPPORTED_ROOM_TYPE,
                proceed=False,
                explanation="This MVP only designs Living Rooms.",
                redirect="Submit a Living Room brief instead.",
            )

    guardrail = ScopeGuardrail(classifier=llm_classifier(FakeModel()))
    decision = guardrail.evaluate(None, extra_text="Design my bedroom.")
    assert decision.label == ScopeLabel.UNSUPPORTED_ROOM_TYPE
    assert decision.proceed is False
    assert "Living Room" in decision.redirect


def test_guardrail_structural_request():
    decision = heuristic_classify(
        "Should I knock down the kitchen wall? Is it load-bearing?"
    )
    assert decision.label == ScopeLabel.STRUCTURAL_CONSTRUCTION
    assert decision.proceed is False
    assert "load-bearing" in decision.explanation.lower() or "demolition" in decision.explanation.lower()


def test_guardrail_guarantee_request():
    decision = heuristic_classify("Guarantee that this furniture will arrive tomorrow.")
    assert decision.label == ScopeLabel.UNSUPPORTED_GUARANTEE
    assert decision.proceed is False


@pytest.mark.parametrize(
    ("text", "should_block"),
    [
        ("Spend exactly ₹36,000.", False),
        ("Guarantee that the final price is exactly ₹36,000.", True),
        ("I need everything delivered before the 25th.", False),
        ("Guarantee everything will be delivered before the 25th.", True),
        ("Exact price requirement: total should be ₹36,000 if a sofa exists.", False),
        ("Guaranteed final price of ₹36,000 — do not change it.", True),
        ("I want to stay under ₹50,000", False),
        ("Guarantee I will stay under ₹50,000", True),
        ("Spend exactly this amount if a sofa exists at this price", False),
        ("Please furnish the whole room for one rupee.", False),
        ("Lock the final discounted price now and do not change it.", True),
        ("Guarantee everything is delivered and installed before the 25th.", True),
    ],
)
def test_guarantee_detection_distinguishes_constraints_from_promises(
    text: str, should_block: bool
):
    assert is_unsupported_guarantee_request(text) is should_block
    decision = heuristic_classify(
        f"room_type=Living Room\nmust_haves=sofa\ncustomer_note={text}"
    )
    if should_block:
        assert decision.label == ScopeLabel.UNSUPPORTED_GUARANTEE
        assert decision.proceed is False
    else:
        assert decision.label == ScopeLabel.LIVING_ROOM_DESIGN
        assert decision.proceed is True


def test_graph_allows_exact_budget_constraint_without_guarantee():
    brief = RoomBrief(
        room_type="Living Room",
        length_cm=480,
        width_cm=360,
        ceiling_cm=300,
        budget_inr=36000,
        style_preference="Minimalist",
        must_haves="sofa",
        constraints="Spend exactly this amount if a sofa exists at this price",
        customer_note="Cheapest acceptable seating only.",
    )
    result = InteriorDesignAgent().invoke(brief)
    assert result["scope_decision"].label == ScopeLabel.LIVING_ROOM_DESIGN
    assert result["scope_decision"].proceed is True
    joined = "\n".join(result["messages"])
    assert "tool:catalog_search" in joined


def test_graph_unsupported_room_does_not_call_tools():
    result = run_design(
        {
            "room_type": "Bedroom",
            "length_cm": 420,
            "width_cm": 360,
            "ceiling_cm": 290,
            "budget_inr": 200000,
            "style_preference": "Minimalist",
            "must_haves": "Queen bed",
            "constraints": "",
            "customer_note": "Design my bedroom.",
        }
    )
    joined = "\n".join(result["messages"])
    assert "tool:catalog_search" not in joined
    assert "tool:budget" not in joined
    assert "tool:layout" not in joined
    assert any("unsupported_room_type" in err for err in result["validation_errors"])


def test_graph_structural_request_explains_and_redirects():
    brief = RoomBrief(
        room_type="Living Room",
        length_cm=500,
        width_cm=400,
        ceiling_cm=300,
        budget_inr=300000,
        style_preference="Industrial",
        must_haves="Open up the space and design an industrial living-dining",
        constraints="Want to remove the wall between kitchen and living room",
        customer_note="Should I knock down the kitchen wall? Is it load-bearing?",
    )
    result = InteriorDesignAgent().invoke(brief)
    joined = "\n".join(result["messages"])
    assert "tool:catalog_search" not in joined
    assert result["scope_decision"].label == ScopeLabel.STRUCTURAL_CONSTRUCTION
    plan = result["final_plan"]
    assert plan is not None
    assert plan.selected_products == []
    assert any("wall" in item.lower() or "demolition" in item.lower() or "load-bearing" in item.lower() for item in plan.limitations)


def test_graph_guarantee_request_explains_and_redirects():
    brief = RoomBrief(
        room_type="Living Room",
        length_cm=400,
        width_cm=340,
        ceiling_cm=290,
        budget_inr=160000,
        style_preference="Coastal",
        must_haves="sofa, rug, lighting",
        constraints="moving in three weeks",
        customer_note="Guarantee everything is delivered before the 25th and lock the final price.",
    )
    result = InteriorDesignAgent().invoke(brief)
    joined = "\n".join(result["messages"])
    assert "tool:catalog_search" not in joined
    assert result["scope_decision"].label == ScopeLabel.UNSUPPORTED_GUARANTEE
    assert result["final_plan"] is not None
    assert result["final_plan"].selected_products == []
