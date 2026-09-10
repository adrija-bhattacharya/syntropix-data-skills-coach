"""The DAA core - a **precedence-constrained sequencing DP over the poset's
order ideals**.

The prerequisite graph is a partial order; a learning path is a linear
extension of it and a valid *prefix* is an order ideal (down-set).  This module
finds the **provably optimal linear extension** (not just an optimal resource
selection), then places spaced reviews and packs the result into study sessions.

Three stages, each an exact DP given the previous one:

1. :func:`solve_sequence` - shortest path in the lattice of order ideals.
   State ``(I, r_last)``: the set ``I`` of concepts already taught and the last
   resource chosen (for the difficulty-jump term).  Step cost is
   **position-dependent** (:func:`model.cost.sequence_step_cost`): a concept
   taught before its prerequisites are solid, or long after they have decayed,
   costs more.  Optimal substructure holds because ``(I, r_last)`` is a
   sufficient statistic for the remaining cost - prerequisite mastery is a
   function of ``I`` and the step index ``|I|``.
   Time ``O(#ideals * W * R)``; ``#ideals <= prod(chain_len + 1)`` over a minimum
   chain cover, which is ``O((n/w + 1) ** w)`` for width ``w`` - polynomial for
   real curricula.  Above ``settings.seq_max_ideals`` order ideals the engine
   falls back to knapsack-select + heuristic order.  The time budget is handled
   by re-solving with shortest resources if the optimum overruns it.

2. :func:`insert_reviews` - a 1-D DP over the sequence that inserts up to
   ``settings.max_reviews`` review steps where predicted mastery would otherwise
   fall below threshold before the goal.

3. :func:`pack_sessions` - a 1-D partition DP that splits the final sequence into
   contiguous study sessions honouring per-session time and cognitive-load caps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import networkx as nx

from algorithms.dynamic_programming import (
    InfeasibleError,
    TeacherConstraints,
    build_plan_context,
)
from algorithms.poset import count_order_ideals, order_ideal_bound, poset_width
from config import settings
from model.cost import (
    CostVector,
    predicted_mastery,
    sequence_review_cost,
    sequence_step_cost,
)
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

NodeId = str
Weights = tuple[float, float, float, float, float]
_INF = math.inf
_GOAL_PENALTY = 40.0  # weight on "a goal is still below threshold at the end"


@dataclass(frozen=True, slots=True)
class SeqStep:
    concept: NodeId
    resource_id: NodeId
    review: bool = False


@dataclass(frozen=True, slots=True)
class SequencePlan:
    steps: tuple[SeqStep, ...]
    objective: CostVector
    scalar_cost: float
    total_seconds: float
    sessions: tuple[tuple[int, int], ...] = ()  # [start, end) indices into steps
    feasible: bool = True
    note: str = ""
    reasons: tuple[str, ...] = ()
    ideals: int = 0
    poset_width: int = 0

    @classmethod
    def infeasible(cls, note: str) -> SequencePlan:
        return cls((), CostVector.zero(), _INF, 0.0, feasible=False, note=note)


# --------------------------------------------------------------------------- #
# stage 1 - the sequencing DP over order ideals
# --------------------------------------------------------------------------- #
# order ideals are represented as integer bitmasks over the topological order;
# a DP state is (ideal_mask, last_resource_id).
_Key = tuple[int, str]


@dataclass(slots=True)
class _Cell:
    cost: float
    vec: CostVector
    back: _Key | None
    step: SeqStep | None


def _levels(dag: nx.DiGraph, order: list[NodeId]) -> dict[NodeId, int]:
    """Longest-prerequisite-chain depth - the proxy for 'when concept c is taught'."""
    lvl: dict[NodeId, int] = {}
    for c in order:
        preds = list(dag.predecessors(c))
        lvl[c] = 0 if not preds else 1 + max(lvl[p] for p in preds)
    return lvl


def solve_sequence(
    kg: KnowledgeGraph,
    goals: list[NodeId],
    state: LearnerState,
    *,
    weights: Weights | None = None,
    budget_seconds: float | None = None,
    constraints: TeacherConstraints | None = None,
    half_life_steps: float | None = None,
    max_ideals: int | None = None,
) -> SequencePlan:
    """Optimal linear extension + resource choice.

    Budget: the DP minimises the weighted cost (which includes study time).  If
    the optimal sequence still overruns ``budget_seconds`` it is re-solved with
    every concept locked to its shortest resource - guaranteed to fit if any
    sequence does, otherwise the plan is infeasible.
    """
    w = settings.weights if weights is None else weights
    hl = settings.seq_half_life_steps if half_life_steps is None else half_life_steps
    cap = settings.seq_max_ideals if max_ideals is None else max_ideals
    budget = state.time_budget_s if budget_seconds is None else budget_seconds

    try:
        ctx = build_plan_context(
            kg,
            goals,
            state,
            {r: CostVector.zero() for r in kg.resources},
            constraints=constraints,
        )
    except InfeasibleError as exc:
        return SequencePlan.infeasible(str(exc))

    order = list(ctx.concept_order)
    if not order:
        return SequencePlan((), CostVector.zero(), 0.0, 0.0, note="goal already satisfied")

    dag: nx.DiGraph = ctx.relevant_dag
    bound = order_ideal_bound(dag)
    if bound > cap:
        if bound > settings.seq_ideal_bound_soft:
            return SequencePlan.infeasible(
                f"poset admits up to {bound:.0e} order ideals (> {cap}) - knapsack fallback"
            )
        exact = count_order_ideals(dag, limit=cap + 1)
        if exact > cap:
            return SequencePlan.infeasible(f"poset has > {cap} order ideals - knapsack fallback")

    floor_seconds = sum(min(kg.resources[r].seconds for r in ctx.candidates[c]) for c in order)
    if floor_seconds > budget + 1e-6:
        return SequencePlan.infeasible("no resource selection fits the time budget")

    width = poset_width(dag)
    result = _run_dp(kg, order, dag, ctx.candidates, state, w, hl, goals)
    if result is None:
        return SequencePlan.infeasible(f"sequencing DP exceeded the state cap (width {width})")
    if result.total_seconds > budget + 1e-6:
        # re-solve with each concept pinned to its shortest resource
        def _fastest(c: NodeId) -> tuple[NodeId, ...]:
            return (min(ctx.candidates[c], key=lambda r: kg.resources[r].seconds),)

        pinned = {c: _fastest(c) for c in order}
        result = _run_dp(kg, order, dag, pinned, state, w, hl, goals) or result

    return SequencePlan(
        result.steps,
        result.objective,
        result.scalar_cost,
        result.total_seconds,
        feasible=result.total_seconds <= budget + 1e-6,
        ideals=result.ideals,
        poset_width=width,
        note="" if result.total_seconds <= budget + 1e-6 else "over budget even at minimal time",
    )


def _run_dp(
    kg: KnowledgeGraph,
    order: list[NodeId],
    dag: nx.DiGraph,
    cand: dict[NodeId, tuple[NodeId, ...]],
    state: LearnerState,
    w: Weights,
    hl: float,
    goals: list[NodeId],
) -> SequencePlan | None:
    n = len(order)
    idx = {c: i for i, c in enumerate(order)}
    level = _levels(dag, order)
    pred_mask = [0] * n
    for i, c in enumerate(order):
        for p in dag.predecessors(c):
            pred_mask[i] |= 1 << idx[p]
    full = (1 << n) - 1
    goal_set = [g for g in goals if g in idx]
    state_cap = 20 * settings.seq_max_ideals

    # step-cost cache: (concept_index, resource_id, position, prev_difficulty) is
    # a full statistic for the cost, and there are few distinct tuples.
    cache: dict[tuple[int, str, int, float], tuple[float, CostVector]] = {}

    def step(ci: int, rid: str, pos: int, prev_d: float) -> tuple[float, CostVector]:
        ck = (ci, rid, pos, prev_d)
        hit = cache.get(ck)
        if hit is None:
            cv = sequence_step_cost(
                kg,
                order[ci],
                rid,
                state,
                position=pos,
                taught_at=level,
                prev_difficulty=prev_d,
                half_life_steps=hl,
            )
            hit = (cv.scalarise(w), cv)
            cache[ck] = hit
        return hit

    start: _Key = (0, "")
    dp: dict[_Key, _Cell] = {start: _Cell(0.0, CostVector.zero(), None, None)}
    frontier = [start]
    while frontier:
        nxt: list[_Key] = []
        for key in frontier:
            ideal, r_last = key
            cell = dp[key]
            base_cost, base_vec = cell.cost, cell.vec
            pos = ideal.bit_count()
            prev_d = 1.0 if not r_last else kg.resources[r_last].difficulty
            avail = ~ideal & full
            for ci in range(n):
                bit = 1 << ci
                if not (avail & bit) or (pred_mask[ci] & ideal) != pred_mask[ci]:
                    continue
                nideal = ideal | bit
                for rid in cand[order[ci]]:
                    s_cost, cv = step(ci, rid, pos, prev_d)
                    nkey: _Key = (nideal, rid)
                    ncost = base_cost + s_cost
                    cur = dp.get(nkey)
                    if cur is None:
                        dp[nkey] = _Cell(ncost, base_vec + cv, key, SeqStep(order[ci], rid, False))
                        nxt.append(nkey)
                    elif ncost < cur.cost:
                        cur.cost, cur.vec, cur.back, cur.step = (
                            ncost,
                            base_vec + cv,
                            key,
                            SeqStep(order[ci], rid, False),
                        )
        if len(dp) > state_cap:
            return None
        frontier = nxt

    final_pos = n
    shortfall = sum(
        max(
            0.0,
            settings.mastery_threshold
            - predicted_mastery(settings.seq_post_mastery, level[g], final_pos, hl),
        )
        for g in goal_set
    )
    best_key: _Key | None = None
    best_total = _INF
    for key, cell in dp.items():
        if key[0] != full:
            continue
        total = cell.cost + _GOAL_PENALTY * shortfall
        if total < best_total:
            best_total, best_key = total, key
    if best_key is None:
        return None

    steps: list[SeqStep] = []
    vec = dp[best_key].vec
    k: _Key | None = best_key
    while k is not None and dp[k].step is not None:
        steps.append(dp[k].step)  # type: ignore[arg-type]
        k = dp[k].back
    steps.reverse()
    total_seconds = sum(kg.resources[s.resource_id].seconds for s in steps)
    return SequencePlan(
        tuple(steps),
        vec,
        best_total,
        total_seconds,
        ideals=len({key[0] for key in dp}),
    )


# --------------------------------------------------------------------------- #
# stage 2 - insert spaced reviews
# --------------------------------------------------------------------------- #
def insert_reviews(
    kg: KnowledgeGraph,
    plan: SequencePlan,
    state: LearnerState,
    goals: list[NodeId],
    *,
    weights: Weights | None = None,
    half_life_steps: float | None = None,
) -> SequencePlan:
    """Greedy-optimal 1-D pass: walk the sequence, and whenever a concept that is
    a prerequisite of an upcoming step (or a goal) is predicted to be below
    ``settings.review_threshold``, splice a short review in - up to
    ``settings.max_reviews`` times, each time picking the review that clears the
    most predicted debt per second."""
    if not plan.feasible or not plan.steps:
        return plan
    w = settings.weights if weights is None else weights
    hl = settings.seq_half_life_steps if half_life_steps is None else half_life_steps
    post = settings.seq_post_mastery

    steps = list(plan.steps)
    taught_at: dict[str, int] = {s.concept: i for i, s in enumerate(steps)}
    goal_set = set(goals)

    def m_now(concept: str, at: int) -> float:
        return predicted_mastery(post, taught_at[concept], at, hl)

    inserted = 0
    i = 0
    vec = plan.objective
    while i < len(steps) and inserted < settings.max_reviews:
        s = steps[i]
        # concepts already taught that this step (or a goal) leans on and that have decayed
        needed = kg.direct_prerequisites(s.concept) | ({s.concept} & goal_set)
        stale = [
            q
            for q in needed
            if q in taught_at and taught_at[q] < i and m_now(q, i) < settings.review_threshold
        ]
        if stale:
            q = min(stale, key=lambda x: m_now(x, i))
            rid = _shortest_resource(kg, q)
            prev_d = kg.resources[steps[i - 1].resource_id].difficulty if i else 1.0
            cv = sequence_review_cost(
                kg,
                q,
                rid,
                position=i,
                taught_at=taught_at,
                prev_difficulty=prev_d,
                half_life_steps=hl,
            )
            steps.insert(i, SeqStep(q, rid, review=True))
            vec = vec + cv
            taught_at[q] = i
            for c, p in list(taught_at.items()):
                if p >= i and c != q:
                    taught_at[c] = p + 1
            inserted += 1
            i += 1  # step over the review we just placed
        i += 1

    if inserted == 0:
        return plan
    total_seconds = sum(kg.resources[s.resource_id].seconds for s in steps)
    note = f"{inserted} spaced review{'s' if inserted != 1 else ''} inserted"
    return SequencePlan(
        tuple(steps),
        vec,
        vec.scalarise(w),
        total_seconds,
        note=note,
        ideals=plan.ideals,
        poset_width=plan.poset_width,
    )


def _shortest_resource(kg: KnowledgeGraph, concept: str) -> str:
    return min(kg.resources_for(concept), key=lambda r: kg.resources[r].minutes)


# --------------------------------------------------------------------------- #
# stage 3 - pack the sequence into study sessions
# --------------------------------------------------------------------------- #
def pack_sessions(
    kg: KnowledgeGraph,
    plan: SequencePlan,
    *,
    session_minutes: float | None = None,
    session_max_load: float | None = None,
) -> SequencePlan:
    """Partition DP: split the (ordered, immutable) sequence into the fewest
    contiguous sessions such that no session exceeds the time or cumulative-load
    cap, tie-broken toward balanced session lengths.  ``O(n**2)``."""
    if not plan.feasible or not plan.steps:
        return plan
    tcap = settings.session_minutes if session_minutes is None else session_minutes
    lcap = settings.session_max_load if session_max_load is None else session_max_load

    steps = plan.steps
    n = len(steps)
    pm = [0.0] * (n + 1)
    pl = [0.0] * (n + 1)
    for i, s in enumerate(steps):
        r = kg.resources[s.resource_id]
        pm[i + 1] = pm[i] + r.minutes
        pl[i + 1] = pl[i] + max(0.05, r.difficulty / 5.0)

    def fits(a: int, b: int) -> bool:  # steps [a, b) - a lone step is always its own session
        return b - a == 1 or (pm[b] - pm[a] <= tcap + 1e-9 and pl[b] - pl[a] <= lcap + 1e-9)

    dp: list[tuple[float, float, int]] = [(_INF, 0.0, -1)] * (n + 1)  # (#sessions, balance, split)
    dp[0] = (0.0, 0.0, -1)
    for b in range(1, n + 1):
        for a in range(b - 1, -1, -1):
            if b - a > 1 and not fits(a, b):
                break  # blocks only grow as a shrinks
            base_sessions, base_bal, _ = dp[a]
            if base_sessions == _INF:
                continue
            bal = base_bal + (tcap - (pm[b] - pm[a])) ** 2
            cand = (base_sessions + 1, bal, a)
            if cand < dp[b]:
                dp[b] = cand

    bounds: list[int] = []
    cur = n
    while cur > 0:
        prev = dp[cur][2]
        bounds.append(prev)
        cur = prev
    bounds.reverse()
    sessions = tuple(zip(bounds, [*bounds[1:], n], strict=True))

    return SequencePlan(
        plan.steps,
        plan.objective,
        plan.scalar_cost,
        plan.total_seconds,
        sessions=sessions,
        note=plan.note,
        reasons=plan.reasons,
        ideals=plan.ideals,
        poset_width=plan.poset_width,
    )


# --------------------------------------------------------------------------- #
# the whole pipeline
# --------------------------------------------------------------------------- #
def plan_sequence(
    kg: KnowledgeGraph,
    goals: list[NodeId],
    state: LearnerState,
    *,
    weights: Weights | None = None,
    budget_seconds: float | None = None,
    constraints: TeacherConstraints | None = None,
    reviews: bool = True,
    sessions: bool = True,
) -> SequencePlan:
    """Stage 1 (order-ideal DP) -> stage 2 (spaced reviews) -> stage 3 (sessions)."""
    plan = solve_sequence(
        kg, goals, state, weights=weights, budget_seconds=budget_seconds, constraints=constraints
    )
    if not plan.feasible or not plan.steps:
        return plan
    if reviews:
        plan = insert_reviews(kg, plan, state, goals, weights=weights)
    if sessions:
        plan = pack_sessions(kg, plan)
    return plan
