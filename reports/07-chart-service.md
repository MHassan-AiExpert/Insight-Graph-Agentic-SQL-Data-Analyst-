# Module Report 07 — Chart Service

**File:** `backend/app/services/charts.py`
**Used by:** `analyze_results` node

## 1. Purpose

Makes sure every chart shown to the user is valid for the data. The LLM proposes a chart (`ChartSpec`); this module either accepts it or replaces it with a sensible deterministic choice. A chart can never point at a column that does not exist.

## 2. How it works

### 2.1 Column typing: `numeric_columns`

A column is numeric when every non-null value in the first 50 rows is an `int` or `float` (booleans excluded).

### 2.2 Fallback recommender: `recommend_chart(columns, rows)`

| Result shape | Chart |
|--------------|-------|
| No rows | table |
| 1 row, only numeric columns | **kpi** (up to 3 values) |
| No numeric columns | table |
| A text dimension that looks like time (name contains date/month/year/quarter/period, or values like `2026-01`, `2026`, `2026-Q3`) and more than 2 rows | **line** |
| Any other text dimension + numbers | **bar** (up to 3 series) |
| Only numbers, one of them time-like (e.g. `year, revenue`) | uses the time column as x |

### 2.3 Validator: `validate_chart(spec, columns, rows)`

1. `table` → accepted as is.
2. `kpi` → accepted only for a single row; otherwise the recommender decides.
3. Non-numeric `y` columns are removed.
4. An `x` missing from the result, or an empty `y`, triggers the recommender.
5. A `pie` with more than 8 slices becomes a **bar**, because pies are unreadable with many slices.
6. At most 3 series are kept.

### 2.4 Long-format results: `detect_series`

Models often return comparisons as one row per category and period, for example `(region, year, revenue)`. Plotted directly, each region would appear twice on the axis. `detect_series` spots this shape: the x value repeats, and another text (or time-like) column has 2–6 distinct values that make every row unique. It returns that column as `series`.

The frontend (`frontend/src/chartData.ts`) then pivots the rows so each year becomes its own coloured bar or line, with a legend. This issue was found during live testing with Groq and fixed with tests on both sides.

## 3. How it was built

| Decision | Why |
|----------|-----|
| The LLM proposes, code verifies | The model understands intent (e.g. "share" → pie); code guarantees validity |
| Inferring types from values | SQLite types in results are unreliable; the values are the truth |
| Both name and value heuristics for time | Covers `month` columns as well as aliases such as `period` that hold `2026-01` |
| Limits on pie slices and series | Readability rules from data-visualisation practice |

## 4. Test cases

File: `backend/tests/test_charts.py`

| ID | Test | Input | Expected | Result |
|----|------|-------|----------|--------|
| CH-01 | `test_time_series_becomes_line` | `month, revenue` × 3 rows | line, x = month, y = [revenue] | ✅ Pass |
| CH-02 | `test_categories_become_bar` | `region, revenue` | bar | ✅ Pass |
| CH-03 | `test_single_value_becomes_kpi` | `[[123.4]]` | kpi | ✅ Pass |
| CH-04 | `test_text_only_becomes_table` | `name, email` | table | ✅ Pass |
| CH-05 | `test_invalid_model_chart_falls_back` | x = `does_not_exist` | Replaced: bar with x = region | ✅ Pass |
| CH-06 | `test_pie_with_many_slices_becomes_bar` | Pie with 12 rows | bar | ✅ Pass |
| CH-07 | `test_non_numeric_y_is_dropped` | y = [region, revenue] | y = [revenue] | ✅ Pass |
| CH-08 | `test_long_format_is_split_into_series` | `(region, year, revenue)` with repeated regions | series = year | ✅ Pass |
| CH-09 | `test_wide_format_has_no_series` | `(region, q3_2025, q3_2026)` | No pivot; two y columns | ✅ Pass |
| CH-10 | Frontend `chartData` › pivots long results | `(region, year, revenue)` rows | Pivoted into `{region, 2025, 2026}` | ✅ Pass |
| CH-11 | Frontend `chartData` › keeps wide results | `(region, q3_2025, q3_2026)` rows | Data unchanged | ✅ Pass |

The scenario tests (report 06) also check that the final chart for every golden question uses real columns, and they cover line, bar, multi-series bar, pie and KPI.

**Result: 9 / 9 backend and 2 / 2 frontend tests passed.**
