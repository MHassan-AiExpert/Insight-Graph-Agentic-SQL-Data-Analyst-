import hashlib
import sqlite3

import pytest

from app.db.seed import END_DATE, N_CUSTOMERS, N_ORDERS, START_DATE, build_database


def _digest(path) -> str:
    conn = sqlite3.connect(path)
    rows = conn.execute(
        "SELECT o.order_id, o.order_date, o.status, SUM(oi.quantity) FROM orders o "
        "JOIN order_items oi USING(order_id) GROUP BY o.order_id ORDER BY o.order_id"
    ).fetchall()
    conn.close()
    return hashlib.sha256(repr(rows).encode()).hexdigest()


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    return build_database(tmp_path_factory.mktemp("seed") / "a.db", force=True)


def test_row_counts(db):
    conn = sqlite3.connect(db)
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ["regions", "customers", "products", "orders"]
    }
    assert counts == {"regions": 5, "customers": N_CUSTOMERS, "products": 60, "orders": N_ORDERS}
    assert conn.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] > N_ORDERS


def test_generation_is_deterministic(db, tmp_path):
    other = build_database(tmp_path / "b.db", force=True)
    assert _digest(db) == _digest(other)


def test_dates_and_referential_integrity(db):
    conn = sqlite3.connect(db)
    lo, hi = conn.execute("SELECT MIN(order_date), MAX(order_date) FROM orders").fetchone()
    assert START_DATE.isoformat() <= lo and hi <= END_DATE.isoformat()
    orphans = conn.execute(
        "SELECT COUNT(*) FROM order_items oi LEFT JOIN orders o USING(order_id) WHERE o.order_id IS NULL"
    ).fetchone()[0]
    assert orphans == 0
    assert (
        conn.execute("SELECT COUNT(*) FROM customers WHERE signup_date > ?", (START_DATE.isoformat(),)).fetchone()[0]
        == 0
    )


def test_business_constraints(db):
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM products WHERE unit_cost >= unit_price").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM order_items WHERE discount < 0 OR discount >= 1").fetchone()[0] == 0
    statuses = {r[0] for r in conn.execute("SELECT DISTINCT status FROM orders")}
    assert statuses == {"completed", "shipped", "cancelled", "returned"}


def test_existing_database_is_not_overwritten(db):
    before = db.stat().st_mtime_ns
    build_database(db)  # force=False
    assert db.stat().st_mtime_ns == before
