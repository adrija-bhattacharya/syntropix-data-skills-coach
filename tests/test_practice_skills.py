"""Execution-verified practice beyond SQL: Excel formulas, Python/pandas code and
value answers (stats, Power BI, Tableau, data viz, data engineering, Git).

The same contract as the SQL lab: every task's reference answer grades correct,
every known mistake (distractor) is diagnosed as itself, and the diagnosis names
the concept to repair."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api
from assessment_bank import build_item_bank
from domains import resolve, seed_graph
from engine import Engine
from practice import excel as xl
from practice.catalogue import ALL_TASKS, BY_ID, CONCEPT_DOMAIN, grade_task, tasks_for
from practice.content.excel_tasks import SHEET
from practice.pyrun import SandboxRejected, check_code, run_python

DA_DE = (
    "sql",
    "python",
    "python_data",
    "spreadsheets",
    "stats",
    "dataviz",
    "powerbi",
    "tableau",
    "data_eng",
    "git",
)


# ------------------------------------------------------------- catalogue
def test_every_data_skill_concept_has_a_practice_task() -> None:
    for domain in DA_DE:
        for cid in seed_graph(domain).concept_ids:
            assert tasks_for(cid), f"{domain}.{cid} has no practice task"


def test_task_ids_are_unique_and_concepts_known() -> None:
    assert len(BY_ID) == len(ALL_TASKS)
    for t in ALL_TASKS:
        assert t.concept in CONCEPT_DOMAIN
        assert t.kind in ("sql", "python", "excel", "value")
        for d in t.distractors:
            assert d.concept in CONCEPT_DOMAIN


@pytest.mark.parametrize("kind", ["sql", "excel", "value"])
def test_references_pass_and_distractors_are_diagnosed(kind: str) -> None:
    for t in (t for t in ALL_TASKS if t.kind == kind):
        assert grade_task(t, t.reference).correct, t.id
        for d in t.distractors:
            g = grade_task(t, d.value)
            assert not g.correct, (t.id, d.code)
            assert d.code in [x.code for x in g.diagnoses], (t.id, d.code)


def test_python_references_pass_and_distractors_are_diagnosed() -> None:
    for t in (t for t in ALL_TASKS if t.kind == "python"):
        assert grade_task(t, t.reference).correct, t.id
        for d in t.distractors:
            assert d.code in [x.code for x in grade_task(t, d.value).diagnoses], (t.id, d.code)


# ------------------------------------------------------------- Excel
@pytest.mark.parametrize(
    ("formula", "want"),
    [
        ("=SUM(E2:E11)", 80.0),
        ("=COUNT(E2:E11)", 9.0),
        ('=SUMIF(B2:B11,"East",E2:E11)', 35.0),
        ('=COUNTIFS(B2:B11,"North",D2:D11,"Pens")', 1.0),
        ('=VLOOKUP("Ink",H2:I5,2,FALSE)', "Writing"),
        ('=INDEX(I2:I5,MATCH("Paper",H2:H5,0))', "Office"),
        ("=PROPER(TRIM(C2))", "Asha Rao"),
        ('=IF(E2>10,"big","small")', "big"),
        ('=IFERROR(VLOOKUP("Glue",H2:I5,2,FALSE),"none")', "none"),
    ],
)
def test_excel_evaluator(formula: str, want: object) -> None:
    assert xl.evaluate(formula, SHEET) == want


def test_excel_errors_and_fill_down() -> None:
    with pytest.raises(xl.ExcelError):
        xl.evaluate('=VLOOKUP("Glue",H2:I5,2,FALSE)', SHEET)  # #N/A
    with pytest.raises(xl.ExcelError):
        xl.evaluate("=NOSUCHFN(1)", SHEET)  # #NAME?
    assert xl.shift("=E2/SUM($E$2:$E$11)", 1) == "=E3/SUM($E$2:$E$11)"
    assert xl.shift("=E2/SUM(E2:E11)", 1) == "=E3/SUM(E3:E12)"


def test_excel_missing_anchor_is_diagnosed() -> None:
    t = next(t for t in ALL_TASKS if t.kind == "excel" and t.fill_down)
    g = grade_task(t, t.reference.replace("$", ""))
    assert not g.correct
    codes = [d.code for d in g.diagnoses]
    assert "missing_anchor" in codes or any(d.code in codes for d in t.distractors)


# ------------------------------------------------------------- Python sandbox
@pytest.mark.parametrize(
    "code",
    [
        "import os",
        "from subprocess import run",
        "open('x.txt')",
        "result = ().__class__.__bases__",
        "orders.to_csv('leak.csv')",
        "eval('1+1')",
    ],
)
def test_python_sandbox_rejects_unsafe_code(code: str) -> None:
    with pytest.raises(SandboxRejected):
        check_code(code)


def test_python_runs_with_the_shop_tables_and_times_out() -> None:
    ok = run_python("result = len(orders)")
    assert not ok.exec.error and ok.exec.rows[0][0] > 0
    slow = run_python("while True:\n    pass", timeout_s=1)
    assert slow.exec.error


# ------------------------------------------------------------- graphs and routing
@pytest.mark.parametrize(
    ("goal", "source", "domain"),
    [
        ("bi analyst", "role", "bi analyst"),
        ("data engineer", "role", "data engineer"),
        ("power bi dashboards", "seed", "powerbi"),
        ("tableau", "seed", "tableau"),
        ("airflow", "seed", "data_eng"),
        ("excel", "seed", "spreadsheets"),
    ],
)
def test_goals_route_to_the_right_graph(goal: str, source: str, domain: str) -> None:
    r = resolve(goal)
    assert (r.source, r.domain) == (source, domain)


@pytest.mark.parametrize("domain", DA_DE)
def test_every_data_skill_has_a_calibrated_bank(domain: str) -> None:
    assert build_item_bank(domain) is not None


def test_role_graph_practice_uses_prefixed_ids() -> None:
    eng = Engine(resolve("data engineer").kg)
    assert eng.concept_id("orchestration") == "data_eng.orchestration"
    assert eng.concept_id("no_such_concept") is None
    kinds = {t.kind for t in eng.practice_tasks()}
    assert {"sql", "python", "value"} <= kinds


def test_wrong_excel_answer_repairs_and_replans() -> None:
    eng = Engine(seed_graph("spreadsheets"))
    t = next(t for t in ALL_TASKS if t.id == "xl_share")
    out = eng.submit_practice("xl", t.id, t.reference.replace("$", ""), goals=[t.concept])
    assert not out.correct and out.diagnoses
    assert out.graded is not None and any(not c.passed for c in out.graded.checks)
    assert out.plan.concepts


# ------------------------------------------------------------- API
def test_api_serves_excel_and_value_workspaces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_ENGINES", {})
    monkeypatch.setattr(api, "_LEARNER_ENGINE", {})
    client = TestClient(api.app)
    tasks = client.get(
        "/practice/tasks", params={"goal": "excel", "learner_id": "x1", "target": "lookups"}
    ).json()
    assert tasks["path"][-1] == "lookups" and tasks["start"]
    assert tasks["sheet"][0][:6] == ["Date", "Region", "Rep", "Product", "Units", "Price"]
    excel = [t for t in tasks["tasks"] if t["kind"] == "excel"]
    assert excel and all(t["cell"] for t in excel)

    t = next(t for t in excel if t["id"] == "xl_share")
    r = client.post(
        "/practice/submit",
        json={
            "learner_id": "x1",
            "task_id": t["id"],
            "query": BY_ID[t["id"]].reference,
            "goals": ["lookups"],
            "goal": "excel",
        },
    ).json()
    assert r["correct"] and all(c["passed"] for c in r["checks"])

    bi = client.get(
        "/practice/tasks",
        params={"goal": "bi analyst", "learner_id": "b1", "target": "powerbi.calculate"},
    ).json()
    choice = next(t for t in bi["tasks"] if t["options"])
    assert choice["concept_id"].count(".") == 1
    wrong = next(o for o in choice["options"] if o != BY_ID[choice["id"]].reference)
    r = client.post(
        "/practice/submit",
        json={
            "learner_id": "b1",
            "task_id": choice["id"],
            "query": wrong,
            "goals": ["powerbi.calculate"],
            "goal": "bi analyst",
        },
    ).json()
    assert not r["correct"] and r["diagnoses"]
    assert all(d["concept_id"] in bi["mastery"] or "." in d["concept_id"] for d in r["diagnoses"])
