"""Read-only database access and schema introspection.

Two independent layers keep the database safe:
1. ``app.services.sql_guard`` only lets SELECT queries through.
2. This module opens SQLite in read-only mode and marks PostgreSQL
   transactions READ ONLY, with a statement timeout.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.config import get_settings


class QueryExecutionError(Exception):
    """Raised when a query fails or times out."""


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool
    primary_key: bool = False


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    sample_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    elapsed_ms: float

    @property
    def row_count(self) -> int:
        return len(self.rows)


def _readonly_sqlite_creator(path: str):
    def connect() -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        return conn

    return connect


def build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        db_path = url.database or ""
        return create_engine("sqlite://", creator=_readonly_sqlite_creator(db_path))
    return create_engine(database_url, pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    return build_engine(get_settings().database_url)


def dialect_name(engine: Engine | None = None) -> str:
    engine = engine or get_engine()
    return "postgres" if engine.dialect.name == "postgresql" else engine.dialect.name


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


def execute_readonly(sql: str, engine: Engine | None = None, timeout_s: float | None = None) -> QueryResult:
    """Execute a (pre-validated) SELECT query on a read-only connection."""
    engine = engine or get_engine()
    timeout_s = timeout_s or get_settings().query_timeout_seconds
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            if engine.dialect.name == "sqlite":
                raw = conn.connection.driver_connection
                deadline = started + timeout_s
                raw.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)
            elif engine.dialect.name == "postgresql":
                conn.execute(text("SET TRANSACTION READ ONLY"))
                conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}"))
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [[_jsonable(v) for v in row] for row in result.fetchall()]
            if engine.dialect.name == "sqlite":
                conn.connection.driver_connection.set_progress_handler(None, 0)
            conn.rollback()
    except Exception as exc:  # noqa: BLE001 - surfaced to the agent for self-correction
        message = str(getattr(exc, "orig", exc)) or exc.__class__.__name__
        if "interrupted" in message.lower():
            message = f"Query exceeded the {timeout_s:.0f}s time limit. Simplify it or aggregate more."
        raise QueryExecutionError(message) from exc
    return QueryResult(columns=columns, rows=rows, elapsed_ms=(time.perf_counter() - started) * 1000)


@lru_cache
def get_schema(engine: Engine | None = None) -> tuple[TableInfo, ...]:
    """Introspect all tables, row counts and a few sample rows."""
    engine = engine or get_engine()
    settings = get_settings()
    insp = inspect(engine)
    tables: list[TableInfo] = []
    with engine.connect() as conn:
        for name in sorted(insp.get_table_names()):
            pk_cols = set(insp.get_pk_constraint(name).get("constrained_columns") or [])
            columns = [
                ColumnInfo(
                    name=c["name"],
                    type=str(c["type"]),
                    nullable=bool(c.get("nullable", True)),
                    primary_key=c["name"] in pk_cols,
                )
                for c in insp.get_columns(name)
            ]
            fks = [
                {
                    "columns": fk["constrained_columns"],
                    "references_table": fk["referred_table"],
                    "references_columns": fk["referred_columns"],
                }
                for fk in insp.get_foreign_keys(name)
            ]
            quoted = engine.dialect.identifier_preparer.quote(name)
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar() or 0
            sample = conn.execute(text(f"SELECT * FROM {quoted} LIMIT {settings.sample_rows_per_table}"))
            sample_rows = [{k: _jsonable(v) for k, v in row._mapping.items()} for row in sample]
            tables.append(TableInfo(name, columns, fks, int(row_count), sample_rows))
    return tuple(tables)


def table_names(engine: Engine | None = None) -> list[str]:
    return [t.name for t in get_schema(engine)]


def render_schema_context(tables: list[TableInfo]) -> str:
    """Compact, LLM-friendly description of the selected tables."""
    blocks: list[str] = []
    for t in tables:
        cols = ", ".join(f"{c.name} {c.type}{' PK' if c.primary_key else ''}" for c in t.columns)
        lines = [f"TABLE {t.name} ({t.row_count} rows): {cols}"]
        for fk in t.foreign_keys:
            lines.append(
                f"  FK {', '.join(fk['columns'])} -> {fk['references_table']}({', '.join(fk['references_columns'])})"
            )
        if t.sample_rows:
            lines.append(f"  sample: {t.sample_rows[:2]}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
