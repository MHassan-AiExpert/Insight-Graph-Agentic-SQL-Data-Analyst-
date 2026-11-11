"""Chart-spec validation and a deterministic fallback recommender."""

from __future__ import annotations

import re
from typing import Any

TIME_COLUMN = re.compile(r"(date|day|week|month|year|quarter|period)", re.IGNORECASE)
TIME_VALUE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$|^\d{4}-?Q[1-4]$", re.IGNORECASE)


def numeric_columns(columns: list[str], rows: list[list[Any]]) -> list[str]:
    numeric = []
    for idx, col in enumerate(columns):
        values = [r[idx] for r in rows[:50] if r[idx] is not None]
        if values and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            numeric.append(col)
    return numeric


def _is_time_axis(col: str, columns: list[str], rows: list[list[Any]]) -> bool:
    idx = columns.index(col)
    values = [str(r[idx]) for r in rows[:20] if r[idx] is not None]
    return bool(TIME_COLUMN.search(col)) or (bool(values) and all(TIME_VALUE.match(v) for v in values))


def recommend_chart(columns: list[str], rows: list[list[Any]], title: str = "") -> dict[str, Any]:
    if not rows or not columns:
        return {"type": "table", "x": None, "y": [], "title": title}
    nums = numeric_columns(columns, rows)
    dims = [c for c in columns if c not in nums]
    if len(rows) == 1 and len(nums) >= 1 and not dims:
        return {"type": "kpi", "x": None, "y": nums[:3], "title": title}
    if not nums:
        return {"type": "table", "x": None, "y": [], "title": title}
    x = dims[0] if dims else None
    if x is None:
        # e.g. "year | revenue" where year is numeric
        time_like = [c for c in nums if TIME_COLUMN.search(c)]
        if time_like and len(nums) > 1:
            x = time_like[0]
            nums = [c for c in nums if c != x]
        else:
            return {"type": "table", "x": None, "y": [], "title": title}
    chart_type = "line" if _is_time_axis(x, columns, rows) and len(rows) > 2 else "bar"
    return _with_series({"type": chart_type, "x": x, "y": nums[:3], "title": title}, columns, rows)


def detect_series(x: str | None, y: list[str], columns: list[str], rows: list[list[Any]]) -> str | None:
    """Detect "long" results such as (region, year, revenue), where each x value
    repeats once per series. Returns the column to split into series, or None."""
    if not x or x not in columns or not y or not rows:
        return None
    xi = columns.index(x)
    x_values = [r[xi] for r in rows]
    if len(set(x_values)) == len(x_values):
        return None
    nums = set(numeric_columns(columns, rows))
    for col in columns:
        if col == x or col in y:
            continue
        if col in nums and not TIME_COLUMN.search(col):
            continue
        ci = columns.index(col)
        series_values = {r[ci] for r in rows}
        pairs = {(r[xi], r[ci]) for r in rows}
        if 1 < len(series_values) <= 6 and len(pairs) == len(rows):
            return col
    return None


def _with_series(spec: dict[str, Any], columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    series = None
    if spec["type"] in ("bar", "line"):
        series = detect_series(spec["x"], spec["y"], columns, rows)
    spec["series"] = series
    if series:
        spec["y"] = spec["y"][:1]
    return spec


def validate_chart(spec: dict[str, Any] | None, columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    """Keep the model's chart choice when it references real columns, otherwise fall back."""
    title = (spec or {}).get("title", "") if spec else ""
    if not spec:
        return recommend_chart(columns, rows, title)
    nums = numeric_columns(columns, rows)
    chart_type = spec.get("type", "table")
    y = [c for c in spec.get("y") or [] if c in nums]
    x = spec.get("x")
    if chart_type == "table":
        return {"type": "table", "x": None, "y": [], "title": title}
    if chart_type == "kpi":
        if not nums or len(rows) > 1:
            return recommend_chart(columns, rows, title)
        return {"type": "kpi", "x": None, "y": y or nums[:3], "title": title}
    if x not in columns or not y:
        return recommend_chart(columns, rows, title)
    if chart_type == "pie" and len(rows) > 8:
        chart_type = "bar"
    return _with_series({"type": chart_type, "x": x, "y": y[:3], "title": title}, columns, rows)
