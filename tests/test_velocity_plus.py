"""Claims G1-G5: self-checking forecasts, slowdown diagnosis, chance-constrained
goals, best study times and focus span."""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api
import telemetry
from algorithms.calibration import calibrate
from algorithms.chance_goals import Scenarios, choose, choose_by_mean, hours_for_all
from algorithms.reschedule import LogEntry, Work, availability_windows, reschedule
from algorithms.slowdown import detect
from algorithms.study_context import best_block, focus_span, slot_key, slot_scorer, slot_speeds

MON = date(2026, 1, 5)


# ------------------------------------------------------------------ G1
def _log(rates: list[float]) -> list[LogEntry]:
    return [LogEntry(MON + timedelta(days=i), 60.0, 60.0 * r) for i, r in enumerate(rates)]


def test_steady_learners_keep_full_trust_bursty_ones_lose_it() -> None:
    rng = random.Random(1)
    steady = calibrate(_log([min(1, max(0, rng.gauss(0.8, 0.08))) for _ in range(35)]))
    bursty_rates = [0.95] * 10 + [0.1] * 7 + [0.95] * 7 + [0.15] * 11
    bursty = calibrate(_log(bursty_rates))
    assert steady.checks > 10 and steady.trust >= 0.5
    assert bursty.trust < steady.trust and bursty.hits < bursty.checks
    assert calibrate(_log([0.8, 0.8])).checks == 0  # too little history to check


# ------------------------------------------------------------------ G2
def test_a_slow_topic_names_the_weak_link() -> None:
    pre = {"a": [], "b": ["a"], "x": ["a"], "c": ["b"]}
    vel = {"a": 1.5, "b": 1.4, "x": 1.5, "c": 0.3}
    observed = {"a", "b", "x", "c"}
    # x is an unmastered neighbour that the plan put before c: the likely missing link
    mastery = {"a": 0.9, "b": 0.9, "x": 0.2, "c": 0.8}
    out = detect(list(pre), pre, vel, observed, mastery, order=["a", "b", "x", "c"])
    assert [s.concept for s in out] == ["c"]
    assert out[0].ratio < 0.55 and out[0].suspects[0].concept == "x"
    assert out[0].suspects[0].kind == "missing_prerequisite"
    # a weak *stated* prerequisite comes first
    out2 = detect(list(pre), pre, vel, observed, {**mastery, "b": 0.3}, order=["a", "b", "x", "c"])
    assert out2[0].suspects[0].concept == "b" and out2[0].suspects[0].kind == "weak_prerequisite"
    # learning at the predicted speed raises nothing
    assert detect(list(pre), pre, {**vel, "c": 1.4}, observed, mastery) == []


# ------------------------------------------------------------------ G3
def test_chance_choice_keeps_its_promise_and_mean_choice_over_promises() -> None:
    anc = {"g1": {"p"}, "g2": {"p"}, "g3": set(), "g4": set()}
    minutes = {"p": 60.0, "g1": 60.0, "g2": 60.0, "g3": 110.0, "g4": 110.0}
    values = {"g1": 1.0, "g2": 1.0, "g3": 1.0, "g4": 1.0}
    sc = Scenarios(minutes, sigma=0.4, adherence_rates=[0.8] * 10, samples=500)
    cap = 0.75 * (sum(sc.totals(set(minutes))) / sc.n)
    safe = choose(values, anc, sc, cap, confidence=0.9)
    greedy = choose_by_mean(values, anc, sc, cap)
    assert safe.p_finish >= 0.9
    assert greedy.value >= safe.value and greedy.p_finish < 0.9
    assert set(safe.goals) | set(safe.dropped) == set(values)
    # shared prerequisites are paid once: g1 + g2 is cheaper than g3 + g4
    both = choose({"g1": 1, "g2": 1, "g3": 1, "g4": 1}, anc, sc, 260, confidence=0.5)
    assert set(both.goals) >= {"g1", "g2"}
    h = hours_for_all(values, anc, sc, lambda hours: hours * 60.0, confidence=0.9)
    assert h is not None and h * 60 >= safe.expected_minutes


# ------------------------------------------------------------------ G4 / G5
def _answers(mult: dict[str, float], lam: float, n: int, seed: int = 0) -> list[SimpleNamespace]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        wd, hour, t, exp = (
            rng.randrange(7),
            rng.choice([8, 10, 14, 19, 22]),
            rng.uniform(0, 80),
            0.6,
        )
        p = min(0.98, exp * mult.get(slot_key(wd, hour * 60), 1.0) * math.exp(-lam * t))
        out.append(
            SimpleNamespace(
                hour=hour, weekday=wd, correct=rng.random() < p, expected=exp, session_min=t
            )
        )
    return out


def test_slot_speeds_find_the_learners_best_time() -> None:
    mult = {
        "weekday morning": 1.5,
        "weekend morning": 1.5,
        "weekday night": 0.6,
        "weekend night": 0.6,
    }
    s = slot_speeds(_answers(mult, 0.0, 600))  # type: ignore[arg-type]
    assert s["weekday morning"].multiplier > s["weekday night"].multiplier
    score = slot_scorer(s)
    assert score(MON, 9 * 60) > score(MON, 22 * 60)
    assert score(MON, 15 * 60) == pytest.approx(s["weekday afternoon"].multiplier)


def test_focus_span_and_block_length() -> None:
    fast_fader = focus_span(_answers({}, math.log(2) / 15, 800, 1))  # type: ignore[arg-type]
    stays_sharp = focus_span(_answers({}, 0.0, 800, 2))  # type: ignore[arg-type]
    assert fast_fader.half_life_min < stays_sharp.half_life_min
    assert fast_fader.block_min < stays_sharp.block_min
    assert best_block(math.log(2) / 10) < best_block(math.log(2) / 120)
    assert focus_span([]).block_min == best_block(math.log(2) / 90)  # nothing measured: the default


def test_rescheduler_spends_the_week_in_the_best_slots_and_caps_blocks() -> None:
    score = lambda day, minute: 2.0 if day.weekday() >= 5 and minute < 13 * 60 else 1.0  # noqa: E731
    r = reschedule(
        [Work("w", "c", "c", 300)], start=MON, deadline=MON + timedelta(days=6),
        windows=availability_windows(), base_cap=200, weekly_cap=300, slot_score=score,
    )  # fmt: skip
    weekend_morning = sum(
        b.end - b.start for b in r.blocks if b.day.weekday() >= 5 and b.start < 13 * 60
    )
    plain = reschedule([Work("w", "c", "c", 300)], start=MON, deadline=MON + timedelta(days=6),
                       windows=availability_windows(), base_cap=200, weekly_cap=300)  # fmt: skip
    plain_wm = sum(
        b.end - b.start for b in plain.blocks if b.day.weekday() >= 5 and b.start < 13 * 60
    )
    assert weekend_morning > plain_wm
    capped = reschedule([Work("w", "c", "c", 200)], start=MON, deadline=MON + timedelta(days=6),
                        windows=availability_windows(), block_cap=25)  # fmt: skip
    assert (
        max(b.end - b.start for b in capped.blocks) <= 25 + 15
    )  # cap (+ at most one block to finish)


def test_telemetry_keeps_a_session_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "STATE", tmp_path)
    t0 = datetime(2026, 1, 5, 19, 0)
    telemetry.record("u", correct=True, expected=0.6, concept="c", now=t0)
    e2 = telemetry.record(
        "u", correct=False, expected=0.6, concept="c", now=t0 + timedelta(minutes=12)
    )
    e3 = telemetry.record("u", correct=True, expected=0.6, concept="c", now=t0 + timedelta(hours=3))
    assert e2.session_min == 12 and e3.session_min == 0  # a long pause starts a new session
    assert len(telemetry.load("u")) == 3


# ------------------------------------------------------------------ API
def test_api_exposes_the_new_signals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "STATE", tmp_path)
    client = TestClient(api.app)
    goals = client.post("/resolve", json={"goal": "sql"}).json()["goals"]
    t = date.today()
    body = {"learner_id": "gx", "goals": goals, "goal": "sql", "hours_per_week": 5,
            "deadline": (t + timedelta(days=45)).isoformat()}  # fmt: skip
    r = client.post("/reschedule", json=body).json()
    for k in ("study_times", "focus", "slowdowns", "practice_answers"):
        assert k in r
    assert {"trust", "checks", "hits"} <= set(r["forecast"])
    w = client.post("/what-fits", json={**body, "confidence": 0.9}).json()
    assert w["p_finish"] >= 0.9 or not w["chosen"]
    assert {g["concept_id"] for g in w["chosen"] + w["dropped"]} == set(goals)
