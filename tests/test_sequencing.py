"""The sequencing DP: provably optimal linear extension, spaced review, sessions."""

from __future__ import annotations

import itertools
import math

import networkx as nx
import numpy as np
import pytest
from _helpers import random_curriculum

from algorithms.graph_traversal import ancestors_subgraph, topological_order
from algorithms.sequencing import (
    _levels,
    insert_reviews,
    pack_sessions,
    plan_sequence,
    solve_sequence,
)
from config import settings
from curriculum import build_curriculum
from engine import Engine
from model.cost import sequence_step_cost
from model.knowledge_graph import Concept, KnowledgeGraph, Resource
from model.learner import Attempt, LearnerState

_W = settings.weights
_BIG = 1_000_000.0


def _brute_min_cost(kg: KnowledgeGraph, goals: list[str], state: LearnerState, hl: float) -> float:
    """Exhaustive minimum over every linear extension x every resource choice,
    scored with the *same* position-aware cost the DP uses."""
    dag = ancestors_subgraph(kg.prereq, goals)
    order = topological_order(dag)
    level = _levels(dag, order)
    exts = list(nx.all_topological_sorts(dag))
    best = math.inf
    for ext in exts:
        for combo in itertools.product(*(kg.resources_for(c) for c in ext)):
            prev_d = 1.0
            total = 0.0
            for i, (c, r) in enumerate(zip(ext, combo)):
                cv = sequence_step_cost(
                    kg,
                    c,
                    r,
                    state,
                    position=i,
                    taught_at=level,
                    prev_difficulty=prev_d,
                    half_life_steps=hl,
                )
                total += cv.scalarise(_W)
                prev_d = kg.resources[r].difficulty
            best = min(best, total)
    return best


@pytest.mark.parametrize("seed", range(30))
def test_sequence_dp_matches_exhaustive_search(seed: int) -> None:
    rng = np.random.default_rng(seed)
    kg = random_curriculum(rng, n=int(rng.integers(4, 7)))
    goal = kg.concept_ids[-1]
    dag = ancestors_subgraph(kg.prereq, [goal])
    if sum(1 for _ in nx.all_topological_sorts(dag)) > 400:
        pytest.skip("too many linear extensions to brute-force")
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=_BIG)
    hl = settings.seq_half_life_steps

    plan = solve_sequence(kg, [goal], state, budget_seconds=_BIG)
    assert plan.feasible
    assert plan.objective.scalarise(_W) == pytest.approx(_brute_min_cost(kg, [goal], state, hl))


def test_sequence_is_a_valid_linear_extension() -> None:
    kg = build_curriculum()
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=_BIG)
    plan = solve_sequence(kg, ["quadratics", "word_problems"], state, budget_seconds=_BIG)
    assert plan.feasible
    taught: set[str] = set()
    for s in plan.steps:
        assert not s.review
        for req in kg.direct_prerequisites(s.concept):
            assert req in taught, f"{s.concept} taught before prerequisite {req}"
        taught.add(s.concept)
    relevant = set(
        topological_order(ancestors_subgraph(kg.prereq, ["quadratics", "word_problems"]))
    )
    assert {s.concept for s in plan.steps} == relevant


def test_faster_learner_gets_a_leaner_sequence() -> None:
    kg = build_curriculum()
    slow = LearnerState.cold_start(kg.concept_ids, time_budget_s=6000)
    slow.velocity.update(dict.fromkeys(slow.velocity, 0.4))
    fast = slow.copy()
    fast.velocity.update(dict.fromkeys(fast.velocity, 3.0))
    ps = solve_sequence(kg, ["quadratics"], slow, budget_seconds=6000)
    pf = solve_sequence(kg, ["quadratics"], fast, budget_seconds=6000)
    assert ps.feasible and pf.feasible
    # the fast learner extracts more mastery from the same steps
    assert -pf.objective.neg_gain > -ps.objective.neg_gain


def test_over_tight_budget_is_infeasible() -> None:
    kg = build_curriculum()
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=120)  # ~2 min
    plan = plan_sequence(kg, ["word_problems"], state, budget_seconds=120)
    assert not plan.feasible


def _wide_curriculum(n_sources: int) -> KnowledgeGraph:
    """``n_sources`` incomparable concepts all feeding one sink -> poset width
    ``n_sources``; the order-ideal count is ``~3 * 2 ** (n_sources - 1)``."""
    ids = [f"a{i}" for i in range(n_sources)] + ["sink"]
    concepts = [Concept(c, c.upper()) for c in ids]
    prereqs = [(f"a{i}", "sink") for i in range(n_sources)]
    resources = [
        Resource(f"{c}:{k}", (c,), 1.0 + k, 5.0 + 2 * k, "lesson" if k == 0 else "practice")
        for c in ids
        for k in range(2)
    ]
    return KnowledgeGraph.build(concepts, prereqs, resources)


def test_direct_call_reports_the_fallback() -> None:
    kg = build_curriculum()
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=_BIG)
    direct = solve_sequence(kg, ["word_problems"], state, budget_seconds=_BIG, max_ideals=2)
    assert not direct.feasible and "fallback" in direct.note


def test_too_wide_poset_falls_back_via_the_engine() -> None:
    kg = _wide_curriculum(16)  # ~3 * 2**15 order ideals, far above the cap
    plan = Engine(kg).recommend("u", ["sink"], time_budget_s=_BIG, mode="sequence")[0]
    assert plan.feasible  # engine transparently used the knapsack
    assert "fallback" in plan.note
    assert set(plan.concepts) == {f"a{i}" for i in range(16)} | {"sink"}


# --------------------------------------------------------------------------- #
# stage 2 - spaced review
# --------------------------------------------------------------------------- #
def test_review_inserted_when_a_prerequisite_decays() -> None:
    kg = build_curriculum()
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=_BIG)
    base = solve_sequence(
        kg, ["graphing", "quadratics", "word_problems"], state, budget_seconds=_BIG
    )
    reviewed = insert_reviews(kg, base, state, ["graphing", "quadratics", "word_problems"])

    n_rev = sum(s.review for s in reviewed.steps)
    assert 1 <= n_rev <= settings.max_reviews
    seen: set[str] = set()
    for s in reviewed.steps:
        if s.review:
            assert s.concept in seen  # you can only review something already taught
        seen.add(s.concept)


def test_no_review_when_nothing_decays() -> None:
    kg = build_curriculum()
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=_BIG)
    base = solve_sequence(kg, ["fractions"], state, budget_seconds=_BIG)  # 2 steps, no decay
    assert insert_reviews(kg, base, state, ["fractions"]).steps == base.steps


# --------------------------------------------------------------------------- #
# stage 3 - session packing
# --------------------------------------------------------------------------- #
def test_sessions_are_contiguous_and_within_caps() -> None:
    kg = build_curriculum()
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=_BIG)
    plan = plan_sequence(kg, ["quadratics", "word_problems"], state, budget_seconds=_BIG)
    assert plan.sessions
    # cover every step exactly once, in order
    flat = [i for a, b in plan.sessions for i in range(a, b)]
    assert flat == list(range(len(plan.steps)))
    for a, b in plan.sessions:
        mins = sum(kg.resources[plan.steps[i].resource_id].minutes for i in range(a, b))
        assert b - a == 1 or mins <= settings.session_minutes + 1e-6


def test_session_packing_is_minimal() -> None:
    kg = build_curriculum()
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=_BIG)
    plan = solve_sequence(kg, ["word_problems"], state, budget_seconds=_BIG)
    packed = pack_sessions(kg, plan, session_minutes=25, session_max_load=99)
    # a hand check: greedy from the left can't do better than the DP
    greedy = 0
    acc = 0.0
    for s in plan.steps:
        m = kg.resources[s.resource_id].minutes
        if acc + m > 25 and acc > 0:
            greedy += 1
            acc = 0.0
        acc += m
    greedy += 1
    assert len(packed.sessions) <= greedy


def test_engine_sequence_mode_end_to_end() -> None:
    kg = build_curriculum()
    eng = Engine(kg)
    [plan] = eng.recommend("u", ["quadratics"], time_budget_s=7000, mode="sequence")
    assert plan.feasible and plan.sessions
    assert plan.reasons and plan.reasons[0].endswith(".")
    eng.observe("u", Attempt("integers:lesson", correct=True, seconds=300))
    [plan2] = eng.recommend("u", ["quadratics"], time_budget_s=7000, mode="sequence")
    assert plan2.feasible
