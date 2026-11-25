"""SQLite store shared by the orders, refunds and CRM MCP servers.

Every eval trial builds a fresh database from the committed seed data in spec/seeds/data/,
plus any per-task fixtures, so trials never share state.

    uv run python -m mcp_servers.db --out .data/cases.sqlite
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "spec" / "seeds" / "data"
REFERENCE_DATE = "2026-11-20"  # must match spec/seeds/generate_seeds.py

SCHEMA = """
CREATE TABLE customers (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
    tier TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE orders (
    id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
    channel TEXT NOT NULL CHECK (channel IN ('online', 'in_store', 'factory_outlet')),
    payment_method TEXT NOT NULL CHECK (payment_method IN ('card', 'paypal', 'gift_card')),
    status TEXT NOT NULL CHECK (status IN ('processing', 'shipped', 'delivered', 'cancelled')),
    placed_at TEXT NOT NULL, delivered_at TEXT, shipping_fee REAL NOT NULL, total REAL NOT NULL
);
CREATE TABLE order_items (
    id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id), sku TEXT NOT NULL,
    name TEXT NOT NULL, unit_price REAL NOT NULL, quantity INTEGER NOT NULL
);
CREATE TABLE refunds (
    id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id),
    item_id TEXT REFERENCES order_items(id), amount REAL NOT NULL, reason TEXT NOT NULL,
    refund_method TEXT NOT NULL, return_channel TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, created_by TEXT NOT NULL
);
CREATE TABLE cases (
    id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
    order_id TEXT REFERENCES orders(id), subject TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'pending', 'escalated', 'resolved')),
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE case_notes (
    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Insert order respects foreign keys.
TABLES = ["customers", "orders", "order_items", "refunds", "cases", "case_notes"]


def _insert(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    for row in rows:
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


def build_database(path: str | Path, fixtures: dict[str, list[dict]] | None = None) -> Path:
    """Create a fresh database at `path` from the seed data plus optional task fixtures."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    fixtures = fixtures or {}
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        for table in TABLES:
            _insert(conn, table, json.loads((SEED_DIR / f"{table}.json").read_text()))
            _insert(conn, table, fixtures.get(table, []))
    return path


@contextmanager
def connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a connection that returns dict-like rows and commits on success."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return None if row is None else dict(row)


def next_id(conn: sqlite3.Connection, table: str, prefix: str) -> str:
    """Sequential IDs for rows the agent creates, e.g. REF-A0001, NOTE-A0001."""
    n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE id LIKE ?", (f"{prefix}%",)).fetchone()[0]
    return f"{prefix}{n + 1:04d}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=".data/cases.sqlite")
    print(f"Built {build_database(parser.parse_args().out)}")


if __name__ == "__main__":
    main()
