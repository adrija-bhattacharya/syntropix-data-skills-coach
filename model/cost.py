"""Per-resource cost vectors - the learner-conditioned input to the DP.

Five components, **all "lower is better"** so the DP minimises / takes Pareto
minima uniformly:

============  =========================================================
component     meaning
============  =========================================================
neg_gain      negative expected mastery gain (scaled by learner VELOCITY -
              the same resource is "cheaper" for a faster learner)
seconds       expected study time
load          cognitive load the resource adds
diff_jump     |difficulty - difficulty of the previous step|
neg_review    negative mastery restored to already-decayed concepts
============  =========================================================
"""

from __future__ import annotations

import math
from typing import NamedTuple

from config import settings
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState, resource_load

_HOUR = 3600.0
_TAU_H = 0.5  # hours of study at velocity 1.0 to close ~63% of the remaining gap


class CostVector(NamedTuple):
    neg_gain: float
    seconds: float
    load: float
    diff_jump: float
    neg_review: float

    def __add__(self, other: object) -> CostVector:
        assert isinstance(other, tuple) and len(other) == 5
        return CostVector(*(a + b for a, b in zip(self, other)))

    @classmethod
    def zero(cls) -> CostVector:
        return cls(0.0, 0.0, 0.0, 0.0, 0.0)

    def scalarise(self, weights: tuple[float, float, float, float, float]) -> float:
        return sum(w * x for w, x in zip(weights, self))


def expected_mastery_gain(current: float, velocity: float, seconds: float) -> float:
    """``(1 - m) * (1 - exp(-velocity * hours / tau))`` - bounded by the gap,
    increasing in both study time and learner velocity.  ``O(1)``.
    """
    hours = seconds / _HOUR
    frac = 1.0 - math.exp(-max(velocity, 0.0) * hours / _TAU_H)
    return max(0.0, (1.0 - current) * frac)


def resource_cost(
    kg: KnowledgeGraph, resource_id: str, state: LearnerState, prev_difficulty: float
) -> CostVector:
    r = kg.resources[resource_id]
    per_concept_time = r.seconds / max(1, len(r.concepts))

    gain = review = 0.0
    for c in r.concepts:
        m = state.effective_mastery(c)  # risk-adjusted for measured-but-uncertain skills (claim B)
        gain += expected_mastery_gain(m, state.velocity.get(c, 1.0), per_concept_time)
        if state.last_seen.get(c, 0.0) > 0.0:
            review += max(0.0, 1.0 - m)

    prereqs = kg.prerequisites_of_resource(resource_id)
    prereq_mastery = (
        sum(state.effective_mastery(c) for c in prereqs) / len(prereqs) if prereqs else 1.0
    )

    return CostVector(
        neg_gain=-gain,
        seconds=r.seconds,
        load=resource_load(r.difficulty, prereq_mastery),
        diff_jump=abs(r.difficulty - prev_difficulty),
        neg_review=-review,
    )


def build_cost_vectors(
    kg: KnowledgeGraph, state: LearnerState, prev_difficulty: float = 1.0
) -> dict[str, CostVector]:
    """Cost vector for every resource in the catalogue.  ``O(R * C)``."""
    return {rid: resource_cost(kg, rid, state, prev_difficulty) for rid in kg.resources}


# --------------------------------------------------------------------------- #
# position-aware costs - the input to the sequencing DP (algorithms.sequencing)
# --------------------------------------------------------------------------- #
def predicted_mastery(
    post_mastery: float, taught_position: int, position: int, half_life_steps: float
) -> float:
    """Mastery of a concept last reinforced ``position - taught_position`` steps
    ago, decaying geometrically with a step-based half-life."""
    lag = max(0, position - taught_position)
    return float(post_mastery * 0.5 ** (lag / max(half_life_steps, 1e-6)))


def _prereq_mastery_now(
    kg: KnowledgeGraph,
    concept: str,
    taught_at: dict[str, int],
    position: int,
    half_life_steps: float,
) -> float:
    reqs = [q for q in kg.direct_prerequisites(concept) if q in taught_at]
    if not reqs:
        return 1.0
    post = settings.seq_post_mastery
    return sum(
        predicted_mastery(post, taught_at[q], position, half_life_steps) for q in reqs
    ) / len(reqs)


def sequence_step_cost(
    kg: KnowledgeGraph,
    concept: str,
    resource_id: str,
    state: LearnerState,
    *,
    position: int,
    taught_at: dict[str, int],
    prev_difficulty: float,
    half_life_steps: float,
) -> CostVector:
    """Cost of teaching ``concept`` (for the first time) with ``resource_id`` at
    step ``position`` of the sequence, given when its prerequisites were taught.

    Unlike :func:`resource_cost` this is **position-dependent**: a concept taught
    too early (weak prerequisites) or too late (decayed prerequisites) costs more
    cognitive load and books prerequisite debt.
    """
    r = kg.resources[resource_id]
    per_concept_time = r.seconds / max(1, len(r.concepts))
    prereq_m = _prereq_mastery_now(kg, concept, taught_at, position, half_life_steps)

    gain = 0.0
    for c in r.concepts:
        gain += expected_mastery_gain(
            state.effective_mastery(c), state.velocity.get(c, 1.0), per_concept_time
        )

    theta = settings.mastery_threshold
    # claim B: a prerequisite the adaptive test measured but left uncertain is a
    # cost even when its point estimate looks fine.
    risk = sum(
        max(0.0, theta - state.effective_mastery(q))
        for q in kg.direct_prerequisites(concept)
        if q in state.mastery_se
    )
    return CostVector(
        neg_gain=-gain,
        seconds=r.seconds,
        load=resource_load(r.difficulty, prereq_m),
        diff_jump=abs(r.difficulty - prev_difficulty),
        neg_review=max(0.0, theta - prereq_m) + 0.5 * risk,
    )


def sequence_review_cost(
    kg: KnowledgeGraph,
    concept: str,
    resource_id: str,
    *,
    position: int,
    taught_at: dict[str, int],
    prev_difficulty: float,
    half_life_steps: float,
) -> CostVector:
    """Cost of a *review* step: re-teaching an already-covered ``concept`` whose
    predicted mastery has decayed.  The upside is booked as negative
    ``neg_review`` (mastery restored)."""
    r = kg.resources[resource_id]
    m_now = predicted_mastery(
        settings.seq_post_mastery, taught_at.get(concept, position), position, half_life_steps
    )
    restored = max(0.0, settings.seq_post_mastery - m_now)
    return CostVector(
        neg_gain=0.0,
        seconds=r.seconds,
        load=0.5 * resource_load(r.difficulty, 1.0),
        diff_jump=abs(r.difficulty - prev_difficulty),
        neg_review=-restored,
    )
