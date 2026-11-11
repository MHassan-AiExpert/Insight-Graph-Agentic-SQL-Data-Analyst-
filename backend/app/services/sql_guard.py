"""AST-level SQL safety guard built on sqlglot.

Rules (enforced on the parsed syntax tree, not with regex):
* exactly one statement
* the statement must be a read query (SELECT / UNION / WITH ... SELECT)
* no data-modifying or DDL nodes anywhere in the tree (incl. inside CTEs)
* every referenced table must exist in the allowed schema
* the outer query always carries a LIMIT no larger than ``max_rows``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = tuple(
    node
    for node in (
        getattr(exp, name, None)
        for name in (
            "Insert",
            "Update",
            "Delete",
            "Merge",
            "Create",
            "Drop",
            "Alter",
            "AlterTable",
            "TruncateTable",
            "Command",
            "Grant",
            "Revoke",
            "Copy",
            "Attach",
            "Detach",
            "Pragma",
            "Into",
            "LoadData",
            "Transaction",
            "Commit",
            "Rollback",
            "Set",
            "Use",
        )
    )
    if node is not None
)

FORBIDDEN_FUNCTIONS = {"load_extension", "pg_sleep", "pg_read_file", "pg_ls_dir", "lo_import", "dblink"}


class SQLValidationError(ValueError):
    """Raised when generated SQL violates a safety rule."""


@dataclass
class ValidatedSQL:
    sql: str
    tables: list[str] = field(default_factory=list)
    limit_applied: bool = False


def _strip_fences(sql: str) -> str:
    sql = sql.strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    return sql.strip().rstrip(";").strip()


def validate_sql(
    sql: str,
    allowed_tables: set[str] | list[str],
    dialect: str = "sqlite",
    max_rows: int = 500,
) -> ValidatedSQL:
    cleaned = _strip_fences(sql or "")
    if not cleaned:
        raise SQLValidationError("The query is empty.")

    try:
        statements = [s for s in sqlglot.parse(cleaned, read=dialect) if s is not None]
    except ParseError as exc:
        first = exc.errors[0]["description"] if getattr(exc, "errors", None) else str(exc)
        raise SQLValidationError(f"SQL could not be parsed: {first}") from exc

    if len(statements) != 1:
        raise SQLValidationError("Only a single SQL statement is allowed.")
    tree = statements[0]

    if not isinstance(tree, exp.Query):
        raise SQLValidationError(f"Only read-only SELECT queries are allowed (got {tree.key.upper()}).")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SQLValidationError(
                f"Forbidden operation detected: {node.key.upper()}. Only SELECT queries are allowed."
            )
        if isinstance(node, exp.Anonymous) and str(node.this).lower() in FORBIDDEN_FUNCTIONS:
            raise SQLValidationError(f"Function {node.this} is not allowed.")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    allowed = {t.lower() for t in allowed_tables}
    referenced: list[str] = []
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if not name or name in cte_names:
            continue
        if name not in allowed:
            raise SQLValidationError(f"Unknown table '{table.name}'. Available tables: {', '.join(sorted(allowed))}.")
        if name not in referenced:
            referenced.append(name)

    if not referenced and not cte_names:
        raise SQLValidationError("The query must read from at least one table in the schema.")

    limit_applied = False
    output = cleaned
    limit_node = tree.args.get("limit")
    if limit_node is None:
        # Keep the author's formatting and append the row limit to the outer query.
        output = f"{cleaned}\nLIMIT {max_rows}"
        limit_applied = True
    else:
        try:
            current = int(limit_node.expression.name)
        except (AttributeError, ValueError):
            current = None
        if current is None or current > max_rows:
            output = tree.limit(max_rows).sql(dialect=dialect, pretty=True)
            limit_applied = True

    return ValidatedSQL(sql=output, tables=referenced, limit_applied=limit_applied)


DESTRUCTIVE_INTENT = re.compile(
    r"\b(delete|drop|truncate|insert|update|alter|wipe|erase)\b\s+"
    r"(?:all\s+|the\s+|every\s+|from\s+|into\s+|table\s+|my\s+|our\s+)*(?:\w+\s+){0,2}?"
    r"(orders?|customers?|products?|regions?|items?|order_items|rows?|records?|data|tables?|database|entries|prices?)\b",
    re.IGNORECASE,
)


def looks_destructive(question: str) -> bool:
    """Cheap deterministic pre-check that runs before the LLM is asked anything."""
    return bool(DESTRUCTIVE_INTENT.search(question or ""))
