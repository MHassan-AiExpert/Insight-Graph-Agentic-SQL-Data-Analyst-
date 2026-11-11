import pytest
from langchain_core.messages import HumanMessage

from app.agent.llm import GroqLLM, LLMError, ScriptedLLM
from app.agent.prompts import INSIGHT_PROMPT, INTENT_PROMPT, SQL_PROMPT, TABLE_PROMPT
from app.agent.schemas import ChartSpec, IntentDecision, SQLDraft

MSG = [HumanMessage(content="q")]


def test_scripted_replays_in_order_and_validates():
    llm = ScriptedLLM(responses={"sql": [{"sql": "SELECT 1", "reasoning": "a"}, {"sql": "SELECT 2", "reasoning": "b"}]})
    first = llm.structured("sql", MSG, SQLDraft)
    second = llm.structured("sql", MSG, SQLDraft)
    assert isinstance(first, SQLDraft) and (first.sql, second.sql) == ("SELECT 1", "SELECT 2")
    assert llm.calls == [("sql", ""), ("sql", "")]


def test_scripted_raises_when_exhausted():
    with pytest.raises(LLMError, match="No scripted response"):
        ScriptedLLM().structured("intent", MSG, IntentDecision)


def test_scripted_scenario_matching_and_refill():
    llm = ScriptedLLM(scenarios=[{"match": "revenue", "responses": {"sql": [{"sql": "SELECT 9", "reasoning": "r"}]}}])
    for _ in range(2):  # the queue refills so a question can be asked again
        assert llm.structured("sql", MSG, SQLDraft, key="Total REVENUE?").sql == "SELECT 9"


def test_invalid_payload_is_rejected_by_schema():
    llm = ScriptedLLM(
        responses={"intent": [{"intent": "delete_everything", "standalone_question": "x", "reason": "y"}]}
    )
    with pytest.raises(ValueError):
        llm.structured("intent", MSG, IntentDecision)


def test_groq_requires_api_key():
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqLLM(model="llama-3.3-70b-versatile", api_key=None)


def test_groq_builds_structured_runnable_without_network():
    llm = GroqLLM(model="llama-3.3-70b-versatile", api_key="gsk_test")
    assert llm.provider == "groq" and llm.model == "llama-3.3-70b-versatile"
    assert llm._chat.with_structured_output(SQLDraft) is not None


def test_chart_spec_defaults():
    assert ChartSpec(type="bar").model_dump() == {"type": "bar", "x": None, "y": [], "title": ""}


def test_prompts_render_with_all_variables():
    assert len(INTENT_PROMPT.format_messages(dialect="sqlite", table_list="a", history="-", question="q")) == 2
    assert len(TABLE_PROMPT.format_messages(catalog="a", question="q")) == 2
    sql = SQL_PROMPT.format_messages(
        dialect="sqlite",
        date_hint="h",
        max_rows=5,
        business_rules="r",
        schema="s",
        history="-",
        question="q",
        feedback="",
    )
    assert "SELECT" in sql[0].content and "Question: q" in sql[1].content
    assert len(INSIGHT_PROMPT.format_messages(columns="[]", question="q", sql="s", row_count=1, shown=1, rows="r")) == 2
