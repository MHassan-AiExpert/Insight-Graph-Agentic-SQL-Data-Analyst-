# Module Report 02 — Database Layer

**File:** `backend/app/db/database.py`
**Depends on:** SQLAlchemy 2, `sqlite3`
**Used by:** LangGraph nodes (`select_tables`, `execute_sql`), API (`/api/schema`, `/api/health`)

## 1. Purpose

Gives the agent two capabilities:

1. **Understand the database:** live schema introspection (tables, columns, types, keys, row counts, sample rows) rendered into a compact description the LLM can read.
2. **Run queries safely:** execute an already-validated `SELECT` on a connection that physically cannot write, with a time limit.

## 2. How it works

### 2.1 Read-only engine (`build_engine`)

- **SQLite:** the engine uses a custom `creator` that opens the file with the URI `file:<path>?mode=ro`. SQLite itself refuses every write, whatever SQL arrives.
- **PostgreSQL / others:** a normal SQLAlchemy engine. Every execution first runs `SET TRANSACTION READ ONLY` and `SET LOCAL statement_timeout`, and the transaction is always rolled back.
- `get_engine()` is cached, so the whole app shares one connection pool.

### 2.2 Query execution (`execute_readonly`)

1. Start a timer and open a connection.
2. **SQLite timeout:** install a progress handler that SQLite calls every 10,000 VM instructions; it aborts the query once the deadline passes. **PostgreSQL:** `statement_timeout`.
3. Execute, read column names and rows, and convert values to JSON-safe types (`Decimal` to `float`, dates to ISO strings, bytes to hex).
4. Remove the progress handler and roll back.
5. Any database error is re-raised as `QueryExecutionError` with the driver's original message (for example `no such column: c.customer_name`). A timeout becomes a clear sentence ("Query exceeded the 10s time limit…"). These messages go back to the LLM for self-correction.
6. Return `QueryResult(columns, rows, elapsed_ms)`.

### 2.3 Schema introspection (`get_schema`)

SQLAlchemy's `inspect()` returns, for each table: columns with types and nullability, primary key, foreign keys, `COUNT(*)` row count and the first 3 sample rows. The result is cached because the schema does not change while the app runs.

### 2.4 Schema rendering (`render_schema_context`)

Produces a token-efficient description, for example:

```
TABLE orders (5200 rows): order_id INTEGER PK, customer_id INTEGER, order_date DATE, status TEXT, channel TEXT
  FK customer_id -> customers(customer_id)
  sample: [{'order_id': 1, 'customer_id': 41, 'order_date': '2025-11-23', ...}]
```

Sample rows matter: they show the LLM the real formats (lowercase statuses, ISO dates), which prevents many empty-result mistakes.

## 3. How it was built

| Decision | Alternatives considered | Why |
|----------|-------------------------|-----|
| Database-level read-only mode | Trusting the SQL guard alone | Defence in depth: even if a guard bug let a write through, the database still refuses it |
| SQLite progress handler for timeouts | Thread-based cancellation | Built into SQLite, needs no extra thread, and leaves a clean connection |
| SQLAlchemy for introspection | Hand-written `PRAGMA` / `information_schema` queries | One code path for SQLite and PostgreSQL |
| Original error text passed back | Generic "query failed" | The model fixes queries far better when it sees the exact column or table problem |
| Caching the schema | Introspecting per request | Introspection runs `COUNT(*)` on each table, so caching keeps every question fast |

## 4. Test cases

File: `backend/tests/test_database.py` (runs against a freshly seeded database)

| ID | Test | What it checks | Result |
|----|------|----------------|--------|
| DB-01 | `test_schema_introspection` | 5 tables found; `orders` has 5,200 rows and `regions` 5; `order_items` foreign keys point to `orders` and `products`; primary keys detected | ✅ Pass |
| DB-02 | `test_schema_context_is_compact_and_complete` | The rendered context contains `TABLE orders (5200 rows)` and `FK customer_id -> customers(customer_id)` | ✅ Pass |
| DB-03 | `test_select_executes` | `SELECT COUNT(*) AS n FROM regions` returns columns `["n"]`, rows `[[5]]` and a timing | ✅ Pass |
| DB-04 | `test_connection_is_read_only[INSERT …]` | INSERT sent directly to the engine fails | ✅ Pass |
| DB-05 | `test_connection_is_read_only[DELETE …]` | DELETE fails | ✅ Pass |
| DB-06 | `test_connection_is_read_only[UPDATE …]` | UPDATE fails | ✅ Pass |
| DB-07 | `test_connection_is_read_only[DROP …]` | DROP TABLE fails, and the data is unchanged afterwards | ✅ Pass |
| DB-08 | `test_bad_column_raises_readable_error` | A wrong column raises `QueryExecutionError` containing "no such column" | ✅ Pass |
| DB-09 | `test_long_query_times_out` | An infinite recursive CTE is stopped after 0.3 s with a "time limit" message | ✅ Pass |

**Result: 9 / 9 passed.**

## 5. Limitations and next steps

- The schema cache needs an app restart after schema changes. A refresh endpoint would remove that.
- For very large tables, `COUNT(*)` at startup could be replaced by planner estimates.
