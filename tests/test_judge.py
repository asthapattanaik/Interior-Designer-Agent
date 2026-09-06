"""LLM judge unit tests. The live model is mocked; facts stay authoritative."""

from app.evaluation.judge import (
    JudgeVerdict,
    apply_authoritative_facts,
    aggregate_judge_scores,
    build_judge_prompt,
    judge_case,
)
from app.evaluation.cases import load_golden_set
from app.db.catalog_repository import CatalogRepository


class _FakeJudge:
    def __init__(self, verdict: JudgeVerdict) -> None:
        self.verdict = verdict
        self.prompts: list = []

    def invoke(self, input):
        self.prompts.append(input)
        return self.verdict


def test_judge_verdict_bounds_and_mean():
    verdict = JudgeVerdict(
        relevance=4,
        style_coherence=5,
        explanation_quality=4,
        tradeoff_quality=3,
        customer_usefulness=4,
        rationale="Clear living room scheme from catalogue pieces.",
        honours_deterministic_facts=True,
    )
    assert verdict.mean() == 4.0


def test_judge_does_not_override_deterministic_failure():
    verdict = JudgeVerdict(
        relevance=5,
        style_coherence=5,
        explanation_quality=5,
        tradeoff_quality=5,
        customer_usefulness=5,
        rationale="Looks great.",
        honours_deterministic_facts=True,
    )
    payload = apply_authoritative_facts(verdict, deterministic_passed=False)
    assert payload["deterministic_passed"] is False
    assert payload["quality_does_not_override_facts"] is True
    assert "Deterministic" in payload["note"]
    assert payload["mean"] == 5.0


def test_judge_prompt_includes_facts_and_brief():
    case = load_golden_set()["cases"][0]
    scored = {
        "passed": True,
        "failures": [],
        "checks": {"budget_compliance": {"passed": True, "applicable": True}},
        "selected_ids": ["SOF-008"],
        "guardrail_label": "living_room_design",
    }
    prompt = build_judge_prompt(
        case=case,
        scored=scored,
        state={"final_plan": None, "validation_errors": [], "messages": []},
        repository=CatalogRepository(),
    )
    assert "ORIGINAL BRIEF" in prompt
    assert "DETERMINISTIC VALIDATION" in prompt
    assert "FACTUAL CATALOGUE" in prompt
    assert "CUSTOMER-FACING RESPONSE" in prompt
    assert case["id"] == "BR-01" or "Living Room" in prompt


def test_judge_customer_facing_block_uses_fit_status_customer_not_tool_explanation():
    from app.evaluation.judge import customer_facing_response
    from app.models.output import (
        BudgetResult,
        DesignPlan,
        FitResult,
        MustHaveCoverage,
        SelectedProduct,
    )

    plan = DesignPlan(
        summary="A calm Scandinavian living room.",
        style_rationale="Scandinavian tags preferred when available.",
        selected_products=[
            SelectedProduct(
                item_id="SOF-001",
                quantity=1,
                role_in_room="Sofa",
                why_selected="Matches the brief.",
            )
        ],
        budget=BudgetResult(
            subtotal=58000, budget=250000, remaining=192000, over_budget=False
        ),
        fit=FitResult(
            fits=True,
            explanation=(
                "Furniture footprint 35245 cm² / room 172800 cm² "
                "(occupancy_ratio=0.2040). Rotated 90 degrees allowed."
            ),
            occupancy_ratio=0.204,
            room_area_cm2=172800,
            furniture_footprint_cm2=35245,
        ),
        fit_status_customer=(
            "Your furniture uses about 20% of the floor, leaving plenty of open space."
        ),
        fit_status_technical=(
            "Furniture footprint 35245 cm² / room 172800 cm² (occupancy_ratio=0.2040)."
        ),
        must_have_coverage=MustHaveCoverage(
            requested=["sofa"], covered=["sofa"], missing=[]
        ),
        tradeoffs=["We left budget unused for optional extras."],
        tradeoffs_technical=["Occupancy excludes rug under fit assumptions."],
        limitations=[
            "This checks overall room size and height — not a full floor plan."
        ],
        limitations_technical=[
            "Floor-standing items may be rotated 90 degrees in the fit check."
        ],
    )
    state = {
        "final_plan": plan,
        "normalized_brief": None,
        "validation_errors": [],
        "messages": ["tool:catalog_search:1", "tool:budget:1", "tool:layout:1"],
        "scope_decision": None,
    }
    # Force SUCCESS path by providing a minimal brief so classify can validate.
    from app.models.brief import RoomBrief

    brief = RoomBrief(
        room_type="Living Room",
        length_cm=480,
        width_cm=360,
        ceiling_cm=300,
        budget_inr=250000,
        style_preference="Scandinavian",
        must_haves="sofa",
        constraints="",
        customer_note="",
    )
    state["normalized_brief"] = brief
    customer = customer_facing_response(state)
    assert "about 20% of the floor" in customer
    assert "occupancy_ratio" not in customer
    assert "cm²" not in customer
    assert "Rotated 90" not in customer

    prompt = build_judge_prompt(
        case={"input": {"room_type": "Living Room"}},
        scored={
            "passed": True,
            "failures": [],
            "checks": {},
            "selected_ids": ["SOF-001"],
            "guardrail_label": "living_room_design",
        },
        state=state,
        repository=CatalogRepository(),
    )
    customer_section = prompt.split("CUSTOMER-FACING RESPONSE", 1)[1]
    if "TECHNICAL / AUDIT DETAIL" in customer_section:
        customer_section = customer_section.split("TECHNICAL / AUDIT DETAIL", 1)[0]
    assert "about 20% of the floor" in customer_section
    assert "occupancy_ratio" not in customer_section
    assert "TECHNICAL / AUDIT DETAIL" in prompt
    assert "occupancy_ratio" in prompt.split("TECHNICAL / AUDIT DETAIL", 1)[1]


def test_judge_case_uses_structured_model():
    fake = _FakeJudge(
        JudgeVerdict(
            relevance=4,
            style_coherence=4,
            explanation_quality=4,
            tradeoff_quality=4,
            customer_usefulness=4,
            rationale="Addresses the living room brief without inventing SKUs.",
            honours_deterministic_facts=True,
        )
    )
    case = {
        "id": "x",
        "input": {"room_type": "Living Room", "must_haves": "sofa"},
    }
    scored = {
        "passed": True,
        "failures": [],
        "checks": {},
        "selected_ids": [],
        "guardrail_label": None,
    }
    out = judge_case(
        case=case,
        scored=scored,
        state={"final_plan": None, "validation_errors": [], "messages": []},
        repository=CatalogRepository(),
        structured_model=fake,
    )
    assert out["relevance"] == 4
    assert out["quality_does_not_override_facts"] is True
    assert fake.prompts


def test_aggregate_judge_scores():
    rows = [
        {
            "id": "a",
            "judge": {
                "relevance": 4,
                "style_coherence": 4,
                "explanation_quality": 5,
                "tradeoff_quality": 4,
                "customer_usefulness": 3,
                "mean": 4.0,
                "honours_deterministic_facts": True,
            },
        },
        {
            "id": "b",
            "judge": {
                "relevance": 2,
                "style_coherence": 2,
                "explanation_quality": 2,
                "tradeoff_quality": 2,
                "customer_usefulness": 2,
                "mean": 2.0,
                "honours_deterministic_facts": False,
                "rationale": "Weak",
            },
        },
    ]
    summary = aggregate_judge_scores(rows)
    assert summary["applicable"] == 2
    assert summary["by_dimension"]["relevance"] == 3.0
    assert "b" in summary["contradicted_facts"]
    assert summary["low_scores"][0]["id"] == "b"
