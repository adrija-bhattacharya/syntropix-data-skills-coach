"""Role-gap sequencing (claim A): maximise hiring-readiness inside the budget."""

from __future__ import annotations

import networkx as nx
import pytest

from algorithms.roleplan import choose_prereq_closed_set, readiness, solve_role_plan
from domain_data import ROLES, role_profile
from domains import resolve
from model.knowledge_graph import Concept, KnowledgeGraph, Resource
from model.learner import LearnerState


def _tiny() -> tuple[KnowledgeGraph, dict[str, float]]:
    # a --> b --> d(role, w=1) ;  a --> c(role, w=3)
    concepts = [Concept(x, x.upper()) for x in "abcd"]
    prereqs = [("a", "b"), ("b", "d"), ("a", "c")]
    res = [Resource(f"{x}:l", (x,), 1.0, 10.0, "lesson") for x in "abcd"]
    kg = KnowledgeGraph.build(concepts, prereqs, res)
    return kg, {"c": 3.0, "d": 1.0}


def test_readiness_is_the_weighted_fraction_reached() -> None:
    kg, profile = _tiny()
    st = LearnerState.cold_start(kg.concept_ids, time_budget_s=9999)
    assert readiness(set(), profile, st, threshold=0.75) == 0.0
    assert readiness({"c"}, profile, st, threshold=0.75) == pytest.approx(0.75)  # 3 / 4
    assert readiness({"c", "d"}, profile, st, threshold=0.75) == pytest.approx(1.0)


def test_exact_knapsack_prefers_the_high_value_skill_under_a_tight_budget() -> None:
    kg, profile = _tiny()
    st = LearnerState.cold_start(kg.concept_ids, time_budget_s=9999)
    # 20 min = a + c  (readiness .75)  vs  a + b + d  (readiness .25) -> pick a,c
    chosen, method = choose_prereq_closed_set(kg, profile, st, budget_minutes=20)
    assert method == "ideal-knapsack"
    assert set(chosen) == {"a", "c"}


def test_role_plan_readiness_is_monotone_in_budget() -> None:
    kg, profile = _tiny()
    st = LearnerState.cold_start(kg.concept_ids, time_budget_s=9999)
    r10 = solve_role_plan(kg, "tiny", profile, st, budget_minutes=10).readiness
    r20 = solve_role_plan(kg, "tiny", profile, st, budget_minutes=20).readiness
    r40 = solve_role_plan(kg, "tiny", profile, st, budget_minutes=40).readiness
    assert r10 <= r20 <= r40
    assert r40 == pytest.approx(1.0)


def test_chosen_set_is_prerequisite_closed_and_within_budget() -> None:
    kg, _goals = resolve("become a data analyst").kg, None
    profile = {k: v for k, v in role_profile(ROLES[0]).items() if k in kg.concepts}
    st = LearnerState.cold_start(kg.concept_ids, time_budget_s=9999)
    rp = solve_role_plan(kg, "data analyst", profile, st, budget_minutes=200)
    chosen = set(rp.chosen)
    for c in chosen:
        assert set(kg.prereq.predecessors(c)) <= chosen  # down-closed
    assert 0.0 < rp.readiness <= 1.0
    assert rp.steps_curve[0] == (0.0, rp.readiness_before)
    assert rp.steps_curve[-1][1] == rp.readiness


def test_the_readiness_curve_is_non_decreasing() -> None:
    kg = resolve("become a data analyst").kg
    profile = {k: v for k, v in role_profile(ROLES[0]).items() if k in kg.concepts}
    st = LearnerState.cold_start(kg.concept_ids, time_budget_s=9999)
    curve = solve_role_plan(kg, "da", profile, st, budget_minutes=400).steps_curve
    vals = [r for _m, r in curve]
    assert vals == sorted(vals)


def test_api_role_recommend_reports_readiness() -> None:
    from fastapi.testclient import TestClient

    import api

    c = TestClient(api.app)
    body = {
        "learner_id": "rl",
        "goals": ["x"],
        "time_budget_min": 240,
        "goal": "become a data analyst",
    }
    r = c.post("/recommend", json=body).json()
    assert r["meta"]["role"] is True
    assert 0.0 <= r["meta"]["readiness_before"] <= r["meta"]["readiness"] <= 1.0
    assert r["paths"][0]["feasible"] and r["paths"][0]["steps"]
    assert len(r["meta"]["readiness_curve"]) == len(r["paths"][0]["steps"]) + 1


def test_resolve_marks_a_role() -> None:
    r = resolve("I want to be an analytics engineer")
    assert r.source == "role" and r.domain == "analytics engineer"
    assert nx.is_directed_acyclic_graph(r.kg.prereq)
