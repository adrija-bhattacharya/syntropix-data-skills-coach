"""Execution-verified practice: sandbox, output-diff fingerprints, closed loop.

A learner's SQL is graded by its *result*; a wrong result is fingerprinted into
the concept that typically causes it; that blame updates the learner, the
prerequisite graph's edge evidence, and the re-plan routes through a repair.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api
from domains import seed_graph
from engine import Engine
from practice import SHOP_DB, TASKS, TASKS_BY_ID, expected, grade, run_sql
from practice.catalogue import ALL_TASKS

# --------------------------------------------------------------------- sandbox


@pytest.mark.parametrize(
    ("query", "kind"),
    [
        ("DELETE FROM products", "forbidden"),
        ("UPDATE products SET price = 0", "forbidden"),
        ("DROP TABLE products", "forbidden"),
        ("ATTACH DATABASE 'x.db' AS x", "forbidden"),
        ("PRAGMA table_info(products)", "forbidden"),
        ("SELECT 1; DELETE FROM products", "multiple_statements"),
        ("SELEC name FROM products", "syntax"),
        ("SELECT nme FROM products", "no_such_column"),
        ("SELECT * FROM prodcts", "no_such_table"),
        (
            "WITH RECURSIVE r(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM r) "
            "SELECT COUNT(*) FROM r",
            "timeout",
        ),
        ("SELECT 1 " + "x" * 5000, "too_long"),
    ],
)
def test_sandbox_refuses_or_classifies(query: str, kind: str) -> None:
    r = run_sql(SHOP_DB, query, timeout_s=0.3)
    assert not r.ok
    assert r.error_kind == kind


def test_sandbox_runs_are_isolated() -> None:
    run_sql(SHOP_DB, "DELETE FROM products")
    assert len(run_sql(SHOP_DB, "SELECT * FROM products").rows) == 6


def test_sandbox_caps_rows() -> None:
    r = run_sql(SHOP_DB, "SELECT * FROM order_items a, order_items b", max_rows=20)
    assert r.ok and r.truncated and len(r.rows) == 20


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_every_reference_runs_and_passes_itself(task: object) -> None:
    t = TASKS_BY_ID[task.id]  # type: ignore[attr-defined]
    assert expected(t).ok and expected(t).rows
    _got, verdict = grade(t, t.reference)
    assert verdict.correct


def test_grading_is_by_result_not_text() -> None:
    t = TASKS_BY_ID["unknown_city"]
    _got, v = grade(t, "select NAME from customers c where NOT (c.city IS NOT NULL)")
    assert v.correct


# ---------------------------------------------------------------- fingerprints


@pytest.mark.parametrize(
    ("task_id", "query", "code", "concept"),
    [
        (
            "unknown_city",
            "SELECT name FROM customers WHERE city = NULL",
            "null_equality",
            "null_logic",
        ),
        (
            "repeat_customers",
            "SELECT customer_id FROM orders WHERE COUNT(*) > 1 GROUP BY customer_id",
            "aggregate_in_where",
            "having",
        ),
        (
            "spend_per_customer",
            "SELECT c.name, SUM(o.amount) FROM customers c JOIN orders o ON o.customer_id = c.id "
            "JOIN order_items i ON i.order_id = o.id GROUP BY c.name",
            "join_fanout",
            "inner_join",
        ),
        (
            "orders_per_customer",
            "SELECT c.name, COUNT(o.id) FROM customers c JOIN orders o ON o.customer_id = c.id "
            "GROUP BY c.name",
            "dropped_unmatched",
            "outer_join",
        ),
        (
            "orders_per_customer",
            "SELECT c.name, COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id "
            "GROUP BY c.name",
            "count_star_outer",
            "null_logic",
        ),
        (
            "order_vs_customer_total",
            "SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id",
            "collapsed_window",
            "window_functions",
        ),
        (
            "order_vs_customer_total",
            "SELECT id, customer_id, amount, SUM(amount) OVER () FROM orders",
            "missing_partition",
            "window_functions",
        ),
        (
            "orders_per_status",
            "SELECT status, COUNT(*) FROM orders",
            "missing_group_by",
            "group_by",
        ),
        ("categories", "SELECT category FROM products", "duplicates", "distinct"),
        (
            "top3_products",
            "SELECT name, price FROM products ORDER BY price LIMIT 3",
            "wrong_direction",
            "order_limit",
        ),
        (
            "top3_products",
            "SELECT name, price FROM products ORDER BY price DESC",
            "unlimited",
            "order_limit",
        ),
        ("pricey_products", "SELECT name FROM products", "unfiltered", "where"),
        (
            "repeat_customers",
            "SELECT customer_id FROM orders HAVING COUNT(*) > 1",
            "having_without_group",
            "group_by",
        ),
        (
            "price_band",
            "SELECT name, CASE WHEN price < 5 THEN 'budget' WHEN price <= 30 THEN 'mid' "
            "ELSE 'premium' END FROM products",
            "case_boundary",
            "case_when",
        ),
        (
            "order_customer",
            "SELECT id, name FROM orders o JOIN customers c ON c.id = o.customer_id",
            "ambiguous_column",
            "inner_join",
        ),
        ("products_list", "SELECT name FROM products", "wrong_columns", "select_from"),
    ],
)
def test_misconception_fingerprints(task_id: str, query: str, code: str, concept: str) -> None:
    _got, v = grade(TASKS_BY_ID[task_id], query)
    assert not v.correct
    top = v.diagnoses[0]
    assert (top.code, top.concept) == (code, concept), v.diagnoses


def test_unmatched_failure_falls_back_to_the_task_concept() -> None:
    _got, v = grade(TASKS_BY_ID["shout_names"], "SELECT LOWER(name) FROM customers")
    assert [d.code for d in v.diagnoses] == ["result_differs"]
    assert v.blamed == {"string_fns_sql": 1.0}


# ----------------------------------------------------------------- closed loop

_COUNT_STAR = (
    "SELECT c.name, COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id "
    "GROUP BY c.name"
)


def _engine_with_basics() -> Engine:
    eng = Engine(seed_graph("sql"))
    st = eng.ensure("u", time_budget_s=3600)
    for c in ("select_from", "where", "aggregates", "group_by", "inner_join", "null_logic"):
        st.mastery[c] = 0.9
    eng.store.put("u", st)
    return eng


def test_blame_lands_on_the_prerequisite_and_routes_a_repair() -> None:
    eng = _engine_with_basics()
    out = eng.submit_practice("u", "orders_per_customer", _COUNT_STAR, goals=["outer_join"])
    assert not out.correct
    # the misconception is about NULLs, so null_logic drops - not just the task concept
    before, after = out.mastery["null_logic"]
    assert after < before and after < 0.75
    # null_logic is not an ancestor of outer_join, but the re-plan still routes through it
    assert "null_logic" not in eng.kg.all_prerequisites("outer_join")
    assert "null_logic" in out.plan.concepts
    assert out.next_task == "unknown_city"
    # ... and the watched candidate edge null_logic -> outer_join gains evidence
    assert [(a, b) for a, b, _m in out.edge_evidence] == [("null_logic", "outer_join")]


def test_repair_then_retry_closes_the_loop() -> None:
    eng = _engine_with_basics()
    eng.submit_practice("u", "orders_per_customer", _COUNT_STAR, goals=["outer_join"])
    fixed = eng.submit_practice(
        "u", "unknown_city", "SELECT name FROM customers WHERE city IS NULL", goals=["outer_join"]
    )
    assert fixed.correct and fixed.next_task == "orders_per_customer"
    done = eng.submit_practice(
        "u",
        "orders_per_customer",
        _COUNT_STAR.replace("COUNT(*)", "COUNT(o.id)"),
        goals=["outer_join"],
    )
    assert done.correct
    assert done.mastery["outer_join"][1] > done.mastery["outer_join"][0]


def test_a_failure_without_a_prerequisite_to_blame_is_retried() -> None:
    eng = Engine(seed_graph("sql"))
    out = eng.submit_practice("u", "products_list", "SELECT name FROM products")
    assert not out.correct and out.next_task == "products_list"


def test_repeated_attribution_grows_a_missing_edge() -> None:
    """Claim D fed by execution evidence: enough learners whose outer-join
    failures fingerprint as NULL misconceptions make the healer propose
    null_logic -> outer_join, an edge the curated graph does not have."""
    eng = Engine(seed_graph("sql"))
    for i in range(12):
        lid = f"l{i}"
        st = eng.ensure(lid, time_budget_s=3600)
        for c in ("select_from", "where", "aggregates", "group_by", "inner_join"):
            st.mastery[c] = 0.9
        eng.store.put(lid, st)
        eng.submit_practice(lid, "orders_per_customer", _COUNT_STAR)
    report = eng.graph_health()
    proposed = {(c.a, c.b) for c in (*report.added, *report.suggested)}
    assert ("null_logic", "outer_join") in proposed


def test_replan_is_fast() -> None:
    eng = _engine_with_basics()
    out = eng.submit_practice("u", "orders_per_customer", _COUNT_STAR, goals=["outer_join"])
    assert out.replan_ms < 250


def test_unknown_task_raises() -> None:
    with pytest.raises(KeyError):
        Engine(seed_graph("sql")).submit_practice("u", "nope", "SELECT 1")


# ------------------------------------------------------------------------- API


def test_api_practice_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    # fresh engines: submissions add graph evidence, which must not leak into other tests
    monkeypatch.setattr(api, "_ENGINES", {})
    monkeypatch.setattr(api, "_LEARNER_ENGINE", {})
    client = TestClient(api.app)
    tasks = client.get("/practice/tasks", params={"goal": "learn sql"}).json()
    sql_graph = seed_graph("sql").concepts
    assert "customers" in tasks["schema"] and len(tasks["tasks"]) == sum(
        t.concept in sql_graph for t in ALL_TASKS
    )
    assert {t["kind"] for t in tasks["tasks"]} >= {"sql", "value"}

    r = client.post(
        "/practice/submit",
        json={
            "learner_id": "api-practice",
            "goal": "learn sql",
            "task_id": "orders_per_customer",
            "query": _COUNT_STAR,
        },
    ).json()
    assert r["correct"] is False
    assert r["diagnoses"][0]["code"] == "count_star_outer"
    assert r["result"]["columns"] and r["plan"]["steps"]
    assert r["next_task"]

    bad = client.post(
        "/practice/submit",
        json={"learner_id": "x", "goal": "learn sql", "task_id": "nope", "query": "SELECT 1"},
    )
    assert bad.status_code == 404


# ------------------------------------------------- Stitch UI data contracts


def test_checks_and_row_status_explain_a_wrong_result() -> None:
    from practice import checks, row_status

    t = TASKS_BY_ID["orders_per_customer"]
    got, _v = grade(t, _COUNT_STAR)
    cs = {c.id: c.passed for c in checks(t, got, expected(t))}
    assert cs == {"runs": True, "columns": True, "rows": True, "values": False}
    status, missing = row_status(got, expected(t))
    assert status.count("extra") == missing == 2  # Eshan and Farah show 1, not 0


def test_skeleton_hint_blanks_every_name() -> None:
    from practice import skeleton

    s = skeleton(TASKS_BY_ID["orders_per_customer"].reference)
    assert s.startswith("SELECT …, COUNT(…) FROM … LEFT JOIN")
    assert "customers" not in s and "orders" not in s


def test_api_practice_exposes_schema_hints_checks_and_repairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "_ENGINES", {})
    monkeypatch.setattr(api, "_LEARNER_ENGINE", {})
    client = TestClient(api.app)
    tasks = client.get(
        "/practice/tasks", params={"goal": "learn sql", "learner_id": "ui", "target": "outer_join"}
    ).json()
    assert tasks["path"][-1] == "outer_join" and tasks["start"]
    assert tasks["schema"]["customers"]["rows"] == 6
    city = next(c for c in tasks["schema"]["customers"]["columns"] if c["name"] == "city")
    assert city["nulls"] == 1
    assert all(len(t["hints"]) == 2 for t in tasks["tasks"] if t["kind"] == "sql")
    assert all(t["hints"] for t in tasks["tasks"])
    assert 0 < tasks["p_correct"]["outer_join"] < 1

    r = client.post(
        "/practice/submit",
        json={
            "learner_id": "ui",
            "goal": "learn sql",
            "task_id": "orders_per_customer",
            "query": _COUNT_STAR,
            "goals": ["outer_join"],
        },
    ).json()
    assert [c["passed"] for c in r["checks"]] == [True, True, True, False]
    assert r["result"]["row_status"].count("extra") == r["result"]["missing_rows"] == 2
    repaired = [s["concept_id"] for s in r["plan"]["steps"] if s["repair"]]
    assert repaired == ["null_logic"]

    plan = client.post(
        "/recommend",
        json={
            "learner_id": "ui",
            "goal": "learn sql",
            "goals": ["outer_join"],
            "time_budget_min": 600,
        },
    ).json()["paths"][0]
    assert any(s["repair"] for s in plan["steps"])  # the repair persists into the study plan
    assert plan["baseline_minutes"] >= plan["total_minutes"]
    assert set(plan["p_correct"]) == set(plan["mastery"])
