"""Route a free-text learning goal to a knowledge graph.

* a **curated seed** graph for a known data-analytics / job skill
  (see :mod:`domain_data`),
* a **role** ("data analyst") -> the union of the domains that role needs,
* the legacy ``algebra`` curriculum if the goal is clearly maths,
* otherwise a graph **built dynamically from Wikipedia** (:mod:`dynamic`).

Absolute beginners are covered: "I'm a complete beginner" routes to the
``foundations`` on-ramp, and a true beginner also just scores low on the
adaptive test and gets a plan that starts from the roots.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import networkx as nx

from curriculum import build_curriculum
from domain_data import ROLES, SEEDS, Role, SeedSpec
from model.knowledge_graph import Concept, KnowledgeGraph, Resource

_SEEDS: dict[str, SeedSpec] = {s.name: s for s in SEEDS}
_ROLES: dict[str, Role] = {r.name: r for r in ROLES}


# --------------------------------------------------------------------------- #
def _with_synthetic_resources(
    concepts: list[Concept], prereqs: list[tuple[str, str]]
) -> KnowledgeGraph:
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
        minutes = round(9.0 + 3.5 * diff, 1)
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


def seed_graph(name: str) -> KnowledgeGraph:
    s = _SEEDS[name]
    return _with_synthetic_resources(
        [Concept(cid, label) for cid, label in s.concepts], list(s.prereqs)
    )


def role_graph(role: Role) -> tuple[KnowledgeGraph, list[str]]:
    """Union the domains a role needs into one graph; the goal concepts are the
    role's weighted skills (ids prefixed with their domain)."""
    domains = sorted({d for d, _c, _w in role.skills})
    concepts: list[Concept] = []
    edges: list[tuple[str, str]] = []
    for d in domains:
        s = _SEEDS[d]
        for cid, label in s.concepts:
            concepts.append(Concept(f"{d}.{cid}", f"{label}"))
        edges += [(f"{d}.{a}", f"{d}.{b}") for a, b in s.prereqs]
    # light bridges: a domain's roots depend on a foundational concept of its parent
    for parent, child, a, b in _BRIDGES:
        if parent in domains and child in domains:
            edges.append((f"{parent}.{a}", f"{child}.{b}"))
    kg = _with_synthetic_resources(concepts, edges)
    goals = [f"{d}.{c}" for d, c, _w in sorted(role.skills, key=lambda s: -s[2])]
    goals = [g for g in goals if g in kg.concepts]
    return kg, goals[:4]


# (parent domain, child domain, parent concept, child concept)
_BRIDGES: tuple[tuple[str, str, str, str], ...] = (
    ("python", "python_data", "functions", "numpy_arrays"),
    ("python", "dsa_python", "functions", "big_o"),
    ("python", "git", "modules", "vcs_idea"),
    ("sql", "python_data", "inner_join", "merge_join"),
    ("python_data", "stats", "groupby_agg", "descriptive"),
    ("python_data", "dataviz", "plot_pandas", "matplotlib_basics"),
)


# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Resolved:
    kg: KnowledgeGraph
    goals: list[str] = field(default_factory=list)
    domain: str = ""
    source: str = "seed"  # "seed" | "role" | "dynamic"
    hint: str = "general"


def _norm(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9+]+", s.lower()) if len(w) > 1}


def available_domains() -> list[str]:
    return [*sorted(_SEEDS), "algebra", *(f"role:{r}" for r in sorted(_ROLES))]


_BEGINNER = {"beginner", "beginners", "scratch", "zero", "nothing", "no experience", "new"}
_MATH = {"algebra", "equation", "equations", "quadratic", "quadratics", "calculus", "trigonometry"}


def resolve(goal: str, *, allow_dynamic: bool = True) -> Resolved:
    g = goal.strip().lower()
    want = _norm(goal)

    # roles first ("become a data analyst")
    for role in _ROLES.values():
        if any(a in g for a in role.aliases):
            kg, goals = role_graph(role)
            return Resolved(kg, goals, role.name, "role", "cs")

    if want & _BEGINNER or "complete beginner" in g:
        kg = seed_graph("foundations")
        return Resolved(kg, kg.sink_concepts(), "foundations", "seed", "general")

    if want & _MATH:
        kg = build_curriculum()
        return Resolved(
            kg, _match_concepts(kg, want) or kg.sink_concepts()[:1], "algebra", "seed", "math"
        )

    best: tuple[float, SeedSpec] | None = None
    for s in _SEEDS.values():
        score = 3 * sum(1 for a in s.aliases if a in g)
        score += 2 * len(want & _norm(s.name))
        score += sum(1 for _cid, label in s.concepts if want & _norm(label))
        if score and (best is None or score > best[0]):
            best = (score, s)

    if best is not None:
        s = best[1]
        kg = seed_graph(s.name)
        goals = _match_concepts(kg, want) or kg.sink_concepts()[:1]
        return Resolved(kg, goals, s.name, "seed", s.hint)

    if allow_dynamic:
        from dynamic import build_dynamic_graph

        kg, goals = build_dynamic_graph(goal)
        return Resolved(kg, goals, g, "dynamic", "general")

    kg = seed_graph("foundations")
    return Resolved(kg, kg.sink_concepts(), "foundations", "seed", "general")


def _match_concepts(kg: KnowledgeGraph, want: set[str]) -> list[str]:
    hits = [
        (len(want & _norm(c.name)) + (2 if c.id in want else 0), c.id) for c in kg.concepts.values()
    ]
    hits = sorted(((s, cid) for s, cid in hits if s > 0), reverse=True)
    if not hits:
        return []
    top = hits[0][0]
    return [cid for s, cid in hits if s == top][:2]
