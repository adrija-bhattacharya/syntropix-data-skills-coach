"""Claim B - risk-aware planning.

The adaptive test returns a point mastery *and* a standard error.  The planner
acts on the pessimistic edge of that estimate (:meth:`LearnerState.effective_mastery`)
and, for a pivotal prerequisite the test left uncertain, splices a short
confidence check before the concepts that build on it
(:func:`algorithms.sequencing.insert_checks`).

Two learners with the *same* point mastery for the pivot but different
measurement uncertainty must get different plans - that is the observable,
novel behaviour.
"""

from __future__ import annotations

import dataclasses
import math

import algorithms.sequencing as seqmod
import config
import model.learner as learnermod
from algorithms.sequencing import plan_sequence
from config import settings
from model.knowledge_graph import Concept, KnowledgeGraph, Resource
from model.learner import LearnerState, _logit, _sigmoid


def _diamond() -> KnowledgeGraph:
    """``root`` gates three otherwise-independent concepts (out-degree 3)."""
    ids = ["root", "b", "c", "d"]
    concepts = [Concept(i, i.upper()) for i in ids]
    prereqs = [("root", "b"), ("root", "c"), ("root", "d")]
    resources = [
        Resource(f"{i}:{k}", (i,), 1.0 + k, 6.0 + 3 * k, "lesson" if k == 0 else "practice")
        for i in ids
        for k in range(2)
    ]
    return KnowledgeGraph.build(concepts, prereqs, resources)


def _state(se_root: float | None) -> LearnerState:
    kg_ids = ["root", "b", "c", "d"]
    st = LearnerState.cold_start(kg_ids, time_budget_s=1_000_000.0)
    st.mastery["root"] = 0.80  # comfortably above the 0.75 threshold as a point estimate
    if se_root is not None:
        st.mastery_se["root"] = se_root
    return st


# --------------------------------------------------------------------------- #
# the learner-model primitives
# --------------------------------------------------------------------------- #
def test_effective_mastery_is_pessimistic_only_when_measured() -> None:
    unmeasured = _state(None)
    measured = _state(1.2)
    # no SE -> the planner acts on the point estimate unchanged
    assert unmeasured.effective_mastery("root") == unmeasured.decayed_mastery("root")
    # wide SE -> pulled down by kappa * SE on the logit scale
    expected = _sigmoid(_logit(measured.decayed_mastery("root")) - settings.risk_kappa * 1.2)
    assert math.isclose(measured.effective_mastery("root"), expected, rel_tol=1e-9)
    assert measured.effective_mastery("root") < measured.decayed_mastery("root")


def test_confidence_falls_as_the_standard_error_grows() -> None:
    tight = _state(0.15).confidence("root")
    wide = _state(1.3).confidence("root")
    assert 0.0 < wide < tight <= 1.0
    # a skill the test never touched is reported as certain (point estimate clears)
    assert _state(None).confidence("root") == 1.0


# --------------------------------------------------------------------------- #
# the plan-level behaviour
# --------------------------------------------------------------------------- #
def test_uncertain_pivot_gets_a_confidence_check_a_confident_one_does_not() -> None:
    kg = _diamond()
    goals = ["b", "c", "d"]

    confident = plan_sequence(kg, goals, _state(0.15), budget_seconds=1_000_000.0)
    uncertain = plan_sequence(kg, goals, _state(1.3), budget_seconds=1_000_000.0)
    baseline = plan_sequence(kg, goals, _state(None), budget_seconds=1_000_000.0)

    def checks_on(plan: object, concept: str) -> int:
        return sum(1 for s in plan.steps if s.check and s.concept == concept)  # type: ignore[attr-defined]

    assert checks_on(uncertain, "root") == 1
    assert checks_on(confident, "root") == 0
    assert checks_on(baseline, "root") == 0

    # the check is spliced immediately after root is first taught, never before it
    steps = list(uncertain.steps)
    taught = next(i for i, s in enumerate(steps) if s.concept == "root" and not s.check)
    checked = next(i for i, s in enumerate(steps) if s.concept == "root" and s.check)
    assert checked == taught + 1


def test_check_step_still_produces_a_prerequisite_valid_sequence() -> None:
    kg = _diamond()
    plan = plan_sequence(kg, ["b", "c", "d"], _state(1.3), budget_seconds=1_000_000.0)
    seen: set[str] = set()
    for s in plan.steps:
        if not (s.review or s.check):
            for q in kg.direct_prerequisites(s.concept):
                assert q in seen, f"{s.concept} taught before prerequisite {q}"
            seen.add(s.concept)
    assert {"root", "b", "c", "d"} <= seen


def test_risk_kappa_zero_disables_the_whole_mechanism(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    off = dataclasses.replace(settings, risk_kappa=0.0)
    for mod in (config, seqmod, learnermod):
        monkeypatch.setattr(mod, "settings", off)
    kg = _diamond()
    plan = plan_sequence(kg, ["b", "c", "d"], _state(1.3), budget_seconds=1_000_000.0)
    assert all(not s.check for s in plan.steps)
    assert _state(1.3).effective_mastery("root") == _state(1.3).decayed_mastery("root")
