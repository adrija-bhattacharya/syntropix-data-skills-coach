from __future__ import annotations

import networkx as nx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from algorithms.graph_traversal import ancestors_subgraph, remove_cycles, topological_order
from model.knowledge_graph import KnowledgeGraph


def test_topological_order_respects_edges(kg: KnowledgeGraph) -> None:
    order = topological_order(kg.prereq)
    pos = {n: i for i, n in enumerate(order)}
    assert set(order) == set(kg.prereq.nodes)
    for u, v in kg.prereq.edges:
        assert pos[u] < pos[v]


def test_topological_order_deterministic_and_rejects_cycles() -> None:
    g = nx.DiGraph([("b", "d"), ("a", "d"), ("a", "c"), ("c", "d")])
    assert topological_order(g) == topological_order(g.copy())
    assert topological_order(g)[0] == "a"
    with pytest.raises(ValueError, match="cycle"):
        topological_order(nx.DiGraph([(1, 2), (2, 1)]))


def test_ancestors_subgraph_is_exact(kg: KnowledgeGraph) -> None:
    sub = ancestors_subgraph(kg.prereq, ["quadratics"])
    assert set(sub.nodes) == set(nx.ancestors(kg.prereq, "quadratics")) | {"quadratics"}
    assert "word_problems" not in sub.nodes


def test_remove_cycles_untouched_when_acyclic(kg: KnowledgeGraph) -> None:
    dag, report = remove_cycles(kg.prereq)
    assert report.was_acyclic and report.n_removed == 0
    assert set(dag.edges) == set(kg.prereq.edges)


def test_remove_cycles_breaks_2cycle() -> None:
    dag, report = remove_cycles(nx.DiGraph([(1, 2), (2, 1), (2, 3)]))
    assert nx.is_directed_acyclic_graph(dag)
    assert (2, 3) in dag.edges and report.n_removed == 1


@settings(max_examples=150, deadline=None)
@given(
    edges=st.lists(
        st.tuples(st.integers(0, 7), st.integers(0, 7)).filter(lambda e: e[0] != e[1]),
        max_size=25,
        unique=True,
    )
)
def test_remove_cycles_always_yields_a_dag_subset(edges: list[tuple[int, int]]) -> None:
    g = nx.DiGraph(edges)
    g.add_nodes_from(range(8))
    dag, _ = remove_cycles(g)
    assert nx.is_directed_acyclic_graph(dag)
    assert set(dag.edges) <= set(g.edges) and set(dag.nodes) == set(g.nodes)
