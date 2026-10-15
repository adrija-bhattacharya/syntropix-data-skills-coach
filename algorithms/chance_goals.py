"""What can I finish by my date, with 90% confidence?  (claim G3)

Choose a set of goal skills to aim for by a deadline.  Each goal drags in its
prerequisite closure, so goals share costs; each concept's time is *uncertain*
(this learner's velocity estimate, log-normal, plus how much of the planned time
they really study, Beta).  Picking by expected time (the usual approach, and
what the role planner does with point estimates) fills the calendar exactly -
and then fails about half the time.  This picks the most valuable
prerequisite-closed set whose **probability of finishing is at least the
confidence asked for** (a chance-constrained knapsack over the goal lattice):

    max  sum value(g)        s.t.  P( sum_{c in closure(S)} T_c / A  <=  capacity )  >=  1 - eps

``T_c`` and ``A`` are sampled once (common random numbers), so every candidate
set is judged on the same scenarios and comparisons between sets are not noise.
Exact over all subsets for up to ``EXACT_MAX`` goals (the usual case: a role
has 8-14 goal skills), greedy by value per expected minute beyond that.
Also answers the inverse question: how many hours a week would let *every*
goal fit at that confidence.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

EXACT_MAX = 14


@dataclass(frozen=True, slots=True)
class Choice:
    goals: tuple[str, ...]
    dropped: tuple[str, ...]
    value: float
    p_finish: float  # probability the chosen set fits before the deadline
    expected_minutes: float
    p90_minutes: float  # the 90th percentile of the time it needs
    capacity_minutes: float


class Scenarios:
    """Sampled minutes per concept and adherence, shared by every candidate."""

    def __init__(
        self,
        minutes: Mapping[str, float],
        *,
        sigma: float,
        adherence_rates: Sequence[float] = (),
        samples: int = 600,
        seed: int = 3,
    ) -> None:
        rng = random.Random(seed)
        rates = [min(1.0, max(0.0, r)) for r in adherence_rates]
        a, b = (1.0 + sum(rates), 1.0 + sum(1.0 - r for r in rates)) if rates else (8.0, 1.5)
        self.concepts = list(minutes)
        self.n = samples
        self.rows: list[dict[str, float]] = []
        for _ in range(samples):
            common = rng.gauss(0.0, sigma * 0.7)  # the whole learner faster / slower
            adh = min(1.0, max(0.15, rng.betavariate(a, b)))
            self.rows.append(
                {
                    c: m * math.exp(common + rng.gauss(0.0, sigma * 0.7)) / adh
                    for c, m in minutes.items()
                }
            )

    def totals(self, concepts: set[str]) -> list[float]:
        return [sum(r[c] for c in concepts) for r in self.rows]


def _closure(goals: Sequence[str], ancestors: Mapping[str, set[str]], todo: set[str]) -> set[str]:
    out: set[str] = set()
    for g in goals:
        out |= ({g} | ancestors.get(g, set())) & todo
    return out


def _evaluate(
    goals: Sequence[str],
    sc: Scenarios,
    ancestors: Mapping[str, set[str]],
    todo: set[str],
    capacity: float,
) -> tuple[float, float, float]:
    t = sorted(sc.totals(_closure(goals, ancestors, todo)))
    p = sum(1 for x in t if x <= capacity) / len(t)
    return p, sum(t) / len(t), t[int(0.9 * (len(t) - 1))]


def choose(
    values: Mapping[str, float],
    ancestors: Mapping[str, set[str]],
    sc: Scenarios,
    capacity: float,
    *,
    confidence: float = 0.9,
) -> Choice:
    """The most valuable goal set that finishes with probability >= ``confidence``."""
    todo = set(sc.concepts)
    goals = [g for g in values if values[g] > 0]
    best: tuple[float, float, tuple[str, ...]] = (0.0, 0.0, ())  # value, -E[time], goals
    if len(goals) <= EXACT_MAX:
        for k in range(len(goals), 0, -1):
            for combo in combinations(goals, k):
                v = sum(values[g] for g in combo)
                if v < best[0]:
                    continue
                p, mean, _ = _evaluate(combo, sc, ancestors, todo, capacity)
                if p >= confidence and (v, -mean) > best[:2]:
                    best = (v, -mean, combo)
    else:
        chosen: list[str] = []
        rest = sorted(
            goals,
            key=lambda g: -values[g] / max(1.0, _evaluate([g], sc, ancestors, todo, capacity)[1]),
        )
        for g in rest:
            p, mean, _ = _evaluate([*chosen, g], sc, ancestors, todo, capacity)
            if p >= confidence:
                chosen.append(g)
        best = (sum(values[g] for g in chosen), 0.0, tuple(chosen))
    picked = best[2]
    p, mean, p90 = _evaluate(picked, sc, ancestors, todo, capacity) if picked else (1.0, 0.0, 0.0)
    return Choice(
        picked, tuple(g for g in goals if g not in picked), round(best[0], 3), round(p, 3),
        round(mean, 1), round(p90, 1), round(capacity, 1),
    )  # fmt: skip


def choose_by_mean(
    values: Mapping[str, float], ancestors: Mapping[str, set[str]], sc: Scenarios, capacity: float
) -> Choice:
    """The usual approach, for comparison: the most valuable set whose *expected*
    time fits (exact for small goal sets)."""
    todo = set(sc.concepts)
    goals = [g for g in values if values[g] > 0]
    best: tuple[float, float, tuple[str, ...]] = (0.0, 0.0, ())
    for k in range(len(goals), 0, -1):
        for combo in combinations(goals, k):
            v = sum(values[g] for g in combo)
            if v < best[0]:
                continue
            p, mean, _ = _evaluate(combo, sc, ancestors, todo, capacity)
            if mean <= capacity and (v, -mean) > best[:2]:
                best = (v, -mean, combo)
    picked = best[2]
    p, mean, p90 = _evaluate(picked, sc, ancestors, todo, capacity) if picked else (1.0, 0.0, 0.0)
    return Choice(
        picked, tuple(g for g in goals if g not in picked), round(best[0], 3), round(p, 3),
        round(mean, 1), round(p90, 1), round(capacity, 1),
    )  # fmt: skip


def hours_for_all(
    values: Mapping[str, float],
    ancestors: Mapping[str, set[str]],
    sc: Scenarios,
    capacity_at: Callable[[float], float],
    *,
    confidence: float = 0.9,
    lo: float = 1.0,
    hi: float = 60.0,
) -> float | None:
    """Fewest hours a week (to 0.5 h) at which every goal fits with ``confidence``;
    ``capacity_at(hours)`` gives the minutes available by the deadline."""
    todo = set(sc.concepts)
    goals = [g for g in values if values[g] > 0]
    need = sorted(sc.totals(_closure(goals, ancestors, todo)))
    q = need[min(len(need) - 1, math.ceil(confidence * len(need)) - 1)]
    if capacity_at(hi) < q:
        return None
    while hi - lo > 0.5:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if capacity_at(mid) < q else (lo, mid)
    return round(hi * 2) / 2
