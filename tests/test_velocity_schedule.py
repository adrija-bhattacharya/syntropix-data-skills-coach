"""Velocity-aware scheduling (claim G)."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import api
from algorithms.reschedule import Work, availability_windows, reschedule
from algorithms.velocity_schedule import (
    M_INIT,
    PRIOR_WEIGHT,
    RATIO_BOUNDS,
    TARGET,
    capacity,
    forecast,
    predicted_velocity,
    size_work,
    time_ratio,
    time_to_mastery,
)
from model.cost import expected_mastery_gain

MON = date(2026, 1, 5)


def test_time_to_mastery_inverts_the_planners_learning_curve() -> None:
    for m0, v in [(0.1, 1.0), (0.4, 2.0), (0.05, 0.5)]:
        h = time_to_mastery(m0, v)
        assert m0 + expected_mastery_gain(m0, v, h * 3600) == pytest.approx(TARGET)
    assert time_to_mastery(0.9, 1.0) == 0.0  # already there
    assert time_to_mastery(0.1, 2.0) == pytest.approx(time_to_mastery(0.1, 1.0) / 2)


def test_time_ratio_is_relative_to_a_typical_beginner_and_bounded() -> None:
    assert time_ratio(M_INIT, 1.0) == pytest.approx(1.0)
    assert time_ratio(M_INIT, 0.5) == pytest.approx(2.0)
    assert time_ratio(M_INIT, 0.01) == RATIO_BOUNDS[1]
    assert time_ratio(0.74, 1.0) < 0.5 and time_ratio(0.9, 1.0) == RATIO_BOUNDS[0]


def test_unseen_topics_borrow_speed_from_what_they_build_on() -> None:
    pre = {"a": [], "b": ["a"], "c": ["b"], "d": []}
    vel = {"a": 2.0, "d": 0.5}
    v = predicted_velocity(list(pre), pre, vel, {"a", "d"})
    mean = 1.25
    assert v["a"] == 2.0 and v["d"] == 0.5  # measured: kept
    assert v["b"] == pytest.approx((2.0 + PRIOR_WEIGHT * mean) / (1 + PRIOR_WEIGHT))  # shrunk
    assert v["c"] == pytest.approx(v["b"])  # walks up to the nearest measured ancestor
    assert predicted_velocity(["x"], {"x": []}, {}, set())["x"] == 1.0  # a brand-new learner


def test_size_work_scales_teaching_but_not_reviews() -> None:
    out = size_work([("a", 60, "teach"), ("a", 10, "review")], {"a": M_INIT}, {"a": 0.5})
    assert out[0].minutes == pytest.approx(120) and out[1].minutes == 10


def test_forecast_is_ordered_and_responds_to_adherence() -> None:
    cap = capacity(MON, MON + timedelta(days=120), windows=availability_windows(), weekly_cap=300)
    kw = {"observed_concepts": 0, "samples": 300}
    good = forecast([60] * 20, [1.0] * 20, cap, MON + timedelta(days=40),
                    adherence_rates=[1.0] * 10, **kw)  # fmt: skip
    poor = forecast([60] * 20, [1.0] * 20, cap, MON + timedelta(days=40),
                    adherence_rates=[0.35] * 10, **kw)  # fmt: skip
    assert good.p50 and good.p80 and good.p95 and good.p50 <= good.p80 <= good.p95
    assert poor.p50 and poor.p50 > good.p50 and poor.p_on_time < good.p_on_time


def test_forecast_spread_narrows_with_practice() -> None:
    cap = capacity(MON, MON + timedelta(days=200), windows=availability_windows(), weekly_cap=300)

    def spread(n: int) -> int:
        f = forecast([60] * 20, [1.0] * 20, cap, MON + timedelta(days=60), observed_concepts=n,
                     adherence_rates=[1.0] * 30, samples=400)  # fmt: skip
        assert f.p50 and f.p95
        return (f.p95 - f.p50).days

    assert spread(15) < spread(0)


def test_matching_respects_prerequisites_and_reviews() -> None:
    work = [
        Work("w0", "a", "a", 30, hardness=0.5),
        Work("w1", "b", "b", 30, hardness=3.0),  # b needs a
        Work("w2", "c", "c", 30, hardness=2.0),
        Work("w3", "c", "c", 10, "review"),
        Work("w4", "d", "d", 30, hardness=3.0),
    ]
    anc = {"b": {"a"}, "c": set(), "a": set(), "d": set()}
    r = reschedule(work, start=MON, deadline=MON + timedelta(days=30),
                   windows=availability_windows(), match=True, ancestors=anc)  # fmt: skip
    first = [b.work_id for b in r.blocks if b.part == 1]
    assert first.index("w0") < first.index("w1")  # prerequisite first
    assert first[0] == "w2"  # light day: the hardest *ready* item jumps ahead
    assert first.index("w3") < first.index("w4")  # nothing jumps over a review


def test_api_returns_forecast_and_per_topic_speed() -> None:
    client = TestClient(api.app)
    goals = client.post("/resolve", json={"goal": "sql"}).json()["goals"]
    t = date.today()
    body = {"learner_id": "vel", "goals": goals, "goal": "sql", "hours_per_week": 5,
            "deadline": (t + timedelta(days=60)).isoformat()}  # fmt: skip
    r = client.post("/reschedule", json=body).json()
    assert r["velocity"]["aware"] and r["velocity"]["topics"]
    assert {"p50", "p80", "p95", "p_on_time"} <= set(r["forecast"])
    off = client.post("/reschedule", json={**body, "velocity_aware": False}).json()
    assert not off["velocity"]["aware"] and math.isfinite(off["forecast"]["p_on_time"])
