# InsightGraph — System Features

## F1. Natural-language questions to verified SQL
- Ask business questions in plain English; the agent produces a single read-only SQL query in the database's dialect (SQLite or PostgreSQL).
- LangChain structured output returns the SQL together with the **reasoning** behind it and the **business assumptions** it made (e.g. how revenue is defined).
- Central business definitions (revenue, gross profit, AOV, quarters) keep every answer consistent.

## F2. Intent routing and guardrails
- Every message is classified as a data question, small talk, unsafe, or out of scope.
- Destructive requests ("delete…", "drop…", "update prices…") are refused by a deterministic pre-check before the model is called.
- Unsafe or out-of-scope messages never reach the SQL generator.

## F3. Smart schema selection
- The database is introspected live: tables, column types, primary and foreign keys, row counts and sample rows.
- The model selects only the relevant tables, and a foreign-key path search adds any bridge tables needed for the joins automatically.
- Smaller prompts mean faster and more accurate SQL on larger schemas.

## F4. Multi-layer SQL safety
- sqlglot parses every query into an AST and enforces: one statement, SELECT/UNION/WITH root, no write/DDL/PRAGMA/ATTACH/SET nodes (including inside CTEs), known tables only, and no dangerous functions.
- A row `LIMIT` is always applied (added or capped).
- Queries run on a read-only connection with a statement timeout.

## F5. Self-correcting agent loop
- SQL errors, safety violations and empty results are fed back to the model with the failing query and the exact error message.
- Up to 3 attempts (configurable); each retry is visible in the UI and recorded in the attempt log.
- The agent stops cleanly with an explanation instead of looping when it cannot recover.

## F6. Insight generation and automatic charts
- A plain-language answer that cites the actual numbers, up to 4 key findings, and up to 3 follow-up questions.
- Chart recommendation: line (time series), bar (comparisons, multi-series), pie (share of total), KPI cards (single values), or table.
- The model's chart choice is validated against the real result columns; a deterministic recommender takes over if the choice is invalid.

## F7. Conversational memory
- Each conversation is a LangGraph thread with checkpointed state.
- Follow-ups like "Now only for Europe" are rewritten into standalone questions using the previous turns; the UI shows how the question was interpreted.
- Threads are isolated; history can be retrieved with `GET /api/threads/{id}`.

## F8. Real-time transparency
- Server-Sent Events stream every graph step as it happens.
- The UI shows a six-stage pipeline (Understand → Pick tables → Write SQL → Safety check → Run query → Explain), a self-correction badge, and an expandable timed reasoning trace.
- A "How it was built" tab lists the approach, tables used, assumptions, attempts and the errors that were fixed.

## F9. Results workspace
- Sortable, paginated results table with number, currency and percentage formatting.
- One-click CSV download of the full result set.
- Syntax-highlighted SQL viewer with copy button.
- Schema explorer sidebar with row counts and PK/FK markers.

## F10. Engineering quality
- 118 automated tests (99 backend: unit, graph, API and golden scenarios; 19 frontend component and client tests) that run without network or API key.
- GitHub Actions CI: lint, backend tests, frontend tests, type-check and build, Docker build.
- Single-command deployment with Docker Compose; FastAPI serves both the API and the built React app.
- Pluggable LLM provider and database through environment variables.
