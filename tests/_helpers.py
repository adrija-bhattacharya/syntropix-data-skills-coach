"""Independent reference implementations - deliberately naive so a bug in the DP
cannot hide behind a shared helper."""

from __future__ import annotations

import itertools
import math

import networkx as nx

from velpo.algorithms.dynamic_programming import Plan, build_plan_context
from velpo.algorithms.graph_traversal import ancestors_subgraph, topological_order
from velpo.model.cost import CostVector
from velpo.model.knowledge_graph import Concept, KnowledgeGraph, Resource
from velpo.model.learner import LearnerState

Weights = tuple[float, float, float, float, float]


def brute_force(
    kg: KnowledgeGraph,
    goals: list[str],
    state: LearnerState,
    costs: dict[str, CostVector],
    weights: Weights,
    *,
    budget_buckets: int,
) -> float:
    """Exhaustive minimum scalar cost over every resource-choice combination that
    fits the budget.  ``inf`` if none fit."""
    ctx = build_plan_context(kg, goals, state, costs, budget_buckets=budget_buckets)
    if not ctx.concept_order:
        return 0.0
    choice_sets = [ctx.candidates[c] for c in ctx.concept_order]
    best = math.inf
    for combo in itertools.product(*choice_sets):
        if sum(ctx.buckets_for(r) for r in combo) > ctx.budget_buckets:
            continue
        best = min(best, sum(costs[r].scalarise(weights) for r in combo))
    return best


def assert_feasible(
    kg: KnowledgeGraph, plan: Plan, state: LearnerState, goals: list[str], *, budget_buckets: int
) -> None:
    assert plan.feasible, plan.note
    if not plan.steps:
        assert not ancestors_subgraph(kg.prereq, goals).nodes
        return

    ctx = build_plan_context(
        kg,
        goals,
        state,
        {r: CostVector(0, kg.resources[r].seconds, 0, 0, 0) for r in kg.resources},
        budget_buckets=budget_buckets,
    )

    introduced = {c for c in kg.concept_ids if state.is_mastered(c)}
    for rid, cid in zip(plan.steps, plan.concepts):
        assert cid in kg.resources[rid].concepts
        for req in kg.prerequisites_of_resource(rid):
            assert req in introduced, f"{rid} studied before prerequisite {req}"
        introduced.update(kg.resources[rid].concepts)

    relevant = set(topological_order(ancestors_subgraph(kg.prereq, goals)))
    assert set(plan.concepts) == relevant

    used = sum(max(1, math.ceil(kg.resources[r].seconds / ctx.bucket_seconds)) for r in plan.steps)
    assert used <= budget_buckets
    assert set(goals) <= introduced


def random_curriculum(rng, *, n: int = 6, edge_p: float = 0.35, max_alt: int = 3) -> KnowledgeGraph:
    ids = [f"c{i}" for i in range(n)]
    concepts = [Concept(c, c.upper()) for c in ids]
    prereqs = [(ids[i], ids[j]) for i in range(n) for j in range(i + 1, n) if rng.random() < edge_p]
    g = nx.DiGraph(prereqs)
    g.add_nodes_from(ids)
    assert nx.is_directed_acyclic_graph(g)
    resources = [
        Resource(
            f"{c}:{k}",
            (c,),
            float(rng.integers(1, 6)),
            float(rng.integers(2, 12)),
            "lesson" if k == 0 else "practice",
        )
        for c in ids
        for k in range(rng.integers(1, max_alt + 1))
    ]
    return KnowledgeGraph.build(concepts, prereqs, resources)
