"""Mocked structured-output tests for the four LLM agent stages."""

from __future__ import annotations

import pytest

from app.agent.guardrails import ScopeGuardrail, llm_classifier
from app.agent.llm import LlmError, invoke_structured
from app.agent.prompts import ScopeDecision, ScopeLabel
from app.agent.requirements import MustHaveNeed, UnderstoodRequirements
from app.agent.schemas import PlanExplanation, ProductChoice, ProductSelectionResult
from app.config import SettingsError, load_settings
from app.models.brief import RoomBrief


class _FakeModel:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return self.response


def test_scope_check_parses_structured_scope_decision():
    decision = ScopeDecision(
        label=ScopeLabel.UNSUPPORTED_ROOM_TYPE,
        proceed=False,
        explanation="This MVP only designs Living Rooms.",
        redirect="Submit a Living Room brief instead.",
    )
    model = _FakeModel(decision)
    guardrail = ScopeGuardrail(classifier=llm_classifier(model))
    result = guardrail.evaluate(None, extra_text="Design my bedroom.")
    assert result.label == ScopeLabel.UNSUPPORTED_ROOM_TYPE
    assert result.proceed is False
    assert model.calls
    parsed = invoke_structured(
        _FakeModel(decision.model_dump()),
        [{"role": "user", "content": "bedroom"}],
        stage="scope_check",
        schema=ScopeDecision,
    )
    assert parsed.label == ScopeLabel.UNSUPPORTED_ROOM_TYPE


def test_understand_requirements_parses_structured_output():
    payload = UnderstoodRequirements(
        needed_categories=["Sofa", "Coffee Table", "Rug"],
        must_haves=[
            MustHaveNeed(phrase="3-seater sofa", covering_categories=["Sofa"]),
            MustHaveNeed(phrase="coffee table", covering_categories=["Coffee Table"]),
            MustHaveNeed(phrase="rug", covering_categories=["Rug"]),
        ],
        preferences=["calm", "bright"],
        constraints=["south-facing light"],
        prefer_large_sofa=False,
        prefer_higher_spend=False,
    )
    parsed = invoke_structured(
        _FakeModel(payload.model_dump()),
        [{"role": "user", "content": "brief"}],
        stage="understand_requirements",
        schema=UnderstoodRequirements,
    )
    assert parsed.needed_categories == ["Sofa", "Coffee Table", "Rug"]
    assert parsed.must_haves[0].covering_categories == ["Sofa"]
    assert parsed.preferences == ["calm", "bright"]


def test_understand_requirements_normalizes_verbose_branded_must_have_labels():
    """Display labels must be short/generic, not echoed customer free text."""
    from app.agent.requirements import REQUIREMENTS_SYSTEM_PROMPT

    verbose_input = (
        "comfy big couch for movie nights, that round marble coffee table vibe, "
        "lamp like Monica Geller lighting"
    )
    # Simulated model response: understands verbose input, emits clean labels.
    payload = UnderstoodRequirements(
        needed_categories=["Sofa", "Coffee Table", "Table Lamp"],
        must_haves=[
            MustHaveNeed(phrase="sofa", covering_categories=["Sofa"]),
            MustHaveNeed(phrase="coffee table", covering_categories=["Coffee Table"]),
            MustHaveNeed(phrase="table lamp", covering_categories=["Table Lamp"]),
        ],
        preferences=[],
        constraints=[],
        prefer_large_sofa=False,
        prefer_higher_spend=False,
    )
    model = _FakeModel(payload)
    parsed = invoke_structured(
        model,
        [
            {"role": "system", "content": REQUIREMENTS_SYSTEM_PROMPT},
            {"role": "user", "content": f"must_haves={verbose_input}"},
        ],
        stage="understand_requirements",
        schema=UnderstoodRequirements,
    )

    assert "Do NOT copy verbatim" in REQUIREMENTS_SYSTEM_PROMPT
    assert "table lamp" in REQUIREMENTS_SYSTEM_PROMPT
    labels = [need.phrase for need in parsed.must_haves]
    assert labels == ["sofa", "coffee table", "table lamp"]
    for label in labels:
        assert 1 <= len(label.split()) <= 4
        assert "Monica" not in label
        assert "marble" not in label
        assert "movie nights" not in label
    # Prompt still receives the full verbose input for intent.
    user_msg = model.calls[0][1]["content"]
    assert "Monica Geller" in user_msg


def test_product_selection_parses_structured_output():
    payload = ProductSelectionResult(
        selections=[
            ProductChoice(
                item_id="SOF-001",
                role_in_room="Sofa",
                why_selected="Scandinavian 3-seater sofa from the candidate list.",
            ),
            ProductChoice(
                item_id="CFT-002",
                role_in_room="Coffee Table",
                why_selected="Matching coffee table from candidates.",
            ),
        ]
    )
    parsed = invoke_structured(
        _FakeModel(payload.model_dump()),
        [{"role": "user", "content": "candidates"}],
        stage="product_selection",
        schema=ProductSelectionResult,
    )
    assert [item.item_id for item in parsed.selections] == ["SOF-001", "CFT-002"]
    assert parsed.selections[0].why_selected.startswith("Scandinavian")


def test_finalize_explanation_parses_structured_output():
    payload = PlanExplanation(
        summary="A Scandinavian living room from catalogue pieces.",
        style_rationale="Selected items carry Scandinavian style tags.",
        fit_status_customer=(
            "Your furniture uses about 20% of the floor, leaving plenty of open space."
        ),
        fit_status_technical=(
            "Furniture footprint 35245 cm² / room 172800 cm² (occupancy_ratio=0.2040)."
        ),
        tradeoffs=["We left budget unused for optional extras later."],
        tradeoffs_technical=[
            "Occupancy excludes rug/lamp/pendant under fit assumptions."
        ],
        limitations=[
            "This checks overall room size and height — not a full floor plan."
        ],
        limitations_technical=[
            "Floor-standing items may be rotated 90 degrees in the fit check."
        ],
    )
    parsed = invoke_structured(
        _FakeModel(payload.model_dump()),
        [{"role": "user", "content": "facts"}],
        stage="finalize",
        schema=PlanExplanation,
    )
    assert "Scandinavian" in parsed.summary
    assert parsed.tradeoffs
    assert parsed.limitations
    assert "cm²" not in parsed.fit_status_customer
    assert "occupancy_ratio" in parsed.fit_status_technical


_CUSTOMER_BANNED = (
    "cm²",
    "cm2",
    "occupancy_ratio",
    "rotated 90",
    "rotation",
    "footprint",
)


def test_customer_facing_copy_excludes_internal_fit_terms():
    payload = PlanExplanation(
        summary="A calm living room plan from the catalogue.",
        style_rationale="Scandinavian tags were preferred when available.",
        fit_status_customer=(
            "Your furniture uses about 20% of the floor, leaving plenty of open space. "
            "This checks overall room fit, not exact walking paths between pieces."
        ),
        fit_status_technical=(
            "Selected floor-standing items fit the room rectangle and ceiling. "
            "Furniture footprint 35245 cm² / room 172800 cm² (occupancy_ratio=0.2040). "
            "Circulation was not measured."
        ),
        tradeoffs=[
            "We left ₹106,000 of your budget unused in case you'd like to add "
            "extra pieces later."
        ],
        tradeoffs_technical=[
            "The furniture occupancy calculation is 35,245 cm² out of 172,800 cm² "
            "room area, or 20.4%, but this figure excludes the rug, table lamp, and "
            "pendant under the stated fit assumptions."
        ],
        limitations=[
            "This checks that your furniture fits the room's overall size and height — "
            "it isn't a full floor plan or a guarantee of exact placement."
        ],
        limitations_technical=[
            "Floor-standing items may be rotated 90 degrees in the fit check. "
            "The rug is excluded from furniture occupancy because the check assumes "
            "rugs sit beneath furniture."
        ],
    )
    customer_blob = " ".join(
        [
            payload.fit_status_customer,
            *payload.tradeoffs,
            *payload.limitations,
        ]
    ).lower()
    for term in _CUSTOMER_BANNED:
        assert term.lower() not in customer_blob, term

    technical_blob = " ".join(
        [
            payload.fit_status_technical,
            *payload.tradeoffs_technical,
            *payload.limitations_technical,
        ]
    ).lower()
    assert "cm²" in technical_blob or "cm2" in technical_blob.replace("²", "2")
    assert "occupancy_ratio" in technical_blob
    assert "rotated 90" in technical_blob


@pytest.mark.no_llm_fakes
def test_missing_api_key_fails_clearly_not_silent(monkeypatch):
    from app.config import PROJECT_ROOT

    with pytest.raises(SettingsError, match="OPENAI_API_KEY"):
        load_settings(
            env_file=None,
            environ={
                "OPENAI_API_KEY": "",
                "OPENAI_MODEL": "gpt-5.6",
                "CATALOG_DB_PATH": str(PROJECT_ROOT / "interior_company_catalog.db"),
                "MAX_REPLANS": "3",
            },
        )

    def _boom(**_kwargs):
        raise SettingsError("OPENAI_API_KEY is required")

    monkeypatch.setattr("app.agent.graph.load_settings", _boom)
    from app.agent.graph import InteriorDesignAgent

    with pytest.raises(SettingsError, match="OPENAI_API_KEY"):
        InteriorDesignAgent()


def test_invoke_structured_wraps_provider_errors():
    class Boom:
        def invoke(self, _messages):
            raise RuntimeError("invalid_api_key")

    with pytest.raises(LlmError, match="scope_check"):
        invoke_structured(Boom(), "x", stage="scope_check", schema=ScopeDecision)


def test_requirements_runner_uses_brief_fields():
    from tests.fakes import fake_requirements_runner

    brief = RoomBrief(
        room_type="Living Room",
        length_cm=480,
        width_cm=360,
        ceiling_cm=300,
        budget_inr=250000,
        style_preference="Scandinavian",
        must_haves="3-seater sofa, coffee table",
        constraints="south light",
        customer_note="calm",
    )
    understood = fake_requirements_runner()(brief)
    assert "Sofa" in understood.needed_categories
    assert "Coffee Table" in understood.needed_categories
