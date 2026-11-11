# InsightGraph — Test Cases

## Test strategy

Per-module details (how each module works, how it was built, and its test cases) are in [`../reports`](../reports).

| Level | File | Count | What it proves |
|-------|------|------:|----------------|
| Unit — configuration | `backend/tests/test_config.py` | 4 | Defaults, overrides, CORS parsing, business rules |
| Unit — data generator | `backend/tests/test_seed.py` | 5 | Determinism, counts, integrity, constraints |
| Unit — LLM layer | `backend/tests/test_llm.py` | 9 | Scripted provider, schema validation, Groq client, prompts |
| Unit — SQL guard | `backend/tests/test_sql_guard.py` | 27 | Read-only enforcement, LIMIT handling, intent pre-check |
| Unit — database | `backend/tests/test_database.py` | 9 | Introspection, read-only connection, timeout, error messages |
| Unit — charts | `backend/tests/test_charts.py` | 9 | Chart recommendation and validation |
| Integration — graph | `backend/tests/test_graph.py` | 11 | Routing, self-correction, give-up, memory, thread isolation |
| Integration — API | `backend/tests/test_api.py` | 8 | REST + SSE contract, validation, history |
| Regression — golden scenarios | `backend/tests/test_scenarios.py` | 10 | Seven realistic business questions end-to-end against the real database |
| Frontend — unit and component | `frontend/src/__tests__/*` | 19 | Formatting, chart pivoting, SSE parsing, Pipeline, ResultsTable, Composer |
| **Total** | | **111** | |

All tests run offline. A fresh database is seeded into a temporary directory and the language model is replaced with `ScriptedLLM`, which replays predefined structured responses. The real graph, guard and database code paths still run on every test.

```bash
cd backend
pip install -r requirements-dev.txt
pytest            # 92 passed
cd ../frontend && npm test   # 19 passed
ruff check .
```

## Functional test cases

| ID | Feature | Scenario | Steps | Expected result | Automated in |
|----|---------|----------|-------|-----------------|--------------|
| TC-01 | F1, F6 | Category comparison | Ask "What is total revenue by region?" | 5 rows sorted by revenue, bar chart, attempts = 1, `LIMIT 500` added | `test_happy_path_answers_with_rows_and_chart`, scenario `total revenue by region` |
| TC-02 | F6 | Time series | Ask "Show monthly revenue for 2026 as a trend" | 10 monthly rows, line chart | scenario `monthly revenue for 2026` |
| TC-03 | F6 | Share of total | Ask "What share of orders comes from each sales channel?" | 3 rows, pie chart | scenario `sales channel` |
| TC-04 | F6 | Multi-series | Ask "Compare Q3 2026 revenue with Q3 2025 by region" | 5 rows, bar chart with 2 series | scenario `q3 2026` |
| TC-05 | F5 | Self-correction: execution error | First SQL references a missing column | Error logged (`execution`), second attempt succeeds, attempts = 2 | `test_self_corrects_after_execution_error`, `test_top_customers_scenario_self_corrects` |
| TC-06 | F5, F4 | Self-correction: safety violation | First SQL is `DELETE FROM orders` | Blocked at `validation`, corrected SELECT runs | `test_self_corrects_after_safety_violation` |
| TC-07 | F5 | Empty result retry | First SQL filters `status = 'Completed'` (wrong case) | Logged as `empty_result`, retried once, KPI chart | `test_retries_once_on_empty_result` |
| TC-08 | F5 | Give up | Every attempt fails | status `failed`, `give_up` node reached after 3 attempts, explanation returned | `test_gives_up_after_max_attempts` |
| TC-09 | F2 | Destructive request | Ask "Delete all cancelled orders" | Refused, no LLM call made, no SQL executed | `test_destructive_request_blocked_without_calling_llm` |
| TC-10 | F2 | LLM-classified unsafe | Ask to export every customer email | status `refused`, execution never reached | `test_llm_classified_unsafe_request_is_refused` |
| TC-11 | F2 | Small talk | Say "hello!" | Friendly reply with suggested questions, no SQL | `test_small_talk_does_not_query` |
| TC-12 | F7 | Follow-up | Ask region revenue, then "Now only for Europe" | Question rewritten, 1 Europe row, history = 2 turns | `test_follow_up_uses_conversation_memory`, `test_follow_up_scenario` |
| TC-13 | F7 | Thread isolation | Ask in thread A and thread B | Thread B has only its own history | `test_threads_are_isolated` |
| TC-14 | F3 | Join bridging | Model selects `regions` + `order_items` | `customers` and `orders` added automatically | `test_happy_path_answers_with_rows_and_chart` |
| TC-15 | F8 | SSE contract | `POST /api/ask/stream` | `start` → `step` events in node order → `result` | `test_stream_emits_steps_then_result` |
| TC-16 | API | Input validation | Empty question | HTTP 422 | `test_ask_rejects_empty_question` |
| TC-17 | API | Health and schema | `GET /api/health`, `/api/schema` | Dialect, 5 tables, row counts | `test_health`, `test_schema` |
| TC-18 | F7 | History endpoint | Ask, then `GET /api/threads/{id}` | One turn with SQL | `test_thread_history` |

## Security test cases (SQL guard and database)

| ID | Input | Expected | Layer |
|----|-------|----------|-------|
| SEC-01 | `DELETE FROM orders` | Rejected: only read-only queries | AST guard |
| SEC-02 | `UPDATE orders SET status='x'` | Rejected | AST guard |
| SEC-03 | `INSERT INTO regions VALUES (...)` | Rejected | AST guard |
| SEC-04 | `DROP TABLE orders` | Rejected | AST guard |
| SEC-05 | `PRAGMA table_info(orders)` | Rejected | AST guard |
| SEC-06 | `SELECT 1; DROP TABLE orders` | Rejected: single statement only | AST guard |
| SEC-07 | `WITH x AS (DELETE … RETURNING *) SELECT * FROM x` | Rejected: forbidden nested operation | AST guard |
| SEC-08 | `SELECT * FROM users` | Rejected: unknown table | AST guard |
| SEC-09 | `SELECT load_extension('evil') …` | Rejected: function not allowed | AST guard |
| SEC-10 | `SELECT * FROM orders LIMIT 100000` | LIMIT capped to 500 | AST guard |
| SEC-11 | Write statements sent straight to the engine | Fail on the read-only connection; data unchanged | Database |
| SEC-12 | Infinite recursive CTE | Aborted by the statement timeout | Database |
| SEC-13 | "Drop the orders table" via the API | `status = refused`, no rows, no SQL | API |

## Chart test cases

| ID | Input | Expected |
|----|-------|----------|
| CH-01 | `month, revenue` with 3+ periods | Line chart |
| CH-02 | `region, revenue` | Bar chart |
| CH-03 | Single numeric cell | KPI card |
| CH-04 | Only text columns | Table |
| CH-05 | Model references a non-existent column | Falls back to a valid recommendation |
| CH-06 | Pie with 12 slices | Converted to bar |
| CH-07 | Non-numeric column in `y` | Dropped |
| CH-08 | Long result `(region, year, revenue)` | Split into one series per year |
| CH-09 | Wide result `(region, q3_2025, q3_2026)` | Kept as two series, no pivot |

## Manual UI test checklist

| ID | Check | Result |
|----|-------|--------|
| UI-01 | Pipeline nodes turn green in order while streaming; retry shows an amber badge | Pass, see `screenshots/03-self-correction-trace.png` |
| UI-02 | Blocked request shows a red node and the "Blocked: read-only assistant" label | Pass, `screenshots/07-safety-guard.png` |
| UI-03 | Follow-up shows "Interpreted as …" | Pass, `screenshots/06-follow-up-memory.png` |
| UI-04 | Results table sorts by column and downloads CSV | Pass |
| UI-05 | Copy SQL button copies the query | Pass |
| UI-06 | Layout works at 390 px (mobile) with a collapsible schema drawer | Pass, `screenshots/10-mobile-home.png`, `11-mobile-answer.png` |
| UI-07 | Keyboard: Enter sends, Shift+Enter adds a new line, visible focus rings | Pass |
| UI-08 | API down: a clear error message is shown in the answer card | Pass |

## Latest run

```
$ pytest
92 passed

$ npm test
Test Files  4 passed (4)
     Tests  19 passed (19)
```
