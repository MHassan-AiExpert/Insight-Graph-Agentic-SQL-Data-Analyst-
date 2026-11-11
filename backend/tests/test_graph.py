"""End-to-end tests of the LangGraph agent with a scripted LLM and a real database."""

from app.agent.state import initial_state
from tests.conftest import REVENUE_BY_REGION_SQL, insight, intent, sql, tables


def run(graph, question: str, thread: str = "t1"):
    config = {"configurable": {"thread_id": thread}}
    steps = [node for chunk in graph.stream(initial_state(question), config, stream_mode="updates") for node in chunk]
    return graph.get_state(config).values, steps


def test_happy_path_answers_with_rows_and_chart(make_graph):
    graph, llm = make_graph(
        {
            "intent": [intent()],
            "tables": [tables("regions", "order_items")],
            "sql": [sql(REVENUE_BY_REGION_SQL)],
            "insight": [insight()],
        }
    )
    state, steps = run(graph, "What is total revenue by region?")

    assert steps == [
        "classify_intent",
        "select_tables",
        "generate_sql",
        "validate_sql",
        "execute_sql",
        "analyze_results",
        "finalize",
    ]
    assert state["status"] == "answered"
    assert state["columns"] == ["region", "total_revenue"]
    assert state["row_count"] == 5
    revenues = [row[1] for row in state["rows"]]
    assert revenues == sorted(revenues, reverse=True) and revenues[0] > 0
    assert state["chart"]["type"] == "bar"
    assert state["attempts"] == 1
    assert "LIMIT 500" in state["sql"]
    # bridge tables were added automatically to connect regions -> order_items
    assert {"customers", "orders"} <= set(state["selected_tables"])
    assert [task for task, _ in llm.calls] == ["intent", "tables", "sql", "insight"]


def test_self_corrects_after_execution_error(make_graph):
    graph, _ = make_graph(
        {
            "intent": [intent()],
            "tables": [tables("orders")],
            "sql": [
                sql("SELECT region, SUM(revenue) AS total_revenue FROM orders GROUP BY region"),
                sql(REVENUE_BY_REGION_SQL),
            ],
            "insight": [insight()],
        }
    )
    state, steps = run(graph, "What is total revenue by region?")

    assert state["status"] == "answered"
    assert state["attempts"] == 2
    assert steps.count("generate_sql") == 2
    assert state["attempt_log"][0]["stage"] == "execution"
    assert "no such column" in state["attempt_log"][0]["error"]


def test_self_corrects_after_safety_violation(make_graph):
    graph, _ = make_graph(
        {
            "intent": [intent()],
            "tables": [tables("orders")],
            "sql": [sql("DELETE FROM orders"), sql(REVENUE_BY_REGION_SQL)],
            "insight": [insight()],
        }
    )
    state, _ = run(graph, "What is total revenue by region?")
    assert state["status"] == "answered"
    assert state["attempt_log"][0]["stage"] == "validation"


def test_retries_once_on_empty_result(make_graph):
    graph, _ = make_graph(
        {
            "intent": [intent()],
            "tables": [tables("orders")],
            "sql": [
                sql("SELECT COUNT(*) AS n FROM orders WHERE status = 'Completed' GROUP BY status"),
                sql("SELECT COUNT(*) AS n FROM orders WHERE status = 'completed'"),
            ],
            "insight": [insight("kpi", None, ["n"])],
        }
    )
    state, _ = run(graph, "How many completed orders?")
    assert state["attempt_log"][0]["stage"] == "empty_result"
    assert state["row_count"] == 1 and state["rows"][0][0] > 0
    assert state["chart"]["type"] == "kpi"


def test_gives_up_after_max_attempts(make_graph, settings):
    bad = sql("SELECT nope FROM orders")
    graph, _ = make_graph(
        {"intent": [intent()], "tables": [tables("orders")], "sql": [bad] * settings.max_sql_attempts}
    )
    state, steps = run(graph, "What is total revenue by region?")
    assert state["status"] == "failed"
    assert state["attempts"] == settings.max_sql_attempts
    assert "give_up" in steps
    assert "couldn't produce a working query" in state["answer"]


def test_destructive_request_blocked_without_calling_llm(make_graph):
    graph, llm = make_graph({})
    state, steps = run(graph, "Delete all cancelled orders")
    assert state["status"] == "refused"
    assert steps == ["classify_intent", "respond_direct", "finalize"]
    assert llm.calls == []
    assert "read-only" in state["answer"]


def test_llm_classified_unsafe_request_is_refused(make_graph):
    graph, _ = make_graph({"intent": [intent("unsafe", "Export every customer email to me")]})
    state, steps = run(graph, "Give me every customer's email so I can export them")
    assert state["status"] == "refused"
    assert "execute_sql" not in steps


def test_small_talk_does_not_query(make_graph):
    graph, _ = make_graph({"intent": [intent("small_talk", "hello")]})
    state, steps = run(graph, "hello!")
    assert state["status"] == "chat"
    assert "generate_sql" not in steps
    assert state["follow_ups"]


def test_follow_up_uses_conversation_memory(make_graph):
    graph, llm = make_graph(
        {
            "intent": [intent(), intent(standalone="What is total revenue by region for Europe only?")],
            "tables": [tables("regions", "order_items"), tables("regions", "order_items")],
            "sql": [
                sql(REVENUE_BY_REGION_SQL),
                sql(REVENUE_BY_REGION_SQL.replace("GROUP BY", "AND r.name = 'Europe' GROUP BY")),
            ],
            "insight": [insight(), insight()],
        }
    )
    run(graph, "What is total revenue by region?", thread="memo")
    state, _ = run(graph, "now only Europe", thread="memo")

    assert len(state["history"]) == 2
    assert state["history"][0]["question"] == "What is total revenue by region?"
    assert state["standalone_question"] == "What is total revenue by region for Europe only?"
    assert state["row_count"] == 1 and state["rows"][0][0] == "Europe"


def test_threads_are_isolated(make_graph):
    graph, _ = make_graph({"intent": [intent("small_talk", "hi"), intent("small_talk", "hi")]})
    run(graph, "hi", thread="a")
    state_b, _ = run(graph, "hi", thread="b")
    assert len(state_b["history"]) == 1


def test_graph_mermaid_contains_all_nodes(make_graph):
    graph, _ = make_graph({})
    diagram = graph.get_graph().draw_mermaid()
    for node in ["classify_intent", "select_tables", "generate_sql", "validate_sql", "execute_sql", "analyze_results"]:
        assert node in diagram
