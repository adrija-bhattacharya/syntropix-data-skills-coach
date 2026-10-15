"""Role-gap sequencing (novelty claim **A**).

The goal is a **target job role** - a weighted set of skills mined from what the
role actually requires - and a study-time budget.  VELPO chooses the
**prerequisite-closed set of concepts that maximises hiring-readiness inside the
budget**, then sequences it.

    readiness(S) = ( sum of w_i over role skills reached given S ) / ( sum of all w_i )   in [0, 1]

A "prerequisite-closed set" is exactly an **order ideal** of the prerequisite
poset (if a concept is in the set, all its prerequisites are too).  So the
choice is a **knapsack over the lattice of order ideals of a weighted poset**:

    best  =  argmax over order ideals I with time(I) <= budget  of  readiness(I)

enumerated smallest-first, ``O(#ideals * n)``; ``#ideals = O((n/w + 1) ** w)``
for width ``w``.  Above ``settings.role_max_ideals`` we fall back to a greedy
prerequisite-closed fill by value density (weight per marginal hour).

The result carries a **readiness curve** - readiness after each step - so a
learner who stops early still knows exactly how employable the partial plan
leaves them.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from algorithms.graph_traversal import ancestors_subgraph
from algorithms.poset import order_ideal_bound, order_ideals
from algorithms.sequencing import SeqStep, SequencePlan, plan_sequence
from config import settings
from model.knowledge_graph import Concept, KnowledgeGraph, Resource
from model.learner import LearnerState

NodeId = str
RoleProfile = dict[NodeId, float]  # concept id -> importance weight


@dataclass(frozen=True, slots=True)
class RolePlan:
    role: str
    chosen: tuple[NodeId, ...]  # the prerequisite-closed concept set, taught order
    readiness: float  # 0-1, after the whole plan
    readiness_before: float  # 0-1, from the assessment alone
    curve: tuple[float, float]  # (minutes, readiness) after each step  -> flattened pairs
    steps_curve: tuple[tuple[float, float], ...]
    covered_weight: float
    total_weight: float
    method: str  # "ideal-knapsack" | "greedy"
    sequence: SequencePlan

    @classmethod
    def empty(cls, role: str, note: str) -> RolePlan:
        return cls(
            role, (), 0.0, 0.0, (0.0, 0.0), (), 0.0, 1.0, note, SequencePlan.infeasible(note)
        )


# --------------------------------------------------------------------------- #
def _concept_minutes(kg: KnowledgeGraph, concept: NodeId) -> float:
    res = kg.resources_for(concept)
    return min((kg.resources[r].minutes for r in res), default=12.0)


def _reached(
    mastered: set[NodeId], profile: RoleProfile, state: LearnerState, threshold: float
) -> set[NodeId]:
    return {s for s in profile if s in mastered or state.decayed_mastery(s) >= threshold}


def readiness(
    mastered: set[NodeId], profile: RoleProfile, state: LearnerState, *, threshold: float
) -> float:
    total = sum(profile.values()) or 1.0
    got = sum(profile[s] for s in _reached(mastered, profile, state, threshold))
    return got / total


# --------------------------------------------------------------------------- #
def choose_prereq_closed_set(
    kg: KnowledgeGraph,
    profile: RoleProfile,
    state: LearnerState,
    *,
    budget_minutes: float,
    threshold: float | None = None,
) -> tuple[list[NodeId], str]:
    """The order ideal (prerequisite-closed concept set) of maximum readiness that
    fits the time budget.  Returns ``(concepts_in_topo_order, method)``."""
    theta = settings.mastery_threshold if threshold is None else threshold
    sub: nx.DiGraph = ancestors_subgraph(kg.prereq, list(profile))
    if sub.number_of_nodes() == 0:
        return [], "empty"

    already = {c for c in sub.nodes if state.decayed_mastery(c) >= theta}
    minutes = {c: _concept_minutes(kg, c) for c in sub.nodes}

    if order_ideal_bound(sub) <= settings.role_max_ideals:
        best_ideal: frozenset[NodeId] = frozenset()
        best_r = readiness(set(), profile, state, threshold=theta)
        best_t = 0.0
        for ideal in order_ideals(sub, limit=settings.role_max_ideals):
            t = sum(minutes[c] for c in ideal if c not in already)
            if t > budget_minutes:
                continue
            r = readiness(set(ideal), profile, state, threshold=theta)
            if r > best_r + 1e-9 or (abs(r - best_r) < 1e-9 and t < best_t):
                best_ideal, best_r, best_t = ideal, r, t
        return _topo(sub, best_ideal), "ideal-knapsack"

    # too wide - greedy prerequisite-closed fill by value density
    chosen: set[NodeId] = set(already)
    spent = 0.0
    remaining = [s for s in profile if s not in chosen]
    while remaining:
        best_s: NodeId | None = None
        best_density, best_cost = -1.0, 0.0
        best_add: frozenset[NodeId] = frozenset()
        for s in remaining:
            add = (nx.ancestors(sub, s) | {s}) - chosen
            cost = sum(minutes[c] for c in add if c not in already)
            if spent + cost > budget_minutes or cost <= 0:
                continue
            density = profile[s] / cost
            if density > best_density:
                best_s, best_density, best_cost, best_add = s, density, cost, frozenset(add)
        if best_s is None:
            break
        chosen |= best_add
        spent += best_cost
        remaining.remove(best_s)
    return _topo(sub, frozenset(chosen)), "greedy"


def _topo(sub: nx.DiGraph, ideal: frozenset[NodeId]) -> list[NodeId]:
    return [c for c in nx.topological_sort(sub) if c in ideal]


# --------------------------------------------------------------------------- #
def solve_role_plan(
    kg: KnowledgeGraph,
    role_name: str,
    profile: RoleProfile,
    state: LearnerState,
    *,
    budget_minutes: float,
    threshold: float | None = None,
) -> RolePlan:
    theta = settings.mastery_threshold if threshold is None else threshold
    total_w = sum(profile.values()) or 1.0
    r0 = readiness(set(), profile, state, threshold=theta)

    chosen, method = choose_prereq_closed_set(
        kg, profile, state, budget_minutes=budget_minutes, threshold=theta
    )
    if not chosen:
        return RolePlan(
            role_name,
            (),
            r0,
            r0,
            (0.0, r0),
            ((0.0, r0),),
            r0 * total_w,
            total_w,
            method,
            SequencePlan.infeasible("nothing fits the budget"),
        )

    seq = _sequence_chosen(kg, chosen, _role_goals(kg, chosen, profile), state, budget_minutes)

    # readiness after each taught step
    taught: set[NodeId] = set()
    mins = 0.0
    curve: list[tuple[float, float]] = [(0.0, r0)]
    for st in seq.steps:
        taught.add(st.concept)
        mins += kg.resources[st.resource_id].minutes
        curve.append((round(mins, 1), round(readiness(taught, profile, state, threshold=theta), 3)))

    final = readiness(taught, profile, state, threshold=theta)
    return RolePlan(
        role=role_name,
        chosen=tuple(chosen),
        readiness=round(final, 3),
        readiness_before=round(r0, 3),
        curve=(round(mins, 1), round(final, 3)),
        steps_curve=tuple(curve),
        covered_weight=round(final * total_w, 2),
        total_weight=round(total_w, 2),
        method=method,
        sequence=seq,
    )


def _restrict(kg: KnowledgeGraph, chosen: list[NodeId]) -> KnowledgeGraph:
    cset = set(chosen)
    concepts = [Concept(c, kg.concepts[c].name) for c in chosen]
    edges = [(u, v) for u, v in kg.prereq.edges() if u in cset and v in cset]
    resources: list[Resource] = [kg.resources[r] for c in chosen for r in kg.resources_for(c)]
    return KnowledgeGraph.build(concepts, edges, resources)


def _sequence_chosen(
    kg: KnowledgeGraph,
    chosen: list[NodeId],
    goals: list[NodeId],
    state: LearnerState,
    budget_minutes: float,
) -> SequencePlan:
    if not chosen:
        return SequencePlan.infeasible("nothing chosen")
    rkg = _restrict(kg, chosen)
    tgt = [g for g in goals if g in rkg.concepts] or list(chosen)
    sp = plan_sequence(rkg, tgt, state, budget_seconds=budget_minutes * 60)
    if sp.feasible and sp.steps:
        return sp
    # role poset too wide for the exact sequencing DP.  The concept *set* was
    # already chosen to fit the budget, so all that is left is to order it: a
    # topological order that greedily smooths the difficulty jump.
    order = _smooth_topo(rkg, state)
    steps = tuple(SeqStep(concept=c, resource_id=_cheapest(rkg, c)) for c in order)
    total = sum(rkg.resources[s.resource_id].seconds for s in steps)
    from model.cost import CostVector

    return SequencePlan(
        steps=steps,
        objective=CostVector.zero(),
        scalar_cost=0.0,
        total_seconds=total,
        feasible=True,
        note="topological order (role poset too wide for the exact sequencing DP)",
    )


def _cheapest(kg: KnowledgeGraph, concept: NodeId) -> str:
    return min(kg.resources_for(concept), key=lambda r: kg.resources[r].minutes)


def _smooth_topo(kg: KnowledgeGraph, state: LearnerState) -> list[NodeId]:
    g = kg.prereq
    indeg = {n: g.in_degree(n) for n in g.nodes}
    ready = sorted(n for n, d in indeg.items() if d == 0)
    out: list[NodeId] = []
    last = 1.0
    while ready:
        pick = min(ready, key=lambda c: (abs(kg.resources[_cheapest(kg, c)].difficulty - last), c))
        ready.remove(pick)
        out.append(pick)
        last = kg.resources[_cheapest(kg, pick)].difficulty
        for s in sorted(g.successors(pick)):
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
        ready.sort()
    return out


def _role_goals(kg: KnowledgeGraph, chosen: list[NodeId], profile: RoleProfile) -> list[NodeId]:
    """Goal concepts for the sequencer: the role skills that are in the chosen
    set (fall back to the maximal elements so the sequencer has a target)."""
    goals = [c for c in chosen if c in profile]
    if goals:
        return goals
    inside = set(chosen)
    return [c for c in chosen if not any(s in inside for s in kg.prereq.successors(c))] or chosen[
        -1:
    ]
