"""N4 - cold-start-complete, then DKT-lite refinement (not replacement)."""

from __future__ import annotations

from curriculum import build_curriculum
from engine import Engine
from model.knowledge_graph import KnowledgeGraph
from model.learner import Attempt, LearnerState
from model.refine import MasteryRefiner


def test_pfa_tracks_the_direction_of_evidence() -> None:
    r = MasteryRefiner()
    for _ in range(8):
        r.observe("k", correct=True)
    hi = r.refined("k", bkt_mastery=0.2)
    r2 = MasteryRefiner()
    for _ in range(8):
        r2.observe("k", correct=False)
    lo = r2.refined("k", bkt_mastery=0.2)
    assert hi > 0.5 > lo


def test_refiner_is_inert_with_no_observations() -> None:
    r = MasteryRefiner()
    assert r.refined("k", bkt_mastery=0.37) == 0.37


def test_blend_weight_ramps_with_evidence() -> None:
    r = MasteryRefiner()
    r.observe("k", correct=True)
    near_bkt = r.refined("k", bkt_mastery=0.1)  # n=1, weight ~1/6
    for _ in range(10):
        r.observe("k", correct=True)
    near_pfa = r.refined("k", bkt_mastery=0.1)  # weight saturated at 1
    assert abs(near_bkt - 0.1) < abs(near_pfa - 0.1)


def test_cold_start_plan_is_valid_at_interaction_zero(kg: KnowledgeGraph) -> None:
    eng = Engine(kg)
    plan = eng.recommend("new", ["quadratics"], time_budget_s=9000)[0]
    assert plan.feasible and plan.steps
    assert eng.store.get("new").n_interactions == 0  # no history was needed


def test_refinement_changes_the_estimate_after_history() -> None:
    kg = build_curriculum()
    eng = Engine(kg)
    eng.recommend("u", ["linear_eq"], time_budget_s=9000)
    before = eng.store.get("u").decayed_mastery("integers")
    for _ in range(6):
        eng.observe("u", Attempt("integers:practice", correct=True, seconds=200))
    after = eng.store.get("u").decayed_mastery("integers")
    assert after > before  # a run of correct answers lifts the refined estimate
    assert eng.store.get("u").refiner.n_obs("integers") == 6


def test_refiner_survives_state_copy() -> None:
    s = LearnerState.cold_start(["a"], time_budget_s=100)
    s.refiner.observe("a", correct=True)
    clone = s.copy()
    clone.refiner.observe("a", correct=False)
    assert s.refiner.n_obs("a") == 1 and clone.refiner.n_obs("a") == 2
