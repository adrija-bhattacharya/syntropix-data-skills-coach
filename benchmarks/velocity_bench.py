"""Claim G - does velocity-aware scheduling plan better than lesson minutes?

    python -m benchmarks.velocity_bench      # -> results/velocity.{json,csv}

Simulated learners study a 24-concept prerequisite graph through busy weeks
(the calendar model of ``reschedule_bench``).  All policies run the calendar
feedback loop (claim F) every morning; they differ in how they size and order
the work:

* **lesson minutes** - every concept is planned at its lesson's minutes (what a
  course says), for everyone;
* **velocity-sized** - planned at this learner's predicted time (velocity
  measured on finished concepts, predicted for new ones from their
  prerequisites, shrunk to the learner's mean);
* **velocity-sized + matched** - also puts slow concepts on light days and
  quick ones on busy days.

Learner model (stated, so it can be audited):

* a learner's true velocity on a concept = the mean true velocity of its
  prerequisites (or a personal base rate) times log-normal(0, 0.25) noise - how
  fast you learned what a topic builds on predicts how fast you'll learn it;
* the true time a concept needs = lesson minutes x ``time_ratio(m_init, v_true)``;
  the velocity *estimate* after finishing a concept has 10% log-normal error;
* a block overlapping a calendar event doesn't happen; otherwise it is done with
  probability ``0.95 - 0.45 * fatigue - 0.30 * hard * fatigue`` (``hard`` = the
  concept's true time ratio / 3): hard topics get skipped on draining days.

Reported: share of learners finishing by the deadline; at the start, the error
of the predicted finish date (lesson-minutes policy: the plan's finish date;
velocity policies: the forecast's median); how often the actual finish fell on
or before the forecast's 80% date (calibration; ~80% is right); and, two weeks
in, how many of the learners who end up late the plan had already flagged
(predicted finish after the deadline).
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from datetime import date, datetime, time, timedelta
from pathlib import Path

from algorithms.reschedule import (
    LogEntry,
    Work,
    adherence,
    availability_windows,
    by_day,
    fatigue_index,
    reschedule,
    typical_busy,
)
from algorithms.velocity_schedule import (
    M_INIT,
    capacity,
    forecast,
    predicted_velocity,
    size_work,
    time_ratio,
)
from benchmarks.reschedule_bench import SCENARIOS, START, Scenario, _calendar

RESULTS = Path(__file__).resolve().parent.parent / "results"
POLICIES = ("lesson minutes", "velocity-sized", "velocity-sized + matched")
N_CONCEPTS = 24


def _graph(rng: random.Random) -> dict[str, list[str]]:
    pre: dict[str, list[str]] = {}
    for i in range(N_CONCEPTS):
        k = 0 if i == 0 else rng.choice([1, 1, 2]) if i > 2 else 1
        pre[f"c{i}"] = (
            sorted({f"c{rng.randrange(max(0, i - 6), i)}" for _ in range(k)}) if i else []
        )
    return pre


def _ancestors(pre: dict[str, list[str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for c in pre:  # concepts are in topological order
        out[c] = set(pre[c]).union(*(out[p] for p in pre[c])) if pre[c] else set()
    return out


def run_one(seed: int, sc: Scenario, policy: str) -> dict[str, float]:
    rng = random.Random(seed)
    hours = rng.choice([5, 7, 10])
    pre = _graph(rng)
    anc = _ancestors(pre)
    concepts = list(pre)
    lesson = {c: float(rng.choice([30, 40, 45, 60, 75, 90])) for c in concepts}
    base_v = math.exp(rng.gauss(0.0, 0.45))
    v_true: dict[str, float] = {}
    for c in concepts:
        parent = statistics.mean(v_true[p] for p in pre[c]) if pre[c] else base_v
        v_true[c] = min(5.0, max(0.15, parent * math.exp(rng.gauss(0.0, 0.25))))
    need = {c: lesson[c] * time_ratio(M_INIT, v_true[c]) for c in concepts}
    avg_need = sum(lesson.values())
    deadline = START + timedelta(days=round(7 * avg_need / (hours * 60) * (1 + sc.slack)))
    busy = _calendar(rng, 7 * 40, sc)
    buckets = by_day(busy)
    usual = typical_busy(buckets, START, START + timedelta(days=7 * 40 - 1))
    luck = random.Random(seed * 7919 + 3)
    windows = availability_windows()
    base_cap, weekly_cap = hours * 60 / 7 * 1.6, hours * 60

    done_min = dict.fromkeys(concepts, 0.0)
    v_obs: dict[str, float] = {}
    log: list[LogEntry] = []
    day = START
    finish: date | None = None
    predicted_start: date | None = None
    p80_start: date | None = None
    flagged_late = False

    def plan_work() -> tuple[list[Work], list[float]]:
        left = [c for c in concepts if done_min[c] < need[c] - 0.5]
        if policy == "lesson minutes":
            est = {c: lesson[c] for c in left}
            ratios = [1.0] * len(left)
        else:
            vh = predicted_velocity(concepts, pre, v_obs, set(v_obs))
            sized = size_work([(c, lesson[c], "teach") for c in left], {}, vh)
            est = {c: s.minutes for c, s in zip(left, sized)}
            ratios = [s.ratio for s in sized]
        work = [
            Work(c, c, c, max(10.0, est[c] - done_min[c]), "teach", hardness=est[c] / lesson[c])
            for c in left
        ]
        return work, ratios

    for k in range(7 * 40):
        if all(done_min[c] >= need[c] - 0.5 for c in concepts):
            break
        work, ratios = plan_work()
        week_done = sum(
            e.done_minutes for e in log if e.day.isocalendar()[:2] == day.isocalendar()[:2]
        )
        r = reschedule(
            work, start=day, deadline=day + timedelta(days=200), windows=windows, busy=busy,
            adherence_rate=adherence(log), base_cap=base_cap, weekly_cap=weekly_cap,
            week_done=week_done, match=policy.endswith("matched"), ancestors=anc,
        )  # fmt: skip
        if k in (0, 14):
            if policy == "lesson minutes":
                pred, p80 = r.finish, r.finish
            else:
                cap = capacity(
                    day, day + timedelta(days=200), windows=windows, busy=busy,
                    base_cap=base_cap, weekly_cap=weekly_cap, week_done=week_done,
                )  # fmt: skip
                fc = forecast(
                    [w.minutes for w in work], ratios, cap, deadline,
                    observed_concepts=len(v_obs),
                    adherence_rates=[x.done_minutes / x.planned_minutes for x in log if x.planned_minutes],  # noqa: E501
                    samples=200, seed=seed,
                )  # fmt: skip
                pred, p80 = fc.p50, fc.p80
            if k == 0:
                predicted_start, p80_start = pred, p80
            else:
                flagged_late = pred is None or pred > deadline
        today = [b for b in r.blocks if b.day == day]
        fat = fatigue_index(day, buckets.get(day, []), usual[day.weekday()])
        sick = luck.random() < sc.p_sick
        rolls = [luck.random() for _ in range(16)]
        plan_min = got = 0.0
        for i, b in enumerate(today):
            length = b.end - b.start
            plan_min += length
            s = datetime.combine(day, time()) + timedelta(minutes=b.start)
            e = datetime.combine(day, time()) + timedelta(minutes=b.end)
            if any(a < e and z > s for a, z in buckets.get(day, [])):
                continue
            hard = min(1.0, need[b.concept] / lesson[b.concept] / 3.0)
            p = 0.95 - 0.45 * fat - 0.30 * hard * fat
            if sick or rolls[i % len(rolls)] >= p:
                continue
            c = b.concept
            before = done_min[c]
            done_min[c] = min(need[c], done_min[c] + length)
            got += done_min[c] - before
            if before < need[c] - 0.5 <= done_min[c] and c not in v_obs:
                v_obs[c] = v_true[c] * math.exp(luck.gauss(0.0, 0.1))
        if plan_min:
            log.append(LogEntry(day, plan_min, got))
        if all(done_min[c] >= need[c] - 0.5 for c in concepts):
            finish = day
        day += timedelta(days=1)

    actual = finish or day
    err = abs((predicted_start - actual).days) if predicted_start else 120.0
    return {
        "on_time": float(finish is not None and finish <= deadline),
        "late": float(finish is None or finish > deadline),
        "forecast_error_days": float(err),
        "within_p80": float(p80_start is not None and actual <= p80_start),
        "flagged_late": float(flagged_late),
    }


def main(n: int = 100) -> int:
    rows = []
    for sc in SCENARIOS:
        for pol in POLICIES:
            runs = [run_one(seed, sc, pol) for seed in range(n)]
            late = [r for r in runs if r["late"]]
            rows.append(
                {
                    "scenario": sc.name,
                    "policy": pol,
                    "on_time": round(statistics.mean(r["on_time"] for r in runs), 3),
                    "forecast_error_days": round(
                        statistics.mean(r["forecast_error_days"] for r in runs), 1
                    ),
                    "actual_within_p80": round(statistics.mean(r["within_p80"] for r in runs), 3),
                    "late_flagged_by_week_2": round(
                        statistics.mean(r["flagged_late"] for r in late), 3
                    )
                    if late
                    else None,
                    "learners": n,
                }
            )
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "velocity.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    with (RESULTS / "velocity.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    head = ("scenario", "policy", "on time", "forecast err", "done by P80", "late flagged wk2")
    print(f"{head[0]:28} {head[1]:26} {head[2]:>8} {head[3]:>13} {head[4]:>12} {head[5]:>17}")
    for r in rows:
        lf = "-" if r["late_flagged_by_week_2"] is None else f"{r['late_flagged_by_week_2']:.0%}"
        print(
            f"{r['scenario']:28} {r['policy']:26} {r['on_time']:>8.0%} "
            f"{r['forecast_error_days']:>11} d {r['actual_within_p80']:>12.0%} {lf:>17}"
        )
    print(f"\nwritten to {RESULTS / 'velocity.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
