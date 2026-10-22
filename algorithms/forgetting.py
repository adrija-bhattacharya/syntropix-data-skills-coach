"""Claim H3 - forgetting learned per learner *and per topic*, reviewed just in time.

The planner already models forgetting with one half-life for everyone and
every topic (``config.forgetting_half_life_h``).  Here it is **measured**:

1. **recalls** - every time the learner answers a topic again after a pause of
   at least :data:`MIN_GAP_H`, that answer is a recall test after ``gap`` days
   (:func:`recalls`, read from the practice telemetry);
2. **half-life per topic** - a Bayesian fit on a log-spaced grid with
   ``P(correct | gap, H) = FLOOR + (CEIL - FLOOR) * 2^(-gap / H)``.  The prior
   for a topic is centred on the half-lives of the topics it builds on (topics
   built on the same base are forgotten alike), else on the learner's own
   overall half-life, else on the default; a topic's own recalls then move it
   (:func:`fit_half_lives`);
3. **when to review** - a known topic is due either when its predicted recall
   falls to :data:`THRESHOLD`, or - earlier - the day before a scheduled lesson
   that needs it would start with it below :data:`READY` (*just in time*:
   prerequisites are refreshed right before they are used) (:func:`plan_reviews`);
4. **where** - 10-minute reviews go into real free gaps of the learner's
   calendar around the planned study blocks, on the due day or up to
   :data:`SLACK_DAYS` before it (:func:`place_reviews`).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

MIN_GAP_H = 12.0
FLOOR, CEIL = 0.2, 0.95  # guessing / slipping
DEFAULT_HALF_LIFE_D = 5.0  # = config.forgetting_half_life_h (120 h)
PRIOR_SIGMA = 0.9  # spread of the prior, in log-days
GRID: list[float] = [0.5 * math.pow(720.0, i / 79) for i in range(80)]  # 0.5 .. 360 days
THRESHOLD = 0.7  # review a known topic before its recall drops below this
READY = 0.8  # a lesson should start with its prerequisites at least this fresh
REVIEW_MIN = 10
SLACK_DAYS = 3
MAX_REVIEWS_PER_DAY = 2


class EventLike(Protocol):
    at: str
    correct: bool
    concept: str


@dataclass(frozen=True, slots=True)
class Recall:
    concept: str
    gap_days: float
    correct: bool


@dataclass(frozen=True, slots=True)
class HalfLife:
    concept: str
    days: float
    recalls: int
    source: str  # measured | from prerequisites | your average | default


@dataclass(frozen=True, slots=True)
class Review:
    concept: str
    due: date
    recall_at_due: float
    reason: str  # "before:<concept>" | "fading"
    priority: int  # topics later in the plan that build on it


@dataclass(frozen=True, slots=True)
class Placed:
    review: Review
    day: date
    start: int  # minute of the day
    end: int
    late: bool  # no room before it was due


# ----------------------------------------------------------------- recalls
def recalls(events: Iterable[EventLike], min_gap_h: float = MIN_GAP_H) -> list[Recall]:
    """Answers given after a pause on the same topic, with the pause in days."""
    last: dict[str, datetime] = {}
    out: list[Recall] = []
    for e in sorted(events, key=lambda e: e.at):
        if not e.concept:
            continue
        t = datetime.fromisoformat(e.at)
        prev = last.get(e.concept)
        if prev is not None:
            gap_h = (t - prev).total_seconds() / 3600
            if gap_h >= min_gap_h:
                out.append(Recall(e.concept, gap_h / 24, bool(e.correct)))
        last[e.concept] = t
    return out


def last_seen(events: Iterable[EventLike]) -> dict[str, date]:
    out: dict[str, date] = {}
    for e in events:
        if e.concept:
            d = datetime.fromisoformat(e.at).date()
            out[e.concept] = max(out.get(e.concept, d), d)
    return out


# --------------------------------------------------------------------- fit
def p_recall(gap_days: float, half_life: float) -> float:
    return FLOOR + (CEIL - FLOOR) * math.pow(2.0, -gap_days / half_life)


def retention(gap_days: float, half_life: float) -> float:
    """Share of the topic still remembered after ``gap_days`` (1 = just studied)."""
    return math.pow(2.0, -max(0.0, gap_days) / half_life)


def _posterior(rs: Sequence[Recall], center: float, sigma: float = PRIOR_SIGMA) -> float:
    """Posterior median half-life (days) on the grid."""
    mu = math.log(center)
    logw = []
    for h in GRID:
        lw = -((math.log(h) - mu) ** 2) / (2 * sigma**2)
        for r in rs:
            p = p_recall(r.gap_days, h)
            lw += math.log(p if r.correct else 1.0 - p)
        logw.append(lw)
    top = max(logw)
    w = [math.exp(x - top) for x in logw]
    total, acc = sum(w), 0.0
    for h, x in zip(GRID, w):
        acc += x
        if acc >= total / 2:
            return h
    return GRID[-1]


def _topo(concepts: Sequence[str], prereqs: Mapping[str, Sequence[str]]) -> list[str]:
    seen: set[str] = set()
    order: list[str] = []

    def visit(c: str) -> None:
        if c in seen:
            return
        seen.add(c)
        for p in prereqs.get(c, ()):
            if p in concepts:
                visit(p)
        order.append(c)

    for c in concepts:
        visit(c)
    return order


def fit_half_lives(
    rs: Sequence[Recall],
    concepts: Sequence[str],
    prereqs: Mapping[str, Sequence[str]],
    default_days: float = DEFAULT_HALF_LIFE_D,
) -> dict[str, HalfLife]:
    """Half-life per topic, from own recalls, prerequisites, then the learner's average."""
    learner = _posterior(rs, default_days) if rs else default_days
    by: dict[str, list[Recall]] = {}
    for r in rs:
        by.setdefault(r.concept, []).append(r)
    out: dict[str, HalfLife] = {}
    for c in _topo(concepts, prereqs):
        ups = [out[p] for p in prereqs.get(c, ()) if p in out and out[p].source != "default"]
        informed = [u for u in ups if u.source in ("measured", "from prerequisites")]
        if informed:
            center = math.exp(sum(math.log(u.days) for u in informed) / len(informed))
            source = "from prerequisites"
        elif rs:
            center, source = learner, "your average"
        else:
            center, source = default_days, "default"
        own = by.get(c, [])
        if own:
            out[c] = HalfLife(c, round(_posterior(own, center), 2), len(own), "measured")
        else:
            out[c] = HalfLife(c, round(center, 2), 0, source)
    return out


# --------------------------------------------------------------- reviews
def _descendants(
    concepts: Sequence[str], prereqs: Mapping[str, Sequence[str]]
) -> dict[str, set[str]]:
    kids: dict[str, set[str]] = {c: set() for c in concepts}
    for c in concepts:
        for p in prereqs.get(c, ()):
            kids.setdefault(p, set()).add(c)
    out: dict[str, set[str]] = {}
    for c in concepts:
        stack, seen = list(kids.get(c, ())), set()
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(kids.get(x, ()))
        out[c] = seen
    return out


def plan_reviews(
    known: Mapping[str, date],
    half_lives: Mapping[str, HalfLife],
    prereqs: Mapping[str, Sequence[str]],
    lesson_starts: Mapping[str, date],
    *,
    today: date,
    until: date,
    unmastered: set[str] | None = None,
    threshold: float = THRESHOLD,
    ready: float = READY,
) -> list[Review]:
    """When each known topic needs a review.

    ``known``: topic -> the day it was last practised; ``lesson_starts``: topic
    -> the day its first planned lesson starts (the topics still to learn)."""
    concepts = list(dict.fromkeys([*known, *lesson_starts, *prereqs]))
    desc = _descendants(concepts, prereqs)
    todo = unmastered if unmastered is not None else set(lesson_starts)
    out: list[Review] = []
    for c, seen in known.items():
        h = half_lives[c].days if c in half_lives else DEFAULT_HALF_LIFE_D
        fade = seen + timedelta(days=h * math.log2(1 / threshold))
        due, reason = fade, "fading"
        # just in time: the earliest planned lesson that needs c, if c would be stale by then
        needs = sorted(
            (d, b) for b, d in lesson_starts.items() if c in prereqs.get(b, ()) and d >= today
        )
        for d, b in needs:
            if retention((d - seen).days, h) < ready and d - timedelta(days=1) < due:
                due, reason = d - timedelta(days=1), f"before:{b}"
            break
        due = max(today, due)
        if due > until:
            continue
        out.append(
            Review(
                c, due, round(retention((due - seen).days, h), 3), reason,
                len(desc.get(c, set()) & todo),
            )
        )  # fmt: skip
    return sorted(out, key=lambda r: (r.due, -r.priority))


Interval = tuple[datetime, datetime]


def place_reviews(
    reviews: Sequence[Review],
    blocks: Iterable[Any],
    windows: dict[int, list[tuple[int, int]]],
    busy: Sequence[Interval],
    *,
    today: date,
    now_minute: int = 0,
    slot_score: Callable[[date, int], float] | None = None,
    minutes: int = REVIEW_MIN,
) -> list[Placed]:
    """Put each review in a free gap on its due day, or up to SLACK_DAYS before
    (else after, marked late), never on top of a study block or an event."""
    from algorithms.reschedule import _gaps

    taken: list[Interval] = list(busy)
    for b in blocks:
        lo = datetime.combine(b.day, datetime.min.time())
        taken.append((lo + timedelta(minutes=b.start), lo + timedelta(minutes=b.end)))
    per_day: dict[date, int] = {}
    out: list[Placed] = []
    for r in sorted(reviews, key=lambda r: (r.due, -r.priority)):
        before = [r.due - timedelta(days=k) for k in range(SLACK_DAYS + 1)]
        after = [r.due + timedelta(days=k) for k in range(1, SLACK_DAYS + 1)]
        placed = None
        for day in [d for d in before if d >= today] + after:
            if per_day.get(day, 0) >= MAX_REVIEWS_PER_DAY:
                continue
            gaps = _gaps(day, windows, taken)
            starts = []
            for a, b in gaps:
                a = max(a, now_minute + 5) if day == today else a
                if b - a >= minutes:
                    starts.append(a)
            if not starts:
                continue
            start = max(starts, key=lambda m: (slot_score(day, m) if slot_score else 0.0, -m))
            placed = Placed(r, day, start, start + minutes, day > r.due)
            break
        if placed is None:
            continue
        lo = datetime.combine(placed.day, datetime.min.time())
        taken.append((lo + timedelta(minutes=placed.start), lo + timedelta(minutes=placed.end + 5)))
        per_day[placed.day] = per_day.get(placed.day, 0) + 1
        out.append(placed)
    return out
