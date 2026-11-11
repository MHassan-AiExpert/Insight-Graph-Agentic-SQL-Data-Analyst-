# InsightGraph — UI/UX Design

## 1. Design goals

1. **Trust before beauty.** Business users only act on an answer they can verify, so every answer shows how it was produced: the pipeline, the SQL, the assumptions and any errors that were fixed.
2. **Answer first.** The written answer and the chart come before the raw table and the SQL, which are one click away.
3. **Zero SQL knowledge required.** Plain language everywhere: "Pick tables", "Safety check", "How it was built", never internal node names.
4. **Calm analyst workspace.** A quiet, paper-like canvas where data and colour carry the meaning.

## 2. Users and key journeys

| Persona | Goal | Journey |
|---------|------|---------|
| Sales manager | "Which region is growing fastest?" | Picks a starter question → reads the answer → asks a follow-up |
| Operations lead | Weekly numbers without waiting for an analyst | Asks a question → downloads the CSV → shares it |
| Data analyst | A fast first draft of a query | Asks → opens the SQL tab → copies the SQL into their own tool |
| Engineering lead | Is it safe to point an LLM at our database? | Tries "delete all cancelled orders" → sees it blocked → reviews the trace |

## 3. Information architecture

```
┌──────────────┬──────────────────────────────────────────────┐
│ Sidebar      │  Conversation (max 920 px, graph-paper bg)   │
│ ─ Logo       │  ┌────────────────────────────────────────┐  │
│ ─ New chat   │  │ Answer sheet                           │  │
│ ─ Your data  │  │  Question  (+ "Interpreted as …")      │  │
│   tables ▸   │  │  Pipeline: 6 stages + trace toggle     │  │
│   columns    │  │  Answer + key findings                 │  │
│   PK / FK    │  │  Chart card                            │  │
│              │  │  Tabs: Results | SQL | How it was built│  │
│              │  │  Follow-up chips          timing       │  │
│ ─ Model      │  └────────────────────────────────────────┘  │
│   status     │  Composer (sticky)                           │
└──────────────┴──────────────────────────────────────────────┘
```

On screens narrower than 1024 px the sidebar becomes a slide-over drawer opened from a top bar.

## 4. Visual system

### Colour tokens

| Token | Hex | Role |
|-------|-----|------|
| `ink` | `#172033` | Text, primary buttons, brand mark |
| `paper` | `#F3F5F2` | App background, with a faint 28 px graph-paper grid |
| `sheet` | `#FFFFFF` | Answer sheets, cards, sidebar |
| `grid` | `#DDE3DC` | Hairlines, borders, table rules |
| `cobalt` | `#2D5BD8` | Primary accent: actions, links, first chart series, SQL keywords |
| `moss` | `#2E7D52` | Completed steps, read-only reassurance |
| `amber` | `#C97F0C` | Self-correction and retries |
| `brick` | `#B8402B` | Blocked requests and failures |

Status colours are always paired with an icon (check, retry arrow, stop sign) and a text label, so colour is never the only signal.

### Typography

| Use | Typeface | Size / weight |
|-----|----------|---------------|
| Hero headline | Instrument Sans | 54 px / 600, tight tracking |
| Question title | Instrument Sans | 18 px / 600 |
| Body and answers | Instrument Sans | 15.5 px / 400, line-height 1.55, max 72 characters |
| SQL, timings, types | JetBrains Mono | 11–13 px |

Fonts are self-hosted through Fontsource, so the app works offline and inside private networks.

## 5. Key components

| Component | Behaviour |
|-----------|-----------|
| **Pipeline** | Six numbered stages, because the work really is a sequence. Pending stages are outlined, the running stage pulses (disabled under `prefers-reduced-motion`), and completed stages turn moss. A retry turns the stage amber and adds a "Self-corrected N times" badge. A blocked request collapses the pipeline to *Understand → Reply* with a red stop icon. |
| **Reasoning trace** | Collapsible timeline with elapsed time per step, so users can see exactly where time was spent and why. |
| **Answer** | Direct answer first, then up to 4 findings marked with cobalt dots. |
| **Chart card** | Recharts line, bar (single or grouped), donut, or KPI tiles. Axis labels are compact (`$450K`); tooltips show full values. |
| **Results table** | Sort by any column, 25 rows per page, right-aligned tabular numbers, currency and percentage formatting, CSV download. |
| **SQL viewer** | Syntax highlighting (keywords, strings, numbers) and a copy button. |
| **How it was built** | Approach, tables used, assumptions, attempt count and every error that was fixed. |
| **Follow-up chips** | One click asks the next question in the same thread. |
| **Schema explorer** | Expandable tables with row counts, column types, and PK (key) / FK (link) icons. |
| **Composer** | Auto-growing textarea. Enter sends, Shift+Enter adds a new line, and a Stop button aborts a streaming request. |

## 6. States

| State | Treatment |
|-------|-----------|
| Empty | Headline "Ask your database a question.", one-sentence explanation, a read-only reassurance badge, and four starter questions labelled by the kind of insight they produce |
| Streaming | Pipeline animates; the latest step title appears under the pipeline |
| Self-correcting | Amber stage and badge; errors listed in "How it was built" |
| Blocked | Red label "Blocked: read-only assistant"; no SQL or table shown |
| No rows | Answer explains that nothing matched and suggests widening filters |
| Failure | Plain explanation of the last error and how to rephrase |
| API unreachable | Inline error in the answer sheet telling the user to check that the backend is running |

## 7. Accessibility

- Semantic landmarks (`aside`, `main`, `article`, `nav`) and an ordered list for the pipeline, with an `aria-label` per stage state.
- Visible 2 px focus rings on every interactive element; full keyboard operation.
- `role="tablist"` / `aria-selected` on result tabs; `aria-expanded` on collapsibles.
- Text contrast of at least 4.5:1 on all body text.
- Reduced-motion users get no pulsing animation.
- Charts have an accessible label, and the same data is always available in the table.

## 8. Responsive behaviour

| Breakpoint | Layout |
|------------|--------|
| ≥ 1024 px | Fixed 288 px sidebar plus conversation column |
| 640–1023 px | Sidebar becomes a drawer; starter questions in two columns |
| < 640 px | Single column; pipeline uses short labels (Intent, Tables, SQL, Safety, Run, Explain); table scrolls horizontally |

## 9. Screens

| Screen | File |
|--------|------|
| Home / empty state | `screenshots/01-home.png` |
| Answer with bar chart | `screenshots/02-revenue-by-region.png`, `02b-revenue-answer-card.png` |
| Self-correction trace and details | `screenshots/03-self-correction-trace.png`, `03b-self-correction-details.png` |
| Time-series line chart | `screenshots/04-monthly-trend.png` |
| SQL tab with grouped bars | `screenshots/05-generated-sql.png` |
| Follow-up with memory and KPI tiles | `screenshots/06-follow-up-memory.png` |
| Blocked destructive request | `screenshots/07-safety-guard.png` |
| Donut chart | `screenshots/08-channel-share.png` |
| Percentage metrics | `screenshots/09-gross-margin-table.png` |
| Mobile | `screenshots/10-mobile-home.png`, `11-mobile-answer.png` |
