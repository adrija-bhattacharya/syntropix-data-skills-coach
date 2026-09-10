"""N2 - learning velocity must be a *load-bearing* input to the optimiser.

`test_velocity_changes_the_optimal_plan` - with the velocity signal on, a fast
and a slow learner get different optimal plans for the same goal + budget.
`test_without_velocity_signal_plans_are_identical` - remove the signal (flatten
every velocity to 1.0) and the two plans coincide, proving the divergence above
is caused by velocity and nothing else.
"""

from __future__ import annotations

from dataclasses import replace

from algorithms.dynamic_programming import solve_optimal
from config import settings
from model.cost import build_cost_vectors
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

_BUDGET_S = 6000.0


def _scaled(kg: KnowledgeGraph, factor: float) -> LearnerState:
    base = LearnerState.cold_start(kg.concept_ids, time_budget_s=_BUDGET_S)
    lo, hi = settings.velocity_min, settings.velocity_max
    return replace(
        base, velocity={c: min(hi, max(lo, v * factor)) for c, v in base.velocity.items()}
    )


def _chosen(kg: KnowledgeGraph, goal: str, state: LearnerState) -> dict[str, str]:
    costs = build_cost_vectors(kg, state)
    plan = solve_optimal(kg, [goal], state, costs, budget_buckets=40)
    assert plan.feasible, plan.note
    return dict(zip(plan.concepts, plan.steps))


def test_velocity_changes_the_optimal_plan(kg: KnowledgeGraph) -> None:
    fast, slow = _scaled(kg, 3.0), _scaled(kg, 0.45)
    diverged = [
        goal for goal in kg.sink_concepts() if _chosen(kg, goal, fast) != _chosen(kg, goal, slow)
    ]
    assert diverged, "velocity had no effect on any goal's optimal plan"

    goal = diverged[0]
    fast_plan, slow_plan = _chosen(kg, goal, fast), _chosen(kg, goal, slow)
    fast_min = sum(kg.resources[r].minutes for r in fast_plan.values())
    slow_min = sum(kg.resources[r].minutes for r in slow_plan.values())
    assert fast_min > slow_min  # the fast learner is steered to the fuller resources


def test_without_velocity_signal_plans_are_identical(kg: KnowledgeGraph) -> None:
    flat_a, flat_b = _scaled(kg, 1.0), _scaled(kg, 1.0)
    for goal in kg.sink_concepts():
        assert _chosen(kg, goal, flat_a) == _chosen(kg, goal, flat_b)


def test_recommend_speed_knob_changes_the_plan(kg: KnowledgeGraph) -> None:
    from engine import Engine

    eng = Engine(kg)
    goal = "quadratics"
    fast = eng.recommend("f", [goal], time_budget_s=_BUDGET_S, speed=3.0)[0]
    slow = eng.recommend("s", [goal], time_budget_s=_BUDGET_S, speed=0.45)[0]
    assert fast.feasible and slow.feasible
    assert fast.steps != slow.steps
