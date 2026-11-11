import pytest

from app.services.sql_guard import SQLValidationError, looks_destructive, validate_sql

TABLES = {"orders", "customers", "regions", "products", "order_items"}


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM orders",
        "select count(*) as n from orders where status = 'completed'",
        "WITH monthly AS (SELECT strftime('%Y-%m', order_date) AS m, COUNT(*) AS n FROM orders GROUP BY 1) "
        "SELECT * FROM monthly ORDER BY m",
        "SELECT name FROM regions UNION SELECT category FROM products",
        "```sql\nSELECT name FROM regions;\n```",
    ],
)
def test_allows_read_only_queries(query):
    result = validate_sql(query, TABLES)
    assert result.sql.upper().lstrip().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize(
    "query, message",
    [
        ("DELETE FROM orders", "Only read-only"),
        ("UPDATE orders SET status = 'x'", "Only read-only"),
        ("INSERT INTO regions VALUES (9, 'Mars')", "Only read-only"),
        ("DROP TABLE orders", "Only read-only"),
        ("PRAGMA table_info(orders)", "Only read-only"),
        ("SELECT 1; DROP TABLE orders", "single SQL statement"),
        ("WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x", "Forbidden operation"),
        ("SELECT * FROM users", "Unknown table"),
        ("SELECT load_extension('evil') FROM orders", "not allowed"),
        ("SELEC * FROM", "could not be parsed"),
        ("", "empty"),
    ],
)
def test_blocks_unsafe_or_invalid_queries(query, message):
    with pytest.raises(SQLValidationError, match=message):
        validate_sql(query, TABLES)


def test_adds_limit_when_missing():
    result = validate_sql("SELECT * FROM orders", TABLES, max_rows=100)
    assert result.limit_applied
    assert "LIMIT 100" in result.sql


def test_caps_excessive_limit():
    result = validate_sql("SELECT * FROM orders LIMIT 100000", TABLES, max_rows=500)
    assert result.limit_applied
    assert "LIMIT 500" in result.sql


def test_keeps_small_limit():
    result = validate_sql("SELECT * FROM orders LIMIT 5", TABLES, max_rows=500)
    assert not result.limit_applied
    assert "LIMIT 5" in result.sql


def test_cte_names_are_not_treated_as_unknown_tables():
    result = validate_sql("WITH t AS (SELECT * FROM orders) SELECT * FROM t", TABLES)
    assert result.tables == ["orders"]


@pytest.mark.parametrize(
    "question, expected",
    [
        ("Delete all cancelled orders", True),
        ("drop the orders table", True),
        ("Update prices for all products", True),
        ("Truncate the customers table", True),
        ("What is total revenue by region?", False),
        ("Show the change in orders month over month", False),
        ("Which customers placed the most orders?", False),
    ],
)
def test_destructive_intent_precheck(question, expected):
    assert looks_destructive(question) is expected
