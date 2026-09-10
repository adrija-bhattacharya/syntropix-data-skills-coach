"""Adaptive capability assessment - the CAT recovers ability and picks
informative items; it never asks the learner to rate themselves."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from assessment_bank import build_item_bank
from engine import Engine
from model.assessment import (
    AdaptiveSession,
    Item,
    eap_estimate,
    item_information,
    p_correct,
    select_next_item,
)


def _mcq(iid: str, skill: str, a: float, b: float) -> Item:
    return Item(iid, skill, a, b, "stem", "mcq", ("w", "x", "y", "z"), 0)


def test_p_correct_is_monotone_in_ability() -> None:
    lo = float(p_correct(-2.0, 1.0, 0.0))
    hi = float(p_correct(2.0, 1.0, 0.0))
    assert lo < 0.5 < hi
    assert p_correct(0.0, 1.0, 0.0) == pytest.approx(0.5)


def test_information_peaks_where_difficulty_matches_ability() -> None:
    at_match = item_information(0.0, 1.5, 0.0)
    off = item_information(0.0, 1.5, 2.5)
    assert at_match > off


def test_selection_prefers_the_item_matched_to_current_ability() -> None:
    bank_items = [
        _mcq("s:easy", "s", 1.2, -2.0),
        _mcq("s:mid", "s", 1.2, 0.1),
        _mcq("s:hard", "s", 1.2, 2.0),
    ]
    from model.assessment import ItemBank

    bank = ItemBank(bank_items)
    chosen = select_next_item(bank, "s", theta=0.0, asked=set())
    assert chosen is not None and chosen.id == "s:mid"


@settings(max_examples=40, deadline=None)
@given(true_theta=st.floats(-2.5, 2.5))
def test_eap_recovers_ability_from_many_responses(true_theta: float) -> None:
    rng = np.random.default_rng(int(abs(true_theta) * 1000) + 1)
    items = [_mcq(f"i{k}", "s", 1.3, float(b)) for k, b in enumerate(np.linspace(-3, 3, 30))]
    responses = [(it, rng.random() < float(p_correct(true_theta, it.a, it.b))) for it in items]
    theta_hat, se = eap_estimate(responses)
    assert abs(theta_hat - true_theta) < 1.0  # some prior shrinkage at the extremes is expected
    assert se < 0.6


def test_eap_with_no_responses_returns_the_prior() -> None:
    assert eap_estimate([]) == (0.0, 1.5)


def test_adaptive_session_recovers_rank_order() -> None:
    bank = build_item_bank()
    rng = np.random.default_rng(7)
    skills = ["integers", "linear_eq", "quadratics"]
    truth = {"integers": 1.6, "linear_eq": 0.0, "quadratics": -1.6}
    sess = AdaptiveSession(bank, skills=skills)
    guard = 0
    while not sess.done and guard < 50:
        q = sess.next_question()
        assert q is not None
        correct = rng.random() < float(p_correct(truth[q.skill], q.a, q.b))
        sess.submit(q.id, correct)
        guard += 1
    est = sess.estimates()
    assert est["integers"].theta > est["linear_eq"].theta > est["quadratics"].theta
    m = sess.to_mastery()
    assert m["integers"] > m["quadratics"]


def test_task_items_are_graded_numerically() -> None:
    bank = build_item_bank()
    task = bank.items["linear_eq:task"]  # "Solve 3x + 7 = 22"
    assert task.grade("5") is True
    assert task.grade(" 5.0 ") is True
    assert task.grade("6") is False


def test_engine_uses_the_assessment_for_cold_start() -> None:
    from curriculum import build_curriculum

    kg = build_curriculum()
    eng = Engine(kg, item_bank=build_item_bank())
    sess = eng.start_assessment("u", ["quadratics"])
    # answer everything wrong -> low ability -> low mastery
    guard = 0
    while not sess.done and guard < 60:
        q = sess.next_question()
        assert q is not None
        eng.answer_assessment("u", q.id, -1 if q.kind == "mcq" else "definitely-wrong")
        guard += 1
    state = eng.store.get("u")
    assert state is not None
    assert state.mastery["integers"] < 0.4  # measured, not a fixed prior
    assert eng.recommend("u", ["quadratics"], time_budget_s=9000, mode="sequence")[0].feasible


def test_answering_an_item_twice_is_rejected() -> None:
    bank = build_item_bank()
    sess = AdaptiveSession(bank, skills=["integers"])
    q = sess.next_question()
    assert q is not None
    sess.submit(q.id, True)
    with pytest.raises(ValueError, match="already answered"):
        sess.submit(q.id, False)
