"""Bi-directional calendar feedback: read what really happened, then re-fit the
rest of the plan into the learner's real free time (claim F).

Most study planners only *push* a fixed schedule; one missed day breaks it.  Here
the loop closes:

1. **Read back** - the learner's log (done / partly done / missed sessions) and,
   optionally, their real calendar (busy times from an ``.ics`` export).
2. **Adherence velocity** - an exponentially-weighted share of planned minutes
   actually studied.  Remaining work is inflated by it, so the new plan is
   realistic rather than optimistic.
3. **Fatigue index** - per day, how much busier the calendar is than the
   learner's usual day of that weekday (so a normal workday is not "draining",
   an extra evening event is).  A dense day gets a lower cap and shorter blocks.
4. **Split and re-fit** - remaining work (in prerequisite order) is cut into
   micro-blocks and packed into the free gaps of the study windows,
   earliest-first.

Why earliest-first is right: the work order is fixed by the prerequisite DAG
and work is preemptible (a lesson may be split across gaps).  For a fixed
sequence of preemptible jobs on one machine whose capacity varies over time,
filling capacity in time order gives every prefix of jobs its earliest
possible completion time - any schedule that finishes job *k* earlier would
have to put some of jobs 1..k into capacity before the greedy one does, which
the greedy never leaves unused (exchange argument).  Block rules (minimum block
length, daily cap, a break between blocks) only shrink the capacity; the
argument holds over the capacity that remains.

Baseline for comparison (what static calendars do): the missed session is moved
to the next day whole, and everything after it shifts by the same number of
days.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from itertools import pairwise

MIN_BLOCK = 15  # minutes: shorter blocks aren't worth the context switch
BREAK = 5  # minutes between two blocks in the same gap
WAKING = (8 * 60, 22 * 60)  # waking window used for the fatigue index

Interval = tuple[datetime, datetime]


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Work:
    """One remaining piece of the plan (a lesson, practice or review)."""

    id: str
    concept: str
    title: str
    minutes: float
    kind: str = "teach"
    hardness: float = 1.0  # this learner's time-to-master, relative (velocity-aware, claim G)


@dataclass(frozen=True, slots=True)
class LogEntry:
    """What happened to one planned study day."""

    day: date
    planned_minutes: float
    done_minutes: float


# windows: weekday (0 = Monday) -> list of (start minute, end minute) of the day
Windows = dict[int, list[tuple[int, int]]]


def default_windows(hours_per_week: float) -> Windows:
    """Evenings on weekdays and two blocks on weekends, sized to the hours offered.
    Weekends carry about 1.5x a weekday's time."""
    per_week = max(1.0, hours_per_week) * 60
    weekday = per_week / (5 + 2 * 1.5)
    weekend = weekday * 1.5
    out: Windows = {}
    for d in range(5):
        start = 19 * 60
        out[d] = [(start, min(23 * 60, start + round(weekday * 1.25)))]
    for d in (5, 6):
        half = round(weekend * 1.25 / 2)
        out[d] = [(10 * 60, 10 * 60 + half), (16 * 60, 16 * 60 + half)]
    return out


def availability_windows() -> Windows:
    """When a learner *could* study (the planner picks inside these, up to the
    weekly hours they offered): weekday evenings and most of the weekend day."""
    out: Windows = {d: [(18 * 60, 22 * 60)] for d in range(5)}
    out[5] = [(9 * 60, 13 * 60), (14 * 60, 20 * 60)]
    out[6] = [(9 * 60, 13 * 60), (14 * 60, 20 * 60)]
    return out


# --------------------------------------------------------------------------- #
# reading the calendar back
# --------------------------------------------------------------------------- #
_DT = re.compile(r"^(DTSTART|DTEND)(;[^:]*)?:(\d{8})(T(\d{6})(Z)?)?$")


def parse_ics_busy(text: str) -> list[Interval]:
    """Busy intervals from an iCalendar export (Google/Outlook/Apple).

    Handles timed events (local or ``Z``), all-day events (``VALUE=DATE``) and
    folded lines.  Times are kept as naive local wall-clock times; ``Z`` times
    are taken as-is (the learner's export is assumed to be in their zone)."""
    lines: list[str] = []
    for raw in text.splitlines():
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw.strip())
    out: list[Interval] = []
    start: datetime | None = None
    end: datetime | None = None
    transparent = False
    for ln in lines:
        if ln == "BEGIN:VEVENT":
            start, end, transparent = None, None, False
        elif ln.startswith("TRANSP:") and ln.endswith("TRANSPARENT"):
            transparent = True  # marked "free" in the calendar
        elif m := _DT.match(ln):
            d = datetime.strptime(m.group(3), "%Y%m%d")
            if m.group(5):
                d = d.replace(hour=int(m.group(5)[:2]), minute=int(m.group(5)[2:4]))
            if m.group(1) == "DTSTART":
                start = d
            else:
                end = d
        elif ln == "END:VEVENT" and start is not None and not transparent:
            if end is None:
                end = start + (timedelta(days=1) if start.time() == time(0) else timedelta(hours=1))
            if end > start:
                out.append((start, end))
    return sorted(out)


def by_day(busy: Sequence[Interval]) -> dict[date, list[Interval]]:
    """Events bucketed by every day they touch - lookups per day stay cheap."""
    out: dict[date, list[Interval]] = {}
    for a, b in busy:
        d = a.date()
        while d <= b.date():
            if d < b.date() or b.time() != time(0) or d == a.date():
                out.setdefault(d, []).append((a, b))
            d += timedelta(days=1)
    return out


def busy_minutes_on(day: date, busy: Sequence[Interval], window: tuple[int, int] = WAKING) -> float:
    lo = datetime.combine(day, time()) + timedelta(minutes=window[0])
    hi = datetime.combine(day, time()) + timedelta(minutes=window[1])
    spans = sorted((max(a, lo), min(b, hi)) for a, b in busy if a < hi and b > lo)
    total = 0.0
    cur_a: datetime | None = None
    cur_b: datetime | None = None
    for a, b in spans:  # union of overlapping events
        if cur_b is None or a > cur_b:
            if cur_a is not None and cur_b is not None:
                total += (cur_b - cur_a).total_seconds() / 60
            cur_a, cur_b = a, b
        else:
            cur_b = max(cur_b, b)
    if cur_a is not None and cur_b is not None:
        total += (cur_b - cur_a).total_seconds() / 60
    return total


def fatigue_index(day: date, busy: Sequence[Interval], baseline: float = 0.0) -> float:
    """How much busier this day is than the learner's usual day of this kind,
    as a share of the waking hours left after that usual load, 0..1.

    A normal workday is *not* draining by itself (baseline); an extra evening
    meeting or a packed Saturday is."""
    awake = WAKING[1] - WAKING[0]
    extra = busy_minutes_on(day, busy) - baseline
    return max(0.0, min(1.0, extra / max(60.0, awake - baseline)))


def typical_busy(buckets: dict[date, list[Interval]], first: date, last: date) -> dict[int, float]:
    """The learner's usual day: median busy minutes over ``first``..``last``, for
    weekdays and for weekends separately (robust even with a short calendar)."""
    weekday: list[float] = []
    weekend: list[float] = []
    d = first
    while d <= last:
        (weekday if d.weekday() < 5 else weekend).append(busy_minutes_on(d, buckets.get(d, [])))
        d += timedelta(days=1)

    def median(xs: list[float]) -> float:
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else 0.0

    wd, we = median(weekday), median(weekend)
    return {k: wd if k < 5 else we for k in range(7)}


def adherence(log: Iterable[LogEntry], alpha: float = 0.35, prior: float = 1.0) -> float:
    """Exponentially-weighted share of planned minutes actually studied (recent
    days count most).  Starts from ``prior`` (1.0 = trust the plan)."""
    a = prior
    for e in sorted(log, key=lambda e: e.day):
        if e.planned_minutes <= 0:
            continue
        a = (1 - alpha) * a + alpha * min(1.5, e.done_minutes / e.planned_minutes)
    return max(0.2, min(1.25, a))


# --------------------------------------------------------------------------- #
# output
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Block:
    day: date
    start: int  # minute of the day
    end: int
    work_id: str
    concept: str
    title: str
    kind: str
    part: int
    parts: int


@dataclass(frozen=True, slots=True)
class DayPlan:
    day: date
    busy_minutes: float
    fatigue: float
    cap_minutes: float
    max_block: int
    study_minutes: float


@dataclass(slots=True)
class Reschedule:
    blocks: list[Block]
    days: list[DayPlan]
    feasible: bool
    finish: date | None
    deadline: date
    remaining_minutes: float  # after the adherence inflation
    unplaced_minutes: float
    hours_per_week_needed: float
    reasons: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# the algorithm
# --------------------------------------------------------------------------- #
def _gaps(day: date, windows: Windows, busy: Sequence[Interval]) -> list[tuple[int, int]]:
    """Free minutes of the study windows on ``day`` after removing busy events."""
    base = datetime.combine(day, time())
    out: list[tuple[int, int]] = []
    for w0, w1 in windows.get(day.weekday(), []):
        segs = [(w0, w1)]
        for a, b in busy:
            a_m = (a - base).total_seconds() / 60
            b_m = (b - base).total_seconds() / 60
            if b_m <= w0 or a_m >= w1:
                continue
            nxt: list[tuple[int, int]] = []
            for s0, s1 in segs:
                if b_m <= s0 or a_m >= s1:
                    nxt.append((s0, s1))
                    continue
                if a_m > s0:
                    nxt.append((s0, math.floor(a_m)))
                if b_m < s1:
                    nxt.append((math.ceil(b_m), s1))
            segs = nxt
        out += [(s0, s1) for s0, s1 in segs if s1 - s0 >= MIN_BLOCK]
    return sorted(out)


def day_rules(fatigue: float, base_cap: float) -> tuple[float, int]:
    """(study cap in minutes, longest block) for a day with this fatigue index.
    Light days allow long focus blocks; dense days get short micro-blocks."""
    cap = base_cap * (1.0 - 0.6 * fatigue)
    max_block = 60 if fatigue < 0.25 else 30 if fatigue < 0.5 else MIN_BLOCK
    return max(MIN_BLOCK, cap), max_block


def reschedule(
    work: Sequence[Work],
    *,
    start: date,
    deadline: date,
    windows: Windows,
    busy: Sequence[Interval] = (),
    adherence_rate: float = 1.0,
    base_cap: float | None = None,
    weekly_cap: float | None = None,
    week_done: float = 0.0,
    now_minute: int | None = None,
    match: bool = False,
    ancestors: Mapping[str, set[str]] | None = None,
    window: int = 3,
    slot_score: Callable[[date, int], float] | None = None,
    block_cap: int | None = None,
) -> Reschedule:
    """Split the remaining work into micro-blocks and fit them, earliest first,
    into the free gaps between ``start`` and ``deadline``.

    ``adherence_rate`` < 1 inflates the work (you tend to do less than planned),
    ``base_cap`` is the most study on one ordinary day, ``weekly_cap`` the most
    in one Monday-Sunday week (the hours the learner offered; ``week_done`` of it
    already used before ``start``), and
    ``now_minute`` skips the part of ``start`` that has already passed.

    ``match`` (velocity-aware, claim G): when a new piece of work starts, look
    ``window`` items ahead and take the *hardest* ready one on a light day, the
    *easiest* on a busy day.  "Ready" = no earlier unfinished item is one of its
    prerequisites (``ancestors``: concept -> all its prerequisites); reviews and
    work already in progress are never moved.

    ``slot_score`` (claim G4): with a weekly budget, spend each week's hours in
    the best-scoring free slots first (score x a fatigue discount) rather than
    the earliest; work still runs in order through the chosen slots.
    ``block_cap`` (claim G5): the learner's own best block length."""
    weekly = sum(b - a for ws in windows.values() for a, b in ws)
    if base_cap is None:
        base_cap = 1.5 * weekly / max(1, len([d for d in windows if windows[d]]))
    inflate = 1.0 / max(0.2, min(1.0, adherence_rate))
    queue = [(w, w.minutes * inflate) for w in work if w.minutes > 0]
    total = sum(m for _, m in queue)
    parts_left = {w.id: m for w, m in queue}
    parts_n: dict[str, int] = {}

    blocks: list[Block] = []
    days: list[DayPlan] = []
    buckets = by_day(busy)
    week_used = 0.0
    # the learner's usual day, measured only over the dates their calendar covers
    known = [d for d in buckets if start <= d <= deadline]
    usual = typical_busy(buckets, min(known), max(known)) if known else dict.fromkeys(range(7), 0.0)
    chosen = (
        _best_slots(
            start, deadline, windows, buckets, usual, slot_score, weekly_cap, week_done, base_cap
        )
        if slot_score is not None and weekly_cap is not None
        else None
    )
    qi = 0
    day = start
    while day <= deadline and qi < len(queue):
        today_busy = buckets.get(day, [])
        fat = fatigue_index(day, today_busy, usual[day.weekday()])
        cap, max_block = day_rules(fat, base_cap)
        if block_cap is not None:
            max_block = max(MIN_BLOCK, min(max_block, block_cap))
        if weekly_cap is not None:
            if day == start:
                week_used = week_done  # already studied earlier this week
            elif day.weekday() == 0:
                week_used = 0.0
            cap = min(cap, max(0.0, weekly_cap - week_used))
        used = 0.0
        for g0, g1 in (
            chosen.get(day, []) if chosen is not None else _gaps(day, windows, today_busy)
        ):
            t = g0 if (now_minute is None or day != start) else max(g0, now_minute)
            while qi < len(queue) and g1 - t >= MIN_BLOCK and cap - used >= MIN_BLOCK:
                if match and parts_n.get(queue[qi][0].id, 0) == 0:
                    _pull_forward(queue, qi, window, light=fat < 0.25, ancestors=ancestors or {})
                w, _ = queue[qi]
                left = parts_left[w.id]
                room = min(g1 - t, max_block, cap - used)
                take = left if left <= room else room
                # never leave a crumb shorter than a block behind: take less now,
                # or wait for a bigger gap if the piece can't be split cleanly
                if 0 < left - take < MIN_BLOCK:
                    if left <= min(g1 - t, cap - used) and left <= room + MIN_BLOCK:
                        take = left  # finish it: at most one block longer than usual
                    elif left - MIN_BLOCK >= MIN_BLOCK:
                        take = left - MIN_BLOCK
                    else:
                        break
                take = max(1, round(take))
                parts_n[w.id] = parts_n.get(w.id, 0) + 1
                blocks.append(
                    Block(day, t, t + take, w.id, w.concept, w.title, w.kind, parts_n[w.id], 0)
                )
                parts_left[w.id] = left - take
                used += take
                t += take + BREAK
                if parts_left[w.id] <= 0.5:
                    qi += 1
        days.append(DayPlan(day, busy_minutes_on(day, today_busy), fat, cap, max_block, used))
        week_used = (week_used if weekly_cap is not None else 0.0) + used
        day += timedelta(days=1)

    # number the parts ("2 of 3")
    totals = parts_n
    blocks = [
        Block(
            b.day, b.start, b.end, b.work_id, b.concept, b.title, b.kind, b.part, totals[b.work_id]
        )
        for b in blocks
    ]
    unplaced = sum(max(0.0, parts_left[w.id]) for w, _ in queue[qi:])
    feasible = qi >= len(queue)
    finish = blocks[-1].day if blocks else None
    span_weeks = max(1 / 7, ((deadline - start).days + 1) / 7)
    needed = (total / span_weeks) / 60 if not feasible else 0.0
    reasons: list[str] = []
    if adherence_rate < 0.98:
        reasons.append(
            f"You've been studying about {round(adherence_rate * 100)}% of planned time, so the "
            f"remaining work is planned as {round(total)} minutes "
            f"instead of {round(total / inflate)}."
        )
    dense = [d for d in days if d.fatigue >= 0.5]
    if dense:
        reasons.append(
            f"{len(dense)} busy day(s) in your calendar get short {MIN_BLOCK}-minute blocks "
            "and a lower cap."
        )
    split = sum(1 for n in totals.values() if n > 1)
    if split:
        reasons.append(
            f"{split} lesson(s) were split into smaller blocks to fit the gaps in your days."
        )
    if not feasible:
        reasons.append(
            f"{round(unplaced)} minutes don't fit before the deadline: "
            f"about {needed:.1f} hours a week would be needed."
        )
    return Reschedule(blocks, days, feasible, finish, deadline, total, unplaced, needed, reasons)


def _best_slots(
    start: date,
    deadline: date,
    windows: Windows,
    buckets: Mapping[date, list[Interval]],
    usual: Mapping[int, float],
    slot_score: Callable[[date, int], float],
    weekly_cap: float,
    week_done: float,
    base_cap: float,
) -> dict[date, list[tuple[int, int]]]:
    """Per Monday-Sunday week, the free pieces (gaps cut at slot boundaries) with
    the best scores, enough to cover the week's budget with some slack for
    breaks - never more on one day than that day's study cap allows."""
    from algorithms.study_context import BOUNDARIES

    out: dict[date, list[tuple[int, int]]] = {}
    week: list[tuple[float, date, int, int]] = []
    day_cap: dict[date, float] = {}

    def flush(budget: float) -> None:
        got = 0.0
        taken: dict[date, float] = {}
        for _score, d, a, b in sorted(week, key=lambda x: (-x[0], x[1], x[2])):
            if got >= budget * 1.15:
                break
            room = day_cap[d] * 1.15 - taken.get(d, 0.0)
            if room < MIN_BLOCK:
                continue  # that day is already full: the next-best slot elsewhere
            b = min(b, a + int(room))
            out.setdefault(d, []).append((a, b))
            taken[d] = taken.get(d, 0.0) + (b - a)
            got += b - a
        week.clear()

    budget = max(0.0, weekly_cap - week_done)
    day = start
    while day <= deadline:
        if day.weekday() == 0 and day != start:
            flush(budget)
            budget = weekly_cap
        fat = fatigue_index(day, buckets.get(day, []), usual[day.weekday()])
        day_cap[day] = day_rules(fat, base_cap)[0]
        for g0, g1 in _gaps(day, windows, buckets.get(day, [])):
            cuts = [g0, *[c for c in BOUNDARIES if g0 < c < g1], g1]
            for a, b in pairwise(cuts):
                if b - a >= MIN_BLOCK:
                    score = slot_score(day, (a + b) // 2) * (1.0 - 0.3 * fat)
                    week.append((score, day, a, b))
        day += timedelta(days=1)
    flush(budget)
    return {d: sorted(v) for d, v in out.items()}


def _pull_forward(
    queue: list[tuple[Work, float]],
    qi: int,
    window: int,
    *,
    light: bool,
    ancestors: Mapping[str, set[str]],
) -> None:
    """Move the best-matched ready item of ``queue[qi : qi + window]`` to ``qi``."""
    head = queue[qi][0]
    if head.kind in ("review", "retention"):
        return
    best = qi
    for j in range(qi + 1, min(len(queue), qi + window)):
        cand = queue[j][0]
        if cand.kind in ("review", "retention"):
            break  # reviews are anchors: never jump over them
        needs = ancestors.get(cand.concept, set())
        if any(queue[i][0].concept in needs for i in range(qi, j)):
            continue  # a prerequisite is still waiting
        cur = queue[best][0].hardness
        if (light and cand.hardness > cur) or (not light and cand.hardness < cur):
            best = j
    if best != qi:
        queue.insert(qi, queue.pop(best))


def naive_shift(
    work: Sequence[Work],
    *,
    start: date,
    deadline: date,
    windows: Windows,
    busy: Sequence[Interval] = (),
    missed_days: int = 0,
) -> Reschedule:
    """What a static calendar does after a miss: keep each lesson whole, keep
    the original one-lesson-after-another daily pattern, push everything back by
    the missed days, and ignore the calendar's busy times (they clash)."""
    blocks: list[Block] = []
    buckets = by_day(busy)
    day = start + timedelta(days=missed_days)
    qi = 0
    clashes = 0
    while qi < len(work) and day <= deadline + timedelta(days=365):
        for g0, g1 in sorted(windows.get(day.weekday(), [])):
            t = g0
            while qi < len(work) and t + work[qi].minutes <= g1 + 1:
                w = work[qi]
                end = t + round(w.minutes)
                s_dt = datetime.combine(day, time()) + timedelta(minutes=t)
                e_dt = datetime.combine(day, time()) + timedelta(minutes=end)
                if any(a < e_dt and b > s_dt for a, b in buckets.get(day, [])):
                    clashes += 1
                blocks.append(Block(day, t, end, w.id, w.concept, w.title, w.kind, 1, 1))
                t = end + BREAK
                qi += 1
            if qi < len(work) and t == g0 and work[qi].minutes > g1 - g0:
                # a lesson longer than any window: a static plan just overruns it
                w = work[qi]
                blocks.append(
                    Block(day, g0, g0 + round(w.minutes), w.id, w.concept, w.title, w.kind, 1, 1)
                )
                qi += 1
        day += timedelta(days=1)
    finish = blocks[-1].day if blocks else None
    feasible = finish is not None and finish <= deadline and qi >= len(work)
    reasons = [f"{clashes} block(s) clash with events in your calendar."] if clashes else []
    return Reschedule(
        blocks, [], feasible, finish, deadline, sum(w.minutes for w in work), 0.0, 0.0, reasons
    )


def hhmm(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"
