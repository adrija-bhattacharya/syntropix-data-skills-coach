"""Every plan any solver returns must pass an independent feasibility check."""

from __future__ import annotations

import numpy as np
from _helpers import assert_feasible, random_curriculum
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from velpo.algorithms.astar import solve_astar
from velpo.algorithms.dynamic_programming import solve_optimal, solve_pareto
from velpo.model.cost import build_cost_vectors
from velpo.model.knowledge_graph import KnowledgeGraph
from velpo.model.learner import LearnerState


def test_curriculum_plans_feasible(kg: KnowledgeGraph) -> None:
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=9000)
    costs = build_cost_vectors(kg, state)
    goals = ["quadratics", "word_problems"]
    assert_feasible(
        kg,
        solve_optimal(kg, goals, state, costs, budget_buckets=40),
        state,
        goals,
        budget_buckets=40,
    )
    a = solve_astar(kg, goals, state, costs, budget_buckets=40)
    assert_feasible(kg, a, state, goals, budget_buckets=40)
    for p in solve_pareto(kg, goals, state, costs, budget_buckets=40):
        assert_feasible(kg, p, state, goals, budget_buckets=40)


@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
@given(seed=st.integers(0, 50_000), n=st.integers(3, 8), scale=st.floats(0.4, 2.2))
def test_random_plans_feasible(seed: int, n: int, scale: float) -> None:
    rng = np.random.default_rng(seed)
    kg = random_curriculum(rng, n=n)
    goals = [kg.concept_ids[-1]]
    min_s = sum(min(kg.resources[r].seconds for r in kg.resources_for(c)) for c in kg.concept_ids)
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=max(600.0, min_s * scale))
    costs = build_cost_vectors(kg, state)
    bb = 24

    p = solve_optimal(kg, goals, state, costs, budget_buckets=bb)
    if p.feasible:
        assert_feasible(kg, p, state, goals, budget_buckets=bb)
    for q in solve_pareto(kg, goals, state, costs, budget_buckets=bb):
        assert q.feasible
        assert_feasible(kg, q, state, goals, budget_buckets=bb)


@settings(max_examples=60, deadline=None)
@given(seed=st.integers(0, 10_000))
def test_infeasible_when_budget_tiny(seed: int) -> None:
    rng = np.random.default_rng(seed)
    kg = random_curriculum(rng, n=6)
    goals = [kg.concept_ids[-1]]
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=1.0)
    costs = build_cost_vectors(kg, state)
    assert not solve_optimal(kg, goals, state, costs, budget_buckets=20).feasible
    assert solve_pareto(kg, goals, state, costs, budget_buckets=20) == []
