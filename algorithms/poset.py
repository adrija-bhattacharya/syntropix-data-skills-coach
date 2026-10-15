"""The prerequisite DAG **as a partial order** - the structure the sequencing DP
runs on.

A valid learning path is a *linear extension* of this poset; a valid **prefix**
of a path is an **order ideal** (down-set): a set ``I`` of concepts such that if
``c in I`` then every prerequisite of ``c`` is in ``I`` too.  The sequencing DP
in :mod:`algorithms.sequencing` walks the lattice of order ideals from the empty
set to the full relevant set, so its running time is governed by the **number of
order ideals**, which for a poset of width ``w`` and ``n`` elements is
``O((n/w + 1) ** w)`` - polynomial for the "tall, narrow" posets real curricula
form.

Functions
    min_chain_cover      Dilworth: fewest chains that cover the poset   (bipartite matching)
    poset_width          size of the largest antichain  ( = len(min_chain_cover) )
    order_ideals         enumerate the order ideals, smallest first, with a cap
    count_order_ideals   how many there are (stops early at ``limit``)
"""

from __future__ import annotations

from collections.abc import Iterator

import networkx as nx

NodeId = str


# --------------------------------------------------------------------------- #
# Dilworth - minimum chain cover via maximum bipartite matching
# --------------------------------------------------------------------------- #
def min_chain_cover(dag: nx.DiGraph) -> list[list[NodeId]]:
    """Partition the poset into the fewest vertex-disjoint chains (Dilworth).

    Min chain cover ``= n - (maximum matching in the bipartite graph on the
    strict order relation)``.  ``O(V * E_tc)`` with a simple augmenting-path
    matching; ``E_tc`` is the transitive closure edge count.
    """
    nodes = list(dag.nodes)
    reach: dict[NodeId, set[NodeId]] = {u: set(nx.descendants(dag, u)) for u in nodes}

    match_right: dict[NodeId, NodeId] = {}

    def augment(u: NodeId, seen: set[NodeId]) -> bool:
        for v in sorted(reach[u]):
            if v in seen:
                continue
            seen.add(v)
            if v not in match_right or augment(match_right[v], seen):
                match_right[v] = u
                return True
        return False

    for u in nodes:
        augment(u, set())

    # rebuild chains from the matching: successor[u] = v  means u,v consecutive in a chain
    succ = {u: v for v, u in match_right.items()}
    has_pred = set(match_right)
    chains: list[list[NodeId]] = []
    for start in nodes:
        if start in has_pred:
            continue
        chain = [start]
        while chain[-1] in succ:
            chain.append(succ[chain[-1]])
        chains.append(chain)
    return chains


def poset_width(dag: nx.DiGraph) -> int:
    """Largest antichain (Dilworth).  ``0`` for the empty graph."""
    return len(min_chain_cover(dag)) if dag.number_of_nodes() else 0


def order_ideal_bound(dag: nx.DiGraph) -> int:
    """A cheap upper bound on the number of order ideals: ``prod(len(chain) + 1)``
    over a minimum chain cover.  (An ideal is fixed by how far it reaches into
    each chain; cross-chain constraints only *remove* combinations.)  ``O(matching)``.
    """
    if not dag.number_of_nodes():
        return 1
    bound = 1
    for chain in min_chain_cover(dag):
        bound *= len(chain) + 1
        if bound > 10**18:
            return 10**18
    return bound


# --------------------------------------------------------------------------- #
# order ideals (down-sets) of the poset
# --------------------------------------------------------------------------- #
def _direct_preds(dag: nx.DiGraph) -> dict[NodeId, frozenset[NodeId]]:
    return {n: frozenset(dag.predecessors(n)) for n in dag.nodes}


def order_ideals(dag: nx.DiGraph, *, limit: int = 1_000_000) -> Iterator[frozenset[NodeId]]:
    """Yield every order ideal of the poset, breadth-first by size (``frozenset``s).

    Stops after ``limit`` ideals (the caller treats that as "too wide, fall back").
    """
    preds = _direct_preds(dag)
    start: frozenset[NodeId] = frozenset()
    seen: set[frozenset[NodeId]] = {start}
    frontier = [start]
    yielded = 0
    while frontier:
        nxt: list[frozenset[NodeId]] = []
        for ideal in frontier:
            yield ideal
            yielded += 1
            if yielded >= limit:
                return
            for c in dag.nodes:
                if c in ideal or not preds[c] <= ideal:
                    continue
                grown = ideal | {c}
                if grown not in seen:
                    seen.add(grown)
                    nxt.append(grown)
        frontier = nxt


def count_order_ideals(dag: nx.DiGraph, *, limit: int = 1_000_000) -> int:
    """Number of order ideals, capped at ``limit`` (returns ``limit`` if it hits it)."""
    n = 0
    for _ in order_ideals(dag, limit=limit):
        n += 1
    return n
