# Module Report 08 — API Layer

**Files:** `backend/app/api/routes.py`, `backend/app/main.py`
**Depends on:** FastAPI, sse-starlette, Pydantic v2
**Used by:** the React frontend and any HTTP client

## 1. Purpose

Exposes the agent over HTTP with typed request and response models, streams the agent's progress in real time, and serves the built React app from the same server.

## 2. How it works

### 2.1 Endpoints

| Method | Path | Behaviour |
|--------|------|-----------|
| `GET` | `/api/health` | LLM provider, model and readiness (`degraded` with the reason if the key is missing), database dialect and table count |
| `GET` | `/api/schema` | Tables with columns, PK/FK flags and row counts (feeds the schema explorer) |
| `GET` | `/api/examples` | 8 suggested questions |
| `POST` | `/api/ask` | Runs the whole graph (in a thread pool, so the event loop stays free) and returns `AskResponse` |
| `POST` | `/api/ask/stream` | Same, streamed as Server-Sent Events |
| `GET` | `/api/threads/{id}` | The thread's conversation memory from the checkpointer |

`AskRequest` validates input: `question` must be 1–1000 characters, and `thread_id` is optional (a new UUID is created if it is missing).

### 2.2 Streaming flow (`/api/ask/stream`)

```
event: start   {thread_id, question}
event: step    {node, title, detail, status, data, t_ms}     ← one per graph node, as it finishes
...
event: result  {full AskResponse}
(or)
event: error   {message}                                       ← LLM provider failure or unexpected error
```

The generator iterates `graph.astream(..., stream_mode="updates")`. Each update holds the node's `last_step`, which is forwarded with the elapsed time. At the end the final state is read from the checkpointer and serialised.

### 2.3 Response shaping (`_payload`)

- Rows, columns and the chart are included only when `status == "answered"`. A refused request therefore never returns data or SQL.
- `truncated` is true only when a LIMIT was applied **and** the row cap was reached, so the UI only warns when rows were actually cut off.

### 2.4 Application factory (`main.py`)

- **Lifespan:** if the default SQLite database is missing, it is seeded (first Docker run).
- **CORS:** from `CORS_ORIGINS` (the Vite dev server by default).
- **SPA hosting:** if `frontend/dist` exists, `/assets` is mounted and any other path returns `index.html`. The file lookup is resolved and checked to stay inside `dist`, which blocks path traversal.

## 3. How it was built

| Decision | Alternatives | Why |
|----------|--------------|-----|
| Server-Sent Events | WebSockets, polling | One-way server-to-client updates are exactly what is needed; SSE works over plain HTTP and through proxies |
| POST for streaming | GET with query string | Questions can be long and should not end up in URLs or server logs |
| Pydantic response model | Raw dicts | The contract is typed and documented automatically in OpenAPI at `/docs` |
| One server for API and UI | Separate frontend hosting | Single container, one port, no CORS in production |
| Errors as SSE events | Dropping the connection | The UI can show a readable message in the answer card |

## 4. Test cases

File: `backend/tests/test_api.py` (FastAPI `TestClient` with a scripted graph and a real database)

| ID | Test | What it checks | Result |
|----|------|----------------|--------|
| API-01 | `test_health` | Dialect `sqlite`, 5 tables, provider reported | ✅ Pass |
| API-02 | `test_schema` | Tables in alphabetical order; `orders` row count 5,200 | ✅ Pass |
| API-03 | `test_examples` | At least 6 suggested questions | ✅ Pass |
| API-04 | `test_ask_returns_full_answer` | status `answered`, 5 rows, correct columns, bar chart, thread id, SQL starts with SELECT | ✅ Pass |
| API-05 | `test_ask_rejects_empty_question` | Empty question → HTTP 422 | ✅ Pass |
| API-06 | `test_destructive_question_is_refused` | "Drop the orders table" → `refused`, no rows, no SQL | ✅ Pass |
| API-07 | `test_stream_emits_steps_then_result` | First event `start`, last `result`; steps arrive in node order; result has 5 rows | ✅ Pass |
| API-08 | `test_thread_history` | After one question, `/api/threads/{id}` returns 1 turn with SQL | ✅ Pass |

### Manual checks on the running server

| Check | Result |
|-------|--------|
| `curl -N` on `/api/ask/stream` shows events arriving one by one | ✅ Pass |
| Built SPA served at `/`, deep links fall back to `index.html` | ✅ Pass |
| `/docs` returns 200 and the OpenAPI spec lists all 6 endpoints | ✅ Pass |
| Path traversal (`/../../etc/passwd`, `%2e%2e` encoded) returns the SPA page, never a file outside `dist` | ✅ Pass |

**Result: 8 / 8 automated tests passed.**
