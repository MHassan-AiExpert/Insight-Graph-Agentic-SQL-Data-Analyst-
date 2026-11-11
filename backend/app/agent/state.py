"""Shared state passed between LangGraph nodes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class Turn(TypedDict):
    question: str
    sql: str
    answer: str


class Step(TypedDict, total=False):
    node: str
    title: str
    detail: str
    status: Literal["done", "retry", "blocked", "error"]
    data: dict[str, Any]


class AttemptRecord(TypedDict):
    attempt: int
    sql: str
    stage: str
    error: str


class AgentState(TypedDict, total=False):
    # input
    question: str
    # routing
    standalone_question: str
    intent: str
    intent_reason: str
    # schema
    selected_tables: list[str]
    table_reason: str
    schema_context: str
    # sql generation / self-correction
    sql: str
    sql_reasoning: str
    assumptions: list[str]
    attempts: int
    last_error: str | None
    error_stage: str | None
    empty_retried: bool
    attempt_log: list[AttemptRecord]
    # execution
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    limit_applied: bool
    exec_ms: float
    # output
    answer: str
    key_findings: list[str]
    chart: dict[str, Any] | None
    follow_ups: list[str]
    status: Literal["answered", "chat", "refused", "failed"]
    last_step: Step
    # memory (persisted per thread by the checkpointer)
    history: list[Turn]


def initial_state(question: str) -> AgentState:
    """Fresh per-turn state. ``history`` is intentionally absent so the
    checkpointer keeps the conversation memory of the thread."""
    return AgentState(
        question=question.strip(),
        standalone_question="",
        intent="",
        intent_reason="",
        selected_tables=[],
        table_reason="",
        schema_context="",
        sql="",
        sql_reasoning="",
        assumptions=[],
        attempts=0,
        last_error=None,
        error_stage=None,
        empty_retried=False,
        attempt_log=[],
        columns=[],
        rows=[],
        row_count=0,
        limit_applied=False,
        exec_ms=0.0,
        answer="",
        key_findings=[],
        chart=None,
        follow_ups=[],
    )
