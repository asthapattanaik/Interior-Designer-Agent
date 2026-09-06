"""Model-based scope/intent guardrail. Does not call catalogue, budget, or layout tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from app.agent.llm import build_structured_model, invoke_structured
from app.agent.prompts import SCOPE_SYSTEM_PROMPT, ScopeDecision, ScopeLabel
from app.models.brief import RoomBrief

Classifier = Callable[[str], ScopeDecision]


class SupportsStructuredScope(Protocol):
    def invoke(self, input: dict | list | str) -> ScopeDecision: ...


def _request_text(brief: RoomBrief | None, extra_text: str = "") -> str:
    parts: list[str] = []
    if brief is not None:
        parts.extend(
            [
                f"room_type={brief.room_type}",
                f"style={brief.style_preference}",
                f"must_haves={brief.must_haves}",
                f"constraints={brief.constraints}",
                f"customer_note={brief.customer_note}",
            ]
        )
    if extra_text and extra_text.strip():
        parts.append(extra_text.strip())
    return "\n".join(parts).strip()


def is_unsupported_guarantee_request(text: str) -> bool:
    """True only for commitment/promise language about delivery or price.

    Budget caps, exact spend targets, and delivery preferences alone are NOT
    guarantees. Requires explicit assurance / lock / promise wording.
    """
    blob = text.lower()
    commitment_markers = (
        "guarantee",
        "guaranteed",
        "guaranteeing",
        "promise that",
        "promise me",
        "promised",
        "assure me",
        "assured that",
        "lock the final",
        "lock the price",
        "lock in the price",
        "locked price",
        "firm quote",
        "price will not change",
        "do not change it",
        "warranty that",
        "commit to the price",
        "commit to delivery",
    )
    return any(marker in blob for marker in commitment_markers)


def heuristic_classify(text: str) -> ScopeDecision:
    """Offline stand-in used when no LLM is injected. Tests should mock the LLM path."""
    blob = text.lower()
    if any(
        token in blob
        for token in (
            "load-bearing",
            "knock down",
            "knockdown",
            "remove the wall",
            "remove wall",
            "demolish",
            "tear down",
        )
    ):
        return ScopeDecision(
            label=ScopeLabel.STRUCTURAL_CONSTRUCTION,
            proceed=False,
            explanation=(
                "This MVP cannot advise on demolition or whether a wall is load-bearing."
            ),
            redirect=(
                "I can still help you furnish a Living Room from the catalogue if you "
                "share room size, budget, and style without construction work."
            ),
        )
    if is_unsupported_guarantee_request(text):
        return ScopeDecision(
            label=ScopeLabel.UNSUPPORTED_GUARANTEE,
            proceed=False,
            explanation=(
                "I cannot guarantee delivery dates, installation deadlines, or a locked "
                "final discounted price."
            ),
            redirect=(
                "Ask for a Living Room furniture plan from the catalogue instead; lead "
                "times in the database are information only, not a promise."
            ),
        )
    other_rooms = (
        "bedroom",
        "kitchen",
        "dining room",
        "kids room",
        "children",
        "study",
        "office",
        "bathroom",
    )
    living = "living room" in blob or "room_type=living room" in blob
    if any(room in blob for room in other_rooms) and not living:
        return ScopeDecision(
            label=ScopeLabel.UNSUPPORTED_ROOM_TYPE,
            proceed=False,
            explanation="This MVP only designs Living Rooms.",
            redirect="Submit a Living Room brief with dimensions, budget, and style.",
        )
    if living or "room_type=living room" in blob:
        return ScopeDecision(
            label=ScopeLabel.LIVING_ROOM_DESIGN,
            proceed=True,
            explanation="This looks like a supported Living Room furniture request.",
            redirect="Continue with catalogue-backed Living Room recommendations.",
        )
    return ScopeDecision(
        label=ScopeLabel.AMBIGUOUS,
        proceed=False,
        explanation="I cannot tell whether this is a Living Room furniture design request.",
        redirect="Describe your Living Room size, budget, style, and must-haves.",
    )


def llm_classifier(structured_model: SupportsStructuredScope) -> Classifier:
    def _classify(text: str) -> ScopeDecision:
        return invoke_structured(
            structured_model,
            [
                {"role": "system", "content": SCOPE_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            stage="scope_check",
            schema=ScopeDecision,
        )

    return _classify


class ScopeGuardrail:
    """Classifies intent only. Never searches the catalogue or computes budget/fit."""

    def __init__(self, classifier: Classifier | None = None) -> None:
        if classifier is None:
            classifier = llm_classifier(build_structured_model(ScopeDecision))
        self._classifier = classifier

    def evaluate(
        self, brief: RoomBrief | None, extra_text: str = ""
    ) -> ScopeDecision:
        text = _request_text(brief, extra_text)
        if not text:
            return ScopeDecision(
                label=ScopeLabel.AMBIGUOUS,
                proceed=False,
                explanation="No request text was provided.",
                redirect="Provide a Living Room brief with dimensions, budget, and style.",
            )
        decision = self._classifier(text)
        if decision.label != ScopeLabel.LIVING_ROOM_DESIGN:
            return decision.model_copy(update={"proceed": False})
        return decision.model_copy(update={"proceed": True})
