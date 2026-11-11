# Module Report 01 — Configuration

**File:** `backend/app/config.py`
**Depends on:** `pydantic-settings`
**Used by:** every backend module

## 1. Purpose

Provides one typed, validated source of truth for all runtime settings: LLM provider and model, database URL, agent limits, API options and business metric definitions. Nothing else in the codebase reads environment variables directly.

## 2. How it works

1. `Settings` extends `pydantic_settings.BaseSettings`. Every field has a type and a safe default.
2. On creation, values are read in this order: constructor arguments, then environment variables, then `.env` (project root or `backend/`), then defaults. Names are case-insensitive (`GROQ_MODEL` maps to `groq_model`).
3. Pydantic validates types: `MAX_SQL_ATTEMPTS=abc` fails at startup instead of halfway through a request. `llm_provider` is a `Literal["groq", "scripted"]`, so a typo is rejected.
4. `get_settings()` is wrapped in `lru_cache`, so the file is parsed once per process and every module shares the same object.
5. The derived property `cors_origin_list` turns the comma-separated `CORS_ORIGINS` string into a clean list.

### Settings groups

| Group | Fields |
|-------|--------|
| LLM | `llm_provider`, `groq_api_key`, `groq_model`, `llm_temperature`, `llm_timeout_seconds`, `llm_reasoning_effort`, `scripted_responses_path` |
| Database | `database_url`, `query_timeout_seconds`, `max_result_rows`, `sample_rows_per_table`, `business_rules` |
| Agent | `max_sql_attempts`, `history_turns`, `rows_for_analysis` |
| API | `cors_origins`, `frontend_dist` |

## 3. How it was built

| Decision | Reason |
|----------|--------|
| pydantic-settings instead of `os.getenv` | Type validation, defaults and `.env` support in one place; works naturally with FastAPI and Pydantic models |
| Safe defaults (temperature 0, 3 attempts, 500-row limit, 10 s timeout) | The app is safe and deterministic before anyone tunes it |
| `business_rules` as a setting | Metric definitions (revenue, gross profit, AOV, quarters) live in configuration, not hidden inside a prompt, so another dataset can set its own definitions without code changes |
| Paths computed from `__file__` | The default SQLite path and the built frontend path work the same locally and inside Docker |
| `extra="ignore"` | Unrelated variables in a shared `.env` do not crash the app |

## 4. Test cases

File: `backend/tests/test_config.py`

| ID | Test | What it checks | Result |
|----|------|----------------|--------|
| CFG-01 | `test_defaults_are_safe` | With no environment, the provider is `groq`, the model is `openai/gpt-oss-120b`, the limits are 3 attempts / 500 rows / 10 s, and the database points to the bundled SQLite file | ✅ Pass |
| CFG-02 | `test_environment_overrides` | `MAX_SQL_ATTEMPTS=5` and `GROQ_MODEL=llama-3.3-70b-versatile` override the defaults and are converted to the right types | ✅ Pass |
| CFG-03 | `test_cors_origin_list_is_parsed` | `" http://a.com, ,http://b.com "` becomes `["http://a.com", "http://b.com"]` (spaces and empty entries removed) | ✅ Pass |
| CFG-04 | `test_business_rules_define_core_metrics` | The default rules define revenue, gross profit, average order value and quarters | ✅ Pass |

**Result: 4 / 4 passed.**

## 5. Limitations and next steps

- Secrets are read from the environment. In production they should come from a secret manager (for example Vercel or Docker secrets).
