from app.agent.requirements import needed_categories, parse_must_have_phrases
from app.agent.state import empty_agent_state
from app.models.brief import RoomBrief


def test_parse_must_haves():
    phrases = parse_must_have_phrases("3-seater sofa, coffee table, TV unit")
    assert phrases == ["3-seater sofa", "coffee table", "TV unit"]
    cats = needed_categories("3-seater sofa, coffee table, TV unit")
    assert cats == ["Sofa", "Coffee Table", "TV Unit"]


def test_state_messages_start_empty():
    brief = RoomBrief(
        room_type="Living Room",
        length_cm=400,
        width_cm=300,
        ceiling_cm=280,
        budget_inr=100000,
        style_preference="Minimalist",
        must_haves="sofa",
        constraints="",
        customer_note="",
    )
    state = empty_agent_state(brief)
    assert "replan_count" in state
    assert state["replan_count"] == 0
