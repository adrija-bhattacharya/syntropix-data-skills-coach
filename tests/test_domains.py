"""Seed knowledge graphs + the free-text goal router (dynamic path is offline,
served from the committed snapshot)."""

from __future__ import annotations

import networkx as nx
import pytest

from domains import _PYTHON, _SEEDS, Domain, available_domains, resolve
from dynamic import build_dynamic_graph
from engine import Engine


@pytest.mark.parametrize("dom", list(_SEEDS.values()), ids=lambda d: d.name)
def test_seed_graphs_are_plannable_dags(dom: Domain) -> None:
    kg = dom.graph()
    assert nx.is_directed_acyclic_graph(kg.prereq)
    ids = {cid for cid, _ in dom.concepts}
    for a, b in dom.prereqs:
        assert a in ids and b in ids, f"{dom.name}: edge {a}->{b} references an unknown concept"
    for c in kg.concept_ids:
        assert kg.resources_for(c)
    goal = kg.sink_concepts()[0]
    plan = Engine(kg).recommend("u", [goal], time_budget_s=20000, mode="sequence")[0]
    assert plan.feasible and plan.steps


def test_router_picks_the_dsa_seed() -> None:
    r = resolve("I want to get better at data structures and algorithms")
    assert r.source == "seed" and r.domain == "dsa"
    assert "dynamic_programming" in r.kg.concepts


def test_router_picks_the_python_seed_and_a_matching_goal() -> None:
    r = resolve("learn python decorators")
    assert r.domain == "python"
    assert "decorators" in r.goals  # the goal concept was matched from the phrase


def test_router_picks_algebra_for_a_math_goal() -> None:
    r = resolve("quadratic equations")
    assert r.domain == "algebra" and r.hint == "math"
    assert "quadratics" in r.goals


def test_a_goal_that_matches_a_seed_concept_uses_the_seed() -> None:
    # "dynamic programming" IS a DSA concept - the curated graph beats a dynamic one
    r = resolve("dynamic programming")
    assert r.source == "seed" and r.domain == "dsa"


def test_router_falls_back_to_dynamic_for_the_long_tail() -> None:
    r = resolve("Photosynthesis")  # no seed -> bundled snapshot, no network
    assert r.source == "dynamic"
    assert nx.is_directed_acyclic_graph(r.kg.prereq)
    plan = Engine(r.kg).recommend("u", r.goals, time_budget_s=20000, mode="sequence")[0]
    assert plan.feasible and plan.steps
    assert plan.concepts[-1] == r.goals[0]  # the goal is taught last


def test_dynamic_graph_from_snapshot_is_valid() -> None:
    kg, goals = build_dynamic_graph("Photosynthesis")
    assert goals and goals[0] in kg.concepts
    assert nx.is_directed_acyclic_graph(kg.prereq)
    assert all(kg.resources_for(c) for c in kg.concept_ids)


def test_available_domains_lists_the_seeds() -> None:
    got = available_domains()
    assert "algebra" in got and "dsa" in got and "python" in got


def test_python_seed_orders_basics_before_advanced() -> None:
    from algorithms.graph_traversal import ancestors_subgraph, topological_order

    kg = _PYTHON.graph()
    order = topological_order(ancestors_subgraph(kg.prereq, ["async"]))
    assert order.index("functions") < order.index("async")
    assert order.index("variables") < order.index("functions")
