"""Autouse deterministic LLM stand-ins so integration tests never call OpenAI."""

from __future__ import annotations

import pytest

from tests.fakes import make_test_agent


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "no_llm_fakes: do not patch agent LLM defaults"
    )


@pytest.fixture
def llm_test_agent():
    return make_test_agent


@pytest.fixture(autouse=True)
def _patch_agent_defaults(monkeypatch, request):
    if request.node.get_closest_marker("no_llm_fakes"):
        return

    from app.agent import graph as graph_mod

    def _run_design(brief, *, max_replans: int = 3):
        return make_test_agent(max_replans=max_replans).invoke(brief)

    # design_from_form lazily imports run_design from this module.
    monkeypatch.setattr(graph_mod, "run_design", _run_design)
