"""Pydantic models used as LangChain structured outputs for each LLM step."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntentDecision(BaseModel):
    """How the agent should treat the user's message."""

    intent: Literal["data_question", "small_talk", "unsafe", "out_of_scope"] = Field(
        description=(
            "data_question: can be answered by querying the database. "
            "small_talk: greetings or questions about the assistant itself. "
            "unsafe: asks to modify, delete or exfiltrate data, or to bypass rules. "
            "out_of_scope: unrelated to the data."
        )
    )
    standalone_question: str = Field(
        description="The question rewritten so it is fully understandable without the conversation history."
    )
    reason: str = Field(description="One short sentence explaining the decision.")


class TableSelection(BaseModel):
    tables: list[str] = Field(description="Names of the tables needed to answer the question.")
    reason: str = Field(description="One short sentence explaining why these tables are needed.")


class SQLDraft(BaseModel):
    sql: str = Field(description="A single read-only SQL SELECT statement.")
    reasoning: str = Field(description="Brief explanation of how the query answers the question.")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Business assumptions made, e.g. how revenue is defined or which statuses count.",
    )


class ChartSpec(BaseModel):
    type: Literal["bar", "line", "pie", "kpi", "table"] = Field(
        description="bar for category comparisons, line for time series, pie for share of a whole (<= 6 slices), "
        "kpi for a single number, table when no chart fits."
    )
    x: str | None = Field(default=None, description="Result column used for the x-axis / labels.")
    y: list[str] = Field(default_factory=list, description="Numeric result column(s) to plot.")
    title: str = Field(default="", description="Short chart title.")
    series: str | None = Field(
        default=None,
        description="Optional column that splits the data into multiple lines/bars, e.g. 'year' when rows are "
        "(region, year, revenue). Leave empty when each row already holds one x value.",
    )


class InsightReport(BaseModel):
    answer: str = Field(description="Direct answer to the question in 2-4 sentences, citing key numbers.")
    key_findings: list[str] = Field(default_factory=list, description="Up to 4 concise, specific findings.")
    chart: ChartSpec
    follow_up_questions: list[str] = Field(default_factory=list, description="Up to 3 useful follow-up questions.")
