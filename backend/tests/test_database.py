import pytest

from app.db.database import QueryExecutionError, execute_readonly, get_schema, render_schema_context


def test_schema_introspection(engine):
    tables = {t.name: t for t in get_schema(engine)}
    assert set(tables) == {"customers", "order_items", "orders", "products", "regions"}
    assert tables["orders"].row_count == 5200
    assert tables["regions"].row_count == 5
    fk_targets = {fk["references_table"] for fk in tables["order_items"].foreign_keys}
    assert fk_targets == {"orders", "products"}
    assert any(c.primary_key for c in tables["orders"].columns)


def test_schema_context_is_compact_and_complete(engine):
    context = render_schema_context(list(get_schema(engine)))
    assert "TABLE orders (5200 rows)" in context
    assert "FK customer_id -> customers(customer_id)" in context


def test_select_executes(engine):
    result = execute_readonly("SELECT COUNT(*) AS n FROM regions", engine)
    assert result.columns == ["n"]
    assert result.rows == [[5]]
    assert result.elapsed_ms >= 0


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO regions VALUES (99, 'Atlantis')",
        "DELETE FROM orders",
        "UPDATE products SET unit_price = 0",
        "DROP TABLE customers",
    ],
)
def test_connection_is_read_only(engine, statement):
    """Second safety layer: even if SQL reached the database, writes fail."""
    with pytest.raises(QueryExecutionError):
        execute_readonly(statement, engine)
    assert execute_readonly("SELECT COUNT(*) FROM regions", engine).rows == [[5]]


def test_bad_column_raises_readable_error(engine):
    with pytest.raises(QueryExecutionError, match="no such column"):
        execute_readonly("SELECT revenue FROM orders", engine)


def test_long_query_times_out(engine):
    heavy = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c"
    with pytest.raises(QueryExecutionError, match="time limit"):
        execute_readonly(heavy, engine, timeout_s=0.3)
