"""FastAPI service.  Endpoints:

    GET  /health
    GET  /catalogue        concepts, resources, sink (goal) concepts
    POST /resolve          {goal}                           free-text goal -> knowledge graph
    POST /assess/start     {learner_id, goals[]}            begin the adaptive diagnostic
    POST /assess/answer    {learner_id, item_id, response}  grade + get the next item
    GET  /assess/{id}      current questions + ability estimates
    POST /recommend        {learner_id, goals[], time_budget_min, mode, n_paths, ban[], lock[], ...}
    POST /schedule         {learner_id, goals[], deadline, weekly_minutes}  deadline calendar (C)
    POST /graph/health     {goal, learners}     self-healing prerequisite graph (claim D)
    POST /roadmap          {learner_id, goal, weekly_hours, deadline}   full personalised roadmap
    POST /observe          {learner_id, resource_id, correct, minutes, hints}
    POST /explain          {learner_id, resource_id}
    GET  /practice/tasks   the practice database schema + SQL tasks for a goal's graph
    POST /practice/submit  {learner_id, task_id, query}  sandbox-run, fingerprint, re-plan

The built React SPA (``frontend/`` -> ``velpo/web``) is served at ``/`` when present.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from algorithms.dynamic_programming import Plan, TeacherConstraints
from algorithms.scheduling import Availability, CalendarPlan
from assessment_bank import build_item_bank
from config import __version__, settings
from curriculum import build_curriculum
from engine import Engine
from model.assessment import AdaptiveSession, ItemBank
from model.knowledge_graph import KnowledgeGraph
from model.learner import Attempt, LearnerState
from practice import SHOP_DB, describe_db
from practice.catalogue import hints_for
from practice.content.excel_tasks import grid

_OBJ_KEYS = ("neg_gain", "seconds", "load", "diff_jump", "neg_review")
_SPEED_MULT = {"slow": 0.45, "normal": 1.0, "fast": 3.0}
_WEB = Path(__file__).resolve().parent / "web"

app = FastAPI(title="Syntropix", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_kg() -> KnowledgeGraph:
    """``VELPO_CATALOGUE=discovered`` serves the harvested open-resource catalogue;
    otherwise the default is the curated **SQL** data-analytics track (the most
    common entry point).  ``VELPO_CATALOGUE=algebra`` keeps the legacy curriculum."""
    cat = os.environ.get("VELPO_CATALOGUE")
    if cat == "discovered":
        from harvest import algebra_catalogue

        return algebra_catalogue()
    if cat == "algebra":
        return build_curriculum()
    from domains import seed_graph

    return seed_graph("sql")


_BANKS: dict[str, ItemBank | None] = {}


def _bank(domain: str) -> ItemBank | None:
    """The calibrated item bank for a seed domain or role (cached), if any."""
    if domain not in _BANKS:
        _BANKS[domain] = build_item_bank(domain)
    return _BANKS[domain]


_DEFAULT_DOMAIN = "algebra" if os.environ.get("VELPO_CATALOGUE") == "algebra" else "sql"
engine = Engine(
    _build_kg(), item_bank=build_item_bank(_DEFAULT_DOMAIN), graph_source="seed"
)  # default: the SQL data-analytics track
_ENGINES: dict[str, Engine] = {f"seed:{_DEFAULT_DOMAIN}": engine}
_LEARNER_ENGINE: dict[str, Engine] = {}  # which engine holds a learner's assessment


def _engine_for(goal: str | None) -> tuple[Engine, str, bool]:
    """(engine, domain, assessable) for a free-text goal.  Each resolved graph
    gets a cached engine, with the calibrated item bank when one exists."""
    if not goal or not goal.strip():
        return engine, _DEFAULT_DOMAIN, True
    from domains import resolve

    r = resolve(goal)
    key = f"{r.source}:{r.domain}"
    if key not in _ENGINES:
        bank = _bank(r.domain) if r.source != "dynamic" else None
        _ENGINES[key] = Engine(r.kg, item_bank=bank, graph_source=r.source)
    return _ENGINES[key], r.domain, _ENGINES[key].item_bank is not None


# --------------------------------------------------------------- schemas
class RecommendIn(BaseModel):
    learner_id: str = Field(min_length=1)
    goals: list[str] = Field(min_length=1)
    time_budget_min: float = Field(gt=0)
    mode: Literal["sequence", "optimal", "interactive", "pareto"] = "sequence"
    n_paths: int = Field(1, ge=1, le=20)
    ban: list[str] = []
    lock: list[str] = []
    force_order: list[tuple[str, str]] = []
    speed: Literal["slow", "normal", "fast"] = "normal"
    """Learning speed (N2): scales the learner's per-concept velocity before
    planning, so a fast and a slow learner get different optimal plans."""
    goal: str | None = None
    """Free-text goal - resolved to a knowledge graph; the concept ids in
    ``goals`` must come from that graph (see POST /resolve)."""


class GraphHealthIn(BaseModel):
    goal: str = Field(min_length=1)
    learners: int = Field(0, ge=0, le=20000)
    """> 0 runs a controlled recovery experiment (corrupt the graph, simulate
    trajectories, heal); 0 reports what real logged attempts say so far."""
    perturb: int = Field(2, ge=1, le=6)


class RoadmapIn(BaseModel):
    learner_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    weekly_hours: float = Field(5.0, gt=0, le=80)
    deadline: date | None = None
    band: Literal["beginner", "intermediate", "advanced"] | None = None
    """Self-reported level; defaults to the band from the learner's assessment,
    else 'intermediate'.  Selects which curated resources to recommend."""
    speed: Literal["slow", "normal", "fast"] = "normal"
    """"Take it slow" / "move fast" (N2): scales the learner's velocity before
    pace is read off it, so phase estimates and the finish date move with it -
    the same knob /recommend uses for the sequenced study plan."""


class ScheduleIn(BaseModel):
    learner_id: str = Field(min_length=1)
    goals: list[str] = Field(min_length=1)
    goal: str | None = None
    deadline: date
    weekly_minutes: float | None = Field(None, gt=0)
    """Total study minutes per week; spread evenly across the 7 days."""
    weekday_minutes: list[float] | None = None
    """7 entries (Mon..Sun); overrides ``weekly_minutes`` when given."""
    speed: Literal["slow", "normal", "fast"] = "normal"
    start: date | None = None
    """First study day (default today) - a later start simulates missed days."""


class ObserveIn(BaseModel):
    learner_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    correct: bool
    minutes: float = Field(ge=0)
    hints: int = Field(0, ge=0)


class PracticeIn(BaseModel):
    learner_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=4000)
    goals: list[str] = []
    """Concepts to re-plan toward; defaults to the task's own concept."""
    goal: str | None = None
    minutes: float = Field(5.0, gt=0, le=240)


class ExplainIn(BaseModel):
    learner_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)


class AssessStartIn(BaseModel):
    learner_id: str = Field(min_length=1)
    goals: list[str] = Field(min_length=1)
    goal: str | None = None
    band: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    """The learner's self-reported starting level - sets the prior the adaptive
    test starts from.  A beginner mostly keeps what they said."""


class AssessAnswerIn(BaseModel):
    learner_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    response: str  # MCQ: the chosen index as a string; task: the typed answer


def _assess_out(session: AdaptiveSession) -> dict[str, Any]:
    q = session.next_question()
    return {
        "done": session.done,
        "band": session.band,
        "answered": session.n_answered,
        "progress": round(session.progress(), 3),
        "remaining": session.remaining_estimate(),
        "style": session.style_signal() if session.done else None,
        "question": None
        if q is None
        else {
            "item_id": q.id,
            "skill": q.skill,
            "kind": q.kind,
            "stem": q.stem,
            "choices": list(q.choices),
            "a": q.a,
            "b": q.b,
        },
        "prior_sd": session.prior_sd,
        "prior_mean": session.prior_mean,
        "se_target": session.se_target,
        "estimates": [
            {
                "skill": e.skill,
                "theta": round(e.theta, 3),
                "se": round(e.se, 3),
                "mastery": round(e.mastery, 3),
                "n_items": e.n_items,
                "confident": e.confident,
            }
            for e in session.estimates().values()
        ],
    }


def _plan_out(
    p: Plan,
    kg: KnowledgeGraph,
    state: LearnerState | None = None,
    repairs: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    reviews = p.reviews or (False,) * len(p.steps)
    checks = p.checks or (False,) * len(p.steps)
    steps = []
    for rid, cid, reason, rev, chk in zip(
        p.steps, p.concepts, p.reasons or [""] * len(p.steps), reviews, checks
    ):
        res = kg.resources.get(rid)
        steps.append(
            {
                "resource_id": rid,
                "concept_id": cid,
                "reason": reason,
                "review": bool(rev),
                "check": bool(chk),
                "title": (res.title if res else "") or "",
                "url": res.url if res else "",
                "source": res.source if res else "",
                "kind": res.kind if res else "lesson",
                "difficulty": res.difficulty if res else 0.0,
                "minutes": res.minutes if res else 0.0,
                "concept": kg.concepts[cid].name if cid in kg.concepts else cid,
                "repair": cid in repairs,
            }
        )
    # "take every full lesson": the longest resource for each concept on the path
    baseline = sum(
        max((kg.resources[r].minutes for r in kg.resources_for(c)), default=0.0)
        for c in dict.fromkeys(p.concepts)
    )
    out: dict[str, Any] = {
        "feasible": p.feasible,
        "note": p.note,
        "total_minutes": round(p.total_seconds / 60, 1),
        "objective": dict(zip(_OBJ_KEYS, p.objective)),
        "steps": steps,
        "sessions": [{"start": a, "end": b} for a, b in p.sessions],
        "baseline_minutes": round(baseline, 1),
        "session_minutes": settings.session_minutes,
    }
    if state is not None:
        shown = dict.fromkeys(p.concepts)
        for cid in list(shown):
            shown.update(dict.fromkeys(kg.direct_prerequisites(cid)))
        out["mastery"] = {cid: round(state.mastery.get(cid, 0.0), 3) for cid in shown}
        out["p_correct"] = {cid: round(_p_correct(m), 3) for cid, m in out["mastery"].items()}
        out["prerequisites"] = {
            cid: sorted(kg.direct_prerequisites(cid)) for cid in dict.fromkeys(p.concepts)
        }
        out["names"] = {cid: kg.concepts[cid].name for cid in shown if cid in kg.concepts}
        measured = {
            cid: round(state.confidence(cid), 4)
            for cid in dict.fromkeys(p.concepts)
            if cid in state.mastery_se
        }
        if measured:
            out["confidence"] = measured
            out["min_confidence"] = round(min(measured.values()), 4)
    return out


# --------------------------------------------------------------- endpoints
@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "concepts": len(engine.kg.concepts),
        "resources": len(engine.kg.resources),
    }


@app.get("/catalogue")
def catalogue() -> dict[str, Any]:
    kg = engine.kg
    return {
        "concepts": [{"id": c.id, "name": c.name} for c in kg.concepts.values()],
        "resources": [
            {
                "id": r.id,
                "concepts": list(r.concepts),
                "difficulty": r.difficulty,
                "minutes": r.minutes,
                "kind": r.kind,
                "title": r.title,
                "url": r.url,
                "source": r.source,
            }
            for r in kg.resources.values()
        ],
        "goals": kg.sink_concepts(),
        "discovered": any(r.source for r in kg.resources.values()),
    }


class ResolveIn(BaseModel):
    goal: str = Field(min_length=2)
    allow_dynamic: bool = True


@app.post("/resolve")
def resolve_goal(body: ResolveIn) -> dict[str, Any]:
    """Free-text goal -> a knowledge graph (curated seed, or built dynamically)."""
    from domains import resolve

    try:
        r = resolve(body.goal, allow_dynamic=body.allow_dynamic)
    except Exception as exc:  # dynamic construction hits the network
        raise HTTPException(502, f"could not resolve {body.goal!r}: {exc}") from exc
    return {
        "goal": body.goal,
        "domain": r.domain,
        "source": r.source,
        "assessable": r.source != "dynamic" and _bank(r.domain) is not None,
        "goals": r.goals,
        "concepts": [{"id": c.id, "name": c.name} for c in r.kg.concepts.values()],
        "prerequisites": [[u, v] for u, v in r.kg.prereq.edges()],
    }


@app.get("/discover/{concept_id}")
def discover(concept_id: str, goal: str | None = None, refresh: bool = False) -> dict[str, Any]:
    eng, _domain, _a = _engine_for(goal)
    if concept_id not in eng.kg.concepts:
        raise HTTPException(404, f"unknown concept {concept_id!r}")
    from harvest.catalogue import CONCEPT_QUERY, discover_for_concept

    name = CONCEPT_QUERY.get(concept_id, eng.kg.concepts[concept_id].name)
    try:
        scored = discover_for_concept(name, domain="math", k=8) if refresh else []
    except Exception as exc:  # discovery hits the network - report, don't crash
        raise HTTPException(502, f"discovery failed: {exc}") from exc
    if not scored:  # default: read what the served catalogue already has
        return {
            "concept": concept_id,
            "resources": [
                {
                    "title": r.title or r.id,
                    "url": r.url,
                    "source": r.source or "synthetic",
                    "kind": r.kind,
                    "difficulty": r.difficulty,
                    "minutes": r.minutes,
                }
                for rid in eng.kg.resources_for(concept_id)
                for r in [eng.kg.resources[rid]]
            ],
        }
    return {
        "concept": concept_id,
        "resources": [
            {
                "title": raw.title,
                "url": raw.url,
                "source": raw.source,
                "kind": raw.kind,
                "difficulty": lvl.difficulty,
                "minutes": raw.minutes,
                "fk_grade": lvl.fk_grade,
                "quality": lvl.quality,
            }
            for raw, lvl in scored
        ],
    }


def _role_recommend(learner_id: str, goal: str, minutes: float, _speed: str) -> dict[str, Any]:
    from algorithms.roleplan import solve_role_plan
    from domain_data import ROLES, role_profile
    from domains import resolve

    r = resolve(goal)
    role = next(x for x in ROLES if x.name == r.domain)
    eng, _d, _a = _engine_for(goal)
    state = eng.ensure(learner_id, time_budget_s=minutes * 60)
    profile = {k: v for k, v in role_profile(role).items() if k in r.kg.concepts}
    rp = solve_role_plan(r.kg, role.name, profile, state, budget_minutes=minutes)
    from engine import _sequence_to_plan
    from explain import explain_plan

    plan = explain_plan(r.kg, _sequence_to_plan(r.kg, rp.sequence), state)
    return {
        "paths": [_plan_out(plan, r.kg, state)],
        "meta": {
            "mode": "role",
            "domain": r.domain,
            "role": True,
            "method": rp.method,
            "readiness": rp.readiness,
            "readiness_before": rp.readiness_before,
            "readiness_curve": [list(p) for p in rp.steps_curve],
            "covered_weight": rp.covered_weight,
            "total_weight": rp.total_weight,
        },
    }


@app.post("/recommend")
def recommend(body: RecommendIn) -> dict[str, Any]:
    if body.goal:
        from domains import resolve

        if resolve(body.goal).source == "role":
            return _role_recommend(body.learner_id, body.goal, body.time_budget_min, body.speed)
    eng, domain, _a = _engine_for(body.goal)
    unknown = [c for c in body.goals if c not in eng.kg.concepts]
    if unknown:
        raise HTTPException(422, f"unknown concepts for {domain!r}: {unknown}")
    tc = TeacherConstraints.make(ban=body.ban, lock=body.lock, force_order=body.force_order)
    repairs = eng.repairs(body.learner_id)
    # a concept a practice diagnosis routed in stays on the plan until mastered
    goals = list(dict.fromkeys([*sorted(r for r in repairs if r in eng.kg.concepts), *body.goals]))
    plans = eng.recommend(
        body.learner_id,
        goals,
        time_budget_s=body.time_budget_min * 60,
        mode=body.mode,
        n_paths=body.n_paths,
        constraints=tc,
        speed=_SPEED_MULT[body.speed],
    )
    meta: dict[str, Any] = {
        "mode": body.mode,
        "returned": len(plans),
        "speed": body.speed,
        "domain": domain,
    }
    if plans and not plans[0].feasible:
        meta["infeasible_reason"] = plans[0].note
    lstate = eng.store.get(body.learner_id)
    paths = [_plan_out(p, eng.kg, lstate, repairs) for p in plans]
    if paths and "confidence" in paths[0]:
        conf0 = paths[0]["confidence"]
        goal_conf = {c: conf0[c] for c in body.goals if c in conf0}
        if goal_conf:
            meta["goal_confidence"] = goal_conf
            meta["plan_confidence"] = min(goal_conf.values())
    return {"paths": paths, "meta": meta}


def _calendar_out(cp: CalendarPlan, kg: KnowledgeGraph) -> dict[str, Any]:
    def nm(cid: str) -> str:
        c = kg.concepts.get(cid)
        return c.name if c else cid

    steps = []
    for s in cp.steps:
        res = kg.resources.get(s.resource_id)
        steps.append(
            {
                "day": s.day.isoformat(),
                "weekday": s.day.weekday(),
                "slot_index": s.slot_index,
                "concept_id": s.concept,
                "concept": nm(s.concept),
                "resource_id": s.resource_id,
                "title": (res.title if res else "") or s.resource_id,
                "url": res.url if res else "",
                "source": res.source if res else "",
                "kind": s.kind,
                "minutes": round(s.minutes, 1),
            }
        )
    return {
        "feasible": cp.feasible,
        "note": cp.note,
        "start": cp.start.isoformat(),
        "deadline": cp.deadline.isoformat(),
        "finish": cp.finish.isoformat() if cp.finish else None,
        "slack_days": cp.slack_days,
        "weeks": cp.weeks,
        "hours_per_week": cp.hours_per_week,
        "hours_per_week_needed": cp.hours_per_week_needed,
        "n_retention": cp.n_retention,
        "goal_mastery": {nm(k): v for k, v in cp.goal_mastery.items()},
        "reasons": list(cp.reasons),
        "steps": steps,
    }


@app.post("/schedule")
def schedule(body: ScheduleIn) -> dict[str, Any]:
    eng, domain, _a = _engine_for(body.goal)
    unknown = [c for c in body.goals if c not in eng.kg.concepts]
    if unknown:
        raise HTTPException(422, f"unknown concepts for {domain!r}: {unknown}")
    if body.weekday_minutes is not None:
        if len(body.weekday_minutes) != 7 or any(m < 0 for m in body.weekday_minutes):
            raise HTTPException(422, "weekday_minutes must be 7 non-negative numbers (Mon..Sun)")
        avail = Availability(tuple(body.weekday_minutes))  # type: ignore[arg-type]
    else:
        weekly = body.weekly_minutes or settings.calendar_weekly_minutes_default
        avail = Availability.uniform(weekly)
    cp = eng.calendar_plan(
        body.learner_id,
        body.goals,
        deadline=body.deadline,
        availability=avail,
        start=body.start or date.today(),
        # a later start (missed days) re-schedules the *same* plan: its budget
        # is sized from today, not shrunk to the days that are left
        time_budget_s=avail.weekly_minutes
        * 60.0
        * max(1.0, (body.deadline - date.today()).days / 7.0),
        speed=_SPEED_MULT[body.speed],
    )
    return {"calendar": _calendar_out(cp, eng.kg), "meta": {"domain": domain}}


# ------------------------------------- calendar feedback loop (claim F)
class SessionLog(BaseModel):
    day: date
    planned_minutes: float = Field(ge=0)
    done_minutes: float = Field(ge=0)


class RescheduleIn(BaseModel):
    learner_id: str = Field(min_length=1)
    goals: list[str] = Field(min_length=1)
    goal: str | None = None
    deadline: date
    hours_per_week: float = Field(6.0, gt=0, le=80)
    speed: Literal["slow", "normal", "fast"] = "normal"
    plan_start: date | None = None
    """The day the learner started this plan - sessions before today are read back."""
    today: date | None = None
    now_minute: int | None = Field(None, ge=0, lt=24 * 60)
    log: list[SessionLog] = []
    windows: dict[int, list[tuple[str, str]]] | None = None
    """When the learner *could* study, per weekday (0 = Monday): [["18:00", "22:00"], ...].
    The planner picks inside these, up to ``hours_per_week``."""
    busy_ics: str | None = Field(None, max_length=3_000_000)
    """The learner's calendar export; its events become busy time."""
    velocity_aware: bool = True
    """Size each topic by this learner's measured / predicted learning velocity (claim G)."""


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


class WhatFitsIn(BaseModel):
    learner_id: str = Field(min_length=1)
    goal: str
    goals: list[str] = Field(min_length=1)
    deadline: date
    hours_per_week: float = Field(6.0, gt=0, le=80)
    confidence: float = Field(0.9, ge=0.5, le=0.99)
    log: list[SessionLog] = []
    today: date | None = None


@app.post("/what-fits")
def what_fits(body: WhatFitsIn) -> dict[str, Any]:
    """Which goals can be finished by the deadline with the asked confidence
    (claim G3): a chance-constrained choice over prerequisite closures, with
    this learner's velocity-sized times and adherence uncertainty."""
    import networkx as nx

    from algorithms import chance_goals as cg
    from algorithms import reschedule as rs
    from algorithms import velocity_schedule as vs
    from domain_data import ROLES

    eng, domain, _a = _engine_for(body.goal)
    kg = eng.kg
    unknown = [g for g in body.goals if g not in kg.concepts]
    if unknown:
        raise HTTPException(422, f"unknown concepts: {unknown}")
    today = body.today or date.today()
    if body.deadline <= today:
        raise HTTPException(422, "the deadline must be after today")
    state = eng.store.get(body.learner_id)
    mastery = dict(state.mastery) if state else {}
    vel = dict(state.velocity) if state else {}
    observed = {c for c, v in vel.items() if abs(v - 1.0) > 1e-9}
    prereq = {c: sorted(kg.direct_prerequisites(c)) for c in kg.concept_ids}
    v_hat = vs.predicted_velocity(kg.concept_ids, prereq, vel, observed)
    ancestors = {g: set(nx.ancestors(kg.prereq, g)) for g in body.goals}
    todo = set().union(*({g} | ancestors[g] for g in body.goals))
    # the planner's own minutes per concept (every step it would schedule, not one lesson)
    plan = eng.calendar_plan(
        body.learner_id, body.goals, deadline=today + timedelta(days=730),
        availability=Availability.uniform(body.hours_per_week * 60), start=today,
        time_budget_s=body.hours_per_week * 3600 * 104,
    )  # fmt: skip
    planned: dict[str, float] = {}
    for st in plan.steps:
        if st.kind != "retention":
            planned[st.concept] = planned.get(st.concept, 0.0) + st.minutes
    minutes: dict[str, float] = {}
    for c in todo:
        if mastery.get(c, 0.0) >= settings.mastery_threshold or c not in planned:
            continue  # already known (or not on the plan): costs nothing
        minutes[c] = planned[c] * vs.time_ratio(mastery.get(c, vs.M_INIT), v_hat.get(c, 1.0))
    role = next((r for r in ROLES if r.name == domain), None)
    weights = {f"{d}.{c}": w for d, c, w in role.skills} if role else {}
    values = {g: weights.get(g, 1.0) for g in body.goals}
    rates = [e.done_minutes / e.planned_minutes for e in body.log if e.planned_minutes]
    sc = cg.Scenarios(
        minutes, sigma=0.45 / (1 + len(observed)) ** 0.5, adherence_rates=rates, samples=500
    )

    def capacity_at(hours: float) -> float:
        cap = vs.capacity(
            today, body.deadline, windows=rs.availability_windows(),
            base_cap=hours * 60 / 7 * 1.6, weekly_cap=hours * 60,
        )  # fmt: skip
        return sum(m for _d, m in cap)

    cap_minutes = capacity_at(body.hours_per_week)
    choice = cg.choose(values, ancestors, sc, cap_minutes, confidence=body.confidence)
    by_mean = cg.choose_by_mean(values, ancestors, sc, cap_minutes)
    need_hours = cg.hours_for_all(values, ancestors, sc, capacity_at, confidence=body.confidence)

    def nm(c: str) -> str:
        return kg.concepts[c].name if c in kg.concepts else c

    return {
        "confidence": body.confidence,
        "capacity_hours": round(cap_minutes / 60, 1),
        "chosen": [{"concept_id": g, "concept": nm(g), "value": values[g]} for g in choice.goals],
        "dropped": [
            {"concept_id": g, "concept": nm(g), "value": values[g]} for g in choice.dropped
        ],
        "p_finish": choice.p_finish,
        "expected_hours": round(choice.expected_minutes / 60, 1),
        "p90_hours": round(choice.p90_minutes / 60, 1),
        "value_share": round(choice.value / max(1e-9, sum(values.values())), 3),
        "hours_per_week_for_all": need_hours,
        "by_expected_time": {
            "goals": [nm(g) for g in by_mean.goals],
            "p_finish": by_mean.p_finish,
        },
    }


_SLOW_ATTRIBUTED: set[tuple[str, str, str]] = set()


def _busy_spans(
    busy: list[tuple[datetime, datetime]], first: date, days: int
) -> dict[str, list[list[str]]]:
    """Calendar events clipped to each of the next ``days`` days, as [["09:00", "17:30"], ...]."""
    from algorithms.reschedule import hhmm

    out: dict[str, list[list[str]]] = {}
    for k in range(days):
        d = first + timedelta(days=k)
        lo = datetime.combine(d, datetime.min.time())
        hi = lo + timedelta(days=1)
        spans = []
        for a, b in busy:
            if a < hi and b > lo:
                s0 = int((max(a, lo) - lo).total_seconds() // 60)
                s1 = int((min(b, hi) - lo).total_seconds() // 60)
                spans.append([hhmm(s0), hhmm(min(s1, 24 * 60 - 1))])
        if spans:
            out[d.isoformat()] = spans
    return out


@app.post("/reschedule")
def reschedule_plan(body: RescheduleIn) -> dict[str, Any]:
    """Read back what happened (log + real calendar), measure adherence, then
    split and re-fit the rest of the plan into the learner's real free time."""
    from algorithms import reschedule as rs

    eng, domain, _a = _engine_for(body.goal)
    unknown = [c for c in body.goals if c not in eng.kg.concepts]
    if unknown:
        raise HTTPException(422, f"unknown concepts for {domain!r}: {unknown}")
    today = body.today or date.today()
    start = min(body.plan_start or today, today)
    if body.deadline <= today:
        raise HTTPException(422, "the deadline must be after today")
    weekly = body.hours_per_week * 60
    cp = eng.calendar_plan(
        body.learner_id,
        body.goals,
        deadline=body.deadline,
        availability=Availability.uniform(weekly),
        start=start,
        time_budget_s=weekly * 60.0 * max(1.0, (body.deadline - start).days / 7.0),
        speed=_SPEED_MULT[body.speed],
    )
    names = eng.kg.concepts
    steps = sorted(cp.steps, key=lambda s: (s.day, s.slot_index))
    past: dict[date, float] = {}
    for s in steps:
        if s.day < today:
            past[s.day] = past.get(s.day, 0.0) + s.minutes

    # read back: done minutes come off the front of the plan (work is sequential)
    done = sum(e.done_minutes for e in body.log)
    work: list[rs.Work] = []
    for i, s in enumerate(steps):
        m = s.minutes
        if done >= m:
            done -= m
            continue
        res = eng.kg.resources.get(s.resource_id)
        title = (res.title if res else "") or (
            names[s.concept].name if s.concept in names else s.concept
        )
        work.append(rs.Work(f"{i}", s.concept, title, m - done, s.kind))
        done = 0.0

    # velocity-aware sizing (claim G): this learner's time per topic, not the lesson's
    from algorithms import velocity_schedule as vs

    state = eng.store.get(body.learner_id)
    vel = dict(state.velocity) if state else {}
    observed = {c for c, v in vel.items() if abs(v - 1.0) > 1e-9}  # 1.0 = untouched prior
    sized: list[vs.Sized] = []
    if body.velocity_aware:
        prereq = {c: sorted(eng.kg.direct_prerequisites(c)) for c in eng.kg.concept_ids}
        v_hat = vs.predicted_velocity(eng.kg.concept_ids, prereq, vel, observed)
        mastery = dict(state.mastery) if state else {}
        sized = vs.size_work([(w.concept, w.minutes, w.kind) for w in work], mastery, v_hat)
        work = [
            rs.Work(w.id, w.concept, w.title, z.minutes, w.kind, hardness=z.ratio)
            for w, z in zip(work, sized)
        ]

    entries = [rs.LogEntry(e.day, e.planned_minutes, e.done_minutes) for e in body.log]
    rate = rs.adherence(entries)
    windows = (
        {int(d): [(_hm(a), _hm(b)) for a, b in ws] for d, ws in body.windows.items()}
        if body.windows
        else rs.availability_windows()
    )
    week_done = sum(
        e.done_minutes for e in body.log if e.day.isocalendar()[:2] == today.isocalendar()[:2]
    )
    try:
        busy = rs.parse_ics_busy(body.busy_ics) if body.busy_ics else []
    except ValueError as exc:
        raise HTTPException(422, f"couldn't read the calendar file: {exc}") from exc
    busy = [(a, b) for a, b in busy if b.date() >= today and a.date() <= body.deadline]

    # study context (G4/G5): best slots and focus span, once there's enough evidence
    import telemetry
    from algorithms import study_context as sx

    events = telemetry.load(body.learner_id)
    speeds = sx.slot_speeds(events) if len(events) >= sx.MIN_EVENTS else {}  # type: ignore[arg-type]
    focus = sx.focus_span(events) if len(events) >= sx.MIN_EVENTS else None  # type: ignore[arg-type]
    new = rs.reschedule(
        work, start=today, deadline=body.deadline, windows=windows, busy=busy,
        adherence_rate=rate, base_cap=weekly / 7 * 1.6, weekly_cap=weekly,
        week_done=week_done, now_minute=body.now_minute,
        slot_score=sx.slot_scorer(speeds) if speeds else None,
        block_cap=focus.block_min if focus and focus.answers >= sx.MIN_EVENTS else None,
    )  # fmt: skip
    # slowdowns (G2): a topic learned far slower than predicted points at a gap
    from algorithms.slowdown import detect

    order = list(dict.fromkeys(s.concept for s in steps))
    prereq_map = {c: sorted(eng.kg.direct_prerequisites(c)) for c in eng.kg.concept_ids}
    slowdowns = detect(
        eng.kg.concept_ids, prereq_map, vel, observed,
        dict(state.mastery) if state else {}, order=order,
    )  # fmt: skip
    for sd in slowdowns:  # the top missing-link suspect becomes evidence for the graph (claim D)
        top = next((x for x in sd.suspects if x.kind == "missing_prerequisite"), None)
        key = (body.learner_id, top.concept if top else "", sd.concept)
        if (
            top
            and key not in _SLOW_ATTRIBUTED
            and eng.evidence.attribute(top.concept, sd.concept, 1.0 - sd.ratio) is not None
        ):
            _SLOW_ATTRIBUTED.add(key)
    from algorithms.calibration import calibrate

    calib = calibrate(entries)  # does this learner's record back the forecast's bands?
    cap = vs.capacity(
        today, body.deadline + timedelta(days=180), windows=windows, busy=busy,
        base_cap=weekly / 7 * 1.6, weekly_cap=weekly, week_done=week_done,
    )  # fmt: skip
    fc = vs.forecast(
        [w.minutes for w in work], [z.ratio for z in sized] if sized else [1.0] * len(work),
        cap, body.deadline, observed_concepts=len(observed),
        adherence_rates=[e.done_minutes / e.planned_minutes for e in entries if e.planned_minutes],
        trust=calib.trust,
    )  # fmt: skip
    topics: dict[str, dict[str, Any]] = {}
    for w, z in zip(work, sized):
        if w.kind in ("review", "retention") or w.concept in topics:
            continue
        topics[w.concept] = {
            "concept_id": w.concept,
            "concept": names[w.concept].name if w.concept in names else w.concept,
            "ratio": round(z.ratio, 2),
            "velocity": round(z.velocity, 2),
            "hours_to_master": round(z.hours_to_master, 2),
            "source": "measured" if w.concept in observed else "predicted",
        }
    if sized:
        slow = sum(1 for t in topics.values() if t["ratio"] > 1.15)
        quick = sum(1 for t in topics.values() if t["ratio"] < 0.85)
        if slow or quick:
            new.reasons.insert(
                0,
                f"Planned at your speed: {slow} topic(s) get more time than the lessons say, "
                f"{quick} get less ({len(observed)} measured from your practice, "
                "the rest predicted from what they build on).",
            )
    # the same (adherence-adjusted) workload, the way a fixed calendar handles it
    inflated = [
        rs.Work(w.id, w.concept, w.title, w.minutes / max(0.2, min(1.0, rate)), w.kind)
        for w in work
    ]
    naive = rs.naive_shift(
        inflated, start=today, deadline=body.deadline,
        windows=rs.default_windows(body.hours_per_week), busy=busy,
    )  # fmt: skip

    def nm(c: str) -> str:
        return names[c].name if c in names else c

    return {
        "adherence": round(rate, 3),
        "logged_days": len(body.log),
        "done_minutes": round(sum(e.done_minutes for e in body.log)),
        "planned_minutes_so_far": round(sum(e.planned_minutes for e in body.log)),
        "effective_hours_per_week": round(body.hours_per_week * min(1.0, rate), 2),
        "busy_events": len(busy),
        "past_days": [
            {"day": d.isoformat(), "planned_minutes": round(m)} for d, m in sorted(past.items())
        ],
        "remaining_minutes": round(new.remaining_minutes),
        "feasible": new.feasible,
        "finish": new.finish.isoformat() if new.finish else None,
        "deadline": body.deadline.isoformat(),
        "hours_per_week_needed": round(new.hours_per_week_needed, 1),
        "reasons": new.reasons,
        "forecast": {
            "p50": fc.p50.isoformat() if fc.p50 else None,
            "p80": fc.p80.isoformat() if fc.p80 else None,
            "p95": fc.p95.isoformat() if fc.p95 else None,
            "p_on_time": fc.p_on_time,
            "trust": calib.trust,
            "checks": calib.checks,
            "hits": calib.hits,
        },
        "study_times": [
            {"slot": v.slot, "multiplier": v.multiplier, "answers": v.answers}
            for v in sorted(speeds.values(), key=lambda v: -v.multiplier)
        ],
        "focus": (
            {
                "half_life_min": focus.half_life_min,
                "block_min": focus.block_min,
                "answers": focus.answers,
            }
            if focus
            else None
        ),
        "practice_answers": len(events),
        "slowdowns": [
            {
                "concept_id": sd.concept,
                "concept": names[sd.concept].name if sd.concept in names else sd.concept,
                "ratio": sd.ratio,
                "suspects": [
                    {
                        "concept_id": x.concept,
                        "concept": names[x.concept].name if x.concept in names else x.concept,
                        "kind": x.kind,
                        "mastery": x.mastery,
                    }
                    for x in sd.suspects
                ],
            }
            for sd in slowdowns[:5]
        ],
        "velocity": {
            "aware": bool(sized),
            "measured_topics": len(observed),
            "topics": sorted(topics.values(), key=lambda t: -float(t["ratio"])),
        },
        "blocks": [
            {
                "day": b.day.isoformat(),
                "start": rs.hhmm(b.start),
                "end": rs.hhmm(b.end),
                "minutes": b.end - b.start,
                "concept_id": b.concept,
                "concept": nm(b.concept),
                "title": b.title,
                "kind": b.kind,
                "part": b.part,
                "parts": b.parts,
            }
            for b in new.blocks
        ],
        "days": [
            {
                "day": d.day.isoformat(),
                "busy_minutes": round(d.busy_minutes),
                "fatigue": round(d.fatigue, 3),
                "cap_minutes": round(d.cap_minutes),
                "max_block": d.max_block,
                "study_minutes": round(d.study_minutes),
            }
            for d in new.days
        ],
        "busy_spans": _busy_spans(busy, today, 21),
        "naive": {
            "finish": naive.finish.isoformat() if naive.finish else None,
            "feasible": naive.feasible,
            "notes": naive.reasons,
        },
    }


# --------------------------------------------- self-healing graph (claim D)
def _edge_changes(changes: object) -> list[dict[str, Any]]:
    from algorithms.graph_health import EdgeChange

    seq: tuple[EdgeChange, ...] = changes  # type: ignore[assignment]
    return [
        {
            "a": c.a,
            "b": c.b,
            "a_name": c.a_name,
            "b_name": c.b_name,
            "action": c.action,
            "mean": c.mean,
            "prior_mean": c.prior_mean,
            "support": c.support,
            "summary": c.summary,
        }
        for c in seq
    ]


@app.post("/graph/health")
def graph_health(body: GraphHealthIn) -> dict[str, Any]:
    from algorithms.graph_health import simulate_recovery
    from domains import resolve

    r = resolve(body.goal)
    if body.learners > 0:
        rec = simulate_recovery(r.kg, learners=body.learners, perturb=body.perturb)
        rep = rec.report
        recovery: dict[str, Any] | None = {
            "hidden": [list(e) for e in rec.hidden],
            "injected": [list(e) for e in rec.injected],
            "hidden_recovered": [list(e) for e in rec.hidden_recovered],
            "injected_pruned": [list(e) for e in rec.injected_pruned],
            "recall": round(rec.recall, 3),
            "precision_drop": round(rec.precision_drop, 3),
        }
    else:
        eng, _d, _a = _engine_for(body.goal)
        rep = eng.graph_health()
        recovery = None
    return {
        "domain": r.domain,
        "source": r.source,
        "observations": rep.observations,
        "watched": rep.watched,
        "clean": rep.clean,
        "pruned": _edge_changes(rep.pruned),
        "added": _edge_changes(rep.added),
        "suggested": _edge_changes(rep.suggested),
        "reweighted": _edge_changes(rep.reweighted),
        "recovery": recovery,
    }


# --------------------------------------------------------- roadmap
def _roadmap_out(rm: object) -> dict[str, Any]:
    from roadmap import Roadmap

    r: Roadmap = rm  # type: ignore[assignment]
    return {
        "goal": r.goal,
        "domain": r.domain,
        "role": r.role,
        "pace": r.pace,
        "weekly_hours": r.weekly_hours,
        "starting_readiness": r.starting_readiness,
        "target_readiness": r.target_readiness,
        "already_have": list(r.already_have),
        "you_are_here": r.you_are_here,
        "total_hours": r.total_hours,
        "total_weeks": r.total_weeks,
        "finish_estimate": r.finish_estimate,
        "band": r.band,
        "deadline": r.deadline,
        "on_track": r.on_track,
        "notes": list(r.notes),
        "recommended": list(r.recommended),
        "phases": [
            {
                "index": p.index,
                "title": p.title,
                "domain": p.domain,
                "concept_ids": list(p.concept_ids),
                "concept_names": list(p.concept_names),
                "new_skills": p.new_skills,
                "est_hours": p.est_hours,
                "est_weeks": p.est_weeks,
                "start_week": p.start_week,
                "focus": p.focus,
                "checkpoint": p.checkpoint,
                "resources": list(p.resources),
                "videos": list(p.videos),
                "certifications": [_cert_out(c) for c in p.certifications],
            }
            for p in r.phases
        ],
        "certifications": [_cert_out(c) for c in r.certifications],
    }


def _cert_out(c: object) -> dict[str, Any]:
    from certifications import Certification

    x: Certification = c  # type: ignore[assignment]
    return {
        "id": x.id,
        "name": x.name,
        "provider": x.provider,
        "url": x.url,
        "level": x.level,
        "free": x.free,
        "price_note": x.price_note,
        "hours": x.hours,
        "blurb": x.blurb,
    }


@app.post("/roadmap")
def roadmap(body: RoadmapIn) -> dict[str, Any]:
    from domains import resolve
    from roadmap import build_roadmap

    eng, _domain, _a = _engine_for(body.goal)
    r = resolve(body.goal)
    state = eng.store.get(body.learner_id) or eng.ensure(body.learner_id, time_budget_s=3600.0)
    band = body.band or eng.assessment_band(body.learner_id) or "intermediate"
    rm = build_roadmap(
        r.kg,
        r,
        state,
        weekly_hours=body.weekly_hours,
        deadline=body.deadline,
        band=band,
        speed=_SPEED_MULT[body.speed],
    )
    return {"roadmap": _roadmap_out(rm)}


_SPEED_PACE = {"slow": "deliberate", "normal": "steady", "fast": "fast"}


def _goal_domains(goal: str | None) -> tuple[Engine, str, set[str]]:
    eng, domain, _ = _engine_for(goal)
    ds = {c.split(".", 1)[0] for c in eng.kg.concepts if "." in c} or {domain}
    return eng, domain, ds


@app.get("/library")
def library(
    goal: str | None = None,
    learner_id: str | None = None,
    speed: Literal["slow", "normal", "fast"] = "normal",
    pace: Literal["auto", "deliberate", "steady", "fast"] = "auto",
    hours_per_week: float = Query(7.0, gt=0, le=80),
) -> dict[str, Any]:
    """Videos and practice problems (LeetCode, HackerRank, open sites) for this
    goal, in prerequisite order and paced by the learner's measured velocity."""
    import skill_library

    eng, domain, _ds = _goal_domains(goal)
    state = eng.store.get(learner_id) if learner_id else None
    measured = skill_library.pace_of(state, fallback="")
    chosen = pace if pace != "auto" else (measured or _SPEED_PACE[speed])
    lib = skill_library.build(eng.kg, domain, state, pace=chosen, hours_per_week=hours_per_week)
    return {
        "pace": lib.pace,
        "pace_text": lib.pace_text,
        "pace_source": "chosen"
        if pace != "auto"
        else "measured"
        if measured
        else "your speed setting",
        "harvested": lib.harvested,
        "totals": lib.totals,
        "courses": lib.courses,
        "steps": lib.steps,
        "weeks": lib.weeks,
        "stretch": lib.stretch,
        "extra": lib.extra,
        "review": lib.review,
        "mixed": lib.mixed,
    }


@app.get("/library/stats")
def library_stats() -> dict[str, Any]:
    import skill_library

    return skill_library.stats()


@app.get("/certifications")
def certifications(goal: str | None = None) -> dict[str, Any]:
    from certifications import certifications_for

    _eng, _domain, ds = _goal_domains(goal)
    return {"certifications": [_cert_out(c) for c in certifications_for(ds)]}


@app.post("/observe")
def observe(body: ObserveIn) -> dict[str, Any]:
    eng = _LEARNER_ENGINE.get(body.learner_id, engine)
    if body.resource_id not in eng.kg.resources:
        raise HTTPException(404, f"unknown resource {body.resource_id!r}")
    try:
        state = eng.observe(
            body.learner_id, Attempt(body.resource_id, body.correct, body.minutes * 60, body.hints)
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    mean_v = sum(state.velocity.values()) / len(state.velocity) if state.velocity else 0.0
    return {
        "n_interactions": state.n_interactions,
        "time_budget_min": round(state.time_budget_s / 60, 1),
        "mean_velocity": round(mean_v, 3),
        "mastery": {k: round(v, 3) for k, v in state.mastery.items()},
    }


@app.post("/assess/start")
def assess_start(body: AssessStartIn) -> dict[str, Any]:
    eng, domain, assessable = _engine_for(body.goal)
    if not assessable:
        raise HTTPException(
            422, f"no calibrated diagnostic for {domain!r} yet - plan uses cold-start priors"
        )
    unknown = [c for c in body.goals if c not in eng.kg.concepts]
    if unknown:
        raise HTTPException(422, f"unknown concepts: {unknown}")
    session = eng.start_assessment(body.learner_id, body.goals, band=body.band)
    _LEARNER_ENGINE[body.learner_id] = eng
    return _assess_out(session)


@app.post("/assess/answer")
def assess_answer(body: AssessAnswerIn) -> dict[str, Any]:
    eng = _LEARNER_ENGINE.get(body.learner_id, engine)
    try:
        session = eng.answer_assessment(body.learner_id, body.item_id, body.response)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _assess_out(session)


@app.get("/assess/{learner_id}")
def assess_state(learner_id: str) -> dict[str, Any]:
    try:
        return _assess_out(_LEARNER_ENGINE.get(learner_id, engine).assessment(learner_id))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


def _practice_engine(learner_id: str | None, goal: str | None) -> Engine:
    if learner_id and learner_id in _LEARNER_ENGINE and not goal:
        return _LEARNER_ENGINE[learner_id]
    eng, _domain, _ = _engine_for(goal)
    return eng


@app.get("/practice/tasks")
def practice_tasks(
    goal: str | None = None, learner_id: str | None = None, target: str | None = None
) -> dict[str, Any]:
    """The schema, the tasks, and - given a learner and a ``target`` concept - the
    task to start on (the first one on that learner's plan to the target)."""
    eng = _practice_engine(learner_id, goal)
    tasks = eng.practice_tasks()
    if not tasks:
        raise HTTPException(422, "no practice tasks for this goal's graph")
    start: str | None = None
    path: list[str] = []
    if learner_id and target:
        if target not in eng.kg.concepts:
            raise HTTPException(422, f"unknown concept {target!r}")
        start, path = eng.next_practice_task(learner_id, [target])
    state = eng.store.get(learner_id) if learner_id else None
    shown = [c for t in tasks if (c := eng.concept_id(t.concept)) is not None]
    mastery = {
        c: round(state.mastery.get(c, 0.0), 3) if state else 0.0
        for c in dict.fromkeys(path + shown)
    }
    return {
        "start": start,
        "path": path,
        "mastery": mastery,
        "p_correct": {c: round(_p_correct(m), 3) for c, m in mastery.items()},
        "schema": _schema(),
        "sheet": [list(r) for r in grid()],
        "tasks": [
            {
                "id": t.id,
                "concept_id": cid,
                "concept": eng.kg.concepts[cid].name,
                "kind": t.kind,
                "domain": t.domain,
                "prompt": t.prompt,
                "ordered": t.ordered,
                "minutes": round(eng.kg.resources[f"{cid}:practice"].minutes, 1)
                if f"{cid}:practice" in eng.kg.resources
                else 5.0,
                "hints": [h for h in hints_for(t) if h],
                "cell": t.cell,
                "fill_down": t.fill_down,
                "options": list(t.options),
                "context": [list(r) for r in t.context],
                "context_note": t.context_note,
                "env": {k: repr(v) for k, v in t.env},
            }
            for t in tasks
            if (cid := eng.concept_id(t.concept)) is not None
        ],
    }


_SCHEMA_CACHE: dict[str, Any] = {}


def _schema() -> dict[str, Any]:
    if not _SCHEMA_CACHE:
        _SCHEMA_CACHE.update(describe_db(SHOP_DB))
    return _SCHEMA_CACHE


def _p_correct(mastery: float) -> float:
    """The BKT model's own prediction of a correct answer at this mastery."""
    s, g = settings.bkt_p_slip, settings.bkt_p_guess
    return mastery * (1 - s) + (1 - mastery) * g


@app.post("/practice/submit")
def practice_submit(body: PracticeIn) -> dict[str, Any]:
    eng = _practice_engine(body.learner_id, body.goal)
    unknown = [c for c in body.goals if c not in eng.kg.concepts]
    if unknown:
        raise HTTPException(422, f"unknown concepts: {unknown}")
    try:
        out = eng.submit_practice(
            body.learner_id, body.task_id, body.query, goals=body.goals, minutes=body.minutes
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    _LEARNER_ENGINE.setdefault(body.learner_id, eng)
    names = eng.kg.concepts
    g = out.graded
    assert g is not None
    target_before = next(iter(out.mastery.values()), (0.0, 0.0))[0]
    key = (body.learner_id, out.task_id)
    _ATTEMPTS[key] = _ATTEMPTS.get(key, 0) + 1
    in_portfolio = False
    try:  # study context (claims G4/G5): when, and how far into the session
        import telemetry

        task_concept = next(iter(out.mastery), "")
        telemetry.record(
            body.learner_id,
            correct=out.correct,
            expected=_p_correct(target_before),
            concept=task_concept,
        )
    except OSError:
        pass
    if out.correct:  # proof of skill: the run, checked answer goes into the portfolio
        in_portfolio = _record_solve(body, eng, out, g)
    return {
        "task_id": out.task_id,
        "correct": out.correct,
        "result": {
            "columns": list(out.result.columns),
            "rows": [list(r) for r in out.result.rows[:50]],
            "error": out.result.error,
            "truncated": out.result.truncated or len(out.result.rows) > 50,
            "ms": round(out.result.ms, 2),
            "row_status": g.row_status[:50],
            "missing_rows": g.missing_rows,
            "expected_rows": g.expected_rows,
        },
        "checks": [
            {"id": c.id, "label": c.label, "passed": c.passed, "detail": c.detail} for c in g.checks
        ],
        "p_correct_before": round(_p_correct(target_before), 3),
        "diagnoses": [
            {
                "code": d.code,
                "concept_id": eng.concept_id(d.concept) or d.concept,
                "weight": d.weight,
                "message": d.message,
            }
            for d in out.diagnoses
        ],
        "mastery": {
            c: {"name": names[c].name, "before": b, "after": a} for c, (b, a) in out.mastery.items()
        },
        "edge_evidence": [{"from": a, "to": b, "confidence": m} for a, b, m in out.edge_evidence],
        "plan": _plan_out(
            out.plan, eng.kg, eng.store.get(body.learner_id), eng.repairs(body.learner_id)
        ),
        "next_task": out.next_task,
        "replan_ms": out.replan_ms,
        "in_portfolio": in_portfolio,
    }


_ATTEMPTS: dict[tuple[str, str], int] = {}


def _record_solve(body: PracticeIn, eng: Engine, out: Any, g: Any) -> bool:
    import portfolio
    from practice.catalogue import BY_ID

    task = BY_ID[out.task_id]
    cid = eng.concept_id(task.concept) or task.concept
    state = eng.store.get(body.learner_id)
    names = eng.kg.concepts
    try:
        portfolio.record_solve(
            body.learner_id,
            portfolio.Solve(
                task_id=task.id,
                concept=cid,
                concept_name=names[cid].name if cid in names else task.concept,
                domain=task.domain,
                kind=task.kind,
                prompt=task.prompt,
                answer=body.query,
                checks=[c.label for c in g.checks if c.passed],
                result_preview=[list(r) for r in g.result.rows[:5]],
                columns=list(g.result.columns),
                solved_at=datetime.now().isoformat(timespec="minutes"),
                attempts=_ATTEMPTS.get((body.learner_id, task.id), 1),
            ),
            {names[c].name: m for c, m in state.mastery.items() if c in names} if state else {},
        )
    except OSError:
        return False  # read-only disk: practice still works, the portfolio just isn't saved
    return True


# ------------------------------------------------ proof-of-skill portfolio
class ProfileIn(BaseModel):
    name: str = Field("", max_length=80)
    headline: str = Field("", max_length=160)
    github: str = Field("", max_length=300)
    linkedin: str = Field("", max_length=300)
    public: bool = False


class ProjectIn(BaseModel):
    project_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field("", max_length=1500)
    skills: list[str] = []
    repo_url: str = Field("", max_length=300)
    demo_url: str = Field("", max_length=300)
    check_links: bool = True


def _portfolio_out(learner_id: str) -> dict[str, Any]:
    """The owner's view.  The first successful call claims the portfolio and
    returns its edit key once (the browser keeps it)."""
    import portfolio

    new_key = portfolio.claim(learner_id)
    pf = portfolio.load(learner_id)
    out = {**portfolio.public_view(pf), "share_path": f"/p/{pf.slug}"}
    if new_key:
        out["edit_key"] = new_key
    return out


def _owner(learner_id: str, key: str | None) -> None:
    """403 unless ``key`` opens this portfolio (anyone may, until it is claimed)."""
    import portfolio

    if not portfolio.owns(learner_id, key):
        raise HTTPException(
            403, "This portfolio is protected. Open it from the browser that created it."
        )


@app.get("/portfolio/{learner_id}")
def portfolio_get(learner_id: str, x_portfolio_key: str | None = Header(None)) -> dict[str, Any]:
    """The learner's own view: everything, re-checked.  Needs the edit key."""
    _owner(learner_id, x_portfolio_key)
    return _portfolio_out(learner_id)


@app.put("/portfolio/{learner_id}/profile")
def portfolio_profile(
    learner_id: str, body: ProfileIn, x_portfolio_key: str | None = Header(None)
) -> dict[str, Any]:
    import portfolio

    _owner(learner_id, x_portfolio_key)
    try:
        portfolio.set_profile(learner_id, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _portfolio_out(learner_id)


@app.post("/portfolio/{learner_id}/projects")
def portfolio_add_project(
    learner_id: str, body: ProjectIn, x_portfolio_key: str | None = Header(None)
) -> dict[str, Any]:
    import portfolio

    _owner(learner_id, x_portfolio_key)
    link = body.repo_url or body.demo_url
    try:
        portfolio.add_project(
            learner_id,
            portfolio.Project(
                project_id=body.project_id, title=body.title, summary=body.summary,
                skills=body.skills, repo_url=body.repo_url, demo_url=body.demo_url,
                added_at=datetime.now().isoformat(timespec="minutes"),
                link_ok=portfolio.check_link(link) if body.check_links and link else None,
            ),
        )  # fmt: skip
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _portfolio_out(learner_id)


@app.delete("/portfolio/{learner_id}/solves/{task_id}")
def portfolio_remove_solve(
    learner_id: str, task_id: str, x_portfolio_key: str | None = Header(None)
) -> dict[str, Any]:
    import portfolio

    _owner(learner_id, x_portfolio_key)
    portfolio.remove(learner_id, task_id=task_id)
    return _portfolio_out(learner_id)


@app.delete("/portfolio/{learner_id}/projects/{project_id}")
def portfolio_remove_project(
    learner_id: str, project_id: str, x_portfolio_key: str | None = Header(None)
) -> dict[str, Any]:
    import portfolio

    _owner(learner_id, x_portfolio_key)
    portfolio.remove(learner_id, project_id=project_id)
    return _portfolio_out(learner_id)


@app.get("/portfolio/{learner_id}/export.html")
def portfolio_export(learner_id: str, key: str | None = None) -> Response:
    """A self-contained HTML file to host anywhere (GitHub Pages, a drive link).
    Needs the edit key (as ``?key=``, since it is opened as a download link)."""
    import portfolio
    from portfolio_page import render

    if not portfolio.owns(learner_id, key):
        raise HTTPException(403, "This portfolio is protected.")
    pf = portfolio.load(learner_id)
    html = render(portfolio.public_view(pf))
    return Response(
        html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{pf.slug}-portfolio.html"'},
    )


@app.get("/p/{slug}", response_class=HTMLResponse)
def portfolio_public(slug: str) -> HTMLResponse:
    """The shareable page - only when the learner has made it public."""
    import portfolio
    from portfolio_page import render

    pf = portfolio.by_slug(slug)
    if pf is None or not pf.public:
        raise HTTPException(404, "No public portfolio here.")
    return HTMLResponse(render(portfolio.public_view(pf)))


@app.post("/explain")
def explain(body: ExplainIn) -> dict[str, str]:
    if body.resource_id not in engine.kg.resources:
        raise HTTPException(404, f"unknown resource {body.resource_id!r}")
    return {
        "resource_id": body.resource_id,
        "reason": engine.explain(body.learner_id, body.resource_id),
    }


# --------------------------------------------------------------- static SPA
if (_WEB / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_WEB / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def _index() -> FileResponse:
        return FileResponse(_WEB / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def _spa(path: str) -> FileResponse:
        target = _WEB / path
        return FileResponse(target if target.is_file() else _WEB / "index.html")
else:  # pragma: no cover

    @app.get("/", include_in_schema=False)
    def _no_ui() -> dict[str, str]:
        return {
            "message": "API up. Build the UI: cd frontend && npm install && npm run build."
            " Or open /docs.",
        }


def run() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000)
