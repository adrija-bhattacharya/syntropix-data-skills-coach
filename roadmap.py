"""Personalised end-to-end learning roadmap.

Ties the whole pipeline together into one artefact a learner can follow:

* **where you are** - the skills the adaptive test says you already have;
* **what to learn** - the full prerequisite-closed set for the goal (or the
  hiring-readiness set for a role), grouped into ordered **phases**;
* **your pace** - phase time estimates are scaled by the learner's measured
  learning velocity (deliberate / steady / fast);
* **certifications** - real external credentials, each surfaced at the phase
  where the learner will have covered enough of its skills to sit it;
* **finish estimate** - from the pace and the weekly hours, with a calendar
  check when a target date is given (claim C).

Everything downstream (sequencing, role-gap, risk, calendar, self-healing graph)
already exists; this module only *assembles* and *narrates* it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from algorithms.graph_traversal import ancestors_subgraph, topological_order
from algorithms.roleplan import solve_role_plan
from algorithms.sequencing import plan_sequence
from certifications import Certification, certifications_for
from config import settings
from domain_data import DOMAIN_PREREQS, ROLES, role_profile
from domains import Resolved, resolve
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

NodeId = str

_PACE = {  # mean velocity -> (label, time multiplier)
    "deliberate": 1.30,
    "steady": 1.0,
    "fast": 0.78,
}


def _pace_of(state: LearnerState) -> str:
    vs = list(state.velocity.values())
    v = sum(vs) / len(vs) if vs else 1.0
    if v < 0.85:
        return "deliberate"
    return "steady" if v < 1.6 else "fast"


# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class RoadmapPhase:
    index: int
    title: str
    domain: str
    concept_ids: tuple[NodeId, ...]
    concept_names: tuple[str, ...]
    new_skills: int  # skills in this phase the learner does not already have
    est_hours: float
    est_weeks: float
    start_week: float
    focus: str
    checkpoint: str
    resources: tuple[dict[str, object], ...]
    certifications: tuple[Certification, ...]


@dataclass(frozen=True, slots=True)
class Roadmap:
    goal: str
    domain: str
    role: str | None
    pace: str
    weekly_hours: float
    starting_readiness: float
    target_readiness: float
    already_have: tuple[str, ...]
    you_are_here: dict[str, float]
    phases: tuple[RoadmapPhase, ...]
    total_hours: float
    total_weeks: float
    finish_estimate: str | None
    deadline: str | None = None
    on_track: bool | None = None
    certifications: tuple[Certification, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
def build_roadmap(
    kg: KnowledgeGraph,
    resolved: Resolved,
    state: LearnerState,
    *,
    weekly_hours: float = 5.0,
    deadline: date | None = None,
) -> Roadmap:
    theta = settings.mastery_threshold
    pace = _pace_of(state)
    mult = _PACE[pace]
    # a roadmap is the *whole* picture: for a curated domain, cover the entire
    # track, not just the closure of one fuzzy-matched concept.
    if resolved.source == "seed":
        goals = kg.sink_concepts()
    else:
        goals = [g for g in resolved.goals if g in kg.concepts] or kg.sink_concepts()[:1]

    role_obj = next((r for r in ROLES if r.name == resolved.domain), None)
    if resolved.source == "role" and role_obj is not None:
        profile = {k: v for k, v in role_profile(role_obj).items() if k in kg.concepts}
        rp = solve_role_plan(
            kg, role_obj.name, profile, state, budget_minutes=1e7
        )  # no budget cap: the whole readiness set
        closure = list(rp.chosen)
        start_r, target_r = rp.readiness_before, rp.readiness
    else:
        closure = topological_order(ancestors_subgraph(kg.prereq, goals))
        start_r = _reached(closure, goals, state, theta)
        target_r = 1.0

    already = {c for c in closure if state.decayed_mastery(c) >= theta}
    phases_raw = _group_phases(kg, closure, resolved)

    seq = plan_sequence(kg, goals, state, budget_seconds=1e9)
    res_by_concept: dict[str, dict[str, object]] = {}
    for s in seq.steps:
        r = kg.resources[s.resource_id]
        res_by_concept.setdefault(
            s.concept,
            {
                "concept": kg.concepts[s.concept].name,
                "title": r.title or kg.concepts[s.concept].name,
                "url": r.url,
                "source": r.source,
                "kind": r.kind,
                "difficulty": r.difficulty,
                "minutes": r.minutes,
            },
        )

    domains_seen: set[str] = set()
    for cid in closure:
        domains_seen.add(cid.split(".")[0] if "." in cid else resolved.domain)
    all_certs = certifications_for({d for d in domains_seen if d})

    phases: list[RoadmapPhase] = []
    cum_week = 0.0
    covered_running: set[str] = set(already)
    cert_placed: set[str] = set()
    for i, (title, domain, cids) in enumerate(phases_raw):
        names = tuple(kg.concepts[c].name for c in cids)
        new = [c for c in cids if c not in already]
        hours = sum(_concept_hours(kg, c) for c in new) * mult
        weeks = hours / weekly_hours if weekly_hours > 0 else 0.0
        covered_running.update(cids)
        here_certs = tuple(
            c for c in all_certs if c.id not in cert_placed and c.coverage(covered_running) >= 0.6
        )
        cert_placed.update(c.id for c in here_certs)
        resources = tuple(res_by_concept[c] for c in cids if c in res_by_concept)[:4]
        phases.append(
            RoadmapPhase(
                index=i + 1,
                title=title,
                domain=domain,
                concept_ids=tuple(cids),
                concept_names=names,
                new_skills=len(new),
                est_hours=round(hours, 1),
                est_weeks=round(weeks, 1),
                start_week=round(cum_week, 1),
                focus=_focus_line(names),
                checkpoint=_checkpoint_line(names),
                resources=resources,
                certifications=here_certs,
            )
        )
        cum_week += weeks

    total_hours = round(sum(p.est_hours for p in phases), 1)
    total_weeks = round(sum(p.est_weeks for p in phases), 1)
    finish = (date.today() + timedelta(weeks=total_weeks)).isoformat() if weekly_hours > 0 else None

    on_track: bool | None = None
    if deadline is not None:
        weeks_avail = max(0.0, (deadline - date.today()).days / 7.0)
        on_track = total_weeks <= weeks_avail + 1e-6

    notes = _notes(pace, len(already), len(closure), all_certs, deadline, on_track, total_weeks)

    return Roadmap(
        goal=resolved.goals[0] if resolved.goals else "",
        domain=resolved.domain,
        role=role_obj.name if role_obj else None,
        pace=pace,
        weekly_hours=weekly_hours,
        starting_readiness=round(start_r, 3),
        target_readiness=round(target_r, 3),
        already_have=tuple(sorted(kg.concepts[c].name for c in already)),
        you_are_here={
            kg.concepts[c].name: round(state.decayed_mastery(c), 2)
            for c in closure
            if c in state.mastery_se or state.decayed_mastery(c) >= theta
        },
        phases=tuple(phases),
        total_hours=total_hours,
        total_weeks=total_weeks,
        finish_estimate=finish,
        deadline=deadline.isoformat() if deadline else None,
        on_track=on_track,
        certifications=(*all_certs,),
        notes=notes,
    )


# --------------------------------------------------------------------------- #
def _reached(closure: list[str], goals: list[str], state: LearnerState, theta: float) -> float:
    if not goals:
        return 0.0
    return sum(1 for g in goals if state.decayed_mastery(g) >= theta) / len(goals)


def _concept_hours(kg: KnowledgeGraph, concept: str) -> float:
    """Realistic effort for one skill: at least ``roadmap_min_hours_per_skill``,
    scaled up with the concept's difficulty."""
    rs = kg.resources_for(concept)
    diff = max((kg.resources[r].difficulty for r in rs), default=2.0)
    base = settings.roadmap_min_hours_per_skill
    return base * (0.7 + 0.3 * max(1.0, diff))


def _group_phases(
    kg: KnowledgeGraph, closure: list[str], resolved: Resolved
) -> list[tuple[str, str, list[str]]]:
    """Ordered (title, domain, concept-ids) phases."""
    if not closure:
        return []

    # role graph: ids look like "domain.concept" -> one phase per domain
    if resolved.source == "role" and any("." in c for c in closure):
        seen: list[str] = []
        for d, child in DOMAIN_PREREQS:
            for dd in (d, child):
                if dd not in seen:
                    seen.append(dd)
        buckets: dict[str, list[str]] = {}
        for cid in closure:
            buckets.setdefault(cid.split(".")[0], []).append(cid)
        ordered = sorted(buckets, key=lambda d: (seen.index(d) if d in seen else 99, d))
        return [(_domain_title(d), d, buckets[d]) for d in ordered]

    # single graph: band by longest-prerequisite-chain depth
    depth = _depths(kg, closure)
    dmax = max(depth.values(), default=0)
    n_bands = 2 if dmax <= 1 else 3 if dmax <= 4 else 4
    edges = [round(dmax * k / n_bands) for k in range(1, n_bands)]
    titles = _band_titles(n_bands, resolved.domain)
    bands: list[list[str]] = [[] for _ in range(n_bands)]
    for cid in sorted(closure, key=lambda c: (depth[c], kg.concepts[c].name)):
        b = sum(1 for e in edges if depth[cid] > e)
        bands[b].append(cid)
    return [(titles[i], resolved.domain, b) for i, b in enumerate(bands) if b]


def _depths(kg: KnowledgeGraph, closure: list[str]) -> dict[str, int]:
    cset = set(closure)
    depth: dict[str, int] = {}
    for c in topological_order(ancestors_subgraph(kg.prereq, closure)):
        if c not in cset:
            continue
        preds = [p for p in kg.prereq.predecessors(c) if p in cset]
        depth[c] = 0 if not preds else 1 + max(depth.get(p, 0) for p in preds)
    for c in closure:
        depth.setdefault(c, 0)
    return depth


def _band_titles(n: int, domain: str) -> list[str]:
    d = domain.replace("_", " ")
    if n == 2:
        return [f"Foundations of {d}", f"Applying {d}"]
    if n == 3:
        return [f"Foundations of {d}", f"Core {d}", f"Advanced {d}"]
    return [f"Foundations of {d}", f"Core {d}", f"Advanced {d}", f"{d.title()} in practice"]


def _domain_title(d: str) -> str:
    return {
        "foundations": "Groundwork",
        "spreadsheets": "Spreadsheets",
        "sql": "SQL",
        "python": "Python",
        "python_data": "pandas & NumPy",
        "stats": "Statistics",
        "dataviz": "Data visualisation",
        "dsa_python": "Data structures & algorithms",
        "git": "Git & collaboration",
    }.get(d, d.replace("_", " ").title())


def _focus_line(names: tuple[str, ...]) -> str:
    if not names:
        return ""
    head = ", ".join(names[:3])
    extra = f", and {len(names) - 3} more" if len(names) > 3 else ""
    return f"Work through {head}{extra}."


def _checkpoint_line(names: tuple[str, ...]) -> str:
    return f"Checkpoint: you can use {names[-1]} confidently on a real dataset." if names else ""


def _notes(
    pace: str,
    have: int,
    total: int,
    certs: list[Certification],
    deadline: date | None,
    on_track: bool | None,
    weeks: float,
) -> tuple[str, ...]:
    out = [
        {
            "deliberate": "Pace: deliberate - estimates give you extra time per topic.",
            "steady": "Pace: steady - estimates assume an average learning speed.",
            "fast": "Pace: fast - your measured velocity shortens the estimates.",
        }[pace],
    ]
    if have:
        out.append(f"You already have {have} of {total} skills in this path — those are skipped.")
    if certs:
        free = sum(1 for c in certs if c.free)
        out.append(
            f"{len(certs)} relevant certifications ({free} free to earn). "
            "Treat these as external recommendations and verify current pricing and availability."
        )
    if deadline is not None:
        out.append(
            f"Target {deadline.isoformat()}: {'on track' if on_track else 'tight'} "
            f"at this pace (~{weeks:.0f} weeks of study)."
        )
    return tuple(out)


# --------------------------------------------------------------------------- #
def roadmap_for_goal(
    goal: str,
    state: LearnerState,
    *,
    weekly_hours: float = 5.0,
    deadline: date | None = None,
) -> Roadmap:
    """Convenience: resolve a free-text goal and build the roadmap in one call."""
    r = resolve(goal)
    return build_roadmap(r.kg, r, state, weekly_hours=weekly_hours, deadline=deadline)
