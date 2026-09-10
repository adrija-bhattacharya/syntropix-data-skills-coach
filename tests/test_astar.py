from __future__ import annotations

import numpy as np
import pytest
from _helpers import random_curriculum
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from algorithms.astar import solve_astar
from algorithms.dynamic_programming import build_plan_context, solve_optimal
from model.cost import build_cost_vectors
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

WEIGHTS = [(1.0, 0.0, 0.0, 0.0, 0.0), (5.0, 6e-4, 0.4, 0.25, 0.7), (0.0, 1.0, 0.0, 0.0, 0.0)]


def test_astar_equals_dp_on_curriculum(kg: KnowledgeGraph) -> None:
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=9000)
    costs = build_cost_vectors(kg, state)
    for w in WEIGHTS:
        dp = solve_optimal(kg, ["quadratics"], state, costs, w, budget_buckets=40)
        a = solve_astar(kg, ["quadratics"], state, costs, w, budget_buckets=40)
        assert a.feasible
        assert a.objective.scalarise(w) == pytest.approx(dp.objective.scalarise(w))


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
@given(
    seed=st.integers(0, 20_000),
    n=st.integers(3, 8),
    wi=st.integers(0, 2),
    scale=st.floats(0.5, 1.9),
)
def test_astar_equals_dp_random(seed: int, n: int, wi: int, scale: float) -> None:
    rng = np.random.default_rng(seed)
    kg = random_curriculum(rng, n=n)
    w = WEIGHTS[wi]
    goals = [kg.concept_ids[-1]]
    min_s = sum(min(kg.resources[r].seconds for r in kg.resources_for(c)) for c in kg.concept_ids)
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=max(600.0, min_s * scale))
    costs = build_cost_vectors(kg, state)
    dp = solve_optimal(kg, goals, state, costs, w, budget_buckets=24)
    a = solve_astar(kg, goals, state, costs, w, budget_buckets=24)
    assert a.feasible == dp.feasible
    if dp.feasible:
        assert a.objective.scalarise(w) == pytest.approx(dp.objective.scalarise(w), rel=1e-9)


def test_astar_expands_fewer_states_than_dp_table() -> None:
    ratios = []
    for seed in range(30):
        rng = np.random.default_rng(seed)
        kg = random_curriculum(rng, n=7)
        goals = [kg.concept_ids[-1]]
        # tight-ish budget so the DP path (not the slack fast path) is used
        min_s = sum(
            min(kg.resources[r].seconds for r in kg.resources_for(c)) for c in kg.concept_ids
        )
        state = LearnerState.cold_start(kg.concept_ids, time_budget_s=min_s * 0.9)
        costs = build_cost_vectors(kg, state)
        ctx = build_plan_context(kg, goals, state, costs, budget_buckets=24)
        res = solve_astar(kg, goals, state, costs, budget_buckets=24, return_stats=True)
        _, stats = res  # type: ignore[misc]
        cells = (len(ctx.concept_order) + 1) * (ctx.budget_buckets + 1)
        ratios.append(stats.expanded / cells)
    assert np.mean(ratios) < 1.0
