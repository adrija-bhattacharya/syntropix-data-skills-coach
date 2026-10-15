"""Proof-of-skill portfolio: correct practice answers are recorded, re-checked
by running them again, and published only when the learner says so."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api
import portfolio
from portfolio_page import render
from practice.catalogue import BY_ID


@pytest.fixture(autouse=True)
def tmp_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(portfolio, "STATE", tmp_path / "portfolio")
    monkeypatch.setattr(portfolio, "_RECHECK", {})
    monkeypatch.setattr(api, "_ENGINES", {})
    monkeypatch.setattr(api, "_LEARNER_ENGINE", {})


def _sql_task() -> str:
    return next(t.id for t in BY_ID.values() if t.kind == "sql" and t.concept == "select_from")


def test_a_correct_answer_is_recorded_a_wrong_one_is_not() -> None:
    client = TestClient(api.app)
    tid = _sql_task()
    wrong = client.post(
        "/practice/submit",
        json={"learner_id": "pf1", "task_id": tid, "query": "SELECT 1", "goal": "sql"},
    ).json()
    assert not wrong["correct"] and not wrong["in_portfolio"]
    first = client.get("/portfolio/pf1").json()
    assert first["solved"] == 0 and first["edit_key"]
    key = {"x-portfolio-key": first["edit_key"]}
    right = client.post(
        "/practice/submit",
        json={"learner_id": "pf1", "task_id": tid, "query": BY_ID[tid].reference, "goal": "sql"},
    ).json()
    assert right["correct"] and right["in_portfolio"]
    view = client.get("/portfolio/pf1", headers=key).json()
    assert view["solved"] == 1 and view["rechecked_ok"] == 1 and "edit_key" not in view
    s = view["skills"]["sql"][0]
    assert s["answer"] == BY_ID[tid].reference and s["attempts"] == 2 and s["rechecked"]
    assert s["checks"] and s["columns"]


def test_recheck_catches_an_answer_that_no_longer_passes() -> None:
    tid = _sql_task()
    solve = portfolio.Solve(
        tid, "select_from", "SELECT", "sql", "sql", "p", "SELECT 1", [], [], [], "2026-01-01", 1
    )
    assert portfolio.recheck(solve) is False
    good = portfolio.Solve(
        tid, "select_from", "SELECT", "sql", "sql", "p", BY_ID[tid].reference, [], [], [], "x", 1
    )
    assert portfolio.recheck(good) is True


def test_public_page_needs_consent_and_escapes_input() -> None:
    client = TestClient(api.app)
    tid = _sql_task()
    client.post(
        "/practice/submit",
        json={"learner_id": "pf2", "task_id": tid, "query": BY_ID[tid].reference, "goal": "sql"},
    )
    view = client.put(
        "/portfolio/pf2/profile",
        json={"name": "Ada <script>x</script>", "headline": "Aspiring analyst", "public": False},
    ).json()
    key = view["edit_key"]  # the first write claims the portfolio
    path = view["share_path"]
    assert client.get(path).status_code == 404  # private by default
    client.put(
        "/portfolio/pf2/profile",
        json={"name": "Ada <script>x</script>", "public": True},
        headers={"x-portfolio-key": key},
    )
    page = client.get(path)
    assert page.status_code == 200 and "passes when re-run" in page.text
    assert "<script>x</script>" not in page.text and "&lt;script&gt;" in page.text
    assert client.get("/portfolio/pf2/export.html").status_code == 403
    export = client.get("/portfolio/pf2/export.html", params={"key": key})
    assert "attachment" in export.headers["content-disposition"] and "<html" in export.text


def test_projects_need_https_links_and_can_be_removed() -> None:
    client = TestClient(api.app)
    bad = client.post(
        "/portfolio/pf3/projects",
        json={"project_id": "sql-music", "title": "Music store", "repo_url": "javascript:alert(1)"},
    )
    assert bad.status_code == 422
    ok = client.post(
        "/portfolio/pf3/projects",
        json={
            "project_id": "sql-music",
            "title": "Music store questions",
            "summary": "Joins and window functions on Chinook.",
            "skills": ["sql"],
            "repo_url": "https://github.com/example/chinook-sql",
            "check_links": False,
        },
    ).json()
    assert ok["projects"][0]["title"] == "Music store questions"
    key = {"x-portfolio-key": ok["edit_key"]}
    assert client.delete("/portfolio/pf3/projects/sql-music", headers=key).json()["projects"] == []


def test_slugs_are_unique_per_name() -> None:
    a = portfolio.set_profile(
        "u1", name="Sam Lee", headline="", github="", linkedin="", public=True
    )
    b = portfolio.set_profile(
        "u2", name="Sam Lee", headline="", github="", linkedin="", public=True
    )
    assert a.slug == "sam-lee" and b.slug != a.slug and b.slug.startswith("sam-lee-")
    assert portfolio.by_slug(b.slug).learner_id == "u2"  # type: ignore[union-attr]


def test_render_lists_projects_and_skills() -> None:
    view = {
        "name": "Ada", "headline": "Analyst", "github": "https://github.com/ada", "linkedin": "",
        "slug": "ada", "public": True, "skills": {}, "solved": 0, "rechecked_ok": 0,
        "projects": [{"title": "P", "summary": "S", "skills": ["sql"], "repo_url": "https://x.y/z",
                      "demo_url": "", "link_ok": True}],
        "mastery": {"SELECT": 0.9}, "built": "today",
    }  # fmt: skip
    html = render(view)
    assert "link working" in html and "Strongest topics" in html and "GitHub" in html


def test_only_the_owner_can_read_or_change_a_claimed_portfolio() -> None:
    client = TestClient(api.app)
    key = client.get("/portfolio/pf4").json()["edit_key"]
    for call in (
        lambda h: client.get("/portfolio/pf4", headers=h),
        lambda h: client.put(
            "/portfolio/pf4/profile", json={"name": "X", "public": True}, headers=h
        ),
        lambda h: client.post(
            "/portfolio/pf4/projects",
            json={
                "project_id": "p",
                "title": "t",
                "repo_url": "https://a.b/c",
                "check_links": False,
            },
            headers=h,
        ),
        lambda h: client.delete("/portfolio/pf4/projects/p", headers=h),
    ):
        assert call({}).status_code == 403
        assert call({"x-portfolio-key": "wrong"}).status_code == 403
        assert call({"x-portfolio-key": key}).status_code == 200
    assert client.get("/portfolio/pf4", headers={"x-portfolio-key": key}).json()["name"] == "X"
