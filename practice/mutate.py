"""Fresh-data proof: re-run a solved task on a practice database it has never seen.

A saved answer that passes on the practice data proves little if it could have
been memorised (``SELECT 'Dana'``) or only works by luck on those few rows
(``WHERE id = 4``).  Here every check builds a **new variant of the database**
from a seed and runs both the learner's answer and the task's reference on it;
the answer passes only if it gives the reference's result on the new data too.

How a variant is made from any practice database (no task-specific code):

* every original row is kept, so the traps the tasks rely on stay (NULLs,
  customers without orders, one-to-many joins);
* numeric non-key values of about half the rows are scaled by 0.6-1.6x;
* new rows are added to every table (about half as many again): primary keys
  continue the sequence, ``*_id`` columns point at real rows of their parent
  table (``customer_id -> customers``; an unknown parent means the same table,
  e.g. ``manager_id``), dates fall inside the original date range,
  categories are drawn from the existing values (sometimes a new one), names
  are new, and a column that had NULLs gets at least one new NULL.

Only tasks whose answer is computed from the database can be re-proven this way
(:func:`uses_db`): SQL, and Python that reads the tables.

A variant on which the reference itself is not well defined (ties that make
``ORDER BY ... LIMIT`` depend on storage order) is detected - the reference is
also run with the rows stored in reverse - and skipped.

Each check records the seed, so anyone can rebuild the same variant and
reproduce the verdict.
"""

from __future__ import annotations

import random
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any

from practice.fingerprint import results_match
from practice.sandbox import ExecResult, run_sql
from practice.tasks import SHOP_DB, Task

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NAMES = (
    "Gauri", "Hiro", "Ines", "Jamal", "Kavya", "Liam", "Mina", "Noor", "Omar", "Pia", "Quinn",
    "Ravi", "Sara", "Tomas", "Uma", "Vik", "Wen", "Xena", "Yusuf", "Zara", "Arjun", "Bea",
    "Cyrus", "Divya", "Elif", "Femi", "Gita", "Hana", "Ivan", "Jia",
)  # fmt: skip
# a few new values per familiar column, so a variant can hold a category the
# practice data never had (DISTINCT / GROUP BY answers then change too)
NEW_VALUES = {
    "city": ("Pune", "Chennai", "Jaipur"),
    "category": ("toys", "garden"),
    "status": ("returned",),
}
SUPPORTED = ("sql", "python")
TABLES = ("customers", "products", "orders", "order_items", "employees")


# --------------------------------------------------------------- variants
def _date_between(rng: random.Random, lo: str, hi: str) -> str:
    from datetime import date

    a, b = date.fromisoformat(lo), date.fromisoformat(hi)
    return date.fromordinal(rng.randint(a.toordinal(), b.toordinal())).isoformat()


def _q(v: object) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return repr(v)


def variant_tables(
    setup: str, seed: int
) -> tuple[list[str], dict[str, list[str]], dict[str, list[tuple[Any, ...]]]]:
    """(CREATE statements, columns per table, rows per table) of the variant."""
    rng = random.Random(seed)
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(setup)
        meta = list(
            conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY rowid")
        )
        creates = [sql for _n, sql in meta]
        tables = [n for n, _s in meta]
        cols: dict[str, list[str]] = {}
        rows: dict[str, list[tuple[Any, ...]]] = {}
        for t in tables:
            info = list(conn.execute(f"PRAGMA table_info({t})"))
            names = [c[1] for c in info]
            types = [str(c[2]).upper() for c in info]
            pks = {c[1] for c in info if c[5]}
            old = [tuple(r) for r in conn.execute(f"SELECT * FROM {t}")]
            cols[t] = names
            new_rows = [list(r) for r in old]
            # scale numeric non-key values on about half the rows
            for r in new_rows:
                if rng.random() < 0.5:
                    continue
                for j, (n, ty) in enumerate(zip(names, types)):
                    if n in pks or n.endswith("_id") or r[j] is None:
                        continue
                    if ty == "REAL":
                        r[j] = round(float(r[j]) * rng.uniform(0.6, 1.6), 2)
            # add rows
            k = max(2, len(old) // 2)
            used_names = {r[j] for r in old for j, n in enumerate(names) if n == "name"}
            pool = [x for x in NAMES if x not in used_names]
            rng.shuffle(pool)
            for i in range(k):
                row: list[Any] = []
                for j, (n, ty) in enumerate(zip(names, types)):
                    vals = [r[j] for r in old]
                    present = [v for v in vals if v is not None]
                    null_share = (len(vals) - len(present)) / max(1, len(vals))
                    if n in pks and ty.startswith("INT"):  # continue the key sequence
                        top = max([r[j] for r in new_rows if r[j] is not None] + [0])
                        row.append(top + 1 + rng.randint(0, 2))
                        continue
                    if n.endswith("_id"):
                        parent = next(
                            (p for p in (n[:-3] + "s", n[:-3] + "es", n[:-3]) if p in rows), t
                        )
                        pid = cols[parent].index("id") if "id" in cols.get(parent, []) else None
                        pool_ids = (
                            [r[pid] for r in rows[parent]] if parent in rows and pid is not None
                            else [r[j] for r in new_rows if r[j] is not None]
                        )  # fmt: skip
                        if null_share and rng.random() < max(0.15, null_share):
                            row.append(None)
                        else:
                            row.append(rng.choice(pool_ids) if pool_ids else None)
                        continue
                    if null_share and rng.random() < max(0.2, null_share):
                        row.append(None)
                        continue
                    if not present:
                        row.append(None)
                    elif ty == "REAL":
                        row.append(round(float(rng.choice(present)) * rng.uniform(0.6, 1.6), 2))
                    elif ty.startswith("INT"):
                        row.append(int(rng.choice(present)))
                    elif all(isinstance(v, str) and _DATE.match(v) for v in present):
                        row.append(_date_between(rng, min(present), max(present)))
                    elif n == "name" or len(set(present)) == len(present) > 3:
                        row.append(pool.pop() if pool else f"{rng.choice(present)} {i + 2}")
                    elif n in NEW_VALUES and rng.random() < 0.3:
                        row.append(rng.choice(NEW_VALUES[n]))
                    else:
                        row.append(rng.choice(present))
                new_rows.append(row)
            added = new_rows[len(old) :]
            for j, n in enumerate(names):  # a column that had NULLs gets at least one new NULL
                had_null = any(r[j] is None for r in old)
                if had_null and n not in pks and added and all(r[j] is not None for r in added):
                    rng.choice(added)[j] = None
            if any(n in pks for n in names):  # keep primary keys unique
                pk_j = [j for j, n in enumerate(names) if n in pks]
                seen: set[tuple[Any, ...]] = set()
                uniq = []
                for r in new_rows:
                    key = tuple(r[j] for j in pk_j)
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(r)
                new_rows = uniq
            rows[t] = [tuple(r) for r in new_rows]
        return creates, cols, rows
    finally:
        conn.close()


def _script(
    creates: list[str],
    cols: dict[str, list[str]],
    rows: dict[str, list[tuple[Any, ...]]],
    *,
    reverse: bool = False,
) -> str:
    out = [c + ";" for c in creates]
    for t, rs in rows.items():
        seq = list(reversed(rs)) if reverse else rs
        for r in seq:
            out.append(
                f"INSERT INTO {t} ({', '.join(cols[t])}) VALUES ({', '.join(_q(v) for v in r)});"
            )
    return "\n".join(out)


def variant(setup: str = SHOP_DB, seed: int = 0, *, reverse: bool = False) -> str:
    """The database script for one seed (``reverse``: same rows, stored backwards)."""
    return _script(*variant_tables(setup, seed), reverse=reverse)


# ------------------------------------------------------------------ checks
@dataclass(frozen=True, slots=True)
class FreshRun:
    seed: int
    passed: bool
    changed: bool  # the right answer on this variant differs from the one on the practice data
    rows: int  # rows in the right answer on this variant


@dataclass
class FreshProof:
    task_id: str
    supported: bool
    runs: list[FreshRun] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.supported and bool(self.runs) and all(r.passed for r in self.runs)

    @property
    def fresh(self) -> bool:
        """At least one variant changed the right answer - so this was a real test."""
        return any(r.changed for r in self.runs)

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "passed": self.passed, "fresh": self.fresh}


def uses_db(task: Task) -> bool:
    """Is the answer computed from the practice tables (so new data can test it)?"""
    if task.kind == "sql":
        return True
    return task.kind == "python" and any(re.search(rf"\b{t}\b", task.reference) for t in TABLES)


def _reference(task: Task, db: str, key: str) -> ExecResult:
    if task.kind == "sql":
        return run_sql(db, task.reference)
    from practice.pyrun import run_reference

    return run_reference(key, task.reference, dict(task.env), db)


def fresh_check(task: Task, answer: str, seeds: list[int]) -> FreshProof:
    """Run ``answer`` and the reference on one database variant per seed.

    A seed whose variant leaves the reference ill-defined (its result depends
    on storage order) is replaced by the next one, at most a few times."""
    if not uses_db(task):
        return FreshProof(task.id, False)
    base = _reference(task, SHOP_DB, f"{task.id}@base")
    picked: list[tuple[int, str, ExecResult]] = []
    for s in seeds:
        for attempt in range(4):
            seed = s + attempt * 7919
            db = variant(SHOP_DB, seed)
            want = _reference(task, db, f"{task.id}@{seed}")
            again = _reference(task, variant(SHOP_DB, seed, reverse=True), f"{task.id}@{seed}r")
            if want.ok and results_match(again, want, ordered=task.ordered):
                picked.append((seed, db, want))
                break  # otherwise ties: the reference itself isn't well defined here
    if task.kind == "sql":
        got = [run_sql(db, answer) for _s, db, _w in picked]
    else:
        from practice.pyrun import run_python_many

        got = [
            r.exec for r in run_python_many(answer, [db for _s, db, _w in picked], dict(task.env))
        ]
    proof = FreshProof(task.id, True)
    for (seed, _db, want), g in zip(picked, got):
        proof.runs.append(
            FreshRun(
                seed, results_match(g, want, ordered=task.ordered),
                not results_match(want, base, ordered=task.ordered), len(want.rows),
            )
        )  # fmt: skip
    return proof
