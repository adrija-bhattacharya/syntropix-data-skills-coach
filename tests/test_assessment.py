"""Adaptive capability assessment - the CAT recovers ability and picks
informative items; it never asks the learner to rate themselves."""

from __future__ import annotations

import random

import numpy as np
import pytest

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


@pytest.mark.parametrize("true_theta", [-1.5, -0.5, 0.0, 0.8, 1.6])
def test_eap_recovers_ability_on_average(true_theta: float) -> None:
    items = [_mcq(f"i{k}", "s", 1.3, float(b)) for k, b in enumerate(np.linspace(-3, 3, 30))]
    ests = []
    for seed in range(24):  # average out the Bernoulli sampling noise
        rng = np.random.default_rng(seed)
        responses = [(it, rng.random() < float(p_correct(true_theta, it.a, it.b))) for it in items]
        theta_hat, se = eap_estimate(responses)
        ests.append(theta_hat)
        assert se < 0.6
    assert abs(float(np.mean(ests)) - true_theta) < 0.5  # mild shrinkage toward the prior


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


@pytest.mark.parametrize("domain", ["sql", "python", "algebra"])
def test_item_banks_exist_and_span_a_difficulty_band(domain: str) -> None:
    bank = build_item_bank(domain)
    assert bank is not None and len(bank.skills) >= 8
    for skill in bank.skills:
        items = bank.for_skill(skill)
        assert items
        assert any(it.kind == "task" for it in items)  # a hands-on item per concept


def test_no_item_bank_for_an_uncalibrated_domain() -> None:
    assert build_item_bank("dsa_python") is None


def test_sql_adaptive_session_recovers_rank_order() -> None:
    import numpy as np

    bank = build_item_bank("sql")
    assert bank is not None
    rng = np.random.default_rng(3)
    skills = ["select_from", "group_by", "window_functions"]
    truth = {"select_from": 1.8, "group_by": 0.0, "window_functions": -1.6}
    sess = AdaptiveSession(bank, skills=skills)
    guard = 0
    while not sess.done and guard < 40:
        q = sess.next_question()
        assert q is not None
        sess.submit(q.id, rng.random() < float(p_correct(truth[q.skill], q.a, q.b)))
        guard += 1
    est = sess.estimates()
    assert est["select_from"].theta > est["window_functions"].theta


def test_grade_is_forgiving_of_a_bad_mcq_response() -> None:
    bank = build_item_bank("sql")
    assert bank is not None
    item = next(it for it in bank.items.values() if it.kind == "mcq")
    assert item.grade("not-a-number") is False


def test_self_reported_band_sets_the_prior() -> None:
    from model.assessment import BANDS

    bank = build_item_bank("sql")
    assert bank is not None
    skills = ["select_from", "group_by", "window_functions"]

    # no answers yet -> the estimate IS the band prior
    beg = AdaptiveSession(bank, skills=skills, band="beginner")
    adv = AdaptiveSession(bank, skills=skills, band="advanced")
    assert beg.estimate("group_by").theta == pytest.approx(BANDS["beginner"][0])
    assert adv.estimate("group_by").theta == pytest.approx(BANDS["advanced"][0])
    assert beg.to_mastery()["group_by"] < 0.25 < adv.to_mastery()["group_by"]


def test_a_beginner_answers_only_a_few_confirmation_questions() -> None:
    bank = build_item_bank("python")
    assert bank is not None
    skills = ["variables", "loops", "functions", "dicts"]
    sess = AdaptiveSession(bank, skills=skills, band="beginner")
    n = 0
    while not sess.done and n < 40:
        q = sess.next_question()
        assert q is not None
        sess.submit(q.id, correct=False)
        n += 1
    assert n <= 4  # "majorly depends on what they say"
    assert all(m < 0.3 for m in sess.to_mastery().values())


def test_advanced_test_can_still_find_a_gap() -> None:
    import numpy as np

    from model.assessment import p_correct

    bank = build_item_bank("sql")
    assert bank is not None
    sess = AdaptiveSession(bank, skills=["select_from", "window_functions"], band="advanced")
    rng = np.random.default_rng(0)
    truth = {"select_from": 2.0, "window_functions": -1.0}  # strong on one, weak on the other
    guard = 0
    while not sess.done and guard < 40:
        q = sess.next_question()
        assert q is not None
        sess.submit(q.id, rng.random() < float(p_correct(truth[q.skill], q.a, q.b)))
        guard += 1
    est = sess.estimates()
    assert est["window_functions"].theta < est["select_from"].theta  # the gap was found


def test_style_signal_reads_hands_on_vs_recall() -> None:
    bank = build_item_bank("sql")
    assert bank is not None
    sess = AdaptiveSession(bank, skills=list(bank.skills), band="intermediate")
    for _ in range(30):
        q = sess.next_question()
        if q is None:
            break
        sess.submit(q.id, correct=(q.kind == "task"))  # aces tasks, fails MCQs
    style = sess.style_signal()
    assert style["hands_on"] > style["recall"]
    assert "hands-on" in str(style["note"])


def test_answering_an_item_twice_is_rejected() -> None:
    bank = build_item_bank()
    sess = AdaptiveSession(bank, skills=["integers"])
    q = sess.next_question()
    assert q is not None
    sess.submit(q.id, True)
    with pytest.raises(ValueError, match="already answered"):
        sess.submit(q.id, False)


def test_remaining_estimate_counts_down_to_the_real_end() -> None:
    """'About N more' must be the expected count, not the worst case: it counts
    down by one per answer and reaches 0 exactly when the test stops."""
    for domain in ("sql", "algebra", "python"):
        bank = build_item_bank(domain)
        s = AdaptiveSession(bank, skills=bank.skills[:6])
        rng = random.Random(0)
        seen: list[int] = []
        while not s.done:
            seen.append(s.remaining_estimate())
            q = s.next_question()
            assert q is not None
            s.submit(q.id, rng.random() < 0.6)
        assert s.remaining_estimate() == 0
        assert seen[0] == len(seen)  # the first estimate was the true length
