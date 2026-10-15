"""DKT-lite mastery refinement (novelty claim **N4**).

Cold-start (interaction 0) is handled entirely by :meth:`LearnerState.cold_start`
- knowledge-graph structure plus difficulty-scaled Bayesian priors give a valid,
near-optimal path *before any history exists*.

As attempts accumulate, this module **refines** (does not replace) that estimate.
It is a compact, pure-NumPy **Performance-Factors-Analysis** model - a standard
"lite" alternative to a deep knowledge-tracing RNN:

    logit P(correct | concept k) = b[k] + w_s[k] * successes_k + w_f[k] * failures_k

trained online by one step of logistic-regression SGD per observed attempt.  The
engine blends the PFA probability into the mastery estimate with a weight that
ramps from 0 (use BKT only) to 1 (trust the learned model) over the first
``ramp`` attempts on that concept, so early plans stay BKT-driven and later ones
are corrected by what the learner actually did.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

_LR = 0.15
_RAMP = 6  # attempts on a concept before the PFA estimate is fully trusted


def _sigmoid(x: float) -> float:
    if x < -35.0:
        return 0.0
    if x > 35.0:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


@dataclass(slots=True)
class _Skill:
    b: float = 0.0
    w_s: float = 0.25
    w_f: float = -0.30
    succ: float = 0.0
    fail: float = 0.0
    n: int = 0

    def prob(self) -> float:
        return _sigmoid(self.b + self.w_s * self.succ + self.w_f * self.fail)

    def observe(self, correct: bool) -> None:
        p = self.prob()
        err = (1.0 if correct else 0.0) - p  # dL/dlogit for log-loss
        self.b += _LR * err
        self.w_s += _LR * err * self.succ
        self.w_f += _LR * err * self.fail
        self.succ += 1.0 if correct else 0.0
        self.fail += 0.0 if correct else 1.0
        self.n += 1


@dataclass(slots=True)
class MasteryRefiner:
    """Per-concept PFA models + a BKT/PFA blend.  Serialisable, cheap to copy."""

    skills: dict[str, _Skill] = field(default_factory=dict)
    ramp: int = _RAMP

    def observe(self, concept_id: str, correct: bool) -> None:
        self.skills.setdefault(concept_id, _Skill()).observe(correct)

    def refined(self, concept_id: str, bkt_mastery: float) -> float:
        """Blend the BKT estimate with the learned PFA probability.  ``O(1)``."""
        sk = self.skills.get(concept_id)
        if sk is None or sk.n == 0:
            return bkt_mastery
        w = min(1.0, sk.n / self.ramp)
        return (1.0 - w) * bkt_mastery + w * sk.prob()

    def n_obs(self, concept_id: str) -> int:
        sk = self.skills.get(concept_id)
        return sk.n if sk else 0

    def copy(self) -> MasteryRefiner:
        clone = MasteryRefiner(ramp=self.ramp)
        clone.skills = {
            k: _Skill(v.b, v.w_s, v.w_f, v.succ, v.fail, v.n) for k, v in self.skills.items()
        }
        return clone
