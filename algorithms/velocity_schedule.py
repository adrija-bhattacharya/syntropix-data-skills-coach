"""Velocity-aware scheduling (claim G): plan time in *this learner's* minutes.

The planner already knows each learner's **velocity** - mastery gained per hour,
per concept, updated after every answer (``model.learner.velocity_update``) -
and the same learning curve the DP optimises with (``model.cost``):

    m(h) = 1 - (1 - m0) * exp(-v * h / tau)

Inverting it gives the study time this learner needs to take a concept from its
current mastery ``m0`` to the target ``m*``:

    T(m0, v) = (tau / v) * ln((1 - m0) / (1 - m*))

Three uses, all on top of the calendar feedback loop (``algorithms.reschedule``):

1. **Velocity-sized work** - every concept's planned minutes are the lesson's
   minutes scaled by ``T(m0, v_hat) / T(m_init, 1)``: a learner who flies through
   joins gets less time for joins, one who struggles gets more, and a concept
   already near mastery gets a short check.  ``v_hat`` for a concept never
   practised is *predicted*: the velocities shown on its prerequisites, shrunk
   toward the learner's overall mean (empirical-Bayes style), because how fast
   you learned what a topic builds on is the best evidence for how fast you'll
   learn it.
2. **Hardness** - ``T`` itself, normalised: the time a concept will cost this
   learner.  The rescheduler uses it to put slow topics on light days and quick
   ones on busy days (``reschedule(..., match=True)``).
3. **Forecast** - a Monte-Carlo over the uncertainty in velocity (log-normal,
   narrower the more the learner has practised) and in adherence (Beta from the
   session log) gives finish-date quantiles and P(done by the deadline), mapped
   onto the learner's real day-by-day capacity.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from config import settings
from model.cost import _TAU_H

TARGET = settings.mastery_threshold  # mastery the plan aims for
M_INIT = settings.bkt_p_init  # a typical starting point: what lesson minutes are sized for
RATIO_BOUNDS = (0.25, 3.0)  # never less than a quick check, never more than 3x the lesson
PRIOR_WEIGHT = 2.0  # pseudo-observations of the learner's mean in the shrinkage


def time_to_mastery(m0: float, velocity: float, target: float = TARGET) -> float:
    """Hours of study to go from ``m0`` to ``target`` at ``velocity`` (0 if already there)."""
    if m0 >= target:
        return 0.0
    v = max(velocity, settings.velocity_min)
    return (_TAU_H / v) * math.log((1.0 - m0) / (1.0 - target))


def time_ratio(m0: float, velocity: float) -> float:
    """This learner's time for a concept relative to a typical learner starting
    from scratch, clamped to ``RATIO_BOUNDS``."""
    base = time_to_mastery(M_INIT, 1.0)
    r = time_to_mastery(m0, velocity) / base if base > 0 else 1.0
    return min(RATIO_BOUNDS[1], max(RATIO_BOUNDS[0], r))


def predicted_velocity(
    concepts: Sequence[str],
    prerequisites: Mapping[str, Sequence[str]],
    velocity: Mapping[str, float],
    observed: set[str],
) -> dict[str, float]:
    """``v_hat`` for every concept.  Observed concepts keep their estimate; an
    unobserved one gets the mean velocity of its observed prerequisites (walking
    up the graph until some are found), shrunk toward the learner's overall mean
    with ``PRIOR_WEIGHT`` pseudo-observations.  No evidence at all -> the mean
    (1.0 for a brand-new learner)."""
    seen = [velocity[c] for c in observed if c in velocity]
    mean = sum(seen) / len(seen) if seen else 1.0
    out: dict[str, float] = {}
    for c in concepts:
        if c in observed and c in velocity:
            out[c] = velocity[c]
            continue
        frontier = list(prerequisites.get(c, ()))
        visited: set[str] = set()
        evidence: list[float] = []
        while frontier and not evidence:  # nearest observed ancestors
            nxt: list[str] = []
            for p in frontier:
                if p in visited:
                    continue
                visited.add(p)
                if p in observed and p in velocity:
                    evidence.append(velocity[p])
                else:
                    nxt += list(prerequisites.get(p, ()))
            frontier = nxt
        n = len(evidence)
        out[c] = (sum(evidence) + PRIOR_WEIGHT * mean) / (n + PRIOR_WEIGHT)
    return out


@dataclass(frozen=True, slots=True)
class Sized:
    """A plan step re-sized for this learner."""

    minutes: float
    ratio: float  # vs the lesson's own minutes
    hours_to_master: float  # this learner's T for the concept
    velocity: float  # v_hat used


def size_work(
    steps: Sequence[tuple[str, float, str]],
    mastery: Mapping[str, float],
    v_hat: Mapping[str, float],
) -> list[Sized]:
    """``steps`` = (concept, lesson minutes, kind).  Teaching/practice steps are
    scaled by the learner's time ratio; reviews keep their length (they are
    short by design and sized by the forgetting model, not by learning speed)."""
    out: list[Sized] = []
    for concept, minutes, kind in steps:
        v = v_hat.get(concept, 1.0)
        m0 = mastery.get(concept, M_INIT)
        t = time_to_mastery(m0, v)
        r = 1.0 if kind in ("review", "retention") else time_ratio(m0, v)
        out.append(Sized(minutes * r, r, t, v))
    return out


# --------------------------------------------------------------------------- #
# forecast
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Forecast:
    p50: date | None
    p80: date | None
    p95: date | None
    p_on_time: float
    samples: int


def forecast(
    work_minutes: Sequence[float],
    work_ratios: Sequence[float],
    capacity: Sequence[tuple[date, float]],
    deadline: date,
    *,
    observed_concepts: int,
    adherence_rates: Sequence[float] = (),
    level: float = 0.8,
    trust: float = 1.0,
    samples: int = 400,
    seed: int = 7,
) -> Forecast:
    """Monte-Carlo finish dates.

    Velocity uncertainty: each concept's time ratio is multiplied by a
    log-normal factor whose spread shrinks with practice (``sigma = 0.45 /
    sqrt(1 + observed)``) - a new learner's estimate is rough, a practised one's
    is tight.  Adherence: Beta(1 + sum r, 1 + sum (1 - r)) over the logged days'
    rates ``r`` = done / planned (one observation per day - counting minutes
    would make it overconfident); with nothing logged, a prior centred on doing
    most of what's planned.  Finish = the first day whose cumulative capacity
    covers the sampled work.  ``level`` is the quantile reported as ``p80``;
    ``trust`` scales the history's weight - 1 unless the learner's own record
    shows the model is too sure of them (``algorithms.calibration``)."""
    rng = random.Random(seed)
    sigma = 0.45 / math.sqrt(1.0 + observed_concepts)
    base = [m / max(r, 1e-6) for m, r in zip(work_minutes, work_ratios)]  # lesson minutes
    cum: list[tuple[date, float]] = []
    total = 0.0
    for d, cap in capacity:
        total += cap
        cum.append((d, total))
    rates = [min(1.0, max(0.0, r)) for r in adherence_rates]
    a, b = 1.0 + trust * sum(rates), 1.0 + trust * sum(1.0 - r for r in rates)
    if not rates:
        a, b = 8.0, 1.5  # no log yet: mostly do what's planned, some slack
    finishes: list[date | None] = []
    for _ in range(samples):
        noise = math.exp(rng.gauss(0.0, sigma))
        need = sum(
            bm * min(RATIO_BOUNDS[1], max(RATIO_BOUNDS[0], r * noise))
            for bm, r in zip(base, work_ratios)
        )
        adh = min(1.0, max(0.15, rng.betavariate(a, b)))
        need /= adh
        finishes.append(next((d for d, c in cum if c >= need), None))
    done = sorted(f for f in finishes if f is not None)
    n = len(finishes)

    def q(p: float) -> date | None:
        k = math.ceil(p * n) - 1
        return done[k] if k < len(done) else None  # None: beyond the planning horizon

    on_time = sum(1 for f in finishes if f is not None and f <= deadline) / n
    return Forecast(q(0.5), q(level), q(0.95), round(on_time, 3), n)


def capacity(
    start: date,
    end: date,
    *,
    windows: dict[int, list[tuple[int, int]]],
    busy: Sequence[tuple[object, object]] = (),
    base_cap: float | None = None,
    weekly_cap: float | None = None,
    week_done: float = 0.0,
) -> list[tuple[date, float]]:
    """Minutes the learner can really study on each day (free gaps, fatigue caps,
    the weekly budget): the rescheduler run on an endless piece of work."""
    from algorithms.reschedule import Work, reschedule

    filler = [Work("cap", "cap", "cap", 10_000_000.0)]
    r = reschedule(
        filler, start=start, deadline=end, windows=windows, busy=busy,  # type: ignore[arg-type]
        base_cap=base_cap, weekly_cap=weekly_cap, week_done=week_done,
    )  # fmt: skip
    return [(d.day, d.study_minutes) for d in r.days]
