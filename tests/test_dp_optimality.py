"""The crux: the single-objective DP must equal exhaustive search."""

from __future__ import annotations

import numpy as np
import pytest
from _helpers import brute_force, random_curriculum
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from velpo.algorithms.dynamic_programming import solve_optimal
from velpo.model.cost import build_cost_vectors
from velpo.model.knowledge_graph import KnowledgeGraph
from velpo.model.learner import LearnerState

WEIGHTS = [
    (1.0, 0.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0, 0.0),
    (5.0, 6e-4, 0.4, 0.25, 0.7),
    (2.0, 0.0, 1.0, 0.0, 1.0),
    (0.0, 0.0, 0.0, 1.0, 0.0),
]


@pytest.mark.parametrize("w", WEIGHTS)
def test_matches_brute_force_on_curriculum(kg: KnowledgeGraph, w: tuple) -> None:
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=9000)
    costs = build_cost_vectors(kg, state)
    goals = ["quadratics", "word_problems"]
    got = solve_optimal(kg, goals, state, costs, w, budget_buckets=40)
    ref = brute_force(kg, goals, state, costs, w, budget_buckets=40)
    assert got.feasible
    assert got.objective.scalarise(w) == pytest.approx(ref, rel=1e-9)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
@given(
    seed=st.integers(0, 20_000),
    n=st.integers(3, 7),
    wi=st.integers(0, len(WEIGHTS) - 1),
    scale=st.floats(0.4, 2.0),
)
def test_matches_brute_force_random(seed: int, n: int, wi: int, scale: float) -> None:
    rng = np.random.default_rng(seed)
    kg = random_curriculum(rng, n=n)
    w = WEIGHTS[wi]
    goals = [kg.concept_ids[-1]]
    min_s = sum(min(kg.resources[r].seconds for r in kg.resources_for(c)) for c in kg.concept_ids)
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=max(600.0, min_s * scale))
    costs = build_cost_vectors(kg, state)
    bb = 24

    got = solve_optimal(kg, goals, state, costs, w, budget_buckets=bb)
    ref = brute_force(kg, goals, state, costs, w, budget_buckets=bb)
    if ref == float("inf"):
        assert not got.feasible
    else:
        assert got.feasible
        assert got.objective.scalarise(w) == pytest.approx(ref, rel=1e-9, abs=1e-9)
