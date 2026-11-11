# Module Report 03 — Sample Data Generator

**File:** `backend/app/db/seed.py`
**Depends on:** `sqlite3`, Faker
**Used by:** app startup (`main.py` lifespan), Docker first run, test fixtures

## 1. Purpose

Creates a realistic e-commerce database so the analyst works the moment it starts, with data that has real patterns to discover (growth, seasonality, segment behaviour). A dataset of uniform random numbers would make every insight meaningless.

## 2. How it works

```
build_database(path, force=False)
 ├─ skip if the file exists and force=False   (safe on every app start)
 ├─ create schema (5 tables, CHECK constraints, FKs, 4 indexes)
 ├─ regions     5 rows        each with a customer weight and a growth factor
 ├─ products    60 rows       6 categories × 10 products, price, cost (32–58 % margin)
 ├─ customers   650 rows      region by weight, segment (Consumer 62 % / SMB 28 % / Enterprise 10 %)
 ├─ orders      5,200 rows    Pareto purchase propensity, date sampler, status, channel
 └─ order_items ≈ 9,300 rows  1–4 lines per order, segment-based category bias, quantity, discount
```

### Realistic patterns built in

| Pattern | How it is generated |
|---------|---------------------|
| **Seasonality** | Date sampler with weight `1 + 0.35·cos(…)`, peaking in Nov/Dec/Jan |
| **Regional growth** | Weight grows over time by region: Asia Pacific ×1.45/yr, Middle East ×1.30, Europe ×1.25, North America ×1.10, Latin America ×0.95 |
| **Heavy buyers** | Each customer gets a Pareto(1.6) propensity, so a few customers place many orders |
| **Segment behaviour** | Enterprise buys more Office and Electronics, in larger quantities (up to 12); Consumers buy more Beauty and Toys |
| **Holiday discounts** | November and December lines get discounts more often |
| **Order lifecycle** | completed 82 %, shipped 6 %, cancelled 7 %, returned 5 % |

These patterns are what the agent "discovers": Q3 growth in North America and Asia Pacific, Enterprise AOV about 3.7× Consumer, the year-end revenue peak.

## 3. How it was built

| Decision | Why |
|----------|-----|
| Fixed seed (`random.Random(42)`, `Faker.seed(42)`) | Every machine and every CI run gets byte-identical data, so tests can assert exact counts and golden answers stay valid |
| Rejection sampling for dates | Simple way to apply seasonality and growth together without a full time-series model |
| CHECK constraints in the schema | The data documents its own rules (allowed statuses, discount range), and the LLM sees the valid values |
| Signup dates before the first order | Keeps the data logically consistent (no orders before signup) |
| `force=False` default | The app can call it on every start without wiping user changes |
| Standalone CLI (`python -m app.db.seed --force`) | Easy to regenerate locally |

## 4. Test cases

File: `backend/tests/test_seed.py`

| ID | Test | What it checks | Result |
|----|------|----------------|--------|
| SEED-01 | `test_row_counts` | 5 regions, 650 customers, 60 products, 5,200 orders, and more order lines than orders | ✅ Pass |
| SEED-02 | `test_generation_is_deterministic` | Two databases built separately produce an identical SHA-256 digest of every order and its quantities | ✅ Pass |
| SEED-03 | `test_dates_and_referential_integrity` | All orders fall inside 2025-01-01 to 2026-10-31; no orphan order lines; no signup after the data window starts | ✅ Pass |
| SEED-04 | `test_business_constraints` | Cost is always below price, discounts are in [0, 1), and all four statuses are present | ✅ Pass |
| SEED-05 | `test_existing_database_is_not_overwritten` | A second call without `force` leaves the file untouched | ✅ Pass |

The dataset is also validated indirectly by every database, graph and scenario test, which assert exact results such as 5,200 orders and 5 regions sorted by revenue.

**Result: 5 / 5 passed.**
