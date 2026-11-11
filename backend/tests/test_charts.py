from app.services.charts import recommend_chart, validate_chart


def test_time_series_becomes_line():
    spec = recommend_chart(["month", "revenue"], [["2026-01", 10.0], ["2026-02", 12.0], ["2026-03", 9.0]])
    assert spec["type"] == "line" and spec["x"] == "month" and spec["y"] == ["revenue"]


def test_categories_become_bar():
    spec = recommend_chart(["region", "revenue"], [["Europe", 10.0], ["Asia", 8.0]])
    assert spec["type"] == "bar"


def test_single_value_becomes_kpi():
    spec = recommend_chart(["total_revenue"], [[123.4]])
    assert spec["type"] == "kpi"


def test_text_only_becomes_table():
    assert recommend_chart(["name", "email"], [["a", "b"]])["type"] == "table"


def test_invalid_model_chart_falls_back():
    spec = validate_chart(
        {"type": "bar", "x": "does_not_exist", "y": ["revenue"], "title": "t"},
        ["region", "revenue"],
        [["Europe", 1.0], ["Asia", 2.0]],
    )
    assert spec["x"] == "region" and spec["type"] == "bar"


def test_pie_with_many_slices_becomes_bar():
    rows = [[f"p{i}", float(i)] for i in range(12)]
    spec = validate_chart({"type": "pie", "x": "product", "y": ["units"], "title": ""}, ["product", "units"], rows)
    assert spec["type"] == "bar"


def test_non_numeric_y_is_dropped():
    spec = validate_chart(
        {"type": "bar", "x": "region", "y": ["region", "revenue"], "title": ""},
        ["region", "revenue"],
        [["Europe", 1.0]],
    )
    assert spec["y"] == ["revenue"]
