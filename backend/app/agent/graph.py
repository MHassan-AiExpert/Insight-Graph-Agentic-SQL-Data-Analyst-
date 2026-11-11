"""Builds the InsightGraph LangGraph state machine.

START
  └─ classify_intent ──┬─(data_question)──► select_tables ─► generate_sql ─► validate_sql
                       │                                         ▲              │ ok
                       │                         (retry ≤ N) ────┤              ▼
                       │                                         └──────── execute_sql
                       │                                                        │ rows
                       └─(small_talk / unsafe / out_of_scope)─► respond_direct   ▼
                                                                     │     analyze_results
                                      give_up ◄─(attempts exhausted)  │          │
                                         └──────────────► finalize ◄─┴──────────┘ ─► END
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine

from app.agent.llm import LLMClient, get_llm
from app.agent.nodes import AnalystNodes
from app.agent.state import AgentState
from app.config import Settings, get_settings
from app.db.database import get_engine

NODE_ORDER = [
    "classify_intent",
    "select_tables",
    "generate_sql",
    "validate_sql",
    "execute_sql",
    "analyze_results",
    "respond_direct",
    "give_up",
    "finalize",
]


def build_graph(
    llm: LLMClient,
    engine: Engine,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    settings = settings or get_settings()
    nodes = AnalystNodes(llm, engine, settings)

    graph = StateGraph(AgentState)
    graph.add_node("classify_intent", nodes.classify_intent)
    graph.add_node("select_tables", nodes.select_tables)
    graph.add_node("generate_sql", nodes.generate_sql)
    graph.add_node("validate_sql", nodes.validate)
    graph.add_node("execute_sql", nodes.execute)
    graph.add_node("analyze_results", nodes.analyze)
    graph.add_node("respond_direct", nodes.respond_direct)
    graph.add_node("give_up", nodes.give_up)
    graph.add_node("finalize", nodes.finalize)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges("classify_intent", nodes.route_intent, ["select_tables", "respond_direct"])
    graph.add_edge("select_tables", "generate_sql")
    graph.add_edge("generate_sql", "validate_sql")
    graph.add_conditional_edges(
        "validate_sql", nodes.route_after_validation, ["execute_sql", "generate_sql", "give_up"]
    )
    graph.add_conditional_edges(
        "execute_sql", nodes.route_after_execution, ["analyze_results", "generate_sql", "give_up"]
    )
    graph.add_edge("analyze_results", "finalize")
    graph.add_edge("respond_direct", "finalize")
    graph.add_edge("give_up", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer or InMemorySaver())


@lru_cache
def get_graph():
    return build_graph(get_llm(), get_engine(), get_settings())
