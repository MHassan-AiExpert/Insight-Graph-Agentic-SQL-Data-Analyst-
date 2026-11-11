"""LangGraph node implementations.

Each node receives the current ``AgentState`` and returns a partial update.
Every update also carries ``last_step`` — a human-readable description of what
the node did — which the API streams to the UI as a live trace.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Engine

from app.agent.llm import LLMClient
from app.agent.prompts import DATE_HINTS, INSIGHT_PROMPT, INTENT_PROMPT, SQL_PROMPT, TABLE_PROMPT
from app.agent.schemas import InsightReport, IntentDecision, SQLDraft, TableSelection
from app.agent.state import AgentState, Step
from app.config import Settings
from app.db.database import (
    QueryExecutionError,
    TableInfo,
    dialect_name,
    execute_readonly,
    get_schema,
    render_schema_context,
)
from app.services.charts import validate_chart
from app.services.sql_guard import SQLValidationError, looks_destructive, validate_sql

EXAMPLE_QUESTIONS = [
    "What is total revenue by region?",
    "Show monthly revenue for 2026 as a trend",
    "Who are the top 10 customers by lifetime value?",
    "Which product categories have the highest gross margin?",
]


def _step(node: str, title: str, detail: str = "", status: str = "done", **data: Any) -> Step:
    return Step(node=node, title=title, detail=detail, status=status, data=data)  # type: ignore[typeddict-item]


def _history_text(state: AgentState, limit: int) -> str:
    turns = (state.get("history") or [])[-limit:]
    if not turns:
        return "(no previous questions)"
    return "\n".join(f"Q: {t['question']}\nSQL: {t['sql'] or '-'}\nA: {t['answer']}" for t in turns)


def _rows_preview(columns: list[str], rows: list[list[Any]], limit: int) -> str:
    lines = [" | ".join(columns)]
    for row in rows[:limit]:
        lines.append(" | ".join("" if v is None else str(v) for v in row))
    return "\n".join(lines)


class AnalystNodes:
    """Container for all node callables with their dependencies injected."""

    def __init__(self, llm: LLMClient, engine: Engine, settings: Settings):
        self.llm = llm
        self.engine = engine
        self.settings = settings
        self.dialect = dialect_name(engine)

    # -- helpers -----------------------------------------------------------
    @property
    def schema(self) -> tuple[TableInfo, ...]:
        return get_schema(self.engine)

    @property
    def table_names(self) -> list[str]:
        return [t.name for t in self.schema]

    def _connect_tables(self, selected: list[str]) -> list[str]:
        """Add bridge tables so every selected pair can be joined via foreign keys."""
        links: dict[str, set[str]] = {t.name: set() for t in self.schema}
        for t in self.schema:
            for fk in t.foreign_keys:
                links[t.name].add(fk["references_table"])
                links.setdefault(fk["references_table"], set()).add(t.name)

        def shortest_path(start: str, goal: str) -> list[str]:
            frontier, seen = [[start]], {start}
            while frontier:
                path = frontier.pop(0)
                if path[-1] == goal:
                    return path
                for nxt in sorted(links.get(path[-1], set())):
                    if nxt not in seen:
                        seen.add(nxt)
                        frontier.append(path + [nxt])
            return []

        result = list(dict.fromkeys(selected))
        anchor = result[0] if result else None
        for target in list(result[1:]):
            for table in shortest_path(anchor, target):
                if table not in result:
                    result.append(table)
        return result

    # -- nodes -------------------------------------------------------------
    def classify_intent(self, state: AgentState) -> dict[str, Any]:
        question = state["question"]
        if looks_destructive(question):
            return {
                "intent": "unsafe",
                "standalone_question": question,
                "intent_reason": "The request asks to modify or delete data; this assistant is read-only.",
                "last_step": _step(
                    "classify_intent",
                    "Request blocked",
                    "Data-modifying request detected by the safety pre-check.",
                    "blocked",
                    intent="unsafe",
                ),
            }
        decision = self.llm.structured(
            "intent",
            INTENT_PROMPT.format_messages(
                dialect=self.dialect,
                table_list=", ".join(self.table_names),
                history=_history_text(state, self.settings.history_turns),
                question=question,
            ),
            IntentDecision,
            key=question,
        )
        standalone = decision.standalone_question.strip() or question
        status = "blocked" if decision.intent == "unsafe" else "done"
        title = {
            "data_question": "Understood the question",
            "small_talk": "Conversational message",
            "unsafe": "Request blocked",
            "out_of_scope": "Outside the data scope",
        }[decision.intent]
        return {
            "intent": decision.intent,
            "standalone_question": standalone,
            "intent_reason": decision.reason,
            "last_step": _step(
                "classify_intent",
                title,
                decision.reason,
                status,
                intent=decision.intent,
                standalone_question=standalone,
            ),
        }

    def select_tables(self, state: AgentState) -> dict[str, Any]:
        catalog = "\n".join(f"- {t.name}: {', '.join(c.name for c in t.columns)}" for t in self.schema)
        selection = self.llm.structured(
            "tables",
            TABLE_PROMPT.format_messages(catalog=catalog, question=state["standalone_question"]),
            TableSelection,
            key=state["question"],
        )
        valid = {n.lower(): n for n in self.table_names}
        chosen = [valid[t.lower()] for t in selection.tables if t.lower() in valid]
        if not chosen:
            chosen = list(self.table_names)
        chosen = self._connect_tables(chosen)
        tables = [t for t in self.schema if t.name in chosen]
        return {
            "selected_tables": chosen,
            "table_reason": selection.reason,
            "schema_context": render_schema_context(tables),
            "last_step": _step(
                "select_tables",
                f"Selected {len(chosen)} table{'s' if len(chosen) != 1 else ''}",
                selection.reason,
                tables=chosen,
            ),
        }

    def generate_sql(self, state: AgentState) -> dict[str, Any]:
        attempt = state.get("attempts", 0) + 1
        feedback = ""
        if state.get("last_error"):
            feedback = (
                f"\n\nYour previous query failed ({state.get('error_stage')}).\n"
                f"Previous SQL:\n{state.get('sql')}\n"
                f"Problem: {state['last_error']}\n"
                "Write a corrected query."
            )
        draft = self.llm.structured(
            "sql",
            SQL_PROMPT.format_messages(
                dialect=self.dialect,
                date_hint=DATE_HINTS.get(self.dialect, ""),
                max_rows=self.settings.max_result_rows,
                business_rules=self.settings.business_rules,
                schema=state["schema_context"],
                history=_history_text(state, self.settings.history_turns),
                question=state["standalone_question"],
                feedback=feedback,
            ),
            SQLDraft,
            key=state["question"],
        )
        title = "Generated SQL" if attempt == 1 else f"Rewrote SQL (attempt {attempt})"
        return {
            "sql": draft.sql.strip(),
            "sql_reasoning": draft.reasoning,
            "assumptions": draft.assumptions,
            "attempts": attempt,
            "last_error": None,
            "error_stage": None,
            "last_step": _step(
                "generate_sql",
                title,
                draft.reasoning,
                sql=draft.sql.strip(),
                attempt=attempt,
                assumptions=draft.assumptions,
            ),
        }

    def validate(self, state: AgentState) -> dict[str, Any]:
        try:
            checked = validate_sql(
                state["sql"], self.table_names, dialect=self.dialect, max_rows=self.settings.max_result_rows
            )
        except SQLValidationError as exc:
            log = list(state.get("attempt_log") or [])
            log.append({"attempt": state["attempts"], "sql": state["sql"], "stage": "validation", "error": str(exc)})
            return {
                "last_error": str(exc),
                "error_stage": "validation",
                "attempt_log": log,
                "last_step": _step("validate_sql", "Safety check failed", str(exc), "retry", attempt=state["attempts"]),
            }
        detail = "Read-only SELECT, known tables only"
        if checked.limit_applied:
            detail += f", row limit {self.settings.max_result_rows} applied"
        return {
            "sql": checked.sql,
            "limit_applied": checked.limit_applied,
            "last_step": _step("validate_sql", "Passed safety checks", detail + ".", sql=checked.sql),
        }

    def execute(self, state: AgentState) -> dict[str, Any]:
        log = list(state.get("attempt_log") or [])
        try:
            result = execute_readonly(state["sql"], self.engine, self.settings.query_timeout_seconds)
        except QueryExecutionError as exc:
            log.append({"attempt": state["attempts"], "sql": state["sql"], "stage": "execution", "error": str(exc)})
            return {
                "last_error": str(exc),
                "error_stage": "execution",
                "attempt_log": log,
                "last_step": _step("execute_sql", "Query failed", str(exc), "retry", attempt=state["attempts"]),
            }
        update: dict[str, Any] = {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count,
            "exec_ms": round(result.elapsed_ms, 1),
        }
        can_retry = state["attempts"] < self.settings.max_sql_attempts
        if result.row_count == 0 and not state.get("empty_retried") and can_retry:
            message = (
                "The query ran but returned 0 rows. Check filter values (exact spelling and case of text values, "
                "date formats and ranges) against the sample data."
            )
            log.append({"attempt": state["attempts"], "sql": state["sql"], "stage": "empty_result", "error": message})
            update.update(
                last_error=message,
                error_stage="empty_result",
                empty_retried=True,
                attempt_log=log,
                last_step=_step("execute_sql", "No rows returned", message, "retry", attempt=state["attempts"]),
            )
            return update
        update["last_step"] = _step(
            "execute_sql",
            f"Returned {result.row_count} row{'s' if result.row_count != 1 else ''}",
            f"Executed on a read-only connection in {result.elapsed_ms:.0f} ms.",
            rows=result.row_count,
            ms=round(result.elapsed_ms, 1),
        )
        return update

    def analyze(self, state: AgentState) -> dict[str, Any]:
        columns, rows = state.get("columns") or [], state.get("rows") or []
        if not rows:
            answer = (
                "The query ran successfully but no records match this question. "
                "Try widening the date range or removing a filter."
            )
            return {
                "answer": answer,
                "key_findings": [],
                "chart": {"type": "table", "x": None, "y": [], "title": ""},
                "follow_ups": EXAMPLE_QUESTIONS[:2],
                "status": "answered",
                "last_step": _step("analyze_results", "No matching data", answer),
            }
        shown = min(len(rows), self.settings.rows_for_analysis)
        report = self.llm.structured(
            "insight",
            INSIGHT_PROMPT.format_messages(
                columns=json.dumps(columns),
                question=state["standalone_question"],
                sql=state["sql"],
                row_count=len(rows),
                shown=shown,
                rows=_rows_preview(columns, rows, shown),
            ),
            InsightReport,
            key=state["question"],
        )
        chart = validate_chart(report.chart.model_dump(), columns, rows)
        return {
            "answer": report.answer,
            "key_findings": report.key_findings[:4],
            "chart": chart,
            "follow_ups": report.follow_up_questions[:3],
            "status": "answered",
            "last_step": _step(
                "analyze_results", "Wrote insights", f"Recommended a {chart['type']} chart.", chart=chart
            ),
        }

    def respond_direct(self, state: AgentState) -> dict[str, Any]:
        intent = state.get("intent")
        if intent == "unsafe":
            answer = (
                "I can't do that. I only have read-only access, so I never insert, update or delete data. "
                "I can analyse it for you instead. Try one of the questions below."
            )
            status = "refused"
        elif intent == "out_of_scope":
            answer = (
                "That question isn't something the connected database can answer. I work with the tables "
                f"{', '.join(self.table_names)}. Try one of the questions below."
            )
            status = "chat"
        else:
            answer = (
                "Hi! I'm InsightGraph, your data analyst. Ask me a business question in plain English and I'll "
                "write the SQL, check it for safety, run it, chart the result and explain what it means. "
                "Try one of the questions below."
            )
            status = "chat"
        return {
            "answer": answer,
            "status": status,
            "follow_ups": EXAMPLE_QUESTIONS[:3],
            "last_step": _step("respond_direct", "Replied without querying", state.get("intent_reason", "")),
        }

    def give_up(self, state: AgentState) -> dict[str, Any]:
        answer = (
            f"I couldn't produce a working query after {state.get('attempts', 0)} attempts. "
            f"The last problem was: {state.get('last_error')} "
            "Try rephrasing the question or naming the exact metric and time period you need."
        )
        return {
            "answer": answer,
            "status": "failed",
            "chart": None,
            "last_step": _step("give_up", "Stopped after maximum attempts", state.get("last_error") or "", "error"),
        }

    def finalize(self, state: AgentState) -> dict[str, Any]:
        history = list(state.get("history") or [])
        history.append(
            {
                "question": state.get("standalone_question") or state["question"],
                "sql": state.get("sql", "") if state.get("status") == "answered" else "",
                "answer": (state.get("answer") or "")[:400],
            }
        )
        return {
            "history": history[-self.settings.history_turns :],
            "last_step": _step(
                "finalize", "Saved to conversation memory", "Follow-up questions can refer to this answer."
            ),
        }

    # -- routing -----------------------------------------------------------
    @staticmethod
    def route_intent(state: AgentState) -> str:
        return "select_tables" if state.get("intent") == "data_question" else "respond_direct"

    def route_after_validation(self, state: AgentState) -> str:
        if not state.get("last_error"):
            return "execute_sql"
        return "generate_sql" if state["attempts"] < self.settings.max_sql_attempts else "give_up"

    def route_after_execution(self, state: AgentState) -> str:
        if not state.get("last_error"):
            return "analyze_results"
        if state["attempts"] < self.settings.max_sql_attempts:
            return "generate_sql"
        return "give_up"
