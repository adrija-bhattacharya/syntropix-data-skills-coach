"""Claim F - does reading the calendar back keep learners on their deadline?

    python -m benchmarks.reschedule_bench     # -> results/reschedule.{json,csv}

Simulated learners follow a study plan through real-looking weeks.  Three
policies plan and re-plan every morning from the same work, calendar and luck
(same seeds):

* **fixed calendar** - whole lessons in the study window, one after another;
  anything not done is pushed back to the next day and everything after it
  slides (what calendars that only *push* events do).  It never looks at the
  learner's calendar.
* **adaptive, no calendar** - the feedback loop without reading the calendar:
  adherence-adjusted workload, micro-blocks, earliest-fit re-planning, but the
  busy times are unknown.
* **adaptive + calendar** (the full loop) - also reads the learner's calendar:
  busy times are cut out of the study windows and dense days get a lower cap
  and shorter blocks (fatigue index).

Learner model (stated, so it can be audited):

* weekdays: work 09:00-17:30; an evening event (meeting, class, social) on
  ``p_evening`` of weekdays; a weekend event on ``p_weekend`` of weekend days;
* a block that overlaps a calendar event doesn't happen;
* otherwise a block is done with probability
  ``0.95 - 0.45 * fatigue - 0.12 * [block > 45 min and fatigue > 0.4]``
  (long sessions on draining days get skipped);
* on ``p_sick`` of days nothing is done at all.

Reported: share of learners who finish by the deadline, mean days late (for
those who are late), the share of planned blocks that clashed with an event,
and the average longest study block on high-fatigue days.
"""

from __future__ import annotations

import csv
import json
import random
import statistics
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from algorithms.reschedule import (
    BREAK,
    Block,
    Interval,
    LogEntry,
    Work,
    adherence,
    availability_windows,
    by_day,
    default_windows,
    fatigue_index,
    naive_shift,
    reschedule,
    typical_busy,
)

RESULTS = Path(__file__).resolve().parent.parent / "results"
START = date(2026, 1, 5)  # a Monday


@dataclass(frozen=True)
class Scenario:
    name: str
    p_evening: float
    p_weekend: float
    p_sick: float
    slack: float  # deadline = needed weeks * (1 + slack)


SCENARIOS = (
    Scenario("light calendar", 0.15, 0.15, 0.03, 0.30),
    Scenario("busy calendar", 0.40, 0.35, 0.05, 0.30),
    Scenario("very busy + tight deadline", 0.55, 0.50, 0.06, 0.15),
)
POLICIES = ("fixed calendar", "adaptive, no calendar", "adaptive + calendar")


def _calendar(rng: random.Random, days: int, sc: Scenario) -> list[Interval]:
    out: list[Interval] = []
    for k in range(days):
        d = START + timedelta(days=k)
        base = datetime.combine(d, time())
        if d.weekday() < 5:
            out.append((base + timedelta(hours=9), base + timedelta(hours=17, minutes=30)))
            if rng.random() < sc.p_evening:
                s = rng.choice([18 * 60 + 30, 19 * 60, 19 * 60 + 30, 20 * 60])
                out.append(
                    (
                        base + timedelta(minutes=s),
                        base + timedelta(minutes=s + rng.choice([60, 90, 120, 150])),
                    )
                )
        elif rng.random() < sc.p_weekend:
            s = rng.choice([9 * 60, 11 * 60, 14 * 60, 16 * 60])
            out.append(
                (
                    base + timedelta(minutes=s),
                    base + timedelta(minutes=s + rng.choice([120, 180, 240, 300])),
                )
            )
    return out


def _work(rng: random.Random) -> list[Work]:
    return [
        Work(f"w{i}", f"c{i}", f"lesson {i}", float(rng.choice([20, 30, 40, 45, 60, 75, 90])))
        for i in range(28)
    ]


def _plan(
    policy: str,
    work: list[Work],
    day: date,
    deadline: date,
    hours: float,
    busy: list[Interval],
    log: list[LogEntry],
    week_done: float,
) -> list[Block]:
    if policy == "fixed calendar":  # one fixed evening slot, sized to the hours offered
        return naive_shift(
            work, start=day, deadline=deadline, windows=default_windows(hours)
        ).blocks
    rate = adherence(log)
    known = busy if policy == "adaptive + calendar" else []
    r = reschedule(
        work, start=day, deadline=deadline + timedelta(days=120), windows=availability_windows(),
        busy=known, adherence_rate=rate, base_cap=hours * 60 / 7 * 1.6, weekly_cap=hours * 60,
        week_done=week_done,
    )  # fmt: skip
    return r.blocks


def run_one(seed: int, sc: Scenario, policy: str) -> dict[str, float]:
    rng_setup = random.Random(seed)
    hours = rng_setup.choice([5, 7, 10])
    work = _work(rng_setup)
    need_weeks = sum(w.minutes for w in work) / (hours * 60)
    deadline = START + timedelta(days=round(7 * need_weeks * (1 + sc.slack)))
    busy = _calendar(rng_setup, 7 * 30, sc)
    buckets = by_day(busy)
    usual = typical_busy(buckets, START, START + timedelta(days=7 * 30 - 1))
    luck = random.Random(seed * 7919 + 1)  # the same daily luck for every policy

    remaining = list(work)
    log: list[LogEntry] = []
    day = START
    planned = clashed = 0
    longest_dense: list[int] = []
    finish: date | None = None
    for _ in range(7 * 30):
        if not remaining:
            break
        week_done = sum(
            e.done_minutes for e in log if e.day.isocalendar()[:2] == day.isocalendar()[:2]
        )
        today = [
            b
            for b in _plan(policy, remaining, day, deadline, hours, busy, log, week_done)
            if b.day == day
        ]
        sick = luck.random() < sc.p_sick
        rolls = [luck.random() for _ in range(12)]
        today_busy = buckets.get(day, [])
        fat = fatigue_index(day, today_busy, usual[day.weekday()])
        if fat >= 0.5 and today:
            longest_dense.append(max(b.end - b.start for b in today))
        done_by_work: dict[str, float] = {}
        plan_min = done_min = 0.0
        for i, b in enumerate(today):
            planned += 1
            length = b.end - b.start
            plan_min += length
            s = datetime.combine(day, time()) + timedelta(minutes=b.start)
            e = datetime.combine(day, time()) + timedelta(minutes=b.end)
            if any(a < e and z > s for a, z in today_busy):
                clashed += 1
                continue
            p = 0.95 - 0.45 * fat - (0.12 if length > 45 and fat > 0.4 else 0.0)
            if sick or rolls[i % len(rolls)] >= p:
                continue
            done_by_work[b.work_id] = done_by_work.get(b.work_id, 0.0) + length
            done_min += length
        if plan_min:
            log.append(LogEntry(day, plan_min, done_min))
        # progress: done minutes come off the front of the remaining work
        progress = sum(done_by_work.values())
        nxt: list[Work] = []
        for w in remaining:
            if progress >= w.minutes - 1e-6:
                progress -= w.minutes
                continue
            nxt.append(Work(w.id, w.concept, w.title, w.minutes - progress, w.kind))
            progress = 0.0
        remaining = nxt
        if not remaining:
            finish = day
        day += timedelta(days=1)
    weeks: dict[tuple[int, int], float] = {}
    for entry in log:
        k = entry.day.isocalendar()[:2]
        weeks[k] = weeks.get(k, 0.0) + entry.done_minutes
    late = (finish - deadline).days if finish else 999
    return {
        "on_time": float(finish is not None and finish <= deadline),
        "late_days": float(max(0, late)),
        "clash_rate": clashed / max(1, planned),
        "dense_block": statistics.mean(longest_dense) if longest_dense else 0.0,
        "max_week_share": max(weeks.values(), default=0.0) / (hours * 60),
    }


def main(n: int = 120) -> int:
    rows = []
    for sc in SCENARIOS:
        for pol in POLICIES:
            runs = [run_one(seed, sc, pol) for seed in range(n)]
            late = [r["late_days"] for r in runs if r["late_days"] > 0]
            rows.append(
                {
                    "scenario": sc.name,
                    "policy": pol,
                    "on_time": round(statistics.mean(r["on_time"] for r in runs), 3),
                    "mean_days_late_if_late": round(statistics.mean(late), 1) if late else 0.0,
                    "clash_rate": round(statistics.mean(r["clash_rate"] for r in runs), 3),
                    "longest_block_on_busy_days": round(
                        statistics.mean(r["dense_block"] for r in runs), 1
                    ),
                    "max_week_vs_offered": round(max(r["max_week_share"] for r in runs), 2),
                    "learners": n,
                }
            )
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "reschedule.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    with (RESULTS / "reschedule.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    head = ("scenario", "policy", "on time", "days late", "clashes", "max week / offered")
    print(f"{head[0]:28} {head[1]:24} {head[2]:>8} {head[3]:>10} {head[4]:>8} {head[5]:>19}")
    for r in rows:
        print(
            f"{r['scenario']:28} {r['policy']:24} {r['on_time']:>8.0%} "
            f"{r['mean_days_late_if_late']:>10} {r['clash_rate']:>8.0%} "
            f"{r['max_week_vs_offered']:>18}x"
        )
    print(f"\nwritten to {RESULTS / 'reschedule.csv'}  (break between blocks: {BREAK} min)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
