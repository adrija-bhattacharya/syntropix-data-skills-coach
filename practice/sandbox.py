"""Sandboxed execution of a learner's SQL against a small practice database.

Every run gets a **fresh in-memory SQLite database** built from a fixed script,
so nothing a learner writes can persist or leak between runs.  On top of that:

* **read-only** - an authorizer allows only reads (``SELECT``, column reads,
  scalar / aggregate / window functions, CTEs).  ``INSERT``, ``UPDATE``,
  ``ATTACH``, ``PRAGMA`` and the rest are refused before they execute.
* **one statement** - ``sqlite3`` refuses a second statement in ``execute``.
* **bounded** - a progress handler aborts after ``timeout_s`` of VM work, the
  query text is length-capped, and at most ``max_rows`` rows are fetched.

Errors are classified into a small closed vocabulary (:data:`ErrorKind`) that
the fingerprinting stage reads.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Literal

ErrorKind = Literal[
    "",  # no error
    "syntax",
    "no_such_column",
    "no_such_table",
    "ambiguous_column",
    "misuse_aggregate",
    "having_without_group",
    "misuse_window",
    "forbidden",
    "multiple_statements",
    "timeout",
    "too_long",
    "other",
]

Row = tuple[Any, ...]

MAX_QUERY_CHARS = 4000

_ALLOWED_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        getattr(sqlite3, "SQLITE_RECURSIVE", 33),
    }
)


@dataclass(frozen=True, slots=True)
class ExecResult:
    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    error: str = ""
    error_kind: ErrorKind = ""
    truncated: bool = False
    ms: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.error_kind


def _authorizer(action: int, *_args: object) -> int:
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def _classify(msg: str) -> ErrorKind:
    m = msg.lower()
    if "not authorized" in m:
        return "forbidden"
    if "one statement at a time" in m:
        return "multiple_statements"
    if "interrupted" in m:
        return "timeout"
    if "no such column" in m:
        return "no_such_column"
    if "no such table" in m:
        return "no_such_table"
    if "ambiguous column" in m:
        return "ambiguous_column"
    if "having clause on a non-aggregate" in m:
        return "having_without_group"
    if "misuse of aggregate" in m or "aggregate functions are not allowed" in m:
        return "misuse_aggregate"
    if "misuse of window" in m or "window function" in m:
        return "misuse_window"
    if "syntax error" in m or "incomplete input" in m or "unrecognized token" in m:
        return "syntax"
    return "other"


def run_sql(
    setup_script: str,
    query: str,
    *,
    timeout_s: float = 1.0,
    max_rows: int = 500,
) -> ExecResult:
    """Run ``query`` against a fresh database built from ``setup_script``."""
    query = query.strip().rstrip(";").strip()
    if len(query) > MAX_QUERY_CHARS:
        return ExecResult((), (), f"query longer than {MAX_QUERY_CHARS} characters", "too_long")
    if not query:
        return ExecResult((), (), "empty query", "syntax")

    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(setup_script)
        conn.set_authorizer(_authorizer)
        deadline = time.perf_counter() + timeout_s
        conn.set_progress_handler(lambda: int(time.perf_counter() > deadline), 1000)
        t0 = time.perf_counter()
        try:
            cur = conn.execute(query)
            rows = cur.fetchmany(max_rows + 1)
        except (sqlite3.Error, sqlite3.Warning) as exc:
            msg = str(exc)
            return ExecResult((), (), msg, _classify(msg), ms=(time.perf_counter() - t0) * 1e3)
        cols = tuple(d[0] for d in cur.description or ())
        return ExecResult(
            columns=cols,
            rows=tuple(tuple(r) for r in rows[:max_rows]),
            truncated=len(rows) > max_rows,
            ms=(time.perf_counter() - t0) * 1e3,
        )
    finally:
        conn.close()


def describe_db(setup_script: str) -> dict[str, dict[str, object]]:
    """Per table: row count and per column the declared type, primary key flag
    and how many NULLs it holds - read from the database itself."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(setup_script)
        out: dict[str, dict[str, object]] = {}
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tables:
            cols = []
            for _cid, name, ctype, _notnull, _default, pk in conn.execute(
                f"PRAGMA table_info({t})"
            ):
                nulls = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE {name} IS NULL").fetchone()[0]
                cols.append({"name": name, "type": ctype or "ANY", "pk": bool(pk), "nulls": nulls})
            rows = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            out[t] = {"rows": rows, "columns": cols}
        return out
    finally:
        conn.close()
