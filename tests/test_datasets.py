"""N7 - the multi-dataset benchmark harness.

The bundled Junyi sample is a **real** prerequisite graph; these tests check the
adapter turns it into a valid VELPO problem and that VELPO plans on it.
"""

from __future__ import annotations

import networkx as nx

from algorithms.graph_traversal import ancestors_subgraph, topological_order
from benchmarks.datasets import DATASETS, knowledge_graph_from_edges, load
from engine import Engine


def test_every_dataset_loads_a_dag_with_resources() -> None:
    for name in DATASETS:
        kg, goals = load(name)
        assert nx.is_directed_acyclic_graph(kg.prereq)
        assert goals and set(goals) <= set(kg.concepts)
        for c in kg.concept_ids:
            assert kg.resources_for(c), f"{name}: concept {c} has no resource"


def test_junyi_sample_is_the_real_graph() -> None:
    kg, _ = load("junyi")
    # a couple of edges that exist in the real Junyi prerequisite annotation
    assert kg.prereq.number_of_nodes() == 57
    assert kg.prereq.number_of_edges() >= 60
    assert any(r.kind == "practice" for r in kg.resources.values())


def test_cycle_in_a_raw_edge_list_is_removed() -> None:
    kg = knowledge_graph_from_edges(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")])
    assert nx.is_directed_acyclic_graph(kg.prereq)
    assert kg.prereq.number_of_edges() == 2  # one feedback arc dropped


def test_velpo_plans_on_junyi() -> None:
    kg, goals = load("junyi")
    eng = Engine(kg)
    goal = goals[0]
    order = topological_order(ancestors_subgraph(kg.prereq, [goal]))
    min_s = sum(min(kg.resources[r].seconds for r in kg.resources_for(c)) for c in order)
    plan = eng.recommend("u", [goal], time_budget_s=min_s * 2.0)[0]
    assert plan.feasible
    assert set(plan.concepts) == set(order)  # covers exactly the prerequisite closure
    taught: set[str] = set()
    for rid, cid in zip(plan.steps, plan.concepts):
        for req in kg.prerequisites_of_resource(rid):
            assert req in taught
        taught.add(cid)
