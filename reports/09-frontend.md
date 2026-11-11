# Module Report 09 — Frontend

**Folder:** `frontend/src`
**Stack:** React 18, TypeScript (strict), Vite 6, Tailwind CSS 4, Recharts, Lucide icons, self-hosted fonts (Instrument Sans, JetBrains Mono)

## 1. Purpose

An analyst workspace where a business user asks questions, watches the agent work, and gets an answer they can verify: chart, table, SQL and reasoning.

## 2. How it works

### 2.1 Structure

| File | Responsibility |
|------|----------------|
| `api.ts` | Typed models mirroring the backend (`AskResult`, `AgentStep`, `TableInfo`, `Health`) and `askStream`, a streaming SSE client built on `fetch` |
| `App.tsx` | Layout, conversation state (`turns`, `threadId`), the empty state with starter questions, the mobile drawer, Stop/abort |
| `components/Pipeline.tsx` | Six-stage progress strip, self-correction badge, expandable timed trace |
| `components/AnswerSheet.tsx` | One card per question: interpreted question, pipeline, answer, findings, chart, tabs (Results / SQL / How it was built), follow-up chips, timing |
| `components/ResultChart.tsx` | Renders line, bar (single or grouped), donut or KPI tiles from the `ChartSpec` |
| `components/ResultsTable.tsx` | Sortable, paginated table with CSV export |
| `components/SqlViewer.tsx` | Lightweight SQL syntax highlighting and Copy SQL |
| `components/Sidebar.tsx` | Brand, New conversation, schema explorer (row counts, PK/FK icons), model status |
| `components/Composer.tsx` | Auto-growing input; Enter sends, Shift+Enter adds a new line; Stop while streaming |
| `chartData.ts` | Pivots long-format results into one series per value for Recharts |
| `format.ts` | Labels (`total_revenue` → "Total revenue"), currency, percentage and compact axis formatting |

### 2.2 Streaming client (`askStream`)

1. `POST /api/ask/stream` with the question and `thread_id`.
2. Read the response body as a stream and decode it chunk by chunk.
3. Split on blank lines (both `\n\n` and `\r\n\r\n`), parse the `event:` and `data:` lines, and dispatch to `onStart`, `onStep`, `onResult` and `onError`.
4. A partial event that arrives across two network chunks stays in the buffer until it is complete.
5. Network failures and HTTP errors become readable messages shown inside the answer card.

`EventSource` was not used because it only supports GET, and the question is sent in a POST body.

### 2.3 Pipeline logic

- Each stage's state comes from the last step for that node: `done`, `retry`, `blocked`, `error`, or `pending`.
- While streaming, the next expected stage shows as `running` (after a retry, the next stage is "Write SQL").
- If the request was blocked or answered directly, the strip collapses to **Understand → Reply**.
- Fixes = number of SQL-generation steps minus 1, shown as "Self-corrected N times".

## 3. How it was built

| Decision | Why |
|----------|-----|
| Design direction: "analyst's graph paper", cool paper background, ink text, cobalt accent | Specific to data analysis; colour is reserved for meaning (green done, amber self-correcting, red blocked) |
| The pipeline as the signature element | It is what makes the answer trustworthy, so it gets the visual emphasis; everything else stays quiet |
| Answer first, then chart, then the details in tabs | Business users read the answer; analysts open the SQL |
| Self-hosted fonts | Work offline and inside private networks; no third-party requests |
| Recharts split into its own chunk | The main app bundle stays at about 42 KB |
| Accessibility built in | Landmarks, `aria-label` per stage, `aria-expanded` and `aria-selected`, visible focus rings, reduced-motion support |
| Responsive layout | Sidebar becomes a drawer below 1024 px; the pipeline and tables adapt at 390 px |

## 4. Test cases

### 4.1 Unit and component tests (Vitest + Testing Library): `frontend/src/__tests__`

| ID | File / test | What it checks | Result |
|----|-------------|----------------|--------|
| FE-01 | `format` › humanize | `total_revenue` → "Total revenue"; `q3_2026_revenue` → "Q3 2026 revenue" | ✅ Pass |
| FE-02 | `format` › money | `$472,022`, `$815.00`, `$342.43` | ✅ Pass |
| FE-03 | `format` › percentages | 52.3 → `52.3%`; 0.481 → `48.1%` | ✅ Pass |
| FE-04 | `format` › counts and compact | `1,467`; axis label `$450K` | ✅ Pass |
| FE-05 | `format` › missing and text | `null` → `—`; text unchanged | ✅ Pass |
| FE-06 | `api` › parses events split across chunks | start, step and result parsed correctly even when one event arrives in two chunks with `\r\n` line endings | ✅ Pass |
| FE-07 | `api` › forwards server error events | `event: error` → `onError("boom")` | ✅ Pass |
| FE-08 | `api` › API unreachable | Network failure → "Can't reach the InsightGraph API…" | ✅ Pass |
| FE-09 | `api` › HTTP errors | 422 → message mentions 422 | ✅ Pass |
| FE-10 | `Pipeline` › completed stages + badge | All stages done; "Self-corrected 1 time" shown | ✅ Pass |
| FE-11 | `Pipeline` › blocked request | Collapses to Understand (blocked) → Reply (done); no "Write SQL" | ✅ Pass |
| FE-12 | `Pipeline` › running stage | After the first step, "Pick tables" is running | ✅ Pass |
| FE-13 | `Pipeline` › reasoning trace | Expanding shows step titles | ✅ Pass |
| FE-14 | `ResultsTable` › format and sort | `$412,031` shown; sorting by Region and by revenue reorders rows | ✅ Pass |
| FE-15 | `ResultsTable` › truncation notice | The row-limit notice appears only when `truncated` | ✅ Pass |
| FE-16 | `Composer` › keyboard | Shift+Enter does not send; Enter sends the question | ✅ Pass |
| FE-17 | `Composer` › empty and busy | An empty question is not sent; the Stop button appears while busy | ✅ Pass |

### 4.2 Browser checks on the running app (Playwright + Chrome)

| ID | Check | Result |
|----|-------|--------|
| E2E-01 | Shift+Enter inserts a new line without sending | ✅ Pass |
| E2E-02 | A full question streams to a completed answer card | ✅ Pass |
| E2E-03 | Clicking the Region header re-sorts the table (North America → Asia Pacific first) | ✅ Pass |
| E2E-04 | Download CSV produces `region,total_revenue,orders` with the raw values | ✅ Pass |
| E2E-05 | Copy SQL puts the query on the clipboard; the button changes to "Copied" | ✅ Pass |
| E2E-06 | API unreachable → readable error inside the card | ✅ Pass |
| E2E-07 | Desktop layout at 1440 px: sidebar, schema explorer, answer cards | ✅ Pass (see `docs/screenshots`) |
| E2E-08 | Mobile layout at 390 px: drawer menu, chart and scrollable table in the answer card | ✅ Pass (see `10-mobile-home.png`, `11-mobile-answer.png`) |

| FE-18 | `chartData` › pivots long results | `(region, year, revenue)` → one series per year | ✅ Pass |
| FE-19 | `chartData` › keeps wide results | Wide rows unchanged | ✅ Pass |

**Result: 19 / 19 unit tests and 8 / 8 browser checks passed.**
