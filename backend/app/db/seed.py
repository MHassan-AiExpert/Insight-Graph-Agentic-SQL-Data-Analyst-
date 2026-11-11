"""Create and populate the sample e-commerce database.

The data is generated deterministically (fixed random seed) with realistic
patterns — regional differences, seasonality (Q4 peak), year-over-year growth,
customer segments and order statuses — so analytical questions return
meaningful answers.

Usage:
    python -m app.db.seed            # writes backend/data/insightgraph.db
    python -m app.db.seed --force    # recreate even if it exists
"""

from __future__ import annotations

import argparse
import math
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

from app.config import DEFAULT_DB_PATH

SEED = 42
START_DATE = date(2025, 1, 1)
END_DATE = date(2026, 10, 31)
N_CUSTOMERS = 650
N_ORDERS = 5200

REGIONS = [
    # (name, weight in customer base, growth factor)
    ("North America", 0.34, 1.10),
    ("Europe", 0.28, 1.25),
    ("Asia Pacific", 0.20, 1.45),
    ("Middle East", 0.10, 1.30),
    ("Latin America", 0.08, 0.95),
]

SEGMENTS = [("Consumer", 0.62), ("SMB", 0.28), ("Enterprise", 0.10)]
CHANNELS = [("web", 0.52), ("mobile", 0.33), ("marketplace", 0.15)]
STATUSES = [("completed", 0.82), ("shipped", 0.06), ("cancelled", 0.07), ("returned", 0.05)]

PRODUCTS = {
    "Electronics": [
        ("Aurora Wireless Earbuds", 89.0),
        ("Pulse Smartwatch", 199.0),
        ("Nimbus Bluetooth Speaker", 129.0),
        ("Volt Power Bank 20K", 49.0),
        ("Lumen 4K Webcam", 119.0),
        ("Echo Noise-Cancelling Headphones", 249.0),
        ("Quill Digital Pen", 69.0),
        ("Atlas Portable SSD 1TB", 139.0),
        ("Spark USB-C Hub", 59.0),
        ("Orbit Smart Plug 4-Pack", 39.0),
    ],
    "Home & Kitchen": [
        ("Brewline Pour-Over Kettle", 64.0),
        ("Hearth Cast Iron Skillet", 45.0),
        ("Crisp Air Fryer XL", 139.0),
        ("Bloom Ceramic Planter Set", 34.0),
        ("Cloudrest Memory Pillow", 59.0),
        ("Glow Aroma Diffuser", 42.0),
        ("Prism Glass Food Containers", 38.0),
        ("Steady Knife Block Set", 119.0),
        ("Breeze Desk Fan", 49.0),
        ("Nest Throw Blanket", 55.0),
    ],
    "Sports & Outdoors": [
        ("Summit Hiking Backpack 30L", 98.0),
        ("Stride Running Shoes", 129.0),
        ("Flex Yoga Mat Pro", 58.0),
        ("Trail Insulated Bottle", 32.0),
        ("Core Adjustable Dumbbells", 189.0),
        ("Ridge Camping Lantern", 36.0),
        ("Glide Resistance Bands", 24.0),
        ("Peak Trekking Poles", 74.0),
        ("Tide Swim Goggles", 22.0),
        ("Rally Tennis Racket", 149.0),
    ],
    "Beauty & Personal Care": [
        ("Silk Vitamin C Serum", 36.0),
        ("Pure Hydrating Cleanser", 22.0),
        ("Velvet Hair Dryer", 99.0),
        ("Calm Night Cream", 44.0),
        ("Fresh Bamboo Toothbrush 4-Pack", 14.0),
        ("Shine Argan Hair Oil", 28.0),
        ("Clear SPF 50 Sunscreen", 19.0),
        ("Smooth Electric Shaver", 79.0),
        ("Dew Sheet Mask 10-Pack", 18.0),
        ("Balance Body Lotion", 21.0),
    ],
    "Office & Stationery": [
        ("Ledger Hardcover Notebook", 18.0),
        ("Focus Ergonomic Chair", 289.0),
        ("Align Monitor Stand", 69.0),
        ("Swift Gel Pens 12-Pack", 12.0),
        ("Grid Desk Organizer", 29.0),
        ("Tempo Desk Lamp", 54.0),
        ("Anchor Laptop Sleeve", 35.0),
        ("Script Fountain Pen", 49.0),
        ("Board Whiteboard Kit", 45.0),
        ("Stack Document Trays", 26.0),
    ],
    "Toys & Games": [
        ("Builder Brick Set 500", 49.0),
        ("Strategy Board Game Classic", 39.0),
        ("Puzzle 1000 Pieces", 19.0),
        ("Racer RC Car", 69.0),
        ("Plush Bear Large", 29.0),
        ("Science Kit Junior", 44.0),
        ("Card Game Party Pack", 17.0),
        ("Art Studio Set", 34.0),
        ("Drone Mini Explorer", 89.0),
        ("Magnetic Tiles 60", 59.0),
    ],
}

SCHEMA_SQL = """
CREATE TABLE regions (
    region_id   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
);
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    region_id   INTEGER NOT NULL REFERENCES regions(region_id),
    segment     TEXT NOT NULL CHECK (segment IN ('Consumer','SMB','Enterprise')),
    signup_date DATE NOT NULL
);
CREATE TABLE products (
    product_id  INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    unit_price  REAL NOT NULL,
    unit_cost   REAL NOT NULL
);
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date  DATE NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('completed','shipped','cancelled','returned')),
    channel     TEXT NOT NULL CHECK (channel IN ('web','mobile','marketplace'))
);
CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    REAL NOT NULL,
    discount      REAL NOT NULL DEFAULT 0 CHECK (discount >= 0 AND discount < 1)
);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_items_order ON order_items(order_id);
CREATE INDEX idx_items_product ON order_items(product_id);
"""


def _weighted(rng: random.Random, options: list[tuple]):
    return rng.choices([o[0] for o in options], weights=[o[1] for o in options], k=1)[0]


def _order_date(rng: random.Random, growth: float) -> date:
    """Sample a date with Q4 seasonality and regional year-over-year growth."""
    span = (END_DATE - START_DATE).days
    while True:
        d = START_DATE + timedelta(days=rng.randint(0, span))
        seasonal = 1.0 + 0.35 * math.cos((d.month - 11.5) / 12 * 2 * math.pi)
        trend = 1.0 + (growth - 1.0) * ((d - START_DATE).days / 365)
        if rng.random() < (seasonal * trend) / 2.6:
            return d


def build_database(path: Path = DEFAULT_DB_PATH, force: bool = False) -> Path:
    path = Path(path)
    if path.exists() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    rng = random.Random(SEED)
    fake = Faker()
    Faker.seed(SEED)

    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)

    conn.executemany("INSERT INTO regions VALUES (?, ?)", [(i + 1, r[0]) for i, r in enumerate(REGIONS)])

    product_rows = []
    pid = 1
    for category, items in PRODUCTS.items():
        for name, price in items:
            margin = rng.uniform(0.32, 0.58)
            product_rows.append((pid, name, category, price, round(price * (1 - margin), 2)))
            pid += 1
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", product_rows)

    customers = []
    for cid in range(1, N_CUSTOMERS + 1):
        region_idx = rng.choices(range(len(REGIONS)), weights=[r[1] for r in REGIONS], k=1)[0]
        name = fake.name()
        handle = name.lower().replace(" ", ".").replace("'", "")
        email = f"{handle}{cid}@{fake.free_email_domain()}"
        signup = START_DATE - timedelta(days=rng.randint(0, 540) + rng.randint(0, 180))
        customers.append((cid, name, email, region_idx + 1, _weighted(rng, SEGMENTS), signup.isoformat()))
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", customers)

    # Customer-level purchasing propensity (a few heavy buyers, a long tail).
    propensity = [rng.paretovariate(1.6) for _ in customers]
    category_bias = {
        "Consumer": {"Beauty & Personal Care": 1.5, "Toys & Games": 1.4},
        "SMB": {"Office & Stationery": 2.0, "Electronics": 1.3},
        "Enterprise": {"Office & Stationery": 2.4, "Electronics": 1.8},
    }

    orders, items = [], []
    item_id = 1
    for oid in range(1, N_ORDERS + 1):
        cust = rng.choices(customers, weights=propensity, k=1)[0]
        region_growth = REGIONS[cust[3] - 1][2]
        segment = cust[4]
        od = _order_date(rng, region_growth)
        orders.append((oid, cust[0], od.isoformat(), _weighted(rng, STATUSES), _weighted(rng, CHANNELS)))

        n_lines = rng.choices([1, 2, 3, 4], weights=[0.5, 0.3, 0.14, 0.06], k=1)[0]
        weights = [category_bias.get(segment, {}).get(p[2], 1.0) for p in product_rows]
        for prod in rng.choices(product_rows, weights=weights, k=n_lines):
            qty_max = 12 if segment == "Enterprise" else 5 if segment == "SMB" else 3
            qty = rng.randint(1, qty_max)
            discount = (
                rng.choice([0, 0, 0, 0.05, 0.1, 0.15]) if od.month in (11, 12) else rng.choice([0, 0, 0, 0, 0.05, 0.1])
            )
            items.append((item_id, oid, prod[0], qty, prod[3], discount))
            item_id += 1

    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)
    conn.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?)", items)
    conn.commit()
    conn.close()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the InsightGraph sample database.")
    parser.add_argument("--path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--force", action="store_true", help="Recreate the database if it exists.")
    args = parser.parse_args()
    out = build_database(args.path, force=args.force)
    print(f"Database ready at {out}")


if __name__ == "__main__":
    main()
