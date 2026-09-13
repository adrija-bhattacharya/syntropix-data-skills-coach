"""The learner model the optimiser conditions on.

Deliberately lightweight and CPU-only:

* **mastery** per concept  - Bayesian Knowledge Tracing (a 2-state HMM); works
  from interaction #0 (cold-start) using item-difficulty priors.
* **velocity** per concept - mastery gained per hour of study, estimated online.
  This is what personalises the plan to *how fast this learner learns*.
* **forgetting**           - mastery decays with elapsed time (Ebbinghaus).
* **cognitive load**        - a sensor-free proxy from recent error rate / hints.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace

from config import settings
from model.refine import MasteryRefiner

_HOUR = 3600.0


# --------------------------------------------------------------------------- #
# Bayesian Knowledge Tracing
# --------------------------------------------------------------------------- #
def bkt_update(prior: float, correct: bool) -> float:
    """One BKT step: P(known) after an observation, including the learn transition.

    ``O(1)``.
    """
    s, g, t = settings.bkt_p_slip, settings.bkt_p_guess, settings.bkt_p_transit
    if correct:
        num = prior * (1 - s)
        den = num + (1 - prior) * g
    else:
        num = prior * s
        den = num + (1 - prior) * (1 - g)
    cond = num / den if den > 0 else prior
    return cond + (1 - cond) * t


# --------------------------------------------------------------------------- #
# forgetting
# --------------------------------------------------------------------------- #
def decay(mastery: float, elapsed_hours: float, half_life_h: float) -> float:
    if elapsed_hours <= 0 or half_life_h <= 0:
        return mastery
    return mastery * math.exp(-elapsed_hours / half_life_h)


# --------------------------------------------------------------------------- #
# velocity
# --------------------------------------------------------------------------- #
def velocity_update(v_old: float, delta_mastery: float, delta_seconds: float) -> float:
    """Exponential-weighted update of a per-concept learning-velocity estimate.

    ``O(1)``.
    """
    a = settings.velocity_alpha
    rate = max(delta_mastery, 0.0) / (max(delta_seconds, 1.0) / _HOUR)
    rate = min(max(rate, settings.velocity_min), settings.velocity_max)
    v = (1 - a) * v_old + a * rate
    return min(max(v, settings.velocity_min), settings.velocity_max)


# --------------------------------------------------------------------------- #
# cognitive load
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Attempt:
    resource_id: str
    correct: bool
    seconds: float
    hints: int = 0
    at: float = 0.0


def cognitive_load(recent: Iterable[Attempt], window: int = 8) -> float:
    tail = list(recent)[-window:]
    if not tail:
        return 0.0
    err = sum(0.0 if a.correct else 1.0 for a in tail) / len(tail)
    hint = sum(1.0 if a.hints else 0.0 for a in tail) / len(tail)
    return min(1.0, 0.6 * err + 0.4 * hint)


def resource_load(difficulty: float, prereq_mastery: float, d_scale: float = 5.0) -> float:
    """Load *added* by one resource, discounted by how solid the prerequisites are."""
    base = min(1.0, difficulty / d_scale)
    discount = 0.5 + 0.5 * min(1.0, max(0.0, prereq_mastery))
    return round(base / discount, 6)


# --------------------------------------------------------------------------- #
# state
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class LearnerState:
    mastery: dict[str, float]
    velocity: dict[str, float]
    half_life: dict[str, float]
    last_seen: dict[str, float]
    time_budget_s: float
    now_s: float = 0.0
    n_interactions: int = 0
    recent: list[Attempt] = field(default_factory=list)
    refiner: MasteryRefiner = field(default_factory=MasteryRefiner)
    mastery_se: dict[str, float] = field(default_factory=dict)
    """Posterior SD (logit scale) of the mastery estimate for concepts the
    adaptive test actually measured - empty everywhere else.  Drives the
    risk-aware planning claim: an uncertain skill is treated pessimistically."""

    @classmethod
    def cold_start(
        cls,
        concept_ids: Iterable[str],
        *,
        time_budget_s: float,
        difficulty: Mapping[str, float] | None = None,
    ) -> LearnerState:
        cids = list(concept_ids)
        difficulty = difficulty or {}
        d_max = max(difficulty.values(), default=1.0)
        mastery = {
            c: (
                max(0.02, settings.bkt_p_init * (1 - 0.5 * difficulty.get(c, 0.0) / d_max))
                if difficulty
                else settings.bkt_p_init
            )
            for c in cids
        }
        return cls(
            mastery=mastery,
            velocity=dict.fromkeys(cids, 1.0),
            half_life=dict.fromkeys(cids, settings.forgetting_half_life_h),
            last_seen=dict.fromkeys(cids, 0.0),
            time_budget_s=time_budget_s,
        )

    def decayed_mastery(self, concept_id: str) -> float:
        """Current best estimate: BKT prior, decayed by elapsed time (Ebbinghaus),
        then refined by the DKT-lite / PFA model once attempts exist (N4)."""
        m0 = self.mastery.get(concept_id, 0.0)
        elapsed_h = max(0.0, (self.now_s - self.last_seen.get(concept_id, 0.0)) / _HOUR)
        decayed = decay(
            m0, elapsed_h, self.half_life.get(concept_id, settings.forgetting_half_life_h)
        )
        return self.refiner.refined(concept_id, decayed)

    def is_mastered(self, concept_id: str, threshold: float | None = None) -> bool:
        theta = settings.mastery_threshold if threshold is None else threshold
        return self.mastery.get(concept_id, 0.0) >= theta

    # ---- risk-aware (claim B): the estimator's uncertainty matters ----
    def effective_mastery(self, concept_id: str) -> float:
        """The mastery the planner should *act on*: the point estimate, pulled
        toward a pessimistic lower confidence bound for skills the adaptive test
        measured with residual uncertainty (``kappa`` standard deviations)."""
        m = self.decayed_mastery(concept_id)
        se = self.mastery_se.get(concept_id)
        if not se or settings.risk_kappa <= 0.0:
            return m
        return _sigmoid(_logit(m) - settings.risk_kappa * se)

    def confidence(self, concept_id: str, threshold: float | None = None) -> float:
        """``P(true mastery >= threshold)`` from the estimator's posterior.
        1.0 for a skill we never measured but the point estimate clears; the
        Gaussian tail otherwise."""
        theta = settings.mastery_threshold if threshold is None else threshold
        m = self.decayed_mastery(concept_id)
        se = self.mastery_se.get(concept_id)
        if not se:
            return 1.0 if m >= theta else 0.0
        z = (_logit(m) - _logit(theta)) / se
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    def copy(self) -> LearnerState:
        return replace(
            self,
            mastery=dict(self.mastery),
            velocity=dict(self.velocity),
            half_life=dict(self.half_life),
            last_seen=dict(self.last_seen),
            recent=list(self.recent),
            refiner=self.refiner.copy(),
            mastery_se=dict(self.mastery_se),
        )


def scale_velocity(state: LearnerState, mult: float) -> LearnerState:
    """A copy of ``state`` with every per-concept velocity scaled by ``mult``
    and clamped to ``[velocity_min, velocity_max]``.  ``mult == 1.0`` is a no-op
    (returns ``state`` unchanged) - this is the single knob that turns "take it
    slow" / "move fast" into a different pace and a different plan (N2)."""
    if mult == 1.0:
        return state
    lo, hi = settings.velocity_min, settings.velocity_max
    velocity = {c: min(hi, max(lo, v * mult)) for c, v in state.velocity.items()}
    return replace(state, velocity=velocity)


def _logit(p: float) -> float:
    p = min(1.0 - 1e-6, max(1e-6, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, x))))
