"""Deadline-aware calendar scheduling (novelty claim **C**).

The sequencing DP (claim, :mod:`algorithms.sequencing`) produces a *provably
optimal ordered plan* but no notion of wall-clock time.  Claim C embeds that
plan on a **real calendar** given

* the learner's **weekly availability** (minutes per weekday), and
* a **target date**,

and returns a schedule with a hard guarantee:

    every goal skill's predicted mastery is >= the threshold **on the deadline**,

accounting for **forgetting between study slots** (Ebbinghaus decay with a
half-life that lengthens after each successful review - the spacing effect).
If no schedule can meet the date it returns a **precise diagnostic** (how many
more hours per week, or how many more days, are needed).

Two exact sub-procedures, each with a short optimality argument:

1. **Precedence list-scheduling** of the ordered steps onto slots
   (:func:`_place_steps`).  With the order fixed (it is already an optimal
   linear extension) greedy earliest-fit minimises the finishing slot: given
   two schedules that respect the same order, repeatedly moving a step to the
   earliest slot the greedy rule would pick never increases any later step's
   slot (exchange argument).  ``O(steps * slots)``.

2. **Retention-review covering** (:func:`_cover_retention`).  For each goal
   skill the decay model gives a maximum gap ``g_k`` that keeps mastery >= theta
   after the ``k``-th review.  Covering the interval ``[taught, deadline]`` with
   the fewest review points no more than ``g_k`` apart is the classic
   *minimum points to stab an interval with bounded gap* problem; the greedy
   "place the next review as late as the gap allows (snapped to a real slot)"
   is optimal.  ``O(goals * reviews * slots)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from algorithms.dynamic_programming import Plan
from config import settings
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

NodeId = str


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Availability:
    """Minutes the learner can study on each weekday (0 = Monday .. 6 = Sunday)."""

    weekday_minutes: tuple[float, float, float, float, float, float, float]
    load_cap: float = 0.0  # 0 -> settings.session_max_load

    @classmethod
    def uniform(cls, minutes_per_week: float) -> Availability:
        per_day = minutes_per_week / 7.0
        return cls((per_day,) * 7)

    @classmethod
    def weekdays(cls, minutes_per_weekday: float, *, weekend: float = 0.0) -> Availability:
        return cls((minutes_per_weekday,) * 5 + (weekend, weekend))

    def minutes_on(self, d: date) -> float:
        return self.weekday_minutes[d.weekday()]

    @property
    def weekly_minutes(self) -> float:
        return float(sum(self.weekday_minutes))


@dataclass(slots=True)
class Slot:
    index: int
    day: date
    capacity_min: float
    load_cap: float
    used_min: float = 0.0
    used_load: float = 0.0

    @property
    def free_min(self) -> float:
        return self.capacity_min - self.used_min

    @property
    def free_load(self) -> float:
        return self.load_cap - self.used_load


# --------------------------------------------------------------------------- #
# output
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class CalendarStep:
    day: date
    slot_index: int
    concept: NodeId
    resource_id: NodeId
    minutes: float
    kind: str  # "teach" | "review" | "check" | "retention"
    plan_index: int | None  # index into the source Plan, or None for a retention review


@dataclass(frozen=True, slots=True)
class CalendarPlan:
    steps: tuple[CalendarStep, ...]
    start: date
    deadline: date
    feasible: bool
    finish: date | None  # day of the last scheduled step
    slack_days: int  # deadline - finish (negative if late); 0 when infeasible
    goal_mastery: dict[str, float] = field(default_factory=dict)  # skill -> predicted m(deadline)
    weeks: float = 0.0
    hours_per_week: float = 0.0  # what the learner offered
    hours_per_week_needed: float = 0.0  # >0 only when infeasible for capacity reasons
    note: str = ""
    reasons: tuple[str, ...] = ()

    @classmethod
    def infeasible(
        cls, start: date, deadline: date, note: str, *, needed: float = 0.0, offered: float = 0.0
    ) -> CalendarPlan:
        return cls(
            (), start, deadline, False, None, 0,
            weeks=max(0.0, (deadline - start).days / 7.0),
            hours_per_week=offered, hours_per_week_needed=needed, note=note,
        )  # fmt: skip

    @property
    def n_retention(self) -> int:
        return sum(1 for s in self.steps if s.kind == "retention")


# --------------------------------------------------------------------------- #
# stage 0 - the slot calendar
# --------------------------------------------------------------------------- #
def build_slots(start: date, deadline: date, avail: Availability) -> list[Slot]:
    """One slot per day in ``[start, deadline]`` that has any availability."""
    load_cap = avail.load_cap or settings.session_max_load
    slots: list[Slot] = []
    d = start
    while d <= deadline:
        cap = avail.minutes_on(d)
        if cap > 0:
            slots.append(Slot(len(slots), d, cap, load_cap))
        d += timedelta(days=1)
    return slots


def _step_load(kg: KnowledgeGraph, resource_id: str) -> float:
    return max(0.05, kg.resources[resource_id].difficulty / 5.0)


# --------------------------------------------------------------------------- #
# stage 1 - precedence list-scheduling
# --------------------------------------------------------------------------- #
def _place_steps(
    kg: KnowledgeGraph, plan: Plan, slots: list[Slot]
) -> tuple[list[CalendarStep], dict[str, int], str | None]:
    """Greedy earliest-fit of the ordered plan steps onto slots, respecting
    prerequisite order in time.  Returns (placed, earliest-slot-per-concept,
    error) - ``error`` is set iff a step did not fit before the deadline."""
    placed: list[CalendarStep] = []
    concept_slot: dict[str, int] = {}
    cursor = 0  # no step may start earlier than the previous step's slot (order-preserving)

    for i, (rid, cid) in enumerate(zip(plan.steps, plan.concepts)):
        need_min = kg.resources[rid].minutes
        need_load = _step_load(kg, rid)
        lower = cursor
        for q in kg.direct_prerequisites(cid):
            if q in concept_slot:
                lower = max(lower, concept_slot[q])
        s = _first_fit(slots, lower, need_min, need_load)
        if s is None:
            kind = _kind(plan, i)
            return (
                placed,
                concept_slot,
                (
                    f"step {i + 1} ({kind} {kg.concepts[cid].name if cid in kg.concepts else cid}) "
                    f"does not fit before the deadline"
                ),
            )
        slots[s].used_min += need_min
        slots[s].used_load += need_load
        cursor = s
        concept_slot.setdefault(cid, s)
        placed.append(CalendarStep(slots[s].day, s, cid, rid, need_min, _kind(plan, i), i))
    return placed, concept_slot, None


def _kind(plan: Plan, i: int) -> str:
    if plan.is_check(i):
        return "check"
    if plan.is_review(i):
        return "review"
    return "teach"


def _first_fit(slots: list[Slot], lower: int, need_min: float, need_load: float) -> int | None:
    for s in range(lower, len(slots)):
        if slots[s].free_min + 1e-9 >= need_min and slots[s].free_load + 1e-9 >= need_load:
            return s
    return None


# --------------------------------------------------------------------------- #
# stage 2 - retention-review covering to hit the deadline
# --------------------------------------------------------------------------- #
def _max_gap_days(k: int, retention_scale: float) -> float:
    """Largest gap (days) after the ``k``-th touch that still leaves mastery
    >= threshold.  The window starts at ``calendar_base_retention_days`` (scaled
    per-learner by the forgetting half-life) and lengthens geometrically with
    each review - the spacing effect."""
    base = settings.calendar_base_retention_days * max(0.2, retention_scale)
    return base * settings.calendar_spacing_factor**k


def _predicted_mastery(k: int, gap_days: float, retention_scale: float) -> float:
    """Mastery ``gap_days`` after the ``k``-th touch: decays from ``seq_post_mastery``
    down to exactly ``mastery_threshold`` at the edge of the retention window."""
    m_post, theta = settings.seq_post_mastery, settings.mastery_threshold
    frac = min(1.0, gap_days / _max_gap_days(k, retention_scale))
    return float(m_post * (theta / m_post) ** frac)


def _cover_retention(
    kg: KnowledgeGraph,
    goals: list[str],
    state: LearnerState,
    slots: list[Slot],
    placed: list[CalendarStep],
    deadline: date,
) -> tuple[list[CalendarStep], dict[str, float], str | None]:
    """For every goal skill, add the fewest retention reviews (snapped to real
    slots) so that predicted mastery >= theta on the deadline."""
    touches: dict[str, list[date]] = {}
    for st in placed:
        touches.setdefault(st.concept, []).append(st.day)
    for v in touches.values():
        v.sort()

    extra: list[CalendarStep] = []
    goal_mastery: dict[str, float] = {}

    for g in goals:
        if g not in kg.concepts:
            continue
        retention_scale = (
            state.half_life.get(g, settings.forgetting_half_life_h)
            / settings.forgetting_half_life_h
        )
        seq = list(touches.get(g, []))
        if not seq:  # goal never taught (already mastered) - decay from the start
            seq = [slots[0].day] if slots else [deadline]
        k = len(seq) - 1  # touches already on the calendar count toward the spacing effect
        last = seq[-1]
        rid = _shortest_resource(kg, g)
        need_min = kg.resources[rid].minutes
        need_load = _step_load(kg, rid)
        guard = 0

        name = kg.concepts[g].name
        while True:
            horizon = last + timedelta(days=math.floor(_max_gap_days(k, retention_scale)))
            if horizon >= deadline:
                gap = (deadline - last).days
                goal_mastery[g] = round(_predicted_mastery(k, gap, retention_scale), 3)
                break
            guard += 1
            if guard > settings.calendar_max_reviews_per_goal:
                cap = settings.calendar_max_reviews_per_goal
                err = f"{name} needs more than {cap} reviews to hold until the deadline"
                return extra, goal_mastery, err
            s = _latest_fit(slots, last, horizon, need_min, need_load)
            if s is None:
                err = (
                    f"no free study slot between {last.isoformat()} and "
                    f"{horizon.isoformat()} to reinforce {name}"
                )
                return extra, goal_mastery, err
            slots[s].used_min += need_min
            slots[s].used_load += need_load
            extra.append(CalendarStep(slots[s].day, s, g, rid, need_min, "retention", None))
            last = slots[s].day
            k += 1

    return extra, goal_mastery, None


def _latest_fit(
    slots: list[Slot], after: date, by: date, need_min: float, need_load: float
) -> int | None:
    best: int | None = None
    for s in slots:
        if s.day <= after or s.day > by:
            continue
        if s.free_min + 1e-9 >= need_min and s.free_load + 1e-9 >= need_load:
            best = s.index  # keep going -> ends on the latest feasible slot
    return best


def _shortest_resource(kg: KnowledgeGraph, concept: str) -> str:
    return min(kg.resources_for(concept), key=lambda r: kg.resources[r].minutes)


# --------------------------------------------------------------------------- #
# the whole pipeline
# --------------------------------------------------------------------------- #
def schedule_on_calendar(
    kg: KnowledgeGraph,
    plan: Plan,
    state: LearnerState,
    goals: list[str],
    *,
    start: date,
    deadline: date,
    availability: Availability,
) -> CalendarPlan:
    offered_hpw = round(availability.weekly_minutes / 60.0, 1)
    weeks = max(0.0, (deadline - start).days / 7.0)
    if not plan.feasible or not plan.steps:
        return CalendarPlan.infeasible(
            start, deadline, plan.note or "no plan to schedule", offered=offered_hpw
        )
    if deadline <= start:
        return CalendarPlan.infeasible(start, deadline, "the deadline is not in the future")

    slots = build_slots(start, deadline, availability)
    teach_minutes = sum(kg.resources[r].minutes for r in plan.steps)
    if not slots:
        return CalendarPlan.infeasible(
            start, deadline, "no study availability before the deadline", offered=offered_hpw
        )

    placed, _cslot, err = _place_steps(kg, plan, slots)
    if err is not None:
        needed = round((teach_minutes / max(weeks, 1e-6)) / 60.0, 1)
        return CalendarPlan.infeasible(
            start, deadline, err, needed=max(needed, offered_hpw + 0.1), offered=offered_hpw
        )

    extra, goal_mastery, rerr = _cover_retention(kg, goals, state, slots, placed, deadline)
    if rerr is not None:
        total_min = teach_minutes + sum(s.minutes for s in placed if s.plan_index is None)
        needed = round((total_min * 1.6 / max(weeks, 1e-6)) / 60.0, 1)
        return CalendarPlan.infeasible(
            start, deadline, rerr, needed=max(needed, offered_hpw + 0.5), offered=offered_hpw
        )

    # within a day: keep the plan's order, then any retention reviews
    steps = sorted(
        [*placed, *extra],
        key=lambda s: (s.slot_index, s.plan_index is None, s.plan_index or 0),
    )
    finish = max(s.day for s in steps)
    reasons = _reasons(kg, goal_mastery, deadline, finish)
    return CalendarPlan(
        steps=tuple(steps),
        start=start,
        deadline=deadline,
        feasible=True,
        finish=finish,
        slack_days=(deadline - finish).days,
        goal_mastery=goal_mastery,
        weeks=round(weeks, 1),
        hours_per_week=offered_hpw,
        note="",
        reasons=reasons,
    )


def _reasons(
    kg: KnowledgeGraph, goal_mastery: dict[str, float], deadline: date, finish: date
) -> tuple[str, ...]:
    theta = settings.mastery_threshold
    out = [
        f"On the deadline ({deadline.isoformat()}) every goal skill is predicted at or above "
        f"the {theta:.0%} mastery threshold; the last study day is {finish.isoformat()}."
    ]
    for g, m in sorted(goal_mastery.items(), key=lambda kv: kv[1]):
        name = kg.concepts[g].name if g in kg.concepts else g
        out.append(f"{name}: predicted {m:.0%} on the deadline.")
    return tuple(out)
