"""A* anytime solver - the same optimum as :func:`solve_optimal`, best-first.

State space is identical to the DP: ``(concept_index, time_buckets_used)``.
The heuristic ``h(i) = sum over remaining concepts of the cheapest candidate's
scalar cost`` never overestimates the true remaining cost (the budget can only
*remove* options), so A* is admissible and returns the global optimum - while
typically expanding far fewer states than the DP table has cells.  This is the
"< 100 ms re-plan" path.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from velpo.algorithms.dynamic_programming import (
    InfeasibleError,
    Plan,
    TeacherConstraints,
    Weights,
    _assemble,
    _per_concept_argmin,
    build_plan_context,
)
from velpo.config import settings
from velpo.model.cost import CostVector
from velpo.model.knowledge_graph import KnowledgeGraph
from velpo.model.learner import LearnerState

_INF = math.inf


@dataclass(frozen=True, slots=True)
class AStarStats:
    expanded: int
    pushed: int


def solve_astar(
    kg: KnowledgeGraph,
    goals: list[str],
    state: LearnerState,
    costs: dict[str, CostVector],
    weights: Weights | None = None,
    *,
    budget_buckets: int | None = None,
    constraints: TeacherConstraints | None = None,
    return_stats: bool = False,
) -> Plan | tuple[Plan, AStarStats]:
    w = settings.weights if weights is None else weights
    try:
        ctx = build_plan_context(
            kg, goals, state, costs, budget_buckets=budget_buckets, constraints=constraints
        )
    except InfeasibleError as exc:
        bad = Plan.infeasible(str(exc))
        return (bad, AStarStats(0, 0)) if return_stats else bad

    order = ctx.concept_order
    n = len(order)
    if n == 0:
        empty = Plan((), (), CostVector.zero(), 0.0, note="goal already satisfied")
        return (empty, AStarStats(0, 0)) if return_stats else empty

    if ctx.budget_is_slack():
        choice, vec = _per_concept_argmin(ctx, w)
        plan = _assemble(ctx, kg, choice, vec)
        return (plan, AStarStats(n, n)) if return_stats else plan

    B = ctx.budget_buckets
    suffix_min = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_min[i] = suffix_min[i + 1] + min(
            costs[r].scalarise(w) for r in ctx.candidates[order[i]]
        )

    # (f, g, index, buckets_used, choice, cost vector)
    pq: list[tuple[float, float, int, int, tuple[str, ...], CostVector]] = [
        (suffix_min[0], 0.0, 0, 0, (), CostVector.zero())
    ]
    best_g: dict[tuple[int, int], float] = {(0, 0): 0.0}
    expanded = pushed = 1

    while pq:
        _f, g, i, used, choice, vec = heapq.heappop(pq)
        if g > best_g.get((i, used), _INF):
            continue
        expanded += 1
        if i == n:
            plan = _assemble(ctx, kg, choice, vec)
            return (plan, AStarStats(expanded, pushed)) if return_stats else plan
        for r in ctx.candidates[order[i]]:
            nb = used + ctx.buckets_for(r)
            if nb > B:
                continue
            ng = g + costs[r].scalarise(w)
            key = (i + 1, nb)
            if ng < best_g.get(key, _INF) - 1e-12:
                best_g[key] = ng
                heapq.heappush(
                    pq, (ng + suffix_min[i + 1], ng, i + 1, nb, (*choice, r), vec + costs[r])
                )
                pushed += 1

    bad = Plan.infeasible("no resource selection fits the time budget")
    return (bad, AStarStats(expanded, pushed)) if return_stats else bad
