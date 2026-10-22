"""Claim H3 - learned per-topic forgetting + just-in-time reviews vs one fixed half-life.

    python -m benchmarks.forgetting_bench   # -> results/forgetting.{json,csv}

Simulated learners work through the SQL skill graph (20 topics, its real
prerequisites), one new topic every 2 days.  Learner model (stated, so it can
be audited):

* each learner forgets at their own pace: an overall half-life drawn
  log-normally around 5 days (sigma 0.7); a starting topic varies around it
  (sigma 0.5) and a topic built on others is forgotten like them (geometric
  mean of its prerequisites, sigma 0.35);
* recall after ``g`` days: ``0.2 + 0.75 * 2^(-g / H)`` (the model's own form);
* a lesson opens with one warm-up question per prerequisite, and a review is
  one question: each answer is evidence for the learned policies and refreshes
  that topic.  Half-lives don't change over time.

Policies (all see the same learners and luck):

* **no reviews**;
* **fixed half-life** - review when recall would fall below 70%, assuming
  5 days for everyone and every topic (today's model);
* **fixed + just in time** - the same, plus a review the day before a lesson
  that needs a stale topic;
* **learned** - per-topic half-lives fitted from the learner's own answers,
  review below 70%;
* **learned + just in time** (claim H3).

Reported: share of lessons that start with *every* prerequisite still at
least 70% remembered (true recall), reviews per learner, and wasted reviews
(the topic was still over 90% remembered).
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from algorithms import forgetting as fg
from domains import seed_graph

RESULTS = Path(__file__).resolve().parent.parent / "results"
POLICIES = (
    "no reviews",
    "fixed half-life",
    "fixed + just in time",
    "learned",
    "learned + just in time",
)
DAY0 = date(2026, 1, 5)
READY_TRUE = 0.7


def _truth(rng: random.Random, order: list[str], pre: dict[str, list[str]]) -> dict[str, float]:
    base = math.exp(rng.gauss(math.log(5.0), 0.7))
    h: dict[str, float] = {}
    for c in order:
        ups = [h[p] for p in pre.get(c, []) if p in h]
        if ups:
            h[c] = math.exp(sum(map(math.log, ups)) / len(ups) + rng.gauss(0, 0.35))
        else:
            h[c] = base * math.exp(rng.gauss(0, 0.5))
    return {c: min(120.0, max(0.5, v)) for c, v in h.items()}


def simulate(
    policy: str, truth: dict[str, float], order: list[str], pre: dict[str, list[str]], seed: int
) -> dict[str, Any]:
    rng = random.Random(seed)
    lesson_day = {c: DAY0 + timedelta(days=2 * i) for i, c in enumerate(order)}
    end = DAY0 + timedelta(days=2 * len(order))
    seen: dict[str, date] = {}
    obs: list[fg.Recall] = []
    ready = lessons = reviews = wasted = 0
    learned = policy.startswith("learned")
    jit = policy.endswith("just in time")

    def answer(c: str, day: date) -> None:
        gap = (day - seen[c]).days
        if gap * 24 >= fg.MIN_GAP_H:
            obs.append(fg.Recall(c, gap, rng.random() < fg.p_recall(gap, truth[c])))
        seen[c] = day

    day = DAY0
    while day <= end:
        # reviews the policy wants today
        if policy != "no reviews" and seen:
            if learned:
                hl = fg.fit_half_lives(obs, order, pre)
            else:
                hl = {c: fg.HalfLife(c, fg.DEFAULT_HALF_LIFE_D, 0, "default") for c in order}
            upcoming = {c: d for c, d in lesson_day.items() if d > day and c not in seen}
            due = fg.plan_reviews(
                seen, hl, pre, upcoming if jit else {}, today=day, until=day, ready=fg.READY,
            )  # fmt: skip
            for r in due[: fg.MAX_REVIEWS_PER_DAY]:
                reviews += 1
                wasted += fg.retention((day - seen[r.concept]).days, truth[r.concept]) > 0.9
                answer(r.concept, day)
        # today's lesson
        for c, d in lesson_day.items():
            if d != day:
                continue
            ups = [p for p in pre.get(c, []) if p in seen]
            if ups:
                lessons += 1
                ready += all(
                    fg.retention((day - seen[p]).days, truth[p]) >= READY_TRUE for p in ups
                )
                for p in ups:
                    answer(p, day)  # warm-up question
            seen[c] = day
        day += timedelta(days=1)
    return {
        "ready": ready / max(1, lessons),
        "reviews": reviews,
        "wasted": wasted / max(1, reviews),
    }


def main(n: int = 150) -> int:
    kg = seed_graph("sql")
    pre = {c: sorted(kg.direct_prerequisites(c)) for c in kg.concept_ids}
    order = fg._topo(list(kg.concept_ids), pre)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        truth = _truth(random.Random(1000 + i), order, pre)
        for p in POLICIES:
            r = simulate(p, truth, order, pre, seed=i)
            rows.append({"learner": i, "policy": p, **r})
    summary = []
    for p in POLICIES:
        sub = [r for r in rows if r["policy"] == p]
        summary.append({
            "policy": p,
            "lessons_ready": round(statistics.mean(r["ready"] for r in sub), 3),
            "reviews_per_learner": round(statistics.mean(r["reviews"] for r in sub), 1),
            "wasted_review_share": round(statistics.mean(r["wasted"] for r in sub if r["reviews"]), 3) if any(r["reviews"] for r in sub) else 0.0,
        })  # fmt: skip
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "forgetting.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    with (RESULTS / "forgetting.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    print(f"{n} simulated learners, 20 SQL topics, a lesson every 2 days\n")
    print(f"{'policy':<26}{'lessons ready':>15}{'reviews':>10}{'wasted':>9}")
    for s in summary:
        print(
            f"{s['policy']:<26}{s['lessons_ready']:>15.0%}{s['reviews_per_learner']:>10}{s['wasted_review_share']:>9.0%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
