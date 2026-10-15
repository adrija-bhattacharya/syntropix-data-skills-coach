"""The prerequisite DAG as a partial order - Dilworth chain cover and the
lattice of order ideals the sequencing DP walks."""

from __future__ import annotations

import itertools

import networkx as nx
import numpy as np
import pytest
from _helpers import random_curriculum

from algorithms.poset import (
    count_order_ideals,
    min_chain_cover,
    order_ideal_bound,
    order_ideals,
    poset_width,
)


def _brute_ideals(dag: nx.DiGraph) -> set[frozenset[str]]:
    nodes = list(dag.nodes)
    preds = {n: set(dag.predecessors(n)) for n in nodes}
    out: set[frozenset[str]] = set()
    for r in range(len(nodes) + 1):
        for combo in itertools.combinations(nodes, r):
            s = set(combo)
            if all(preds[x] <= s for x in s):
                out.add(frozenset(s))
    return out


def _brute_width(dag: nx.DiGraph) -> int:
    tc = nx.transitive_closure(dag)
    best = 0
    nodes = list(dag.nodes)
    for r in range(len(nodes) + 1):
        for combo in itertools.combinations(nodes, r):
            if all(
                not tc.has_edge(a, b) and not tc.has_edge(b, a)
                for a, b in itertools.combinations(combo, 2)
            ):
                best = max(best, r)
    return best


def test_chain_cover_partitions_the_poset() -> None:
    g = nx.DiGraph([("a", "b"), ("b", "c"), ("a", "d"), ("d", "c"), ("e", "d")])
    chains = min_chain_cover(g)
    covered = [n for ch in chains for n in ch]
    assert sorted(covered) == sorted(g.nodes)  # partition, no repeats
    tc = nx.transitive_closure(g)
    for ch in chains:
        for x, y in itertools.pairwise(ch):
            assert tc.has_edge(x, y)  # consecutive chain elements are comparable


def test_width_equals_max_antichain() -> None:
    for seed in range(25):
        rng = np.random.default_rng(seed)
        kg = random_curriculum(rng, n=6)
        assert poset_width(kg.prereq) == _brute_width(kg.prereq)


def test_order_ideals_are_downward_closed_and_complete() -> None:
    for seed in range(20):
        rng = np.random.default_rng(seed)
        kg = random_curriculum(rng, n=6)
        got = set(order_ideals(kg.prereq))
        assert got == _brute_ideals(kg.prereq)


def test_ideal_count_shapes() -> None:
    chain = nx.DiGraph([("a", "b"), ("b", "c"), ("c", "d")])
    assert count_order_ideals(chain) == 5  # a chain of n has n+1 ideals
    antichain = nx.DiGraph()
    antichain.add_nodes_from("abcd")
    assert count_order_ideals(antichain) == 16  # 2**4


def test_ideal_bound_is_an_upper_bound() -> None:
    for seed in range(20):
        rng = np.random.default_rng(seed)
        kg = random_curriculum(rng, n=7)
        assert order_ideal_bound(kg.prereq) >= count_order_ideals(kg.prereq)


def test_limit_stops_enumeration() -> None:
    antichain = nx.DiGraph()
    antichain.add_nodes_from(range(10))  # 1024 ideals
    assert count_order_ideals(antichain, limit=50) == 50


def test_empty_poset() -> None:
    assert poset_width(nx.DiGraph()) == 0
    assert order_ideal_bound(nx.DiGraph()) == 1
    assert list(order_ideals(nx.DiGraph())) == [frozenset()]


@pytest.mark.parametrize("goal", ["quadratics", "word_problems"])
def test_curriculum_is_tall_and_narrow(kg, goal: str) -> None:
    from algorithms.graph_traversal import ancestors_subgraph

    sub = ancestors_subgraph(kg.prereq, [goal])
    assert poset_width(sub) <= 4  # narrow -> the sequencing DP is tractable
