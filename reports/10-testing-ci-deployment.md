# Module Report 10 — Testing, CI and Deployment

**Files:** `backend/tests/`, `frontend/src/__tests__/`, `.github/workflows/ci.yml`, `Dockerfile`, `docker-compose.yml`, `.env.example`

## 1. Purpose

Proves on every push that the application works, and makes it possible to run the whole app with one command.

## 2. Test architecture

### 2.1 Test infrastructure (`backend/tests/conftest.py`)

1. Before any app import, set `DATABASE_URL` to a temporary file and `LLM_PROVIDER=scripted`.
2. Seed a fresh database with the deterministic generator.
3. Provide fixtures: `engine` (read-only engine on the test database), `settings`, and `make_graph(responses)`, which builds the **real compiled LangGraph** with a `ScriptedLLM` and its own `InMemorySaver`.
4. Helper builders (`intent()`, `tables()`, `sql()`, `insight()`) keep the scripted responses short and readable.

Only the language model is replaced. The graph, routing, guard, database, chart validation, API and SSE code all run for real.

### 2.2 Golden scenarios

`backend/tests/fixtures/analyst_scenarios.json` holds 9 conversations: 7 analytical questions, 1 follow-up and 1 greeting. Their SQL was written for the sample schema and checked against the real data. The same file powers:

- `test_scenarios.py`, the regression suite
- the screenshots in `docs/screenshots` (the app running with `LLM_PROVIDER=scripted SCRIPTED_RESPONSES_PATH=…`)

### 2.3 Test pyramid

| Level | Suites | Tests |
|-------|--------|------:|
| Unit | config, seed, SQL guard, database, charts, LLM layer | 63 |
| Integration | graph, API | 19 |
| Regression | golden scenarios | 10 |
| Frontend unit and component | format, chart data, SSE client, Pipeline, ResultsTable, Composer | 19 |
| Browser checks | Playwright on the running app | 8 |
| **Total** | | **119** |

## 3. Continuous integration (`.github/workflows/ci.yml`)

Runs on every push to `main` and on pull requests.

| Job | Steps |
|-----|-------|
| **Backend** | Python 3.12 → `pip install -r requirements-dev.txt` → `ruff check` → `ruff format --check` → `pytest` |
| **Frontend** | Node 22 → `npm ci` → `npm test` (Vitest) → `npm run build` (TypeScript strict + Vite) |
| **Docker** | Runs after both jobs pass → `docker build` of the production image |

No secrets are needed, because tests never call the real model.

## 4. Deployment

### 4.1 Docker image (multi-stage)

| Stage | Base | Does |
|-------|------|------|
| `frontend` | `node:22-alpine` | `npm ci` and `vite build` → `dist/` |
| `runtime` | `python:3.12-slim` | Installs the backend dependencies, copies the app and `dist/`, runs as a non-root user (uid 10001), adds a health check on `/api/health`, starts uvicorn on port 8000 |

### 4.2 Docker Compose

One service on port `8000`, configuration from `.env`, and a named volume for the SQLite database so data survives restarts. The database is seeded automatically on first start.

```bash
cp .env.example .env   # add GROQ_API_KEY
docker compose up --build
# open http://localhost:8000
```

## 5. How it was built

| Decision | Why |
|----------|-----|
| A scripted LLM instead of mocking LangChain internals | Mocks of library internals break on upgrades. Replacing only the provider behind our own interface keeps the tests stable and realistic. |
| A deterministic seed | Tests can assert exact values (5,200 orders, region ranking) |
| Lint and format checks in CI | Consistent code style; mistakes caught before review |
| Docker build in CI | The production image is proven to build on every change |
| Non-root container user and health check | Production hardening by default |

## 6. Results

| Run | Result |
|-----|--------|
| `pytest` (local) | **99 passed** |
| `npm test` (local) | **19 passed** |
| `ruff check` / `ruff format --check` | Clean |
| `tsc -b && vite build` | Clean |
| Browser checks | **8 / 8 passed** |
| GitHub Actions: Backend, Frontend, Docker image | ✅ All jobs green |
