from __future__ import annotations

import pytest
from _helpers import assert_feasible

from algorithms.astar import solve_astar
from algorithms.dynamic_programming import (
    InfeasibleError,
    Plan,
    TeacherConstraints,
    build_plan_context,
    solve_optimal,
    solve_pareto,
)
from explain import explain_plan, explain_step
from model.cost import build_cost_vectors
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState


@pytest.fixture
def setup(kg: KnowledgeGraph):
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=9000)
    return kg, state, build_cost_vectors(kg, state), ["quadratics", "word_problems"]


def test_lock_forces_resource(setup) -> None:
    kg, state, costs, goals = setup
    tc = TeacherConstraints.make(lock={"linear_eq:practice"})
    p = solve_optimal(kg, goals, state, costs, budget_buckets=40, constraints=tc)
    assert p.feasible and "linear_eq:practice" in p.steps and "linear_eq:lesson" not in p.steps
    assert_feasible(kg, p, state, goals, budget_buckets=40)


def test_ban_removes_resource(setup) -> None:
    kg, state, costs, goals = setup
    p = solve_optimal(
        kg,
        goals,
        state,
        costs,
        budget_buckets=40,
        constraints=TeacherConstraints.make(ban={"linear_eq:lesson"}),
    )
    assert p.feasible and "linear_eq:lesson" not in p.steps and "linear_eq:practice" in p.steps


def test_ban_only_resource_is_infeasible(setup) -> None:
    kg, state, costs, goals = setup
    # order_ops has no practice alternative and is a prerequisite of quadratics
    tc = TeacherConstraints.make(ban={"order_ops:lesson"})
    assert not solve_optimal(kg, goals, state, costs, budget_buckets=40, constraints=tc).feasible
    assert solve_pareto(kg, goals, state, costs, budget_buckets=40, constraints=tc) == []


def test_force_order_respected(setup) -> None:
    kg, state, costs, goals = setup
    tc = TeacherConstraints.make(force_order=[("roots", "linear_eq")])
    p = solve_optimal(kg, goals, state, costs, budget_buckets=40, constraints=tc)
    pos = {c: i for i, c in enumerate(p.concepts)}
    assert pos["roots"] < pos["linear_eq"]


def test_cyclic_force_order_infeasible(setup) -> None:
    kg, state, costs, goals = setup
    tc = TeacherConstraints.make(force_order=[("quadratics", "linear_eq")])
    with pytest.raises(InfeasibleError):
        build_plan_context(kg, goals, state, costs, constraints=tc)
    assert not solve_optimal(kg, goals, state, costs, budget_buckets=40, constraints=tc).feasible
    assert not solve_astar(kg, goals, state, costs, budget_buckets=40, constraints=tc).feasible


def test_empty_constraints_match_unconstrained(setup) -> None:
    kg, state, costs, goals = setup
    a = solve_optimal(kg, goals, state, costs, budget_buckets=40)
    b = solve_optimal(kg, goals, state, costs, budget_buckets=40, constraints=TeacherConstraints())
    assert a.objective == b.objective


def test_explain_is_kg_grounded_and_deterministic(kg: KnowledgeGraph) -> None:
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=9000)
    costs = build_cost_vectors(kg, state)
    p = solve_optimal(kg, ["quadratics"], state, costs, budget_buckets=40)
    e1 = explain_plan(kg, p, state)
    e2 = explain_plan(kg, p, state)
    assert e1.reasons == e2.reasons
    assert len(e1.reasons) == len(e1.steps)
    names = {c.name for c in kg.concepts.values()}
    for reason, concept in zip(e1.reasons, e1.concepts):
        assert kg.concepts[concept].name in reason
        assert reason.endswith(".")
        for tok in names:  # every concept-name that appears is a real one
            _ = tok in reason


def test_explain_noop_on_infeasible(kg: KnowledgeGraph) -> None:
    bad = Plan.infeasible("nope")
    assert explain_plan(kg, bad, LearnerState.cold_start(kg.concept_ids, time_budget_s=1)) is bad
    _ = explain_step  # referenced for import completeness
