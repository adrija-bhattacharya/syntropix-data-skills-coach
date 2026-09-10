"""Claim C - deadline-aware calendar scheduling.

The ordered plan from the sequencing DP is embedded on a real calendar so that
every goal skill is predicted at/above the mastery threshold **on the deadline**,
accounting for forgetting between study slots - or a precise diagnostic is
returned instead.
"""

from __future__ import annotations

import itertools
from datetime import date, timedelta

import pytest

from algorithms.scheduling import (
    Availability,
    _max_gap_days,
    build_slots,
    schedule_on_calendar,
)
from config import settings
from curriculum import build_curriculum
from engine import Engine
from model.knowledge_graph import Concept, KnowledgeGraph, Resource
from model.learner import LearnerState

_START = date(2026, 1, 5)  # a Monday


def _chain(n: int = 4) -> KnowledgeGraph:
    ids = [f"c{i}" for i in range(n)]
    concepts = [Concept(c, c.upper()) for c in ids]
    prereqs = [(ids[i], ids[i + 1]) for i in range(n - 1)]
    resources = [Resource(f"{c}:r", (c,), 2.0, 20.0, "lesson") for c in ids]
    return KnowledgeGraph.build(concepts, prereqs, resources)


def _plan(kg: KnowledgeGraph, goals: list[str], budget_min: float = 4000.0):
    eng = Engine(kg)
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=budget_min * 60)
    plans = eng.recommend("u", goals, time_budget_s=budget_min * 60, mode="sequence")
    return plans[0], state


# --------------------------------------------------------------------------- #
# the slot calendar
# --------------------------------------------------------------------------- #
def test_build_slots_respects_weekday_availability() -> None:
    avail = Availability.weekdays(60.0)  # Mon-Fri only
    slots = build_slots(_START, _START + timedelta(days=13), avail)  # two weeks
    assert len(slots) == 10  # 5 weekdays x 2
    assert all(s.day.weekday() < 5 for s in slots)
    assert all(s.capacity_min == 60.0 for s in slots)


def test_max_gap_grows_geometrically_with_each_review() -> None:
    g = [_max_gap_days(k, 1.0) for k in range(4)]
    assert g[0] == pytest.approx(settings.calendar_base_retention_days)
    for a, b in itertools.pairwise(g):
        assert b == pytest.approx(a * settings.calendar_spacing_factor)


# --------------------------------------------------------------------------- #
# a feasible schedule
# --------------------------------------------------------------------------- #
def test_feasible_schedule_meets_the_threshold_on_the_deadline() -> None:
    kg = _chain(4)
    plan, state = _plan(kg, ["c3"])
    deadline = _START + timedelta(days=56)
    cp = schedule_on_calendar(
        kg,
        plan,
        state,
        ["c3"],
        start=_START,
        deadline=deadline,
        availability=Availability.weekdays(40.0),
    )
    assert cp.feasible, cp.note
    assert cp.finish is not None and cp.finish <= deadline
    assert cp.slack_days >= 0
    assert cp.goal_mastery["c3"] >= settings.mastery_threshold


def test_precedence_is_preserved_in_time() -> None:
    kg = _chain(5)
    plan, state = _plan(kg, ["c4"])
    cp = schedule_on_calendar(
        kg,
        plan,
        state,
        ["c4"],
        start=_START,
        deadline=_START + timedelta(days=70),
        availability=Availability.weekdays(35.0),
    )
    assert cp.feasible, cp.note
    taught_day = {s.concept: s.day for s in cp.steps if s.kind == "teach"}
    for c in ("c1", "c2", "c3", "c4"):
        assert taught_day[c] >= taught_day[f"c{int(c[1]) - 1}"]


def test_no_slot_is_overbooked() -> None:
    kg = _chain(4)
    plan, state = _plan(kg, ["c3"])
    avail = Availability.weekdays(45.0)
    cp = schedule_on_calendar(
        kg,
        plan,
        state,
        ["c3"],
        start=_START,
        deadline=_START + timedelta(days=60),
        availability=avail,
    )
    assert cp.feasible, cp.note
    per_day: dict[date, float] = {}
    for s in cp.steps:
        per_day[s.day] = per_day.get(s.day, 0.0) + s.minutes
    assert all(v <= 45.0 + 1e-6 for v in per_day.values())


def test_a_later_deadline_needs_no_more_reviews_than_a_nearer_one() -> None:
    kg = _chain(3)
    plan, state = _plan(kg, ["c2"])
    near = schedule_on_calendar(
        kg,
        plan,
        state,
        ["c2"],
        start=_START,
        deadline=_START + timedelta(days=30),
        availability=Availability.weekdays(40.0),
    )
    far = schedule_on_calendar(
        kg,
        plan,
        state,
        ["c2"],
        start=_START,
        deadline=_START + timedelta(days=120),
        availability=Availability.weekdays(40.0),
    )
    assert near.feasible and far.feasible
    # a nearer deadline is covered by fewer (or equal) retention reviews per skill
    assert near.n_retention <= far.n_retention


# --------------------------------------------------------------------------- #
# diagnostics
# --------------------------------------------------------------------------- #
def test_past_deadline_is_infeasible() -> None:
    kg = _chain(3)
    plan, state = _plan(kg, ["c2"])
    cp = schedule_on_calendar(
        kg,
        plan,
        state,
        ["c2"],
        start=_START,
        deadline=_START - timedelta(days=1),
        availability=Availability.weekdays(60.0),
    )
    assert not cp.feasible
    assert "future" in cp.note


def test_too_little_time_reports_the_hours_per_week_gap() -> None:
    kg = _chain(8)
    plan, state = _plan(kg, ["c7"])
    cp = schedule_on_calendar(
        kg,
        plan,
        state,
        ["c7"],
        start=_START,
        deadline=_START + timedelta(days=7),
        availability=Availability.weekdays(10.0),
    )
    assert not cp.feasible
    assert cp.hours_per_week_needed > cp.hours_per_week
    assert cp.hours_per_week == pytest.approx(50.0 / 60.0, abs=0.1)


# --------------------------------------------------------------------------- #
# integration through the engine + a real curriculum
# --------------------------------------------------------------------------- #
def test_engine_calendar_plan_on_the_curriculum() -> None:
    kg = build_curriculum()
    eng = Engine(kg)
    goal = kg.sink_concepts()[:1]
    cp = eng.calendar_plan(
        "learner",
        goal,
        deadline=date.today() + timedelta(days=45),
        availability=Availability.weekdays(45.0),
        start=date.today(),
    )
    assert cp.feasible, cp.note
    assert all(m >= settings.mastery_threshold for m in cp.goal_mastery.values())
    assert cp.reasons and "threshold" in cp.reasons[0]
    # deterministic
    cp2 = eng.calendar_plan(
        "learner2",
        goal,
        deadline=date.today() + timedelta(days=45),
        availability=Availability.weekdays(45.0),
        start=date.today(),
    )
    assert [s.day for s in cp.steps] == [s.day for s in cp2.steps]
