"""The DAA core - constrained resource selection by dynamic programming.

Model
-----
The learner must master every concept in ``relevant = goals U ancestors(goals)``.
That set is **prerequisite-closed by construction** (backward BFS in
:func:`velpo.algorithms.graph_traversal.ancestors_subgraph`), so presenting the
plan in a topological order of the concept graph makes it **prerequisite-valid
by construction** - no runtime check can be violated.

For each concept the learner picks **one** resource from its candidate set.
Each candidate has a precomputed, position-independent 5-D cost vector.  The plan
must fit the time budget ``T`` (discretised into ``B`` buckets).

This is a **multiple-choice knapsack over the topological order**::

    dp[b] = min scalar cost of choosing a resource for concepts c_1..c_i
            (topo order) using at most b time buckets

    dp[b] = min over r in R(c_i) of  dp[b - buckets(r)] + weights . cost(r)

* a transition that would exceed the budget is never generated
  => **an over-budget plan is unrepresentable**;
* the recurrence is exact (multiple-choice knapsack DP) => the returned plan is
  the **global optimum** for the scalarised objective;
* ``O(V * R * B)`` time, ``O(V * B)`` space  (V = relevant concepts,
  R = max candidates/concept, B = budget buckets).  When the budget cannot bind
  the concepts decouple and it drops to ``O(V * R)``.

:func:`solve_pareto` keeps a non-dominated *set* of cost vectors per state
instead of a scalar and returns the Pareto front.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import networkx as nx

from algorithms.graph_traversal import ancestors_subgraph, topological_order
from algorithms.pareto import epsilon_prune, non_dominated
from config import settings
from model.cost import CostVector
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

NodeId = str
Weights = tuple[float, float, float, float, float]
_INF = math.inf


class InfeasibleError(Exception):
    """Raised while building the plan context when no plan can exist."""


@dataclass(frozen=True, slots=True)
class TeacherConstraints:
    ban: frozenset[str] = frozenset()
    lock: frozenset[str] = frozenset()
    force_order: tuple[tuple[str, str], ...] = ()

    @classmethod
    def make(
        cls,
        *,
        ban: Iterable[str] = (),
        lock: Iterable[str] = (),
        force_order: Iterable[tuple[str, str]] = (),
    ) -> TeacherConstraints:
        return cls(frozenset(ban), frozenset(lock), tuple(force_order))

    @property
    def is_empty(self) -> bool:
        return not (self.ban or self.lock or self.force_order)


@dataclass(frozen=True, slots=True)
class Plan:
    steps: tuple[NodeId, ...]  # resource ids, in study order
    concepts: tuple[NodeId, ...]  # concept taught by each step (parallel)
    objective: CostVector
    total_seconds: float
    feasible: bool = True
    reasons: tuple[str, ...] = ()
    note: str = ""
    reviews: tuple[bool, ...] = ()  # parallel to steps: is this a spaced-review step?
    checks: tuple[bool, ...] = ()  # parallel to steps: is this a risk-driven confidence check?
    sessions: tuple[tuple[int, int], ...] = ()  # [start, end) step-index ranges per study session

    @classmethod
    def infeasible(cls, note: str) -> Plan:
        return cls((), (), CostVector.zero(), 0.0, feasible=False, note=note)

    def is_review(self, i: int) -> bool:
        return bool(self.reviews) and self.reviews[i]

    def is_check(self, i: int) -> bool:
        return bool(self.checks) and self.checks[i]


@dataclass(frozen=True, slots=True)
class PlanContext:
    concept_order: tuple[NodeId, ...]
    candidates: dict[NodeId, tuple[NodeId, ...]]
    costs: dict[NodeId, CostVector]
    bucket_seconds: float
    budget_buckets: int
    relevant_dag: nx.DiGraph  # the (constraint-augmented) prerequisite sub-DAG

    def buckets_for(self, resource_id: str) -> int:
        return max(1, math.ceil(self.costs[resource_id].seconds / self.bucket_seconds))

    def budget_is_slack(self) -> bool:
        """The most expensive resource per concept still fits => the budget can
        never bind => the optimum is the per-concept argmin."""
        worst = sum(
            max(self.buckets_for(r) for r in self.candidates[c]) for c in self.concept_order
        )
        return worst <= self.budget_buckets


# --------------------------------------------------------------------------- #
def build_plan_context(
    kg: KnowledgeGraph,
    goals: list[NodeId],
    state: LearnerState,
    costs: dict[NodeId, CostVector],
    *,
    budget_buckets: int | None = None,
    constraints: TeacherConstraints | None = None,
) -> PlanContext:
    tc = constraints or TeacherConstraints()
    if tc.ban & tc.lock:
        raise InfeasibleError(f"resources both locked and banned: {sorted(tc.ban & tc.lock)}")

    prereq: nx.DiGraph = kg.prereq
    if tc.force_order:
        prereq = kg.prereq.copy()
        for src, dst in tc.force_order:
            if src not in kg.concepts or dst not in kg.concepts:
                raise InfeasibleError(f"force_order references unknown concept {src!r}->{dst!r}")
            prereq.add_edge(src, dst)
        if not nx.is_directed_acyclic_graph(prereq):
            raise InfeasibleError("force_order introduces a cyclic prerequisite")

    sub = ancestors_subgraph(prereq, goals)
    order = tuple(topological_order(sub))
    n_buckets = settings.budget_buckets if budget_buckets is None else budget_buckets
    # >= 2 buckets per concept keeps the ceil() discretisation error under ~25 %
    # even when every concept is picked (matters on large real graphs).
    n_buckets = max(n_buckets, 2 * len(order))

    candidates: dict[NodeId, tuple[NodeId, ...]] = {}
    for c in order:
        pool = [r for r in kg.resources_for(c) if r in costs]
        locked = [r for r in pool if r in tc.lock]
        pool = locked or pool
        pool = [r for r in pool if r not in tc.ban]
        if not pool:
            raise InfeasibleError(f"concept {c!r} has no resource left after constraints")
        candidates[c] = tuple(pool)

    return PlanContext(
        order, candidates, costs, max(state.time_budget_s, 1.0) / n_buckets, n_buckets, sub
    )


# --------------------------------------------------------------------------- #
# single-objective  -  provably optimal
# --------------------------------------------------------------------------- #
def solve_optimal(
    kg: KnowledgeGraph,
    goals: list[NodeId],
    state: LearnerState,
    costs: dict[NodeId, CostVector],
    weights: Weights | None = None,
    *,
    budget_buckets: int | None = None,
    constraints: TeacherConstraints | None = None,
) -> Plan:
    """Globally optimal feasible plan for the scalarised objective ``weights . cost``.

    ``O(V * R * B)`` time / ``O(V * B)`` space  (``O(V * R)`` when the budget is slack).
    """
    w = settings.weights if weights is None else weights
    try:
        ctx = build_plan_context(
            kg, goals, state, costs, budget_buckets=budget_buckets, constraints=constraints
        )
    except InfeasibleError as exc:
        return Plan.infeasible(str(exc))

    order = ctx.concept_order
    if not order:
        return Plan((), (), CostVector.zero(), 0.0, note="goal already satisfied")

    if ctx.budget_is_slack():
        choice, vec = _per_concept_argmin(ctx, w)
        return _assemble(ctx, kg, choice, vec)

    B = ctx.budget_buckets
    Cell = tuple[float, CostVector, tuple[NodeId, ...]]
    dp: list[Cell] = [(_INF, CostVector.zero(), ()) for _ in range(B + 1)]
    dp[0] = (0.0, CostVector.zero(), ())

    for concept in order:
        ndp: list[Cell] = [(_INF, CostVector.zero(), ()) for _ in range(B + 1)]
        for used in range(B + 1):
            base_cost, base_vec, base_choice = dp[used]
            if base_cost == _INF:
                continue
            for r in ctx.candidates[concept]:
                nb = used + ctx.buckets_for(r)
                if nb > B:  # feasibility checked *inside* the transition
                    continue
                cv = costs[r]
                cand = base_cost + cv.scalarise(w)
                if cand < ndp[nb][0]:
                    ndp[nb] = (cand, base_vec + cv, (*base_choice, r))
        dp = ndp

    best = min(range(B + 1), key=lambda i: dp[i][0])
    if dp[best][0] == _INF:
        return Plan.infeasible("no resource selection fits the time budget")
    _, vec, choice = dp[best]
    return _assemble(ctx, kg, choice, vec)


# --------------------------------------------------------------------------- #
# multi-objective  -  the Pareto front
# --------------------------------------------------------------------------- #
def solve_pareto(
    kg: KnowledgeGraph,
    goals: list[NodeId],
    state: LearnerState,
    costs: dict[NodeId, CostVector],
    *,
    budget_buckets: int | None = None,
    eps: float | None = None,
    constraints: TeacherConstraints | None = None,
) -> list[Plan]:
    """The set of non-dominated feasible plans.  Returns ``[]`` if infeasible."""
    e = settings.pareto_epsilon if eps is None else eps
    try:
        ctx = build_plan_context(
            kg, goals, state, costs, budget_buckets=budget_buckets, constraints=constraints
        )
    except InfeasibleError:
        return []

    order = ctx.concept_order
    if not order:
        return [Plan((), (), CostVector.zero(), 0.0, note="goal already satisfied")]

    slots = 1 if ctx.budget_is_slack() else ctx.budget_buckets + 1
    Entry = tuple[CostVector, tuple[NodeId, ...]]
    dp: list[list[Entry]] = [[] for _ in range(slots)]
    dp[0] = [(CostVector.zero(), ())]

    for concept in order:
        ndp: list[list[Entry]] = [[] for _ in range(slots)]
        for used in range(slots):
            for vec, choice in dp[used]:
                for r in ctx.candidates[concept]:
                    nb = 0 if slots == 1 else used + ctx.buckets_for(r)
                    if nb >= slots:
                        continue
                    ndp[nb].append((vec + costs[r], (*choice, r)))
        dp = [_prune(bucket, e) for bucket in ndp]

    pool = [entry for bucket in dp for entry in bucket]
    if not pool:
        return []
    front = {tuple(v) for v in non_dominated([vec for vec, _ in pool])}
    seen: set[tuple[float, ...]] = set()
    plans: list[Plan] = []
    for vec, choice in pool:
        key = tuple(float(x) for x in vec)
        if key in front and key not in seen:
            seen.add(key)
            plans.append(_assemble(ctx, kg, choice, vec))
    plans.sort(key=lambda p: p.objective.seconds)
    return plans


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _per_concept_argmin(
    ctx: PlanContext, weights: Weights
) -> tuple[tuple[NodeId, ...], CostVector]:
    choice: list[NodeId] = []
    vec = CostVector.zero()
    for c in ctx.concept_order:
        r = min(ctx.candidates[c], key=lambda x: ctx.costs[x].scalarise(weights))
        choice.append(r)
        vec = vec + ctx.costs[r]
    return tuple(choice), vec


_Entry = tuple[CostVector, tuple[NodeId, ...]]


def _prune(entries: list[_Entry], eps: float) -> list[_Entry]:
    if len(entries) <= 1:
        return entries
    keep = {tuple(v) for v in epsilon_prune([vec for vec, _ in entries], eps)}
    out: list[_Entry] = []
    seen: set[tuple[float, ...]] = set()
    for vec, choice in entries:
        key = tuple(float(x) for x in vec)
        if key in keep and key not in seen:
            seen.add(key)
            out.append((vec, choice))
    return out


def _assemble(
    ctx: PlanContext,
    kg: KnowledgeGraph,
    choice: tuple[NodeId, ...],
    objective: CostVector,
) -> Plan:
    ordered = _order_for_smoothness(kg, ctx.relevant_dag, list(zip(ctx.concept_order, choice)))
    steps = tuple(r for _, r in ordered)
    concepts = tuple(c for c, _ in ordered)
    total = sum(kg.resources[r].seconds for r in steps)
    return Plan(steps, concepts, objective, total, feasible=True)


def _order_for_smoothness(
    kg: KnowledgeGraph,
    dag: nx.DiGraph,
    pairs: list[tuple[NodeId, NodeId]],
    prev_difficulty: float = 1.0,
) -> list[tuple[NodeId, NodeId]]:
    """A topological order of the chosen concepts (w.r.t. the *constraint-augmented*
    prerequisite DAG) that greedily minimises the difficulty jump between
    consecutive steps.  HEURISTIC layer - not part of the optimality proof.
    ``O(k^2)``.
    """
    sub = dag.subgraph(c for c, _ in pairs).copy()
    res_for = dict(pairs)
    indeg = {c: sub.in_degree(c) for c in sub.nodes}
    ready = sorted(c for c, d in indeg.items() if d == 0)
    out: list[tuple[NodeId, NodeId]] = []
    last = prev_difficulty
    while ready:
        pick = min(ready, key=lambda c: (abs(kg.resources[res_for[c]].difficulty - last), c))
        ready.remove(pick)
        out.append((pick, res_for[pick]))
        last = kg.resources[res_for[pick]].difficulty
        for succ in sorted(sub.successors(pick)):
            indeg[succ] -= 1
            if indeg[succ] == 0:
                ready.append(succ)
        ready.sort()
    return out
