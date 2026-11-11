"""Golden scenario regression suite.

Each scenario in ``fixtures/analyst_scenarios.json`` replays the model's
responses through the complete graph against the real sample database, and
checks that the SQL executes, the chart references real columns, and the
self-correction path behaves as expected.
"""

import json
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_graph
from app.agent.llm import ScriptedLLM
from app.agent.state import initial_state

FIXTURE = Path(__file__).parent / "fixtures" / "analyst_scenarios.json"
SCENARIOS = json.loads(FIXTURE.read_text())["scenarios"]

QUESTIONS = {
    "total revenue by region": ("What is total revenue by region?", "bar", 5),
    "monthly revenue for 2026": ("Show monthly revenue for 2026 as a trend", "line", 10),
    "top 10 customers": ("Who are the top 10 customers by lifetime value?", "bar", 10),
    "sales channel": ("What share of orders comes from each sales channel?", "pie", 3),
    "q3 2026": ("Compare Q3 2026 revenue with Q3 2025 by region", "bar", 5),
    "average order value": ("What is the average order value by customer segment?", "bar", 3),
    "gross margin": ("Which product categories have the highest gross margin?", "bar", 6),
}


@pytest.fixture
def scenario_graph(engine, settings):
    return build_graph(ScriptedLLM(scenarios=SCENARIOS), engine, settings, checkpointer=InMemorySaver())


def _ask(graph, question, thread):
    config = {"configurable": {"thread_id": thread}}
    return graph.invoke(initial_state(question), config)


@pytest.mark.parametrize("match", list(QUESTIONS))
def test_scenario_produces_verified_answer(scenario_graph, match):
    question, chart_type, rows = QUESTIONS[match]
    state = _ask(scenario_graph, question, thread=match)
    assert state["status"] == "answered"
    assert state["row_count"] == rows
    assert state["chart"]["type"] == chart_type
    assert state["chart"]["x"] in state["columns"]
    assert set(state["chart"]["y"]) <= set(state["columns"])


def test_top_customers_scenario_self_corrects(scenario_graph):
    state = _ask(scenario_graph, "Who are the top 10 customers by lifetime value?", "fix")
    assert state["attempts"] == 2
    assert "customer_name" in state["attempt_log"][0]["error"]


def test_follow_up_scenario(scenario_graph):
    _ask(scenario_graph, "What is total revenue by region?", "conv")
    state = _ask(scenario_graph, "Now only for Europe", "conv")
    assert state["rows"][0][0] == "Europe"
    assert state["chart"]["type"] == "kpi"
    assert len(state["history"]) == 2


def test_all_fixture_scenarios_are_covered():
    covered = set(QUESTIONS) | {"only for europe", "hello"}
    assert {s["match"] for s in SCENARIOS} == covered
