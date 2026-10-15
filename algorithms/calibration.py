"""A forecast that checks its own promises (claim G1).

The finish forecast (``algorithms.velocity_schedule.forecast``) treats each
logged day as one independent observation of the learner's adherence.  That is
right for a steady learner and badly overconfident for one with good and bad
*weeks*: their month-to-month progress varies far more than independent days
would.  Whether the model fits *this* learner can be checked long before the
plan ends - the same model predicts, every day, a band for how much of the
planned time they will actually study over the next week.

Replaying the log, each week-ahead band either held or it didn't.  An adaptive
conformal-style update (after Gibbs & Candes, 2021) turns the checks into a
**trust** factor ``k`` on the learner's own history - how many "days of
evidence" a logged day is worth:

    log k  <-  log k + eta * (miss_target - miss)        (k capped at 1)

A miss shrinks ``k`` (the model was too sure: widen), a hit grows it back, and
in equilibrium the bands miss as often as promised (20% for an 80% band).  The
forecast then uses the evidence scaled by ``k`` - a bursty learner gets wide,
honest dates; a steady one keeps tight ones.  Prequential and stateless: only
the log is needed, and every check uses only data from before it.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from algorithms.reschedule import LogEntry

HORIZON_DAYS = 7
MIN_HISTORY_DAYS = 3  # don't check bands built on almost nothing
TRUST_FLOOR = 0.02


@dataclass(frozen=True, slots=True)
class Calibration:
    trust: float  # weight of each logged day as evidence (1 = as the model assumes)
    checks: int  # week-ahead bands checked
    hits: int  # ... that held


def week_band(
    prior_rates: Sequence[float], planned: float, level: float, trust: float, rng: random.Random
) -> tuple[float, float]:
    """Central ``level`` band of the minutes studied out of ``planned`` over the
    next week, under the forecast's own model: adherence ~ Beta built from the
    logged daily rates, each worth ``trust`` days of evidence."""
    a = 1.0 + trust * sum(prior_rates)
    b = 1.0 + trust * sum(1.0 - r for r in prior_rates)
    draws = sorted(rng.betavariate(a, b) * planned for _ in range(400))
    lo = draws[int((1 - level) / 2 * (len(draws) - 1))]
    hi = draws[int((1 + level) / 2 * (len(draws) - 1))]
    return lo, hi


def calibrate(
    log: Sequence[LogEntry], *, target: float = 0.8, eta: float = 0.6, seed: int = 11
) -> Calibration:
    """Replay the log: for each day with at least ``MIN_HISTORY_DAYS`` of history,
    predict the next ``HORIZON_DAYS`` of studying, compare with what happened,
    and update the trust factor."""
    entries = sorted((e for e in log if e.planned_minutes > 0), key=lambda e: e.day)
    rng = random.Random(seed)
    log_k = 0.0
    checks = hits = 0
    for i, e in enumerate(entries):
        if i < MIN_HISTORY_DAYS:
            continue
        window = [x for x in entries[i:] if x.day < e.day + timedelta(days=HORIZON_DAYS)]
        if not window or window[-1].day < e.day + timedelta(days=HORIZON_DAYS - 2):
            continue  # that week hasn't happened yet
        planned = sum(x.planned_minutes for x in window)
        rates = [min(1.0, x.done_minutes / x.planned_minutes) for x in entries[:i]]
        lo, hi = week_band(rates, planned, target, math.exp(log_k), rng)
        done = sum(min(x.done_minutes, x.planned_minutes) for x in window)
        miss = 0.0 if lo - 1e-6 <= done <= hi + 1e-6 else 1.0
        checks += 1
        hits += int(miss == 0.0)
        log_k = min(0.0, max(math.log(TRUST_FLOOR), log_k + eta * ((1.0 - target) - miss)))
    return Calibration(round(math.exp(log_k), 4), checks, hits)
