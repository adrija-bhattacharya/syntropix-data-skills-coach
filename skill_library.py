"""The skill library, ordered for one learner.

``harvest/data/library.json`` holds real practice problems (LeetCode,
HackerRank, open sites) and real YouTube lessons, each tagged with the concept
it trains.  This module lays them along the learner's own path:

* **chronology** - concepts in prerequisite order (the graph's topological
  order); inside a concept: the lesson video, then problems Easy -> Hard;
* **velocity** - the learner's measured learning speed (mastery gained per hour,
  from the BKT/velocity model) picks how many warm-ups they get and how much fits
  in a week: a fast learner skips most Easy problems and meets Hard ones sooner,
  a deliberate one gets every warm-up and has Hard problems parked in "stretch";
* **mastery** - concepts already mastered move to an optional "review" list.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from algorithms.graph_traversal import topological_order
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

LIBRARY = Path(__file__).resolve().parent / "harvest" / "data" / "library.json"
CHECKS = LIBRARY.with_name("video_checks.json")
MASTERED = 0.75
_DIFF = {"Easy": 0, "Medium": 1, "Hard": 2}
_MINUTES = {"Easy": 12.0, "Medium": 22.0, "Hard": 35.0}
# pace -> (easy problems per concept, medium, hard; None = all) and a time multiplier
PACES: dict[str, tuple[int | None, int | None, int | None, float]] = {
    "deliberate": (None, None, 0, 1.30),
    "steady": (3, None, 2, 1.0),
    "fast": (1, 3, None, 0.78),
}
PACE_WORDS = {
    "deliberate": (
        "You learn carefully: every warm-up is included and the hardest problems wait in Stretch."
    ),
    "steady": (
        "You learn at a steady pace: a few warm-ups, all medium problems, two hard ones per topic."
    ),
    "fast": "You learn fast: one warm-up per topic, then straight to medium and hard problems.",
}


def difficulty(raw: object) -> str:
    d = str(raw or "Medium").capitalize()
    return "Hard" if d in ("Advanced", "Expert") else d if d in _DIFF else "Medium"


@cache
def load() -> dict[str, Any]:
    if not LIBRARY.exists():
        return {"harvested": None, "problems": [], "videos": []}
    data: dict[str, Any] = json.loads(LIBRARY.read_text(encoding="utf-8"))
    for p in data["problems"]:  # HackerRank also says "EASY", "Advanced", "Expert"
        p["difficulty"] = difficulty(p.get("difficulty"))
    # semantic checks (harvest/verify.py): does each video teach its topic?
    checks: dict[str, Any] = (
        json.loads(CHECKS.read_text(encoding="utf-8")) if CHECKS.exists() else {}
    )
    for v in data["videos"]:
        c = checks.get(v["video_id"])
        v["check"] = (
            {
                k: c[k]
                for k in (
                    "level",
                    "source",
                    "judge",
                    "start",
                    "chapter",
                    "reason",
                    "score",
                    "coverage",
                )
            }
            if c
            else None
        )
    data["videos"] = [
        v for v in data["videos"] if not (v["check"] and v["check"]["level"] == "off-topic")
    ]
    data["checked"] = len(checks)
    return data


def pace_of(state: LearnerState | None, fallback: str = "steady") -> str:
    """The learner's pace from measured velocity; ``fallback`` before any evidence."""
    if state is None:
        return fallback
    vs = [v for v in state.velocity.values() if v != 1.0]  # 1.0 = untouched prior
    if not vs:
        return fallback
    v = sum(vs) / len(vs)
    return "deliberate" if v < 0.85 else "steady" if v < 1.6 else "fast"


def _split(cid: str, domain: str) -> tuple[str, str]:
    """(domain, bare concept) for a graph id - role graphs prefix ``domain.``."""
    if "." in cid:
        d, bare = cid.split(".", 1)
        return d, bare
    return domain, cid


@dataclass
class Library:
    pace: str
    pace_text: str
    harvested: str | None
    steps: list[dict[str, Any]] = field(default_factory=list)  # per concept, in order
    stretch: list[dict[str, Any]] = field(default_factory=list)  # harder problems parked for later
    extra: list[dict[str, Any]] = field(default_factory=list)  # warm-ups a faster learner can skip
    review: list[dict[str, Any]] = field(default_factory=list)
    courses: list[dict[str, Any]] = field(default_factory=list)
    mixed: list[dict[str, Any]] = field(default_factory=list)
    weeks: list[dict[str, Any]] = field(default_factory=list)
    totals: dict[str, int] = field(default_factory=dict)


def _problem_minutes(p: dict[str, Any]) -> float:
    return float(p.get("minutes") or _MINUTES.get(p["difficulty"], 20.0))


def build(
    kg: KnowledgeGraph,
    domain: str,
    state: LearnerState | None,
    *,
    pace: str | None = None,
    hours_per_week: float = 7.0,
) -> Library:
    lib = load()
    pace = pace if pace in PACES else pace_of(state)
    n_easy, n_med, n_hard, mult = PACES[pace]
    caps = {"Easy": n_easy, "Medium": n_med, "Hard": n_hard}

    order = topological_order(kg.prereq)
    keys = {_split(c, domain): c for c in order}
    domains = {d for d, _ in keys}

    by_concept: dict[tuple[str, str], list[dict[str, Any]]] = {}
    mixed: list[dict[str, Any]] = []
    for p in lib["problems"]:
        if p.get("domain") not in domains:
            continue
        if p.get("concept") is None:
            mixed.append(p)
        elif (p["domain"], p["concept"]) in keys:
            by_concept.setdefault((p["domain"], p["concept"]), []).append(p)
    lessons = {(v["domain"], v["concept"]): v for v in lib["videos"] if v["kind"] == "lesson"}
    courses = sorted(
        (v for v in lib["videos"] if v["kind"] == "course" and v["domain"] in domains),
        key=lambda v: (v["domain"], v["order"]),
    )

    out = Library(
        pace=pace, pace_text=PACE_WORDS[pace], harvested=lib.get("harvested"), courses=courses
    )
    for cid in order:
        key = _split(cid, domain)
        probs = sorted(
            by_concept.get(key, []),
            key=lambda p: (_DIFF.get(p["difficulty"], 1), p["platform"] != "LeetCode", p["title"]),
        )
        mastery = round(state.mastery.get(cid, 0.0), 3) if state else 0.0
        video = lessons.get(key)
        step: dict[str, Any] = {
            "concept_id": cid,
            "domain": key[0],
            "concept": kg.concepts[cid].name,
            "mastery": mastery,
            "video": video,
        }
        chosen: list[dict[str, Any]] = []
        step["problems"] = chosen
        if mastery >= MASTERED:
            step["problems"] = probs
            out.review.append(step)
            continue
        taken = {"Easy": 0, "Medium": 0, "Hard": 0}
        for p in probs:
            d = p["difficulty"] if p["difficulty"] in taken else "Medium"
            cap = caps[d]
            if cap is None or taken[d] < cap:
                taken[d] += 1
                chosen.append(p)
            else:
                parked = {**p, "concept_id": cid, "concept": step["concept"]}
                (out.stretch if d == "Hard" else out.extra).append(parked)
        out.steps.append(step)
    out.mixed = sorted(mixed, key=lambda p: (_DIFF.get(p["difficulty"], 1), p["title"]))

    # weeks: lay video + problems end to end against the weekly budget
    budget = max(hours_per_week, 1.0) * 60
    week: dict[str, Any] = {"week": 1, "minutes": 0.0, "items": []}
    for step in out.steps:
        items = ([{"type": "video", **step["video"]}] if step["video"] else []) + [
            {"type": "problem", **p} for p in step["problems"]
        ]
        for it in items:
            m = float(it["minutes"]) if it["type"] == "video" else _problem_minutes(it)
            m *= mult if it["type"] == "problem" else 1.0
            if week["items"] and week["minutes"] + m > budget:
                out.weeks.append(week)
                week = {"week": week["week"] + 1, "minutes": 0.0, "items": []}
            week["items"].append(
                {  # the problem's own "concept" is the bare id - show the name instead
                    **it,
                    "concept_id": step["concept_id"],
                    "concept": step["concept"],
                    "minutes": round(m),
                }
            )
            week["minutes"] += m
    if week["items"]:
        out.weeks.append(week)
    for w in out.weeks:
        w["minutes"] = round(w["minutes"])

    out.totals = {
        "problems": sum(len(s["problems"]) for s in out.steps),
        "videos": sum(1 for s in out.steps if s["video"]) + len(courses),
        "stretch": len(out.stretch),
        "extra": len(out.extra),
        "review": len(out.review),
        "mixed": len(out.mixed),
        "weeks": len(out.weeks),
        "leetcode": sum(1 for s in out.steps for p in s["problems"] if p["platform"] == "LeetCode"),
        "hackerrank": sum(
            1 for s in out.steps for p in s["problems"] if p["platform"] == "HackerRank"
        ),
    }
    return out


def stats() -> dict[str, Any]:
    """Library-wide counts for the opening page."""
    lib = load()
    from collections import Counter

    plat = Counter(p["platform"] for p in lib["problems"])
    return {
        "harvested": lib.get("harvested"),
        "problems": len(lib["problems"]),
        "videos": len(lib["videos"]),
        "leetcode": plat.get("LeetCode", 0),
        "hackerrank": plat.get("HackerRank", 0),
        "open_sites": sum(v for k, v in plat.items() if k not in ("LeetCode", "HackerRank")),
        "domains": sorted({p["domain"] for p in lib["problems"] if p.get("domain")}),
    }
