"""Graph-traversal preprocessing.

remove_cycles        Tarjan SCC + greedy feedback-arc-set   O(V + E)
ancestors_subgraph   backward BFS from the goal concepts    O(V + E)
topological_order    Kahn's algorithm, deterministic         O(V + E)
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

import networkx as nx

NodeId = str


# --------------------------------------------------------------------------- #
# 1. cycle removal
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class CycleReport:
    was_acyclic: bool
    removed_edges: tuple[tuple[NodeId, NodeId], ...] = ()

    @property
    def n_removed(self) -> int:
        return len(self.removed_edges)


def _greedy_feedback_arc_set(g: nx.DiGraph) -> set[tuple[NodeId, NodeId]]:
    """Eades-Lin-Smyth: build a vertex order, then every backward edge is a feedback arc."""
    h = g.copy()
    left: list[NodeId] = []
    right: list[NodeId] = []
    while h.number_of_nodes():
        changed = True
        while changed:
            changed = False
            for n in [n for n in h.nodes if h.out_degree(n) == 0]:
                right.insert(0, n)
                h.remove_node(n)
                changed = True
            for n in [n for n in h.nodes if h.in_degree(n) == 0]:
                left.append(n)
                h.remove_node(n)
                changed = True
        if not h.number_of_nodes():
            break
        u = max(h.nodes, key=lambda n: (h.out_degree(n) - h.in_degree(n), n))
        left.append(u)
        h.remove_node(u)
    pos = {n: i for i, n in enumerate(left + right)}
    return {(u, v) for u, v in g.edges if pos[u] > pos[v]}


def remove_cycles(g: nx.DiGraph) -> tuple[nx.DiGraph, CycleReport]:
    """Return ``(dag, report)``.  An already-acyclic graph is returned unchanged.

    Only edges inside a non-trivial strongly-connected component are candidates
    for removal (Tarjan SCC).  ``O(V + E)``.
    """
    if nx.is_directed_acyclic_graph(g):
        return g.copy(), CycleReport(was_acyclic=True)

    dag = g.copy()
    removed: list[tuple[NodeId, NodeId]] = []
    for comp in nx.strongly_connected_components(g):
        if len(comp) < 2:
            continue
        for u, v in sorted(_greedy_feedback_arc_set(g.subgraph(comp).copy())):
            if dag.has_edge(u, v):
                dag.remove_edge(u, v)
                removed.append((u, v))
    while not nx.is_directed_acyclic_graph(dag):  # rare: greedy missed one
        u, v = sorted(nx.find_cycle(dag))[0]
        dag.remove_edge(u, v)
        removed.append((u, v))
    return dag, CycleReport(was_acyclic=False, removed_edges=tuple(removed))


# --------------------------------------------------------------------------- #
# 2. ancestor extraction
# --------------------------------------------------------------------------- #
def ancestors_subgraph(g: nx.DiGraph, targets: Iterable[NodeId]) -> nx.DiGraph:
    """Backward BFS: the sub-DAG of every (transitive) prerequisite of a target,
    plus the targets themselves.  This set is prerequisite-closed by construction.
    ``O(V + E)``.
    """
    seen = {t for t in targets if t in g}
    if not seen:
        return nx.DiGraph()
    queue: deque[NodeId] = deque(seen)
    while queue:
        node = queue.popleft()
        for pred in g.predecessors(node):
            if pred not in seen:
                seen.add(pred)
                queue.append(pred)
    return g.subgraph(seen).copy()


# --------------------------------------------------------------------------- #
# 3. topological sort
# --------------------------------------------------------------------------- #
def topological_order(dag: nx.DiGraph) -> list[NodeId]:
    """Kahn's algorithm with a sorted (deterministic) frontier.

    Raises ``ValueError`` on a cycle.  ``O(V + E)`` (+ an ``O(V log V)`` sort term).
    """
    indeg = {n: dag.in_degree(n) for n in dag.nodes}
    frontier = sorted(n for n, d in indeg.items() if d == 0)
    order: list[NodeId] = []
    while frontier:
        node = frontier.pop(0)
        order.append(node)
        ready: list[NodeId] = []
        for succ in dag.successors(node):
            indeg[succ] -= 1
            if indeg[succ] == 0:
                ready.append(succ)
        if ready:
            frontier = sorted(frontier + ready)
    if len(order) != dag.number_of_nodes():
        raise ValueError("topological_order: the graph contains a cycle")
    return order
