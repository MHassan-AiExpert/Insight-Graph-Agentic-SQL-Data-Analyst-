# Module Report 04 — SQL Safety Guard

**File:** `backend/app/services/sql_guard.py`
**Depends on:** sqlglot
**Used by:** `classify_intent` node (pre-check), `validate_sql` node (AST guard)

## 1. Purpose

Makes sure nothing the LLM writes can damage or overload the database. It provides two independent checks:

1. **`looks_destructive(question)`:** a deterministic pre-check on the user's *question*, run before any LLM call.
2. **`validate_sql(sql, allowed_tables, dialect, max_rows)`:** a structural check on the generated *SQL*, run before execution.

## 2. How it works

### 2.1 Destructive-intent pre-check

A regular expression looks for a destructive verb (`delete, drop, truncate, insert, update, alter, wipe, erase`) followed, within a couple of words, by a data object (`orders, customers, products, rows, records, table, database, prices…`).

- "Delete all cancelled orders" → blocked
- "Show the **change in orders** month over month" → allowed (no destructive verb)
- "Which customers placed the most orders?" → allowed

Verbs that are often analytical, such as "change", "remove" and "modify", were deliberately left out to avoid false positives. The LLM intent router catches the subtler cases.

### 2.2 AST guard

```
raw SQL
 ├─ strip ``` fences and trailing ;           (models often wrap SQL in markdown)
 ├─ sqlglot.parse(dialect)                     → readable error if it cannot be parsed
 ├─ exactly 1 statement                        → blocks "SELECT 1; DROP TABLE …"
 ├─ root must be exp.Query                     → SELECT / UNION / WITH only
 ├─ walk the whole tree for forbidden nodes    → Insert, Update, Delete, Merge, Create, Drop, Alter,
 │                                               TruncateTable, Command, Grant, Revoke, Copy, Attach,
 │                                               Detach, Pragma, Into, LoadData, Transaction, Set, Use…
 ├─ forbidden functions                        → load_extension, pg_sleep, pg_read_file, dblink…
 ├─ every table must exist (CTE-aware)         → blocks hallucinated tables, allows WITH aliases
 └─ LIMIT                                      → none: append "LIMIT 500"; above 500: cap; otherwise keep
```

It returns `ValidatedSQL(sql, tables, limit_applied)` or raises `SQLValidationError` with a message written for the LLM to act on, for example *"Unknown table 'users'. Available tables: customers, order_items, …"*.

When it only appends a LIMIT, the guard keeps the model's original formatting, so the SQL users see is exactly the SQL that ran.

## 3. How it was built

| Decision | Alternatives | Why |
|----------|--------------|-----|
| Parse into an AST with sqlglot | Regex / keyword blocklists | Regex is easy to bypass (comments, casing, nested CTEs) and also blocks innocent text such as a column named `updated_at`. An AST checks what the query actually *does*. |
| Walk the entire tree | Only check the root | PostgreSQL allows `WITH x AS (DELETE … RETURNING *) SELECT …`. The root is a SELECT, but a write hides inside. Walking every node catches it. |
| Allow-list of tables | Trust the model | Stops hallucinated tables early and gives precise feedback for self-correction |
| Error messages written for the model | Generic errors | The message becomes part of the next prompt, so it states what is allowed |
| Pre-check before the LLM | Rely only on the LLM router | Destructive requests are refused even if the model is unavailable or misclassifies, with zero tokens spent |

## 4. Test cases

File: `backend/tests/test_sql_guard.py`

### Allowed queries

| ID | Input | Expected | Result |
|----|-------|----------|--------|
| SG-01 | `SELECT * FROM orders` | Allowed | ✅ Pass |
| SG-02 | `select count(*) … where status = 'completed'` | Allowed (lowercase) | ✅ Pass |
| SG-03 | `WITH monthly AS (…) SELECT * FROM monthly` | Allowed (CTE) | ✅ Pass |
| SG-04 | `SELECT name FROM regions UNION SELECT category FROM products` | Allowed (UNION) | ✅ Pass |
| SG-05 | `` ```sql SELECT name FROM regions; ``` `` | Allowed after fences are stripped | ✅ Pass |

### Blocked queries

| ID | Input | Expected error | Result |
|----|-------|----------------|--------|
| SG-06 | `DELETE FROM orders` | Only read-only | ✅ Pass |
| SG-07 | `UPDATE orders SET status = 'x'` | Only read-only | ✅ Pass |
| SG-08 | `INSERT INTO regions VALUES (9, 'Mars')` | Only read-only | ✅ Pass |
| SG-09 | `DROP TABLE orders` | Only read-only | ✅ Pass |
| SG-10 | `PRAGMA table_info(orders)` | Only read-only | ✅ Pass |
| SG-11 | `SELECT 1; DROP TABLE orders` | Single SQL statement | ✅ Pass |
| SG-12 | `WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x` | Forbidden operation | ✅ Pass |
| SG-13 | `SELECT * FROM users` | Unknown table | ✅ Pass |
| SG-14 | `SELECT load_extension('evil') FROM orders` | Not allowed | ✅ Pass |
| SG-15 | `SELEC * FROM` | Could not be parsed | ✅ Pass |
| SG-16 | empty string | Empty | ✅ Pass |

### LIMIT handling

| ID | Test | Expected | Result |
|----|------|----------|--------|
| SG-17 | `test_adds_limit_when_missing` | `LIMIT 100` added, `limit_applied=True` | ✅ Pass |
| SG-18 | `test_caps_excessive_limit` | `LIMIT 100000` → `LIMIT 500` | ✅ Pass |
| SG-19 | `test_keeps_small_limit` | `LIMIT 5` unchanged | ✅ Pass |
| SG-20 | `test_cte_names_are_not_treated_as_unknown_tables` | CTE alias `t` accepted; referenced tables `["orders"]` | ✅ Pass |

### Destructive-intent pre-check

| ID | Question | Expected | Result |
|----|----------|----------|--------|
| SG-21 | Delete all cancelled orders | Blocked | ✅ Pass |
| SG-22 | drop the orders table | Blocked | ✅ Pass |
| SG-23 | Update prices for all products | Blocked | ✅ Pass |
| SG-24 | Truncate the customers table | Blocked | ✅ Pass |
| SG-25 | What is total revenue by region? | Allowed | ✅ Pass |
| SG-26 | Show the change in orders month over month | Allowed (no false positive) | ✅ Pass |
| SG-27 | Which customers placed the most orders? | Allowed | ✅ Pass |

The guard is also exercised end-to-end by `test_self_corrects_after_safety_violation` (graph) and `test_destructive_question_is_refused` (API).

**Result: 27 / 27 passed.**
