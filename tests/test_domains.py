"""Seed graphs (data-analytics track) + the free-text goal router.  The dynamic
path is offline, served from a committed snapshot."""

from __future__ import annotations

import networkx as nx
import pytest

from domain_data import ROLES, SEEDS
from domains import available_domains, resolve, role_graph, seed_graph
from dynamic import build_dynamic_graph
from engine import Engine


@pytest.mark.parametrize("spec", list(SEEDS), ids=lambda s: s.name)
def test_seed_graphs_are_plannable_dags(spec) -> None:
    kg = seed_graph(spec.name)
    assert nx.is_directed_acyclic_graph(kg.prereq)
    ids = {cid for cid, _ in spec.concepts}
    for a, b in spec.prereqs:
        assert a in ids and b in ids, f"{spec.name}: edge {a}->{b} references an unknown concept"
    for c in kg.concept_ids:
        assert kg.resources_for(c)
    goal = kg.sink_concepts()[0]
    plan = Engine(kg).recommend("u", [goal], time_budget_s=40000, mode="sequence")[0]
    assert plan.feasible and plan.steps


def test_router_picks_the_sql_seed_and_matches_a_goal_concept() -> None:
    r = resolve("learn sql window functions")
    assert r.source == "seed" and r.domain == "sql"
    assert "window_functions" in r.goals


def test_router_picks_python_for_a_python_goal() -> None:
    r = resolve("python list comprehensions")
    assert r.domain == "python"
    assert "comprehensions" in r.goals


def test_complete_beginner_routes_to_foundations() -> None:
    r = resolve("I have no experience, complete beginner")
    assert r.domain == "foundations"
    assert "algorithm_idea" in r.kg.concepts


def test_a_role_unions_the_domains_it_needs() -> None:
    r = resolve("I want to become a data analyst")
    assert r.source == "role" and r.domain == "data analyst"
    # concept ids are domain-prefixed in a role graph
    assert any(g.startswith("sql.") for g in r.kg.concepts)
    assert any(g.startswith("python_data.") for g in r.kg.concepts)
    plan = Engine(r.kg).recommend("u", r.goals, time_budget_s=60000, mode="sequence")[0]
    assert plan.feasible and plan.steps


def test_role_graph_is_a_dag_with_bridges() -> None:
    kg, goals = role_graph(ROLES[0])
    assert nx.is_directed_acyclic_graph(kg.prereq)
    assert goals and all(g in kg.concepts for g in goals)


def test_algebra_still_reachable() -> None:
    r = resolve("quadratic equations")
    assert r.domain == "algebra" and "quadratics" in r.goals


def test_router_falls_back_to_dynamic_for_the_long_tail() -> None:
    r = resolve("Photosynthesis")  # bundled snapshot -> no network
    assert r.source == "dynamic"
    assert nx.is_directed_acyclic_graph(r.kg.prereq)
    plan = Engine(r.kg).recommend("u", r.goals, time_budget_s=20000, mode="sequence")[0]
    assert plan.feasible and plan.steps
    assert plan.concepts[-1] == r.goals[0]


def test_dynamic_graph_from_snapshot_is_valid() -> None:
    kg, goals = build_dynamic_graph("Photosynthesis")
    assert goals and goals[0] in kg.concepts
    assert nx.is_directed_acyclic_graph(kg.prereq)


def test_available_domains_lists_the_data_track() -> None:
    got = available_domains()
    assert {"sql", "python", "python_data", "stats", "foundations"} <= set(got)
    assert "algebra" in got
