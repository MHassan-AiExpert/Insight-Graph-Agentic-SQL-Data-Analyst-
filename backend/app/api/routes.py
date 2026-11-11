"""REST + Server-Sent Events API."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import get_graph
from app.agent.llm import LLMError, get_llm
from app.agent.nodes import EXAMPLE_QUESTIONS
from app.agent.state import initial_state
from app.config import get_settings
from app.db.database import dialect_name, get_schema

router = APIRouter(prefix="/api", tags=["analyst"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000, description="Business question in plain English.")
    thread_id: str | None = Field(default=None, description="Conversation id. Omit to start a new thread.")


class AskResponse(BaseModel):
    thread_id: str
    question: str
    standalone_question: str
    status: str
    intent: str
    answer: str
    key_findings: list[str]
    sql: str
    sql_reasoning: str
    assumptions: list[str]
    selected_tables: list[str]
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    chart: dict[str, Any] | None
    follow_ups: list[str]
    attempts: int
    attempt_log: list[dict[str, Any]]
    limit_applied: bool
    truncated: bool
    exec_ms: float
    elapsed_ms: float


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}


def _payload(state: dict[str, Any], thread_id: str, elapsed_ms: float) -> dict[str, Any]:
    answered = state.get("status") == "answered"
    return AskResponse(
        thread_id=thread_id,
        question=state.get("question", ""),
        standalone_question=state.get("standalone_question", ""),
        status=state.get("status", "failed"),
        intent=state.get("intent", ""),
        answer=state.get("answer", ""),
        key_findings=state.get("key_findings") or [],
        sql=state.get("sql", "") if answered or state.get("status") == "failed" else "",
        sql_reasoning=state.get("sql_reasoning", ""),
        assumptions=state.get("assumptions") or [],
        selected_tables=state.get("selected_tables") or [],
        columns=state.get("columns") or [] if answered else [],
        rows=state.get("rows") or [] if answered else [],
        row_count=state.get("row_count", 0) if answered else 0,
        chart=state.get("chart") if answered else None,
        follow_ups=state.get("follow_ups") or [],
        attempts=state.get("attempts", 0),
        attempt_log=list(state.get("attempt_log") or []),
        limit_applied=bool(state.get("limit_applied")),
        truncated=bool(state.get("limit_applied")) and state.get("row_count", 0) >= get_settings().max_result_rows,
        exec_ms=float(state.get("exec_ms") or 0.0),
        elapsed_ms=round(elapsed_ms, 1),
    ).model_dump()


@router.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    try:
        llm = get_llm()
        provider, model, llm_ready = llm.provider, llm.model, True
    except LLMError as exc:
        provider, model, llm_ready = settings.llm_provider, settings.groq_model, False
        llm_error = str(exc)
    tables = get_schema()
    body = {
        "status": "ok" if llm_ready else "degraded",
        "llm": {"provider": provider, "model": model, "ready": llm_ready},
        "database": {"dialect": dialect_name(), "tables": len(tables)},
    }
    if not llm_ready:
        body["llm"]["error"] = llm_error
    return body


@router.get("/schema")
def schema() -> dict[str, Any]:
    return {
        "dialect": dialect_name(),
        "tables": [
            {
                "name": t.name,
                "row_count": t.row_count,
                "columns": [c.__dict__ for c in t.columns],
                "foreign_keys": t.foreign_keys,
            }
            for t in get_schema()
        ],
    }


@router.get("/examples")
def examples() -> dict[str, list[str]]:
    return {
        "questions": EXAMPLE_QUESTIONS
        + [
            "Compare Q3 2026 revenue with Q3 2025 by region",
            "What share of orders comes from each sales channel?",
            "What is the average order value by customer segment?",
            "Which 5 products had the highest return rate?",
        ]
    }


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> dict[str, Any]:
    thread_id = req.thread_id or uuid.uuid4().hex
    started = time.perf_counter()
    try:
        graph = get_graph()
        state = await run_in_threadpool(graph.invoke, initial_state(req.question), _config(thread_id))
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _payload(state, thread_id, (time.perf_counter() - started) * 1000)


@router.post("/ask/stream")
async def ask_stream(req: AskRequest) -> EventSourceResponse:
    thread_id = req.thread_id or uuid.uuid4().hex

    async def events():
        started = time.perf_counter()
        yield {"event": "start", "data": json.dumps({"thread_id": thread_id, "question": req.question})}
        try:
            graph = get_graph()
            config = _config(thread_id)
            async for chunk in graph.astream(initial_state(req.question), config, stream_mode="updates"):
                for node, update in chunk.items():
                    step = (update or {}).get("last_step")
                    if step:
                        payload = {**step, "node": node, "t_ms": round((time.perf_counter() - started) * 1000)}
                        yield {"event": "step", "data": json.dumps(payload, default=str)}
            final = graph.get_state(config).values
            result = _payload(final, thread_id, (time.perf_counter() - started) * 1000)
            yield {"event": "result", "data": json.dumps(result, default=str)}
        except LLMError as exc:
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": json.dumps({"message": f"Unexpected error: {exc}"})}

    return EventSourceResponse(events())


@router.get("/threads/{thread_id}")
def thread_history(thread_id: str) -> dict[str, Any]:
    state = get_graph().get_state(_config(thread_id))
    return {"thread_id": thread_id, "history": (state.values or {}).get("history", [])}
