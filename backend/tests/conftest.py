"""Shared fixtures.

The suite runs fully offline: a freshly seeded SQLite database is created in a
temporary directory and the LLM is replaced by ``ScriptedLLM``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="insightgraph-tests-"))
TEST_DB = _TMP / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LLM_PROVIDER"] = "scripted"
os.environ.pop("SCRIPTED_RESPONSES_PATH", None)

import pytest  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from app.agent.graph import build_graph  # noqa: E402
from app.agent.llm import ScriptedLLM  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db.database import build_engine  # noqa: E402
from app.db.seed import build_database  # noqa: E402

build_database(TEST_DB, force=True)

REVENUE_BY_REGION_SQL = """
SELECT r.name AS region,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount)), 2) AS total_revenue
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN customers c ON c.customer_id = o.customer_id
JOIN regions r ON r.region_id = c.region_id
WHERE o.status IN ('completed', 'shipped')
GROUP BY r.name
ORDER BY total_revenue DESC
"""


def intent(kind: str = "data_question", standalone: str = "What is total revenue by region?") -> dict:
    return {"intent": kind, "standalone_question": standalone, "reason": "test"}


def tables(*names: str) -> dict:
    return {"tables": list(names), "reason": "test"}


def sql(query: str, reasoning: str = "test query") -> dict:
    return {"sql": query, "reasoning": reasoning, "assumptions": []}


def insight(chart_type: str = "bar", x: str | None = "region", y: list[str] | None = None) -> dict:
    return {
        "answer": "North America leads revenue.",
        "key_findings": ["North America is first"],
        "chart": {"type": chart_type, "x": x, "y": y if y is not None else ["total_revenue"], "title": "Revenue"},
        "follow_up_questions": ["Show it by month"],
    }


@pytest.fixture(scope="session")
def engine():
    return build_engine(f"sqlite:///{TEST_DB}")


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def make_graph(engine, settings):
    def _make(responses: dict[str, list[dict]]):
        llm = ScriptedLLM(responses=responses)
        graph = build_graph(llm, engine, settings, checkpointer=InMemorySaver())
        return graph, llm

    return _make
