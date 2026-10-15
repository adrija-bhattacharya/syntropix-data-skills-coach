"""When and how long to study, learned from the learner's own practice (claims G4, G5).

Every practice answer is logged with its local time and how far into the session
it came (``telemetry.py``), next to what the knowledge-tracing model *expected*
(P(correct) at the learner's mastery).  The ratio of right answers to expected
right answers is a measure of how well the learner is working, with the topic's
difficulty already divided out.

* **G4 - best study times.**  That ratio per time slot (weekday / weekend x
  morning / afternoon / evening / night), shrunk toward 1 with ``PRIOR`` pseudo
  answers, is the learner's *slot multiplier*.  The rescheduler then spends the
  weekly hours in the best-scoring free slots first, instead of the earliest.
* **G5 - focus span.**  The same ratio by minutes-into-session, fitted with an
  exponential decay ``exp(-lambda t)`` (weighted least squares on the log ratio,
  shrunk toward a 90-minute half-life), gives the learner's fade rate.  The
  block length that maximises learning per minute *including the break* is

      L* = argmax_L  (1 - exp(-lambda L)) / (lambda (L + break))

  - short blocks for a fast fader, long ones for someone who stays sharp.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

MIN_EVENTS = 20  # practice answers before the app trusts the learned study context
PRIOR = 6.0  # pseudo-answers at the learner's average when estimating a slot / a bin
BUCKETS = ((5 * 60, "morning"), (12 * 60, "afternoon"), (17 * 60, "evening"), (21 * 60, "night"))
DEFAULT_HALF_LIFE = 90.0  # minutes - a typical focus span when nothing is measured
BLOCK_RANGE = (15, 90)


class _Answer:  # what both estimators need from a telemetry event
    hour: int
    weekday: int
    correct: bool
    expected: float
    session_min: float


def bucket(minute_of_day: int) -> str:
    name = "night"
    for start, label in BUCKETS:
        if minute_of_day >= start:
            name = label
    return "night" if minute_of_day < BUCKETS[0][0] else name


def slot_key(weekday: int, minute_of_day: int) -> str:
    return f"{'weekend' if weekday >= 5 else 'weekday'} {bucket(minute_of_day)}"


@dataclass(frozen=True, slots=True)
class SlotSpeed:
    slot: str
    multiplier: float  # > 1: you do better than expected here
    answers: int


def slot_speeds(events: Sequence[_Answer]) -> dict[str, SlotSpeed]:
    sums: dict[str, list[float]] = {}
    for e in events:
        k = slot_key(e.weekday, e.hour * 60)
        s = sums.setdefault(k, [0.0, 0.0, 0.0])
        s[0] += float(e.correct)
        s[1] += e.expected
        s[2] += 1
    out: dict[str, SlotSpeed] = {}
    for k, (c, x, n) in sums.items():
        mult = (PRIOR + c) / (PRIOR + x) if x > 0 else 1.0
        out[k] = SlotSpeed(k, round(min(2.0, max(0.5, mult)), 3), int(n))
    return out


@dataclass(frozen=True, slots=True)
class Focus:
    half_life_min: float  # minutes for the learning rate to halve within a session
    block_min: int  # the block length that maximises learning per minute
    answers: int  # answers the estimate rests on (beyond the first 10 minutes)


def best_block(fade_per_min: float, break_min: float = 5.0) -> int:
    lam = max(fade_per_min, 1e-6)
    best, best_eff = BLOCK_RANGE[0], -1.0
    for length in range(BLOCK_RANGE[0], BLOCK_RANGE[1] + 1, 5):
        eff = (1.0 - math.exp(-lam * length)) / (lam * (length + break_min))
        if eff > best_eff + 1e-12:
            best, best_eff = length, eff
    return best


def focus_span(events: Sequence[_Answer]) -> Focus:
    """Fit the within-session fade from answers binned by minutes-into-session."""
    lam0 = math.log(2) / DEFAULT_HALF_LIFE
    bins: dict[int, list[float]] = {}
    for e in events:
        b = int(e.session_min // 15)
        s = bins.setdefault(min(b, 6), [0.0, 0.0, 0.0])
        s[0] += float(e.correct)
        s[1] += e.expected
        s[2] += 1
    pts = [
        ((b + 0.5) * 15.0, math.log((PRIOR + c) / (PRIOR + x)), n)
        for b, (c, x, n) in bins.items()
        if x > 0
    ]
    late = int(sum(n for t, _, n in pts if t > 10))
    lam = lam0
    if len(pts) >= 2:
        w = sum(n for *_, n in pts)
        tm = sum(t * n for t, _, n in pts) / w
        ym = sum(y * n for _, y, n in pts) / w
        var = sum(n * (t - tm) ** 2 for t, _, n in pts)
        if var > 0:
            slope = sum(n * (t - tm) * (y - ym) for t, y, n in pts) / var
            fitted = max(0.0, -slope)
            k = 40.0  # answers worth of trust in the default
            lam = (late * fitted + k * lam0) / (late + k)
    half = math.log(2) / lam if lam > 0 else 999.0
    return Focus(round(min(half, 999.0), 1), best_block(lam), late)


def slot_scorer(speeds: dict[str, SlotSpeed]) -> Callable[[date, int], float]:
    """score(day, minute_of_day) for the rescheduler: the slot multiplier (1 if unknown)."""

    def score(day: date, minute: int) -> float:
        s = speeds.get(slot_key(day.weekday(), minute))
        return s.multiplier if s else 1.0

    return score


BOUNDARIES = tuple(start for start, _ in BUCKETS)
