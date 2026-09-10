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
        m = state.decayed_mastery(c)
        gain += expected_mastery_gain(m, state.velocity.get(c, 1.0), per_concept_time)
        if state.last_seen.get(c, 0.0) > 0.0:
            review += max(0.0, 1.0 - m)

    prereqs = kg.prerequisites_of_resource(resource_id)
    prereq_mastery = (
        sum(state.decayed_mastery(c) for c in prereqs) / len(prereqs) if prereqs else 1.0
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
