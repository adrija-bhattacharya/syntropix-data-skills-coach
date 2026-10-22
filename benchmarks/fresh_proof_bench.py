"""Claim H2 - does re-testing on new data separate real skill from memorised or lucky answers?

    python -m benchmarks.fresh_proof_bench   # -> results/fresh_proof.{json,csv}

Three kinds of answers, each first checked to pass on the practice data (the
check a portfolio does today):

* **memorised** - the expected output typed in as constants (``SELECT 'Dana'``,
  ``result = pd.DataFrame([...])``), one per task that reads the database;
* **lucky** - a query that only works on the practice rows
  (``WHERE id = 4`` for "customers with no city"), written by hand
  (:data:`LUCKY`);
* **correct, written differently** - a right answer that isn't the reference
  (:data:`CORRECT`), to show that real skill is not thrown out.

Each answer is then re-tested on 3 fresh variants of the database
(:mod:`practice.mutate`).  Reported per kind: share passing on the practice
data and share passing all 3 fresh datasets.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from practice.catalogue import ALL_TASKS, BY_ID, grade_task
from practice.fingerprint import expected
from practice.mutate import _q, _reference, fresh_check, uses_db
from practice.tasks import SHOP_DB

RESULTS = Path(__file__).resolve().parent.parent / "results"
SEEDS = [101, 202, 303]

LUCKY: list[tuple[str, str]] = [
    ("unknown_city", "SELECT name FROM customers WHERE id = 4"),
    ("pricey_products", "SELECT name FROM products WHERE id IN (12, 13, 14)"),
    ("top3_products", "SELECT name, price FROM products WHERE price >= 32 ORDER BY price DESC"),
    ("repeat_customers", "SELECT customer_id FROM orders WHERE customer_id IN (1, 2, 3) GROUP BY customer_id"),
    ("categories", "SELECT 'stationery' UNION SELECT 'books' UNION SELECT 'electronics'"),
    ("order_totals", "SELECT 7, SUM(amount) FROM orders"),
    ("above_average", "SELECT name FROM products WHERE price > 20"),
    ("de_null_test", "SELECT 104"),
    ("spend_per_customer", "SELECT c.name, SUM(o.amount) FROM customers c JOIN orders o ON o.customer_id = c.id WHERE c.id < 5 GROUP BY c.name"),
    ("employee_manager", "SELECT e.name, m.name FROM employees e JOIN employees m ON m.id = e.manager_id WHERE e.id <= 5"),
    ("orders_per_customer", "SELECT c.name, COUNT(o.id) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE c.id <= 6 GROUP BY c.id, c.name"),
    ("big_spenders", "SELECT customer_id FROM orders WHERE customer_id IN (1, 4) GROUP BY customer_id"),
    ("orders_per_status", "SELECT status, COUNT(*) FROM orders WHERE id <= 106 GROUP BY status"),
    ("de_incremental", "SELECT id, order_date FROM orders WHERE id IN (104, 105, 106)"),
]  # fmt: skip

CORRECT: list[tuple[str, str]] = [
    ("pricey_products", "SELECT name FROM products WHERE NOT price <= 20"),
    ("top3_products", "SELECT name, price FROM products ORDER BY 2 DESC LIMIT 3"),
    ("categories", "SELECT category FROM products GROUP BY category"),
    ("unknown_city", "SELECT name FROM customers WHERE NOT city IS NOT NULL"),
    ("repeat_customers", "SELECT customer_id FROM orders GROUP BY customer_id HAVING COUNT(id) >= 2"),
    ("big_spenders", "SELECT customer_id FROM orders GROUP BY customer_id HAVING SUM(amount) > 70"),
    ("orders_per_customer", "SELECT c.name, (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.id) FROM customers c"),
    ("above_average", "WITH a AS (SELECT AVG(price) AS p FROM products) SELECT name FROM products, a WHERE price > a.p"),
    ("order_totals", "SELECT COUNT(id), SUM(amount) FROM orders"),
    ("orders_per_status", "SELECT status, COUNT(id) FROM orders GROUP BY 1"),
    ("de_null_test", "SELECT id FROM orders WHERE amount IS NULL ORDER BY id"),
    ("order_customer", "SELECT orders.id, customers.name FROM customers, orders WHERE customers.id = orders.customer_id"),
    ("employee_manager", "SELECT e.name, (SELECT m.name FROM employees m WHERE m.id = e.manager_id) FROM employees e WHERE e.manager_id IS NOT NULL"),
    ("shout_names", "SELECT UPPER(c.name) FROM customers AS c"),
    ("price_band", "SELECT name, CASE WHEN price >= 10 AND price <= 30 THEN 'mid' WHEN price < 10 THEN 'budget' ELSE 'premium' END FROM products"),
]  # fmt: skip


def _memorised(task: Any) -> str | None:
    """The practice data's right answer, typed in as constants."""
    want = expected(task) if task.kind == "sql" else _reference(task, SHOP_DB, f"{task.id}@base")
    if not want.rows:
        return None
    if task.kind == "sql":
        return " UNION ALL ".join("SELECT " + ", ".join(_q(v) for v in r) for r in want.rows)
    if want.columns == ("value",) and len(want.rows) == 1:
        return f"result = {want.rows[0][0]!r}"
    return (
        f"result = pd.DataFrame({[list(r) for r in want.rows]!r}, columns={list(want.columns)!r})"
    )


def _answers() -> list[tuple[str, Any, str]]:
    out: list[tuple[str, Any, str]] = []
    for t in ALL_TASKS:
        if uses_db(t) and (m := _memorised(t)) is not None:
            out.append(("memorised", t, m))
    out += [("lucky", BY_ID[t], q) for t, q in LUCKY]
    out += [("correct, written differently", BY_ID[t], q) for t, q in CORRECT]
    return out


def run() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for kind, task, answer in _answers():
        on_practice = grade_task(task, answer).correct
        proof = fresh_check(task, answer, SEEDS)
        rows.append({
            "kind": kind, "task": task.id, "language": task.kind,
            "passes_practice_data": on_practice,
            "passes_fresh_data": proof.passed,
            "fresh_datasets": len(proof.runs),
            "answer": answer[:160],
        })  # fmt: skip
    summary: dict[str, Any] = {}
    for kind in ("memorised", "lucky", "correct, written differently"):
        sub = [r for r in rows if r["kind"] == kind and r["passes_practice_data"]]
        summary[kind] = {
            "answers_passing_practice_data": len(sub),
            "share_also_passing_fresh_data": round(
                sum(1 for r in sub if r["passes_fresh_data"]) / max(1, len(sub)), 3
            ),
        }
    return {"summary": summary, "rows": rows}


def main() -> int:
    out = run()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "fresh_proof.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    with (RESULTS / "fresh_proof.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out["rows"][0]))
        w.writeheader()
        w.writerows(out["rows"])
    for r in out["rows"]:
        if not r["passes_practice_data"]:
            print(f"  (doesn't pass the practice data, left out) {r['kind']}: {r['task']}")
    for kind, s in out["summary"].items():
        print(f"{kind:<30} pass practice data: {s['answers_passing_practice_data']:>3}   "
              f"of those, pass fresh data: {s['share_also_passing_fresh_data']:.0%}")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
