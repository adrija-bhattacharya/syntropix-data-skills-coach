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

The built React SPA (``frontend/`` -> ``velpo/web``) is served at ``/`` when present.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from algorithms.dynamic_programming import Plan, TeacherConstraints
from algorithms.scheduling import Availability, CalendarPlan
from assessment_bank import build_item_bank
from config import __version__, settings
from curriculum import build_curriculum
from engine import Engine
from model.assessment import AdaptiveSession
from model.knowledge_graph import KnowledgeGraph
from model.learner import Attempt, LearnerState

_OBJ_KEYS = ("neg_gain", "seconds", "load", "diff_jump", "neg_review")
_SPEED_MULT = {"slow": 0.45, "normal": 1.0, "fast": 3.0}
_WEB = Path(__file__).resolve().parent / "web"

app = FastAPI(title="VELPO", version=__version__)
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


_ITEM_BANK_DOMAINS = ("algebra", "sql", "python")  # the calibrated item banks so far
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
        bank = build_item_bank(r.domain) if r.domain in _ITEM_BANK_DOMAINS else None
        _ENGINES[key] = Engine(r.kg, item_bank=bank, graph_source=r.source)
    return _ENGINES[key], r.domain, r.domain in _ITEM_BANK_DOMAINS


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


class ObserveIn(BaseModel):
    learner_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    correct: bool
    minutes: float = Field(ge=0)
    hints: int = Field(0, ge=0)


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
        "style": session.style_signal() if session.done else None,
        "question": None
        if q is None
        else {
            "item_id": q.id,
            "skill": q.skill,
            "kind": q.kind,
            "stem": q.stem,
            "choices": list(q.choices),
        },
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


def _plan_out(p: Plan, kg: KnowledgeGraph, state: LearnerState | None = None) -> dict[str, Any]:
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
            }
        )
    out: dict[str, Any] = {
        "feasible": p.feasible,
        "note": p.note,
        "total_minutes": round(p.total_seconds / 60, 1),
        "objective": dict(zip(_OBJ_KEYS, p.objective)),
        "steps": steps,
        "sessions": [{"start": a, "end": b} for a, b in p.sessions],
    }
    if state is not None:
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
        "assessable": r.domain in _ITEM_BANK_DOMAINS,
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
    plans = eng.recommend(
        body.learner_id,
        body.goals,
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
    paths = [_plan_out(p, eng.kg, lstate) for p in plans]
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
        start=date.today(),
        speed=_SPEED_MULT[body.speed],
    )
    return {"calendar": _calendar_out(cp, eng.kg), "meta": {"domain": domain}}


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
