# InsightGraph — Project Document

**Project:** InsightGraph — Agentic SQL Data Analyst
**Author:** Muhammad Hassan — AI Automation Engineer & Full Stack Developer
**Version:** 1.0.0
**Date:** November 2026

---

## 1. Executive summary

InsightGraph lets business users ask questions about their data in plain English and get back a verified SQL query, the result set, a chart and a written explanation — in seconds and without writing SQL.

Under the hood, InsightGraph is a stateful multi-step agent built with **LangGraph** and **LangChain**. Instead of a single "prompt in, SQL out" call, the agent works the way a careful analyst does: it understands the intent, picks the relevant tables, drafts a query, checks it against strict safety rules, runs it on a read-only connection, repairs its own mistakes, and finally interprets the numbers. Every step is streamed live to a React interface so users can see exactly how each answer was produced.

## 2. Problem statement

Most business questions ("Which region grew fastest last quarter?", "Who are our top customers by lifetime value?") are answerable from data a company already owns, but:

- Non-technical teams depend on a small number of analysts to write SQL, which creates queues and slows decisions.
- Simple "text-to-SQL" tools generate queries in one shot. When the query fails or quietly returns nothing, the user has no way to know why.
- Letting an LLM run SQL directly against a database is risky: a generated `DELETE` or an unbounded `SELECT` can damage data or overload the server.
- Raw result tables do not explain themselves; users still need someone to interpret them.

## 3. Objectives

| # | Objective | Measure of success |
|---|-----------|--------------------|
| O1 | Answer natural-language questions with correct SQL | Generated query runs and answers the question; covered by graph tests |
| O2 | Never modify or overload the database | 100% of write / DDL / multi-statement queries blocked by the SQL guard; row limit always applied |
| O3 | Recover from errors automatically | Failed or empty queries are repaired by the self-correction loop (max 3 attempts) |
| O4 | Explain results, not just return them | Every answer includes a summary, key findings, chart spec and follow-up suggestions |
| O5 | Support conversational follow-ups | "Now only for Europe" resolves against the previous question in the same thread |
| O6 | Full transparency | Each graph node streams a live step to the UI (intent, tables, SQL, validation, execution, insight) |
| O7 | Production-ready engineering | Typed code, automated tests in CI (no API key required), Docker deployment |

## 4. Scope

### In scope

- Natural-language question answering over a relational database (SQLite by default, PostgreSQL via connection URL)
- LangGraph agent with intent routing, schema selection, SQL generation, validation, execution, self-correction and insight generation
- Conversation memory per thread (follow-up questions)
- FastAPI backend with REST and Server-Sent Events (SSE) streaming
- React dashboard: chat, live agent pipeline, SQL viewer, sortable results table, automatic charts, schema explorer, example questions
- Seeded e-commerce dataset (regions, customers, products, orders, order items) for out-of-the-box use
- Automated tests, GitHub Actions CI, Docker and Docker Compose

### Out of scope (v1)

- User accounts and role-based access control
- Writing data back to the database (by design the agent is read-only)
- Scheduled reports and alerting

## 5. Target users

- **Business users** (sales, marketing, operations managers) who need answers without SQL
- **Analysts** who want a fast first draft of a query they can copy and refine
- **Engineering teams** evaluating how to put an LLM safely in front of a database

## 6. Solution overview

```
User question ──► FastAPI (SSE) ──► LangGraph agent ──► Read-only database
                                       │
                                       ├─ Intent router (data / small talk / unsafe)
                                       ├─ Schema selector (relevant tables only)
                                       ├─ SQL generator (structured output)
                                       ├─ SQL guard (sqlglot AST checks + LIMIT)
                                       ├─ Executor (read-only, timeout)
                                       ├─ Self-correction loop (≤ 3 attempts)
                                       └─ Insight writer + chart recommender
                                       │
React dashboard ◄── live step events + final answer, SQL, rows, chart
```

Details: [System design](02-system-design.md) · [Features](03-system-features.md) · [Test cases](04-test-cases.md) · [UI/UX](05-ui-ux-design.md)

## 7. Technology stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Agent orchestration | LangGraph 1.x | Explicit state machine with conditional edges, loops and checkpointed memory |
| LLM framework | LangChain Core, `langchain-groq` | Prompt templates, structured output (Pydantic), provider abstraction |
| LLM | Groq — `llama-3.3-70b-versatile` (configurable) | Very low latency inference, which suits a multi-step agent |
| SQL safety | sqlglot | Parses SQL into an AST so rules are enforced on structure, not on fragile regex |
| Data access | SQLAlchemy 2 | One code path for SQLite and PostgreSQL; schema introspection |
| API | FastAPI, sse-starlette, Pydantic v2 | Typed endpoints and real-time streaming |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts | Fast, typed, component-based dashboard |
| Testing | pytest, scripted LLM, FastAPI TestClient | Deterministic tests with no network or API key |
| Delivery | Docker (multi-stage), Docker Compose, GitHub Actions | One-command run; CI on every push |

## 8. Delivery plan

| Phase | Deliverables |
|-------|--------------|
| 1. Discovery & design | Project document, system design, feature list, UI/UX spec, diagrams |
| 2. Data layer | Seeded e-commerce database, read-only engine, schema introspection |
| 3. Agent | LangGraph state, nodes, routing, SQL guard, self-correction, memory |
| 4. API | REST + SSE endpoints, thread history, health and schema endpoints |
| 5. Frontend | Chat, live pipeline, SQL viewer, results table, charts, schema explorer |
| 6. Quality | Unit, graph and API tests; CI pipeline; test-case document |
| 7. Release | Docker images, README, screenshots |

## 9. Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LLM generates destructive SQL | Data loss | AST-level guard allows only `SELECT`/`WITH`; read-only connection as a second layer |
| LLM hallucinates table/column names | Query errors | Schema context built from live introspection; unknown tables rejected; errors fed back for self-correction |
| Expensive queries | Database load | Enforced row limit, statement timeout |
| Prompt injection inside the question ("ignore rules and drop…") | Unsafe action | Deterministic keyword pre-check plus LLM intent classification; guard runs regardless of LLM output |
| LLM provider outage / rate limits | Unavailable answers | Clear error events to the UI; provider and model configurable via environment |
| Non-deterministic LLM in tests | Flaky CI | Scripted LLM implementation for tests; no network needed |

## 10. Acceptance criteria

1. Asking "What is total revenue by region?" returns a valid SQL query, a results table, a bar chart and a written summary.
2. Asking "Delete all cancelled orders" is refused and no query is executed.
3. A query that fails (e.g. wrong column) is automatically corrected on a later attempt, visible as a retry step in the UI.
4. A follow-up such as "Now show only 2026" uses the context of the previous question.
5. All automated tests pass in CI without any API key.
6. `docker compose up` starts the full application on one port.
