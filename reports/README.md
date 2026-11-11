# Module Reports

One report per module of InsightGraph. Each report explains:

1. **What the module does** and where it sits in the system
2. **How it works**, step by step
3. **How it was built**: design decisions, alternatives considered and why the final approach was chosen
4. **Test cases**: every automated test that covers the module, what it checks and its result

| # | Module | Code | Tests | Report |
|---|--------|------|------:|--------|
| 01 | Configuration | `backend/app/config.py` | 4 | [01-configuration.md](01-configuration.md) |
| 02 | Database layer | `backend/app/db/database.py` | 9 | [02-database-layer.md](02-database-layer.md) |
| 03 | Sample data generator | `backend/app/db/seed.py` | 5 | [03-sample-data-generator.md](03-sample-data-generator.md) |
| 04 | SQL safety guard | `backend/app/services/sql_guard.py` | 27 | [04-sql-safety-guard.md](04-sql-safety-guard.md) |
| 05 | LLM provider, schemas and prompts | `backend/app/agent/llm.py`, `schemas.py`, `prompts.py` | 9 | [05-llm-provider-layer.md](05-llm-provider-layer.md) |
| 06 | LangGraph agent | `backend/app/agent/state.py`, `nodes.py`, `graph.py` | 21 | [06-langgraph-agent.md](06-langgraph-agent.md) |
| 07 | Chart service | `backend/app/services/charts.py` + `frontend/src/chartData.ts` | 9 + 2 | [07-chart-service.md](07-chart-service.md) |
| 08 | API layer | `backend/app/api/routes.py`, `backend/app/main.py` | 8 | [08-api-layer.md](08-api-layer.md) |
| 09 | Frontend | `frontend/src` | 19 + 8 browser checks | [09-frontend.md](09-frontend.md) |
| 10 | Testing, CI and deployment | `backend/tests`, `.github/workflows`, `Dockerfile` | — | [10-testing-ci-deployment.md](10-testing-ci-deployment.md) |

## Overall test results

| Suite | Tests | Result |
|-------|------:|--------|
| Backend (pytest) | 92 | 92 passed |
| Frontend (Vitest + Testing Library) | 19 | 19 passed |
| Browser checks (Playwright on the running app) | 8 | 8 passed |
| GitHub Actions CI (backend, frontend, Docker build) | 3 jobs | All green |

Commands to reproduce:

```bash
cd backend && pytest          # 92 passed
cd frontend && npm test       # 19 passed
```
