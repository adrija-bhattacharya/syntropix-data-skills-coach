from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from velpo.config import settings as cfg
from velpo.model.cost import build_cost_vectors, expected_mastery_gain
from velpo.model.knowledge_graph import KnowledgeGraph
from velpo.model.learner import (
    Attempt,
    LearnerState,
    bkt_update,
    cognitive_load,
    decay,
    resource_load,
    velocity_update,
)


def test_bkt_rises_on_correct_streak() -> None:
    m = cfg.bkt_p_init
    seq = []
    for _ in range(6):
        m = bkt_update(m, True)
        seq.append(m)
    assert seq == sorted(seq) and seq[-1] > 0.9


def test_bkt_in_unit_interval() -> None:
    m = 0.5
    for c in [True, False, True, True, False]:
        m = bkt_update(m, c)
        assert 0.0 <= m <= 1.0


def test_decay_monotonic() -> None:
    vals = [decay(1.0, t, 100.0) for t in (0, 10, 50, 100, 500)]
    assert vals == sorted(vals, reverse=True)
    assert vals[0] == 1.0 and vals[-1] < 0.05
    assert decay(0.7, -1.0, 100.0) == 0.7


@settings(max_examples=200, deadline=None)
@given(
    v0=st.floats(1e-3, 5.0),
    dm=st.floats(-1.0, 1.0),
    ds=st.floats(1.0, 1e5),
)
def test_velocity_bounded(v0: float, dm: float, ds: float) -> None:
    v = velocity_update(v0, dm, ds)
    assert cfg.velocity_min <= v <= cfg.velocity_max


def test_fast_learner_velocity_rises() -> None:
    v = 1.0
    for _ in range(10):
        v = velocity_update(v, 0.4, 300.0)
    assert v > 1.5


def test_cognitive_load() -> None:
    assert cognitive_load([]) == 0.0
    struggling = [Attempt("r", False, 90, 2) for _ in range(8)]
    cruising = [Attempt("r", True, 40, 0) for _ in range(8)]
    assert cognitive_load(struggling) > cognitive_load(cruising)
    assert 0.0 <= cognitive_load(struggling) <= 1.0


def test_resource_load_higher_for_hard_and_weak_prereqs() -> None:
    assert resource_load(5.0, 0.1) > resource_load(1.0, 0.9)


def test_expected_gain_monotonic_and_bounded() -> None:
    assert expected_mastery_gain(0.2, 3.0, 600) > expected_mastery_gain(0.2, 0.5, 600)
    assert expected_mastery_gain(0.2, 1.0, 1200) > expected_mastery_gain(0.2, 1.0, 300)
    assert expected_mastery_gain(0.95, 5.0, 1e5) <= 0.05 + 1e-9


def test_faster_learner_gets_cheaper_mastery(kg: KnowledgeGraph) -> None:
    slow = LearnerState.cold_start(kg.concept_ids, time_budget_s=6000)
    fast = slow.copy()
    for c in fast.velocity:
        fast.velocity[c] = 3.0
    cs = build_cost_vectors(kg, slow)["integers:lesson"]
    cf = build_cost_vectors(kg, fast)["integers:lesson"]
    assert cf.neg_gain < cs.neg_gain  # more negative == more gain
    assert cf.seconds == cs.seconds


def test_cold_start_priors_from_difficulty(kg: KnowledgeGraph) -> None:
    d = {
        c: max((kg.resources[r].difficulty for r in kg.resources_for(c)), default=1.0)
        for c in kg.concept_ids
    }
    st_ = LearnerState.cold_start(kg.concept_ids, time_budget_s=6000, difficulty=d)
    assert st_.mastery["quadratics"] < st_.mastery["integers"]  # harder -> lower prior


def test_rng_seeded() -> None:
    assert np.random.default_rng(0).random() == np.random.default_rng(0).random()
