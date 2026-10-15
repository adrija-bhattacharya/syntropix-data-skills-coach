"""The skill library: real videos and practice problems laid along a learner's
path, in prerequisite order and paced by measured velocity."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api
import skill_library
from algorithms.graph_traversal import topological_order
from domains import resolve, seed_graph
from harvest.library import relevant
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

lib = skill_library.load()
pytestmark = pytest.mark.skipif(not lib["problems"], reason="no harvested library snapshot")


def _state(
    kg: KnowledgeGraph, velocity: float = 1.0, mastered: tuple[str, ...] = ()
) -> LearnerState:
    s = LearnerState.cold_start(kg.concept_ids, time_budget_s=3600.0)
    for c in s.velocity:
        s.velocity[c] = velocity
    for c in mastered:
        s.mastery[c] = 0.9
    return s


def test_snapshot_is_real_and_complete() -> None:
    plats = {p["platform"] for p in lib["problems"]}
    assert {"LeetCode", "HackerRank"} <= plats
    for p in lib["problems"]:
        assert p["url"].startswith("https://")
        assert p["difficulty"] in ("Easy", "Medium", "Hard")
    for v in lib["videos"]:
        assert len(v["video_id"]) == 11 and v["url"].endswith(v["video_id"])
        assert v["minutes"] > 0 and v["channel"]
    ids = [v["video_id"] for v in lib["videos"]]
    assert len(ids) == len(set(ids))


def test_lesson_titles_match_their_topic() -> None:
    names = {}
    for d in {v["domain"] for v in lib["videos"]}:
        kg = seed_graph(d)
        names.update({(d, c): kg.concepts[c].name for c in kg.concept_ids})
    for v in lib["videos"]:
        if v["kind"] == "lesson":
            assert relevant(v["title"], names[(v["domain"], v["concept"])]), v["title"]


def test_order_follows_prerequisites_and_easy_comes_first() -> None:
    kg = seed_graph("sql")
    out = skill_library.build(kg, "sql", _state(kg), pace="steady")
    order = topological_order(kg.prereq)
    pos = {c: i for i, c in enumerate(order)}
    seen = [s["concept_id"] for s in out.steps]
    assert seen == sorted(seen, key=pos.__getitem__)
    rank = {"Easy": 0, "Medium": 1, "Hard": 2}
    for s in out.steps:
        r = [rank[p["difficulty"]] for p in s["problems"]]
        assert r == sorted(r)


def test_velocity_changes_the_mix() -> None:
    kg = seed_graph("sql")
    slow = skill_library.build(kg, "sql", _state(kg, 0.5))
    fast = skill_library.build(kg, "sql", _state(kg, 2.5))
    assert (slow.pace, fast.pace) == ("deliberate", "fast")

    def count(lib_: skill_library.Library, d: str) -> int:
        return sum(p["difficulty"] == d for s in lib_.steps for p in s["problems"])

    assert count(fast, "Easy") < count(slow, "Easy")  # fewer warm-ups
    assert count(fast, "Hard") > count(slow, "Hard") == 0  # hard ones sooner
    assert len(slow.stretch) > len(fast.stretch)
    assert len(fast.weeks) < len(slow.weeks)  # less time per problem


def test_untouched_learner_falls_back_to_the_chosen_speed() -> None:
    kg = seed_graph("sql")
    assert skill_library.pace_of(_state(kg)) == "steady"
    assert skill_library.pace_of(_state(kg), fallback="") == ""


def test_mastered_topics_move_to_review() -> None:
    kg = seed_graph("sql")
    out = skill_library.build(
        kg, "sql", _state(kg, mastered=("where", "select_from")), pace="steady"
    )
    assert {s["concept_id"] for s in out.review} == {"where", "select_from"}
    assert not {"where", "select_from"} & {s["concept_id"] for s in out.steps}


def test_weeks_respect_the_budget() -> None:
    kg = seed_graph("python_data")
    out = skill_library.build(kg, "python_data", _state(kg), pace="steady", hours_per_week=3)
    for w in out.weeks:
        assert w["minutes"] <= 3 * 60 or len(w["items"]) == 1


def test_role_graph_uses_prefixed_ids() -> None:
    r = resolve("data analyst")
    out = skill_library.build(r.kg, r.domain, None, pace="steady")
    assert all("." in s["concept_id"] for s in out.steps)
    assert {s["domain"] for s in out.steps} >= {"sql", "spreadsheets", "python_data"}
    assert out.totals["leetcode"] > 0 and out.totals["hackerrank"] > 0


def test_api_library_stats_and_certifications() -> None:
    client = TestClient(api.app)
    r = client.get("/library", params={"goal": "sql", "learner_id": "lib1", "speed": "fast"}).json()
    assert r["pace"] == "fast" and r["pace_source"] == "your speed setting"
    assert r["steps"] and r["weeks"] and r["courses"]
    r2 = client.get("/library", params={"goal": "sql", "pace": "deliberate"}).json()
    assert r2["pace"] == "deliberate" and r2["pace_source"] == "chosen"
    s = client.get("/library/stats").json()
    assert s["leetcode"] > 100 and s["hackerrank"] > 100 and s["videos"] > 150
    c = client.get("/certifications", params={"goal": "bi analyst"}).json()
    assert any("PL-300" in x["name"] for x in c["certifications"])
