# Module Report 05 — LLM Provider, Structured Schemas and Prompts

**Files:** `backend/app/agent/llm.py`, `backend/app/agent/schemas.py`, `backend/app/agent/prompts.py`
**Depends on:** LangChain Core, `langchain-groq`, Pydantic v2
**Used by:** the four LLM-backed graph nodes

## 1. Purpose

Gives every agent step one reliable way to ask the model for a **typed answer**, and keeps the provider swappable:

- `llm.py`: the provider abstraction (`GroqLLM` for production, `ScriptedLLM` for tests and evaluation)
- `schemas.py`: the Pydantic models each step must return
- `prompts.py`: the LangChain `ChatPromptTemplate` for each step

## 2. How it works

### 2.1 One method for every step

```python
class LLMClient(Protocol):
    def structured(self, task, messages, schema, *, key="") -> BaseModel: ...
```

Nodes never handle raw text: they call `structured("sql", messages, SQLDraft)` and receive a validated `SQLDraft` object.

### 2.2 GroqLLM (production)

1. Creates `ChatGroq(model, temperature=0, timeout, max_retries=2)`, adding `reasoning_effort` (default `low`) for reasoning models such as `openai/gpt-oss-120b`.
2. For each schema, builds `chat.with_structured_output(schema)` once and caches it. LangChain turns the Pydantic model into a tool/function definition, and Groq returns arguments that are parsed back into the model.
3. **Recovery from schema rejections.** Groq validates tool calls on its side. If the model writes a good answer but breaks the schema on a detail (for example `"y": null` for a table chart), Groq returns HTTP 400 `tool_use_failed` with the model's arguments in `failed_generation`. `recover_failed_generation` reads those arguments and validates them with the local Pydantic model, which accepts `null` for optional lists. The answer is kept instead of failing the request. Any other error is retried once.
4. Schemas are null-tolerant: list fields accept `null` (converted to `[]`) and a missing chart becomes a table, so the JSON schema sent to Groq allows these values in the first place.
5. Any remaining provider error becomes `LLMError("<model> failed during '<task>': …")`, shortened to a readable length. The API turns this into an SSE `error` event.
6. A missing API key fails immediately with a clear message.

### 2.3 ScriptedLLM (tests and evaluation)

Replays payloads instead of calling a model:

- `responses={"sql": [p1, p2]}` returns the payloads in order for each task (used to script a failed attempt followed by a fix).
- `scenarios=[{"match": "revenue by region", "responses": {...}}]` selects payloads by a phrase in the question. The queue refills, so the same question can be asked again.
- Payloads still go through `schema.model_validate`, so an invalid scripted response fails exactly like an invalid model response would.
- `calls` records every request, which lets tests prove that the model was **not** called (for example for blocked requests).

### 2.4 Structured schemas

| Schema | Fields | Used by |
|--------|--------|---------|
| `IntentDecision` | `intent` ∈ {data_question, small_talk, unsafe, out_of_scope}, `standalone_question`, `reason` | `classify_intent` |
| `TableSelection` | `tables[]`, `reason` | `select_tables` |
| `SQLDraft` | `sql`, `reasoning`, `assumptions[]` | `generate_sql` |
| `ChartSpec` | `type` ∈ {bar, line, pie, kpi, table}, `x`, `y[]`, `title`, optional `series` | inside `InsightReport` |
| `InsightReport` | `answer`, `key_findings[]`, `chart`, `follow_up_questions[]` | `analyze_results` |

Field descriptions double as instructions to the model (for example, when to choose a pie chart).

### 2.5 Prompts

| Prompt | Key instructions |
|--------|------------------|
| `INTENT_PROMPT` | Classify; rewrite follow-ups ("same but for Europe") into standalone questions using history; treat modify, delete or bulk-export requests as unsafe |
| `TABLE_PROMPT` | Pick the minimum set of tables, including join tables, from the catalog |
| `SQL_PROMPT` | One read-only query in the given dialect; snake_case aliases; date functions for the dialect; business definitions; schema; history; previous error when retrying |
| `INSIGHT_PROMPT` | Answer first using real numbers; never invent numbers; chart rules; x and y must be real column names |

## 3. How it was built

| Decision | Why |
|----------|-----|
| Structured output everywhere | Parsing free text is fragile. Pydantic validation turns a malformed model answer into a clear error instead of a silent bug. |
| Provider protocol | Groq was chosen for very low latency, which matters in a 4-call agent, but swapping to OpenAI or Gemini only needs a new class with one method |
| Temperature 0 | SQL generation should be repeatable |
| Default model `openai/gpt-oss-120b` with low reasoning effort | It produced correct SQL on the first attempt in live testing; low effort keeps answers fast while keeping the quality of a reasoning model |
| Scripted provider in the codebase | CI runs the real graph, guard and database on every push without network or keys; the same mechanism runs the golden evaluation scenarios |
| Error feedback in `SQL_PROMPT` | Self-correction works because the model sees its previous SQL and the exact failure reason |

## 4. Test cases

File: `backend/tests/test_llm.py`

| ID | Test | What it checks | Result |
|----|------|----------------|--------|
| LLM-01 | `test_scripted_replays_in_order_and_validates` | Payloads come back in order as validated `SQLDraft` objects; calls are recorded | ✅ Pass |
| LLM-02 | `test_scripted_raises_when_exhausted` | Running out of scripted responses raises `LLMError` | ✅ Pass |
| LLM-03 | `test_scripted_scenario_matching_and_refill` | Case-insensitive phrase matching; the scenario can be replayed | ✅ Pass |
| LLM-04 | `test_invalid_payload_is_rejected_by_schema` | `intent="delete_everything"` is rejected by the schema | ✅ Pass |
| LLM-05 | `test_groq_requires_api_key` | A missing key raises `LLMError` mentioning `GROQ_API_KEY` | ✅ Pass |
| LLM-06 | `test_groq_builds_structured_runnable_without_network` | The Groq client and structured runnable are created with the correct model | ✅ Pass |
| LLM-07 | `test_chart_spec_defaults` | `ChartSpec(type="bar")` has safe defaults | ✅ Pass |
| LLM-08 | `test_prompts_render_with_all_variables` | All four prompt templates render with their variables (catches missing or misspelt placeholders) | ✅ Pass |
| LLM-09 | `test_reasoning_effort_only_applies_to_reasoning_models` | `reasoning_effort="low"` is passed to `openai/gpt-oss-*` models and ignored for Llama models | ✅ Pass |
| LLM-10 | `test_schema_accepts_nulls_for_lists` | A table chart with `x` and `y` set to `null` validates; `y` becomes `[]` | ✅ Pass |
| LLM-11 | `test_schema_allows_null_in_json_schema` | The JSON schema sent to the provider allows `null` | ✅ Pass |
| LLM-12 | `test_missing_lists_and_chart_default_safely` | `null` findings, follow-ups, assumptions and chart get safe defaults | ✅ Pass |
| LLM-13 | `test_recovers_report_from_groq_tool_use_failed` | A real-shaped Groq 400 `tool_use_failed` error is turned back into a valid `InsightReport` | ✅ Pass |
| LLM-14 | `test_recovers_from_error_text_without_body` | Recovery also works from the error text alone | ✅ Pass |
| LLM-15 | `test_unrelated_errors_are_not_swallowed` | Network errors and answers missing required fields still fail | ✅ Pass |
| LLM-16 | `test_groq_client_returns_recovered_answer_instead_of_failing` | `GroqLLM.structured` returns the recovered answer without a second model call | ✅ Pass |

The layer is also exercised by every graph, API and scenario test (40+ structured calls per run).

**Result: 16 / 16 passed.**

## 5. Note on live model testing

The automated suite does not call Groq, by design. Live behaviour is verified by running the app with a `GROQ_API_KEY` (see the README). Connection errors are handled and surface as a clear message in the UI.
