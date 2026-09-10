"""A* **anytime** solver (novelty claim **N6**).

Same state space as the DP - ``(concept_index, time_buckets_used)`` - explored
best-first with an admissible ``suffix-min`` heuristic
(``h(i) = sum of the cheapest candidate cost over the remaining concepts``),
which never overestimates because a tighter budget can only *remove* options.

**Anytime contract**

1. A feasible *incumbent* is produced immediately (the per-concept
   cheapest-by-time choice), so a plan is available at ``t = 0``.
2. Best-first search then improves it, pruning any node whose
   ``g + h`` already meets the incumbent (branch-and-bound).
3. If ``deadline_s`` elapses first, the current incumbent is returned with
   ``optimal=False``; otherwise the incumbent is the proven global optimum
   (``optimal=True``) - identical to :func:`solve_optimal`.

Because the whole search is a few hundred microseconds on the course curriculum,
"re-plan after every interaction" is practical with no model retraining.
"""

from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass, replace

from algorithms.dynamic_programming import (
    InfeasibleError,
    Plan,
    PlanContext,
    TeacherConstraints,
    Weights,
    _assemble,
    _per_concept_argmin,
    build_plan_context,
)
from config import settings
from model.cost import CostVector
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

_INF = math.inf


@dataclass(frozen=True, slots=True)
class AStarStats:
    expanded: int
    pushed: int
    improved: int = 0
    optimal: bool = True
    elapsed_ms: float = 0.0


def solve_astar(
    kg: KnowledgeGraph,
    goals: list[str],
    state: LearnerState,
    costs: dict[str, CostVector],
    weights: Weights | None = None,
    *,
    budget_buckets: int | None = None,
    constraints: TeacherConstraints | None = None,
    deadline_s: float | None = None,
    return_stats: bool = False,
) -> Plan | tuple[Plan, AStarStats]:
    w = settings.weights if weights is None else weights
    t0 = time.perf_counter()

    def done(plan: Plan, st: AStarStats) -> Plan | tuple[Plan, AStarStats]:
        st = replace(st, elapsed_ms=(time.perf_counter() - t0) * 1000.0)
        return (plan, st) if return_stats else plan

    try:
        ctx = build_plan_context(
            kg, goals, state, costs, budget_buckets=budget_buckets, constraints=constraints
        )
    except InfeasibleError as exc:
        return done(Plan.infeasible(str(exc)), AStarStats(0, 0, optimal=True))

    order = ctx.concept_order
    n = len(order)
    if n == 0:
        empty = Plan((), (), CostVector.zero(), 0.0, note="goal already satisfied")
        return done(empty, AStarStats(0, 0))

    if ctx.budget_is_slack():
        choice, vec = _per_concept_argmin(ctx, w)
        return done(_assemble(ctx, kg, choice, vec), AStarStats(n, n))

    B = ctx.budget_buckets
    suffix_min = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_min[i] = suffix_min[i + 1] + min(
            costs[r].scalarise(w) for r in ctx.candidates[order[i]]
        )

    incumbent = _greedy_incumbent(ctx, w)
    if incumbent is None:
        return done(
            Plan.infeasible("no resource selection fits the time budget"),
            AStarStats(0, 0, optimal=True),
        )
    best_choice, best_vec, best_cost = incumbent

    pq: list[tuple[float, float, int, int, tuple[str, ...], CostVector]] = [
        (suffix_min[0], 0.0, 0, 0, (), CostVector.zero())
    ]
    best_g: dict[tuple[int, int], float] = {(0, 0): 0.0}
    expanded = pushed = 1
    improved = 0
    optimal = True

    while pq:
        if deadline_s is not None and (time.perf_counter() - t0) >= deadline_s:
            optimal = False
            break
        f, g, i, used, choice, vec = heapq.heappop(pq)
        if f >= best_cost:  # admissible h => nothing left can beat the incumbent
            break
        if g > best_g.get((i, used), _INF):
            continue
        expanded += 1
        if i == n:
            if g < best_cost:
                best_choice, best_vec, best_cost = choice, vec, g
                improved += 1
            continue
        for r in ctx.candidates[order[i]]:
            nb = used + ctx.buckets_for(r)
            if nb > B:
                continue
            ng = g + costs[r].scalarise(w)
            if ng + suffix_min[i + 1] >= best_cost:
                continue
            key = (i + 1, nb)
            if ng < best_g.get(key, _INF) - 1e-12:
                best_g[key] = ng
                heapq.heappush(
                    pq, (ng + suffix_min[i + 1], ng, i + 1, nb, (*choice, r), vec + costs[r])
                )
                pushed += 1

    plan = _assemble(ctx, kg, best_choice, best_vec)
    if not optimal:
        plan = replace(
            plan, note=f"anytime: best-so-far after {deadline_s:g}s (not proven optimal)"
        )
    return done(plan, AStarStats(expanded, pushed, improved, optimal))


def _greedy_incumbent(
    ctx: PlanContext, w: Weights
) -> tuple[tuple[str, ...], CostVector, float] | None:
    """A feasible plan available immediately: per concept, the resource with the
    fewest buckets (ties broken by scalar cost).  ``None`` if even that overflows."""
    choice: list[str] = []
    vec = CostVector.zero()
    used = 0
    for c in ctx.concept_order:
        r = min(ctx.candidates[c], key=lambda x: (ctx.buckets_for(x), ctx.costs[x].scalarise(w)))
        used += ctx.buckets_for(r)
        choice.append(r)
        vec = vec + ctx.costs[r]
    if used > ctx.budget_buckets:
        return None
    return tuple(choice), vec, vec.scalarise(w)
