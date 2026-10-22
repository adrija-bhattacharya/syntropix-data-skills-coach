"""Claims H1-H3: mistake -> video moment, proof re-tested on new data,
forgetting learned per topic with just-in-time reviews."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api
import mistake_moments as mm
import portfolio
import telemetry
from algorithms import forgetting as fg
from practice.catalogue import ALL_TASKS, BY_ID, grade_task
from practice.mutate import fresh_check, uses_db, variant
from practice.tasks import SHOP_DB


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(portfolio, "STATE", tmp_path / "portfolio")
    monkeypatch.setattr(portfolio, "ATTEST_KEY", tmp_path / "attest.key")
    monkeypatch.setattr(portfolio, "_RECHECK", {})
    monkeypatch.setattr(telemetry, "STATE", tmp_path / "telemetry")
    monkeypatch.setattr(api, "_ENGINES", {})
    monkeypatch.setattr(api, "_LEARNER_ENGINE", {})
    monkeypatch.setattr(api, "_REPROVED_AT", {})


# ------------------------------------------------------------------ H1
def test_a_mistake_finds_the_chapter_that_explains_it() -> None:
    clips = mm.find(domain="sql", concept="null_logic", concept_name="NULL & three-valued logic",
                    code="null_equality")  # fmt: skip
    assert clips and clips[0].kind == "chapter" and "null" in clips[0].chapter.lower()
    assert 0 <= clips[0].start < clips[0].end <= clips[0].start + mm.MAX_CLIP_S
    assert len({c.video_id for c in clips}) == len(clips)  # one clip per video


def test_use_case_chapters_are_not_case_when() -> None:
    assert "case" not in mm.tokens("Use Case: Data Aggregation")
    clips = mm.find(
        domain="sql", concept="case_when", concept_name="CASE WHEN", code="case_boundary"
    )
    assert all("use case" not in c.chapter.lower() for c in clips)


def test_a_graded_wrong_answer_gets_a_clip_for_the_blamed_topic() -> None:
    task = BY_ID["unknown_city"]
    g = grade_task(task, "SELECT name FROM customers WHERE city = NULL")
    clip = mm.for_answer(
        task.domain, task.kind, g.diagnoses, {"null_logic": "NULL & three-valued logic"}
    )
    assert clip and clip["code"] == "null_equality" and clip["concept_id"] == "null_logic"
    assert mm.for_answer(task.domain, task.kind, [], {}) is None


def test_practice_submit_returns_the_fix_clip() -> None:
    client = TestClient(api.app)
    body = {"learner_id": "h1", "task_id": "unknown_city", "goal": "sql",
            "query": "SELECT name FROM customers WHERE city = NULL"}  # fmt: skip
    wrong = client.post("/practice/submit", json=body).json()
    assert not wrong["correct"] and wrong["fix_clip"]["moments"]
    right = client.post("/practice/submit", json={**body, "query": BY_ID["unknown_city"].reference})
    assert right.json()["fix_clip"] is None


# ------------------------------------------------------------------ H2
def test_variants_are_reproducible_and_keep_the_original_rows() -> None:
    assert variant(SHOP_DB, 7) == variant(SHOP_DB, 7) != variant(SHOP_DB, 8)
    v = variant(SHOP_DB, 7)
    assert "'Dana'" in v and "'Eshan'" in v  # traps stay: no city, no orders
    assert v.count("INSERT INTO customers") > 6


def test_right_answers_survive_new_data_and_memorised_ones_dont() -> None:
    task = BY_ID["unknown_city"]
    assert fresh_check(task, task.reference, [1, 2, 3]).passed
    lucky = fresh_check(task, "SELECT name FROM customers WHERE id = 4", [1, 2, 3])
    assert grade_task(task, "SELECT name FROM customers WHERE id = 4").correct and not lucky.passed
    assert lucky.fresh  # the new data really changed the answer
    other = fresh_check(task, "SELECT name FROM customers WHERE NOT city IS NOT NULL", [1, 2, 3])
    assert other.passed


def test_only_tasks_computed_from_the_tables_can_be_re_proven() -> None:
    kinds = {t.kind for t in ALL_TASKS if uses_db(t)}
    assert kinds == {"sql", "python"}
    assert not uses_db(next(t for t in ALL_TASKS if t.kind == "value"))
    assert not fresh_check(next(t for t in ALL_TASKS if t.kind == "excel"), "=1", [1]).supported


def test_proofs_are_signed_and_tampering_is_caught() -> None:
    task = BY_ID["pricey_products"]
    s = portfolio.Solve(task.id, "where", "WHERE", "sql", "sql", task.prompt, task.reference,
                        [], [], [], "2026-10-22T10:00", 1)  # fmt: skip
    p = portfolio.prove("ada", s, [5, 6, 7])
    assert p and p["payload"]["passed"] and p["payload"]["seeds"]
    assert portfolio.verify_attestation(p["payload"], p["sig"])
    assert not portfolio.verify_attestation({**p["payload"], "passed": False}, p["sig"])


def test_public_page_re_tests_on_request_and_reproduces_a_seed() -> None:
    client = TestClient(api.app)
    tid = "pricey_products"
    submit = {"learner_id": "h2", "task_id": tid, "query": BY_ID[tid].reference, "goal": "sql"}
    client.post("/practice/submit", json=submit)
    view = client.put("/portfolio/h2/profile", json={"name": "Grace", "public": False}).json()
    slug = view["slug"]
    assert client.post(f"/p/{slug}/reprove", json={}).status_code == 404  # private
    key = {"x-portfolio-key": view["edit_key"]}
    client.put("/portfolio/h2/profile", json={"name": "Grace", "public": True}, headers=key)
    r = client.post(f"/p/{slug}/reprove", json={}).json()
    assert r["tested"] == 1 and r["passed"] == 1
    assert client.post(f"/p/{slug}/reprove", json={}).status_code == 429  # rate limit
    proof = r["proofs"][tid]
    again = client.post(f"/p/{slug}/reprove", json={"seed": proof["payload"]["seeds"][0]}).json()
    assert (
        again["reproduced"]
        and again["proofs"][tid]["payload"]["seeds"] == proof["payload"]["seeds"]
    )
    assert client.post("/attest/verify", json=proof).json() == {"valid": True}
    page = client.get(f"/p/{slug}").text
    assert "passed on 3 new datasets" in page and f"/p/{slug}/retest" in page
    view = client.get("/portfolio/h2", headers=key).json()
    assert view["fresh_ok"] == 1 and view["fresh_testable"] == 1


# ------------------------------------------------------------------ H3
def _ev(concept: str, at: datetime, correct: bool) -> SimpleNamespace:
    return SimpleNamespace(concept=concept, at=at.isoformat(), correct=correct)


def test_recalls_need_a_pause() -> None:
    t = datetime(2026, 1, 5, 19)
    evs = [_ev("a", t, True), _ev("a", t + timedelta(minutes=10), True),
           _ev("a", t + timedelta(days=3), False)]  # fmt: skip
    rs = fg.recalls(evs)
    assert len(rs) == 1 and rs[0].gap_days == pytest.approx(3 - 10 / 1440) and not rs[0].correct


def test_fast_forgetting_is_measured_per_topic_and_inherited_downstream() -> None:
    pre = {"a": [], "b": [], "c": ["a"], "d": ["b"]}
    rs = [fg.Recall("a", 2, False)] * 4 + [fg.Recall("a", 1, False)] * 2  # forgets a fast
    rs += [fg.Recall("b", 10, True)] * 5  # keeps b for long
    hl = fg.fit_half_lives(rs, list(pre), pre)
    assert hl["a"].source == "measured" and hl["a"].days < hl["b"].days
    assert hl["c"].source == "from prerequisites" and hl["c"].days < hl["d"].days
    assert fg.fit_half_lives([], list(pre), pre)["c"].days == fg.DEFAULT_HALF_LIFE_D


def test_a_review_lands_the_day_before_the_lesson_that_needs_it() -> None:
    today = date(2026, 1, 5)
    pre = {"a": [], "c": ["a"]}
    hl = {"a": fg.HalfLife("a", 10.0, 4, "measured")}  # known on the day, but not fresh enough
    lesson = {"c": today + timedelta(days=4)}
    jit = fg.plan_reviews({"a": today - timedelta(days=1)}, hl, pre, lesson,
                          today=today, until=today + timedelta(days=30))  # fmt: skip
    assert jit[0].due == today + timedelta(days=3) and jit[0].reason == "before:c"
    assert jit[0].priority == 1
    slow = {"a": fg.HalfLife("a", 60.0, 4, "measured")}  # still fresh by then: no early review
    assert fg.plan_reviews({"a": today}, slow, pre, {"c": today + timedelta(days=4)},
                           today=today, until=today + timedelta(days=10)) == []  # fmt: skip


def test_reviews_go_into_free_time_not_on_events_or_study_blocks() -> None:
    day = date(2026, 1, 5)  # a Monday: window 18:00-22:00
    r = fg.Review("a", day, 0.6, "fading", 2)
    busy = [(datetime(2026, 1, 5, 18), datetime(2026, 1, 5, 19))]
    block = SimpleNamespace(day=day, start=19 * 60, end=20 * 60)
    windows = {d: [(18 * 60, 22 * 60)] for d in range(7)}
    [p] = fg.place_reviews([r], [block], windows, busy, today=day)
    assert p.day == day and p.start >= 20 * 60 and p.end - p.start == fg.REVIEW_MIN and not p.late


def test_reschedule_reports_memory_and_reviews() -> None:
    client = TestClient(api.app)
    goals = client.post("/resolve", json={"goal": "sql"}).json()["goals"]
    t = date.today()
    body = {"learner_id": "h3", "goals": goals, "goal": "sql", "hours_per_week": 5,
            "deadline": (t + timedelta(days=45)).isoformat()}  # fmt: skip
    r = client.post("/reschedule", json=body).json()
    assert r["memory"] == {"recalls": 0, "topics": []} and r["reviews"] == []
