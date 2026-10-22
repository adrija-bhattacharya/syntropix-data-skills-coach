"""Claim H1 - does a wrong answer lead to the video moment that fixes it?

    python -m benchmarks.mistake_moments_bench   # -> results/mistake_moments.{json,csv}

Wrong answers: every built-in wrong answer of the Python / pandas / Excel /
pipeline tasks, plus classic SQL mistakes written for the SQL tasks
(:data:`SQL_WRONG`).  Each is run through the real grader; the strongest
diagnosis picks the clip.

A clip is **on target** when the chapter it plays (or, for a topic-level jump,
the video's title) names the topic the mistake belongs to - checked with a
fixed pattern per topic (:data:`GOLD`), written before looking at the results.
Compared with what a learner gets without it:

* **task topic video** - the checked lesson for the *task's* topic, from its
  jump point (what the Learn page offers).  Often a different topic from the
  one the mistake points at.

Also reported: how much video each asks the learner to watch.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from pathlib import Path
from typing import Any

import mistake_moments as mm
from domains import seed_graph
from practice.catalogue import ALL_TASKS, BY_ID, grade_task

RESULTS = Path(__file__).resolve().parent.parent / "results"

SQL_WRONG: list[tuple[str, str]] = [
    ("unknown_city", "SELECT name FROM customers WHERE city = NULL"),
    ("de_null_test", "SELECT id FROM orders WHERE amount = NULL"),
    ("orders_per_customer", "SELECT c.name, COUNT(o.id) FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name"),
    ("orders_per_customer", "SELECT c.name, COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name"),
    ("repeat_customers", "SELECT customer_id FROM orders WHERE COUNT(*) > 1 GROUP BY customer_id"),
    ("categories", "SELECT category FROM products"),
    ("top3_products", "SELECT name, price FROM products ORDER BY price DESC"),
    ("pricey_products", "SELECT name FROM products"),
    ("orders_per_status", "SELECT status, COUNT(*) FROM orders"),
    ("order_vs_customer_total", "SELECT id, customer_id, amount, SUM(amount) OVER () FROM orders"),
    ("order_vs_customer_total", "SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id"),
    ("spend_per_customer", "SELECT c.name, SUM(o.amount) FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items i ON i.order_id = o.id GROUP BY c.name"),
    ("order_customer", "SELECT id, name FROM orders o JOIN customers c ON c.id = o.customer_id"),
    ("price_band", "SELECT name, CASE WHEN price < 10 THEN 'budget' WHEN price < 30 THEN 'mid' ELSE 'premium' END FROM products"),
    ("products_list", "SELECT name FROM products"),
    ("orders_per_month", "SELECT order_date, COUNT(*) FROM orders GROUP BY order_date"),
    ("top3_products", "SELECT name, price FROM products ORDER BY price LIMIT 3"),
    ("employee_manager", "SELECT e.name, m.name FROM employees e LEFT JOIN employees m ON m.id = e.manager_id"),
]  # fmt: skip

GOLD: dict[str, str] = {
    # sql
    "null_logic": r"null", "outer_join": r"left|right|outer|full", "having": r"having",
    "distinct": r"distinct|duplicate", "order_limit": r"order by|limit|top|sort",
    "where": r"where|filter", "group_by": r"group", "window_functions": r"window|over|partition|rank",
    "inner_join": r"join", "case_when": r"case", "select_from": r"select|column",
    "aggregates": r"aggregat|count|sum|avg", "date_fns_sql": r"date|month|time", "self_join": r"self",
    "subqueries": r"subquer", "ctes": r"cte|with", "set_ops": r"union|intersect|except",
    "incremental_loads": r"incremental|watermark|load", "dimensional_modeling": r"fact|dimension|star|model",
    # pandas / python
    "sort_rank": r"sort|rank", "array_ops": r"vector|array|numpy|operation|arithmetic",
    "merge_join": r"merge|join", "filtering": r"filter|boolean|condition|query",
    "groupby_agg": r"group", "datetime_pd": r"date|time", "missing_data": r"missing|nan|null|fill|drop",
    "pivot_melt": r"pivot|melt|reshap", "selecting": r"loc|select|column", "dataframe": r"data ?frame",
    "new_columns": r"column", "conditionals": r"\bif\b|condition|elif",
    # spreadsheets
    "agg_functions": r"sum|average|count|min|max|aggregat", "logical_functions": r"\bif|\band\b|\bor\b|logical",
    "dynamic_arrays": r"unique|filter|sort|dynamic|array", "cleaning_ss": r"clean|trim",
    "cells_ranges": r"range|cell|reference",
}  # fmt: skip


def _names() -> dict[str, str]:
    out: dict[str, str] = {}
    for d in {t.domain for t in ALL_TASKS}:
        try:
            kg = seed_graph(d)
        except Exception:
            continue
        out.update({c: kg.concepts[c].name for c in kg.concept_ids})
    return out


def _wrong_answers() -> list[tuple[Any, str]]:
    out = [(BY_ID[t], q) for t, q in SQL_WRONG]
    for t in ALL_TASKS:
        if t.kind in ("python", "excel", "sql"):
            out += [(t, d.value) for d in t.distractors]
    return out


def _on_target(concept: str, m: dict[str, Any]) -> bool:
    pat = GOLD.get(concept)
    if not pat:
        return False
    text = m["chapter"] if m["kind"] == "chapter" else f"{m['chapter']} {m['title']}"
    return re.search(pat, text, re.I) is not None


def _task_video(task: Any) -> dict[str, Any] | None:
    """The checked lesson for the task's own topic, from its jump point."""
    videos, _segs, checks = mm._library()
    best: dict[str, Any] | None = None
    for vid, v in videos.items():
        c = checks.get(vid, {})
        if v.get("concept") != task.concept or c.get("level") not in ("verified", "related"):
            continue
        if best is None or c.get("level") == "verified":
            start = int(c.get("start") or 0)
            best = {"video_id": vid, "title": v["title"], "chapter": c.get("chapter", ""),
                    "kind": "topic", "start": start, "end": int(v["minutes"] * 60)}  # fmt: skip
    return best


def run() -> dict[str, Any]:
    names = _names()
    rows: list[dict[str, Any]] = []
    for task, answer in _wrong_answers():
        g = grade_task(task, answer)
        if g.correct or not g.diagnoses:
            continue
        top = max(g.diagnoses, key=lambda d: d.weight)
        clip = mm.for_answer(task.domain, task.kind, g.diagnoses, names, top=1)
        m = clip["moments"][0] if clip else None
        base = _task_video(task)
        rows.append({
            "task": task.id, "domain": task.domain, "code": top.code, "blamed": top.concept,
            "task_topic": task.concept, "other_topic": top.concept != task.concept,
            "clip": f"{m['kind']}: {m['chapter'] or m['title']} [{m['start']}-{m['end']}s]" if m else "",
            "clip_on_target": bool(m and _on_target(top.concept, m)),
            "clip_seconds": (m["end"] - m["start"]) if m else 0,
            "clip_is_chapter": bool(m and m["kind"] == "chapter"),
            "baseline_on_target": bool(base and _on_target(top.concept, base)),
            "baseline_seconds": (base["end"] - base["start"]) if base else 0,
        })  # fmt: skip

    def share(key: str, sub: list[dict[str, Any]]) -> float:
        return round(sum(1 for r in sub if r[key]) / max(1, len(sub)), 3)

    def med_min(key: str) -> float:
        xs = [r[key] for r in rows if r[key]]
        return round(statistics.median(xs) / 60, 1) if xs else 0.0

    other = [r for r in rows if r["other_topic"]]
    summary = {
        "wrong_answers": len(rows),
        "clip_on_target": share("clip_on_target", rows),
        "baseline_on_target": share("baseline_on_target", rows),
        "mistakes_pointing_at_another_topic": len(other),
        "clip_on_target_other_topic": share("clip_on_target", other),
        "baseline_on_target_other_topic": share("baseline_on_target", other),
        "exact_chapter_share": share("clip_is_chapter", rows),
        "median_clip_minutes": med_min("clip_seconds"),
        "median_baseline_minutes": med_min("baseline_seconds"),
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    out = run()
    rows, summary = out["rows"], out["summary"]
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "mistake_moments.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    with (RESULTS / "mistake_moments.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        mark = "ok " if r["clip_on_target"] else "-- "
        print(f"{mark}{r['task']:<26} {r['code']:<22} -> {r['clip'][:70]}")
    print()
    for k, v in summary.items():
        print(f"{k:<36} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
