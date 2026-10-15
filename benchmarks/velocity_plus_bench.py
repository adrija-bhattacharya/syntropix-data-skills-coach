"""Claims G1-G5 - five velocity-aware features, each tested on simulated learners.

    python -m benchmarks.velocity_plus_bench     # -> results/velocity_plus.{json,csv}

Every experiment states its learner model; each feature is compared with what
the app did without it.

* **G1 self-checking forecast** - learners log 60 planned minutes a day for three
  weeks, then forecast when they'll finish the rest.  *Steady* learners study a
  stable share of each session; *bursty* ones have good and bad weeks
  (motivation that persists week to week).  Metric: how often the real finish
  falls on or before the "80% sure" date (80% is right).
* **G2 slowdown -> hidden gap** - a 24-concept graph with one *missing* edge
  A -> B.  Learners who don't know A learn B at 30% of their usual speed.
  Metric: is the slow topic flagged (vs false alarms), and is A named among the
  top 1 / top 3 suspects (vs a random weak neighbour).
* **G3 what fits by the date** - eight weighted goals over a prerequisite graph,
  uncertain time per concept and uncertain adherence; capacity is ~70% of the
  expected total.  Metric: does the chosen set actually get finished (one fresh
  draw of reality per learner), and how much value it carries - 90%-confidence
  choice vs choosing by expected time.
* **G4/G5 best study times, focus span** - learners have a true multiplier per
  time slot and a true focus half-life; 150 logged practice answers (right with
  probability expected x slot multiplier x focus fade) are what the app sees.
  Study progress per block = minutes x true slot multiplier x focus efficiency.
  Metric: effective learning per hour studied and days to finish, for the plain
  loop, +best slots, +focus-sized blocks, and both.
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from algorithms.calibration import calibrate
from algorithms.chance_goals import Scenarios, choose, choose_by_mean
from algorithms.reschedule import LogEntry, Work, reschedule
from algorithms.slowdown import detect
from algorithms.study_context import focus_span, slot_key, slot_scorer, slot_speeds
from algorithms.velocity_schedule import forecast
from benchmarks.velocity_bench import _ancestors, _graph

RESULTS = Path(__file__).resolve().parent.parent / "results"
START = date(2026, 1, 5)


# --------------------------------------------------------------------- G1
def _adherence_path(rng: random.Random, kind: str, days: int) -> list[float]:
    out: list[float] = []
    week_level = rng.uniform(0.55, 0.95)
    for d in range(days):
        if kind == "bursty" and d % 7 == 0:
            week_level = min(
                0.98, max(0.05, 0.5 * week_level + 0.5 * rng.choice([0.15, 0.4, 0.9, 0.95]))
            )
        base = week_level if kind == "bursty" else 0.8
        out.append(min(1.0, max(0.0, rng.gauss(base, 0.12))))
    return out


def g1(n: int) -> list[dict[str, object]]:
    rows = []
    for kind in ("steady", "bursty"):
        plain = calibrated = 0
        for seed in range(n):
            rng = random.Random(seed * 31 + (kind == "bursty"))
            path = _adherence_path(rng, kind, 21 + 200)
            log = [LogEntry(START + timedelta(days=i), 60.0, 60.0 * path[i]) for i in range(21)]
            remaining = rng.uniform(1200, 2400)
            today = START + timedelta(days=21)
            cap = [(today + timedelta(days=i), 60.0) for i in range(200)]
            rates = [e.done_minutes / e.planned_minutes for e in log]
            actual = today
            acc = 0.0
            for i in range(200):
                acc += 60.0 * path[21 + i]
                if acc >= remaining:
                    actual = today + timedelta(days=i)
                    break
            f0 = forecast([remaining], [1.0], cap, today + timedelta(days=60),
                          observed_concepts=50, adherence_rates=rates, samples=300, seed=seed)  # fmt: skip
            k = calibrate(log).trust
            f1 = forecast([remaining], [1.0], cap, today + timedelta(days=60), observed_concepts=50,
                          adherence_rates=rates, trust=k, samples=300, seed=seed)  # fmt: skip
            plain += int(f0.p80 is not None and actual <= f0.p80)
            calibrated += int(f1.p80 is not None and actual <= f1.p80)
        rows.append({"experiment": "G1", "case": f"{kind} learners", "policy": "forecast as is",
                     "metric": "done by the 80% date", "value": round(plain / n, 3)})  # fmt: skip
        rows.append({"experiment": "G1", "case": f"{kind} learners", "policy": "self-checking forecast",
                     "metric": "done by the 80% date", "value": round(calibrated / n, 3)})  # fmt: skip
    return rows


# --------------------------------------------------------------------- G2
def g2(n: int) -> list[dict[str, object]]:
    flagged = false_alarm = top1 = top3 = rand1 = affected_n = 0
    other_flags = 0
    for seed in range(n):
        rng = random.Random(seed + 500)
        pre = _graph(rng)
        anc = _ancestors(pre)
        concepts = list(pre)
        desc = {c: {x for x in concepts if c in anc[x]} for c in concepts}
        pairs = [
            (a, b) for a in concepts for b in concepts
            if a != b and a not in anc[b] and b not in anc[a] and concepts.index(a) < concepts.index(b)
            and (anc[a] & anc[b] or desc[a] & desc[b])
        ]  # fmt: skip
        a, b = rng.choice(pairs)
        affected = seed % 2 == 0
        base = math.exp(rng.gauss(0, 0.4))
        v_true: dict[str, float] = {}
        for c in concepts:
            parent = statistics.mean(v_true[p] for p in pre[c]) if pre[c] else base
            v_true[c] = parent * math.exp(rng.gauss(0, 0.2))
        if affected:
            v_true[b] *= 0.3
        # the learner has studied everything up to b (in plan order) except, if affected, a
        studied = set(concepts[: concepts.index(b) + 1])
        if affected:
            studied.discard(a)
        mastery = {c: (0.85 if c in studied else 0.15) for c in concepts}
        observed = set(studied)
        v_obs = {c: v_true[c] * math.exp(rng.gauss(0, 0.1)) for c in observed}
        found = detect(concepts, pre, v_obs, observed, mastery)
        hit = next((s for s in found if s.concept == b), None)
        other_flags += sum(1 for s in found if s.concept != b)
        if affected:
            affected_n += 1
            flagged += int(hit is not None)
            names = [x.concept for x in hit.suspects] if hit else []
            top1 += int(names[:1] == [a])
            top3 += int(a in names[:3])
            weak = [
                c
                for c in concepts
                if mastery[c] < 0.6 and c != b and c not in anc[b] and c not in desc[b]
            ]
            rand1 += int(bool(weak) and rng.choice(weak) == a)
        else:
            false_alarm += int(hit is not None)
    m = affected_n
    u = n - m
    return [
        {"experiment": "G2", "case": "slow topic with a hidden gap", "policy": "slowdown detector", "metric": "flagged", "value": round(flagged / m, 3)},
        {"experiment": "G2", "case": "same topic, no gap", "policy": "slowdown detector", "metric": "false alarm", "value": round(false_alarm / u, 3)},
        {"experiment": "G2", "case": "other topics", "policy": "slowdown detector", "metric": "false alarms per learner", "value": round(other_flags / n, 3)},
        {"experiment": "G2", "case": "slow topic with a hidden gap", "policy": "slowdown detector", "metric": "missing prerequisite named first", "value": round(top1 / m, 3)},
        {"experiment": "G2", "case": "slow topic with a hidden gap", "policy": "slowdown detector", "metric": "... in top 3", "value": round(top3 / m, 3)},
        {"experiment": "G2", "case": "slow topic with a hidden gap", "policy": "random weak neighbour", "metric": "missing prerequisite named first", "value": round(rand1 / m, 3)},
    ]  # fmt: skip


# --------------------------------------------------------------------- G3
def g3(n: int) -> list[dict[str, object]]:
    res: dict[str, list[tuple[float, float]]] = {"90% confidence": [], "expected time": []}
    for seed in range(n):
        rng = random.Random(seed + 900)
        pre = _graph(rng)
        anc = _ancestors(pre)
        concepts = list(pre)
        minutes = {c: float(rng.choice([30, 45, 60, 90])) for c in concepts}
        goals = rng.sample(concepts[8:], 8)
        values = {g: round(rng.uniform(0.5, 1.0), 2) for g in goals}
        rates = [min(1.0, max(0.0, rng.gauss(0.75, 0.15))) for _ in range(rng.choice([0, 7, 14]))]
        sc = Scenarios(minutes, sigma=0.35, adherence_rates=rates, samples=400, seed=seed)
        everything = set().union(*({g} | anc[g] for g in goals))
        cap = 0.7 * statistics.mean(sc.totals(everything))
        reality = Scenarios(
            minutes, sigma=0.35, adherence_rates=rates, samples=1, seed=seed + 10_000
        )
        for name, ch in (
            ("90% confidence", choose(values, anc, sc, cap)),
            ("expected time", choose_by_mean(values, anc, sc, cap)),
        ):
            need = set().union(*({g} | anc[g] for g in ch.goals)) if ch.goals else set()
            ok = reality.totals(need)[0] <= cap
            res[name].append((float(ok), ch.value / sum(values.values())))
    rows = []
    for name, rs in res.items():
        rows.append(
            {
                "experiment": "G3",
                "case": "8 goals, capacity ~70% of expected need",
                "policy": name,
                "metric": "chosen set actually finished",
                "value": round(statistics.mean(r[0] for r in rs), 3),
            }
        )
        rows.append(
            {
                "experiment": "G3",
                "case": "8 goals, capacity ~70% of expected need",
                "policy": name,
                "metric": "share of goal value chosen",
                "value": round(statistics.mean(r[1] for r in rs), 3),
            }
        )
    return rows  # fmt: skip


# ------------------------------------------------------------------ G4/G5
SLOTS = [
    f"{d} {p}" for d in ("weekday", "weekend") for p in ("morning", "afternoon", "evening", "night")
]


def _learner(rng: random.Random) -> tuple[dict[str, float], float]:
    mult = {s: min(1.8, max(0.55, math.exp(rng.gauss(0, 0.3)))) for s in SLOTS}
    half = rng.choice([20.0, 35.0, 60.0, 120.0])
    return mult, math.log(2) / half


def _telemetry(
    rng: random.Random, mult: dict[str, float], lam: float, n: int = 150
) -> list[SimpleNamespace]:
    out = []
    for _ in range(n):
        wd = rng.randrange(7)
        hour = rng.choice([7, 9, 11, 13, 15, 18, 19, 20, 22])
        t = rng.uniform(0, 75)
        exp = rng.uniform(0.4, 0.8)
        p = min(0.98, exp * mult[slot_key(wd, hour * 60)] * math.exp(-lam * t))
        out.append(
            SimpleNamespace(
                hour=hour, weekday=wd, correct=rng.random() < p, expected=exp, session_min=t
            )
        )
    return out


def g45(n: int) -> list[dict[str, object]]:
    policies = ("plain loop", "+ best study times", "+ focus-sized blocks", "+ both")
    eff: dict[str, list[float]] = {p: [] for p in policies}
    days: dict[str, list[float]] = {p: [] for p in policies}
    windows = {d: [(7 * 60, 9 * 60), (18 * 60, 23 * 60)] for d in range(5)}
    windows.update({5: [(8 * 60, 22 * 60)], 6: [(8 * 60, 22 * 60)]})
    for seed in range(n):
        rng = random.Random(seed + 1300)
        mult, lam = _learner(rng)
        tel = _telemetry(rng, mult, lam)
        speeds = slot_speeds(tel)  # type: ignore[arg-type]
        focus = focus_span(tel)  # type: ignore[arg-type]
        need = 25 * 60.0
        for pol in policies:
            done = 0.0
            studied = 0.0
            week: dict[tuple[int, int], float] = {}
            day = START
            for _ in range(120):
                if done >= need:
                    break
                r = reschedule(
                    [Work("w", "c", "c", need - done)], start=day, deadline=day + timedelta(days=14),
                    windows=windows, base_cap=6 * 60 / 7 * 1.6, weekly_cap=6 * 60,
                    week_done=week.get(day.isocalendar()[:2], 0.0),
                    slot_score=slot_scorer(speeds) if pol in ("+ best study times", "+ both") else None,
                    block_cap=focus.block_min if pol in ("+ focus-sized blocks", "+ both") else None,
                )  # fmt: skip
                for b in (x for x in r.blocks if x.day == day):
                    length = b.end - b.start
                    m = mult[slot_key(day.weekday(), b.start)]
                    fe = (1 - math.exp(-lam * length)) / (lam * length)
                    done += length * m * fe
                    studied += length
                    k = day.isocalendar()[:2]
                    week[k] = week.get(k, 0.0) + length
                day += timedelta(days=1)
            eff[pol].append(done / max(1.0, studied))
            days[pol].append((day - START).days)
    rows = []
    for p in policies:
        rows.append(
            {
                "experiment": "G4/G5",
                "case": "time-of-day effects + focus fade",
                "policy": p,
                "metric": "learning per hour studied",
                "value": round(statistics.mean(eff[p]), 3),
            }
        )
        rows.append(
            {
                "experiment": "G4/G5",
                "case": "time-of-day effects + focus fade",
                "policy": p,
                "metric": "days to finish 25 h of learning",
                "value": round(statistics.mean(days[p]), 1),
            }
        )
    return rows  # fmt: skip


def main(n: int = 120) -> int:
    rows = g1(n) + g2(n) + g3(n) + g45(max(30, n // 3))
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "velocity_plus.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    with (RESULTS / "velocity_plus.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(
            f"{r['experiment']:6} {str(r['case'])[:38]:38} {str(r['policy'])[:24]:24} {str(r['metric'])[:34]:34} {r['value']}"
        )
    print(f"\nwritten to {RESULTS / 'velocity_plus.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
