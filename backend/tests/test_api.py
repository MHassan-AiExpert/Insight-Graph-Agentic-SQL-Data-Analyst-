"""API tests using FastAPI's TestClient and a scripted graph."""

import json

import pytest
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import create_app
from tests.conftest import REVENUE_BY_REGION_SQL, insight, intent, sql, tables


@pytest.fixture
def client(make_graph, monkeypatch):
    graph, _ = make_graph(
        {
            "intent": [intent()] * 3,
            "tables": [tables("regions", "order_items")] * 3,
            "sql": [sql(REVENUE_BY_REGION_SQL)] * 3,
            "insight": [insight()] * 3,
        }
    )
    monkeypatch.setattr(routes, "get_graph", lambda: graph)
    with TestClient(create_app()) as c:
        yield c


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events, current = [], {}
    for line in text.splitlines():
        if line.startswith("event:"):
            current["event"] = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line.split(":", 1)[1].strip())
        elif not line.strip() and current:
            events.append((current.get("event", "message"), current.get("data", {})))
            current = {}
    if current:
        events.append((current.get("event", "message"), current.get("data", {})))
    return events


def test_health(client):
    body = client.get("/api/health").json()
    assert body["database"] == {"dialect": "sqlite", "tables": 5}
    assert body["llm"]["provider"] == "scripted"


def test_schema(client):
    body = client.get("/api/schema").json()
    names = [t["name"] for t in body["tables"]]
    assert names == ["customers", "order_items", "orders", "products", "regions"]
    orders = next(t for t in body["tables"] if t["name"] == "orders")
    assert orders["row_count"] == 5200


def test_examples(client):
    assert len(client.get("/api/examples").json()["questions"]) >= 6


def test_ask_returns_full_answer(client):
    res = client.post("/api/ask", json={"question": "What is total revenue by region?"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "answered"
    assert body["row_count"] == 5
    assert body["columns"] == ["region", "total_revenue"]
    assert body["chart"]["type"] == "bar"
    assert body["thread_id"]
    assert body["sql"].startswith("SELECT")


def test_ask_rejects_empty_question(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422


def test_destructive_question_is_refused(client):
    body = client.post("/api/ask", json={"question": "Drop the orders table"}).json()
    assert body["status"] == "refused"
    assert body["rows"] == [] and body["sql"] == ""


def test_stream_emits_steps_then_result(client):
    res = client.post("/api/ask/stream", json={"question": "What is total revenue by region?", "thread_id": "s1"})
    assert res.status_code == 200
    events = _parse_sse(res.text)
    kinds = [e for e, _ in events]
    assert kinds[0] == "start" and kinds[-1] == "result"
    step_nodes = [d["node"] for e, d in events if e == "step"]
    assert step_nodes[:3] == ["classify_intent", "select_tables", "generate_sql"]
    assert events[-1][1]["row_count"] == 5


def test_thread_history(client):
    client.post("/api/ask", json={"question": "What is total revenue by region?", "thread_id": "h1"})
    history = client.get("/api/threads/h1").json()["history"]
    assert len(history) == 1 and history[0]["sql"]
