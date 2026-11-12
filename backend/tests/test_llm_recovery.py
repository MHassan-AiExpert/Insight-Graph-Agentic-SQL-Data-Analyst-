"""Recovery from provider-side schema rejections (Groq ``tool_use_failed``)."""

import json

import httpx
from groq import BadRequestError

from app.agent.llm import recover_failed_generation
from app.agent.schemas import ChartSpec, InsightReport, SQLDraft

# Shape of the real failure seen with openai/gpt-oss-120b: a table chart with x and y set to null.
FAILED_ARGS = {
    "answer": "In Q4 2025 the biggest revenue spikes in Europe came from Office & Stationery.",
    "chart": {"type": "table", "title": "Revenue by month, category and channel", "x": None, "y": None},
    "key_findings": ["Office & Stationery peaked in November (mobile)."],
    "follow_up_questions": ["Which products drove the November spike?"],
}


def _groq_error(arguments: dict) -> BadRequestError:
    body = {
        "error": {
            "message": "Tool call validation failed: `/chart/y`: expected array, but got null",
            "type": "invalid_request_error",
            "code": "tool_use_failed",
            "failed_generation": json.dumps({"name": "InsightReport", "arguments": arguments}),
        }
    }
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(400, request=request, json=body)
    return BadRequestError("Error code: 400", response=response, body=body)


def test_schema_accepts_nulls_for_lists():
    report = InsightReport.model_validate(FAILED_ARGS)
    assert report.chart.type == "table"
    assert report.chart.y == []
    assert report.chart.x is None


def test_schema_allows_null_in_json_schema():
    schema = json.dumps(ChartSpec.model_json_schema())
    assert '"null"' in schema


def test_missing_lists_and_chart_default_safely():
    report = InsightReport.model_validate({"answer": "x", "chart": None, "key_findings": None})
    assert report.chart.type == "table"
    assert report.key_findings == [] and report.follow_up_questions == []
    assert SQLDraft.model_validate({"sql": "SELECT 1", "reasoning": "r", "assumptions": None}).assumptions == []


def test_recovers_report_from_groq_tool_use_failed():
    report = recover_failed_generation(_groq_error(FAILED_ARGS), InsightReport)
    assert report is not None
    assert report.answer.startswith("In Q4 2025")
    assert report.chart.y == []


def test_recovers_from_error_text_without_body():
    exc = RuntimeError(
        "Error code: 400 - failed_generation: " + json.dumps({"name": "InsightReport", "arguments": FAILED_ARGS})
    )
    assert recover_failed_generation(exc, InsightReport) is not None


def test_unrelated_errors_are_not_swallowed():
    assert recover_failed_generation(RuntimeError("connection reset"), InsightReport) is None
    bad = _groq_error({"chart": {"type": "table"}})  # no answer -> still invalid
    assert recover_failed_generation(bad, InsightReport) is None


def test_groq_client_returns_recovered_answer_instead_of_failing():
    from app.agent.llm import GroqLLM

    class Rejecting:
        calls = 0

        def invoke(self, messages):
            Rejecting.calls += 1
            raise _groq_error(FAILED_ARGS)

    llm = GroqLLM(model="openai/gpt-oss-120b", api_key="test-key")
    llm._runnables[InsightReport] = Rejecting()
    report = llm.structured("insight", [], InsightReport)
    assert report.chart.type == "table"
    assert Rejecting.calls == 1
