"""Curated seed knowledge graphs for a few well-trodden domains, plus a router
that picks the right seed for a free-text goal (falling back to dynamic
construction in :mod:`dynamic` for anything off the beaten track).

A seed is a hand-authored prerequisite DAG - the same shape as ``curriculum.py``
- with a synthetic ``lesson`` + ``practice`` per concept so it is immediately
plannable; ``harvest.discover_catalogue`` swaps in real resources on request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from curriculum import build_curriculum
from model.knowledge_graph import Concept, KnowledgeGraph, Resource


@dataclass(frozen=True, slots=True)
class Domain:
    name: str
    concepts: tuple[tuple[str, str], ...]  # (id, label)
    prereqs: tuple[tuple[str, str], ...]  # (earlier, later)
    aliases: tuple[str, ...] = ()  # extra phrases that should route here
    hint: str = ""  # search domain for the harvester: math | cs | web | science

    def graph(self) -> KnowledgeGraph:
        return _with_synthetic_resources(
            [Concept(cid, label) for cid, label in self.concepts], list(self.prereqs)
        )


# --------------------------------------------------------------------------- #
# Data Structures & Algorithms
# --------------------------------------------------------------------------- #
_DSA = Domain(
    name="dsa",
    hint="cs",
    aliases=("data structures", "algorithms", "dsa", "leetcode", "coding interview"),
    concepts=(
        ("complexity", "Time & space complexity (Big-O)"),
        ("arrays", "Arrays"),
        ("strings", "Strings"),
        ("linked_lists", "Linked lists"),
        ("stacks", "Stacks"),
        ("queues", "Queues"),
        ("hashing", "Hash tables"),
        ("recursion", "Recursion"),
        ("two_pointers", "Two pointers"),
        ("sliding_window", "Sliding window"),
        ("sorting", "Sorting algorithms"),
        ("binary_search", "Binary search"),
        ("divide_conquer", "Divide and conquer"),
        ("trees", "Trees"),
        ("bst", "Binary search trees"),
        ("heaps", "Heaps / priority queues"),
        ("tries", "Tries"),
        ("graphs", "Graphs"),
        ("graph_traversal", "Graph traversal (BFS / DFS)"),
        ("topological_sort", "Topological sort"),
        ("shortest_paths", "Shortest paths (Dijkstra / Bellman-Ford)"),
        ("union_find", "Union-Find (disjoint set)"),
        ("mst", "Minimum spanning tree"),
        ("greedy", "Greedy algorithms"),
        ("backtracking", "Backtracking"),
        ("dynamic_programming", "Dynamic programming"),
        ("bit_manipulation", "Bit manipulation"),
    ),
    prereqs=(
        ("arrays", "strings"),
        ("arrays", "linked_lists"),
        ("arrays", "hashing"),
        ("arrays", "sorting"),
        ("arrays", "two_pointers"),
        ("arrays", "bit_manipulation"),
        ("complexity", "sorting"),
        ("complexity", "binary_search"),
        ("linked_lists", "stacks"),
        ("linked_lists", "queues"),
        ("sorting", "binary_search"),
        ("two_pointers", "sliding_window"),
        ("recursion", "divide_conquer"),
        ("recursion", "trees"),
        ("recursion", "backtracking"),
        ("recursion", "dynamic_programming"),
        ("divide_conquer", "sorting"),
        ("trees", "bst"),
        ("trees", "heaps"),
        ("trees", "tries"),
        ("hashing", "graphs"),
        ("trees", "graphs"),
        ("graphs", "graph_traversal"),
        ("graph_traversal", "topological_sort"),
        ("graph_traversal", "shortest_paths"),
        ("union_find", "mst"),
        ("graphs", "mst"),
        ("arrays", "union_find"),
        ("sorting", "greedy"),
        ("dynamic_programming", "greedy"),
        ("backtracking", "dynamic_programming"),
    ),
)

# --------------------------------------------------------------------------- #
# Core Python
# --------------------------------------------------------------------------- #
_PYTHON = Domain(
    name="python",
    hint="cs",
    aliases=("python", "learn python", "python programming", "python basics"),
    concepts=(
        ("syntax", "Syntax & the REPL"),
        ("variables", "Variables & data types"),
        ("operators", "Operators & expressions"),
        ("strings", "Strings & formatting"),
        ("conditionals", "Conditionals"),
        ("loops", "Loops"),
        ("functions", "Functions & arguments"),
        ("scope", "Scope & closures"),
        ("lists", "Lists"),
        ("tuples", "Tuples"),
        ("dicts", "Dictionaries"),
        ("sets", "Sets"),
        ("comprehensions", "Comprehensions"),
        ("iterators", "Iterators & generators"),
        ("exceptions", "Exceptions"),
        ("files", "File I/O"),
        ("modules", "Modules & packages"),
        ("oop", "Classes & objects"),
        ("inheritance", "Inheritance & polymorphism"),
        ("dunder", "Dunder / magic methods"),
        ("decorators", "Decorators"),
        ("context_managers", "Context managers"),
        ("typing", "Type hints"),
        ("venv", "Virtual environments & pip"),
        ("async", "async / await"),
    ),
    prereqs=(
        ("syntax", "variables"),
        ("variables", "operators"),
        ("variables", "strings"),
        ("operators", "conditionals"),
        ("conditionals", "loops"),
        ("loops", "functions"),
        ("functions", "scope"),
        ("variables", "lists"),
        ("lists", "tuples"),
        ("lists", "dicts"),
        ("lists", "sets"),
        ("loops", "comprehensions"),
        ("lists", "comprehensions"),
        ("comprehensions", "iterators"),
        ("functions", "exceptions"),
        ("exceptions", "files"),
        ("functions", "modules"),
        ("functions", "oop"),
        ("oop", "inheritance"),
        ("oop", "dunder"),
        ("dunder", "context_managers"),
        ("exceptions", "context_managers"),
        ("functions", "decorators"),
        ("scope", "decorators"),
        ("functions", "typing"),
        ("modules", "venv"),
        ("iterators", "async"),
        ("functions", "async"),
    ),
)

_SEEDS: dict[str, Domain] = {d.name: d for d in (_DSA, _PYTHON)}


# --------------------------------------------------------------------------- #
def _with_synthetic_resources(
    concepts: list[Concept], prereqs: list[tuple[str, str]]
) -> KnowledgeGraph:
    import networkx as nx

    g = nx.DiGraph()
    g.add_nodes_from(c.id for c in concepts)
    g.add_edges_from(prereqs)
    depth = dict.fromkeys(g, 0)
    for n in nx.topological_sort(g):
        for s in g.successors(n):
            depth[s] = max(depth[s], depth[n] + 1)
    dmax = max(depth.values(), default=1) or 1

    resources: list[Resource] = []
    for c in concepts:
        diff = round(1.0 + 3.0 * depth[c.id] / dmax, 1)
        minutes = round(8.0 + 3.0 * diff, 1)
        resources.append(Resource(f"{c.id}:lesson", (c.id,), diff, minutes, "lesson"))
        resources.append(
            Resource(
                f"{c.id}:practice",
                (c.id,),
                max(1.0, diff - 1.0),
                round(0.6 * minutes, 1),
                "practice",
            )
        )
    return KnowledgeGraph.build(concepts, prereqs, resources)


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Resolved:
    kg: KnowledgeGraph
    goals: list[str] = field(default_factory=list)
    domain: str = ""
    source: str = "seed"  # "seed" | "dynamic"
    hint: str = "general"


def _norm(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9+]+", s.lower()) if len(w) > 1}


def available_domains() -> list[str]:
    return ["algebra", *sorted(_SEEDS)]


def resolve(goal: str, *, allow_dynamic: bool = True) -> Resolved:
    """Pick a knowledge graph + goal concept(s) for a free-text learning goal."""
    want = _norm(goal)

    if want & {"algebra", "equation", "equations", "quadratic", "quadratics", "linear"}:
        kg = build_curriculum()
        goals = _match_concepts(kg, want) or kg.sink_concepts()[:1]
        return Resolved(kg, goals, "algebra", "seed", "math")

    best: tuple[float, Domain] | None = None
    for dom in _SEEDS.values():
        score = len(want & _norm(dom.name))
        score += 2 * sum(1 for a in dom.aliases if a in goal.lower())
        score += sum(1 for _cid, label in dom.concepts if want & _norm(label))
        if score and (best is None or score > best[0]):
            best = (score, dom)

    if best is not None:
        dom = best[1]
        kg = dom.graph()
        goals = _match_concepts(kg, want) or kg.sink_concepts()[:1]
        return Resolved(kg, goals, dom.name, "seed", dom.hint)

    if allow_dynamic:
        from dynamic import build_dynamic_graph

        kg, goals = build_dynamic_graph(goal)
        return Resolved(kg, goals, goal.strip().lower(), "dynamic", "general")

    kg = build_curriculum()
    return Resolved(kg, kg.sink_concepts()[:1], "algebra", "seed", "math")


def _match_concepts(kg: KnowledgeGraph, want: set[str]) -> list[str]:
    hits = [
        (len(want & _norm(c.name)) + (1 if c.id in want else 0), c.id) for c in kg.concepts.values()
    ]
    hits = sorted(((s, cid) for s, cid in hits if s > 0), reverse=True)
    if not hits:
        return []
    top = hits[0][0]
    return [cid for s, cid in hits if s == top][:2]  # only the best-scoring concept(s)
