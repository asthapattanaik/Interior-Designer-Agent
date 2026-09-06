"""LangGraph-compatible agent state for the Living Room designer."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.agent.prompts import ScopeDecision
from app.agent.requirements import UnderstoodRequirements
from app.models.brief import RoomBrief
from app.models.catalog import CatalogItem
from app.models.output import (
    BudgetResult,
    DesignPlan,
    FitResult,
    MustHaveCoverage,
    SelectedProduct,
)


class AgentState(TypedDict, total=False):
    brief: RoomBrief | None
    normalized_brief: RoomBrief | None
    understood_requirements: UnderstoodRequirements | None
    candidate_products: list[CatalogItem]
    selected_products: list[SelectedProduct]
    budget_result: BudgetResult | None
    layout_result: FitResult | None
    must_have_coverage: MustHaveCoverage | None
    replan_count: int
    replan_reason: str | None
    validation_errors: list[str]
    validation_report: object | None
    final_plan: DesignPlan | None
    messages: Annotated[list[str], operator.add]
    raw_input: dict | None
    scope_decision: ScopeDecision | None


def empty_agent_state(brief: RoomBrief | None = None) -> AgentState:
    return AgentState(
        brief=brief,
        normalized_brief=None,
        understood_requirements=None,
        candidate_products=[],
        selected_products=[],
        budget_result=None,
        layout_result=None,
        must_have_coverage=None,
        replan_count=0,
        replan_reason=None,
        validation_errors=[],
        validation_report=None,
        final_plan=None,
        messages=[],
        raw_input=None,
        scope_decision=None,
    )
