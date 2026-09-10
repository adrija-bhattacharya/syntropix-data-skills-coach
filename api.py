"""FastAPI service.  Endpoints:

    GET  /health
    GET  /catalogue        concepts, resources, sink (goal) concepts
    POST /resolve          {goal}                           free-text goal -> knowledge graph
    POST /assess/start     {learner_id, goals[]}            begin the adaptive diagnostic
    POST /assess/answer    {learner_id, item_id, response}  grade + get the next item
    GET  /assess/{id}      current questions + ability estimates
    POST /recommend        {learner_id, goals[], time_budget_min, mode, n_paths, ban[], lock[], ...}
    POST /observe          {learner_id, resource_id, correct, minutes, hints}
    POST /explain          {learner_id, resource_id}

The built React SPA (``frontend/`` -> ``velpo/web``) is served at ``/`` when present.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from algorithms.dynamic_programming import Plan, TeacherConstraints
from assessment_bank import build_item_bank
from config import __version__
from curriculum import build_curriculum
from engine import Engine
from model.assessment import AdaptiveSession
from model.knowledge_graph import KnowledgeGraph
from model.learner import Attempt

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
    """``VELPO_CATALOGUE=discovered`` serves the harvested open-resource catalogue
    (bundled snapshot); anything else serves the synthetic algebra curriculum."""
    if os.environ.get("VELPO_CATALOGUE") == "discovered":
        from harvest import algebra_catalogue

        return algebra_catalogue()
    return build_curriculum()


engine = Engine(_build_kg(), item_bank=build_item_bank())


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


class AssessAnswerIn(BaseModel):
    learner_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)
    response: str  # MCQ: the chosen index as a string; task: the typed answer


def _assess_out(session: AdaptiveSession) -> dict[str, Any]:
    q = session.next_question()
    return {
        "done": session.done,
        "answered": session.n_answered,
        "progress": round(session.progress(), 3),
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


def _plan_out(p: Plan) -> dict[str, Any]:
    reviews = p.reviews or (False,) * len(p.steps)
    return {
        "feasible": p.feasible,
        "note": p.note,
        "total_minutes": round(p.total_seconds / 60, 1),
        "objective": dict(zip(_OBJ_KEYS, p.objective)),
        "steps": [
            {"resource_id": r, "concept_id": c, "reason": reason, "review": bool(rev)}
            for r, c, reason, rev in zip(
                p.steps, p.concepts, p.reasons or [""] * len(p.steps), reviews
            )
        ],
        "sessions": [{"start": a, "end": b} for a, b in p.sessions],
    }


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
        "goals": r.goals,
        "concepts": [{"id": c.id, "name": c.name} for c in r.kg.concepts.values()],
        "prerequisites": [[u, v] for u, v in r.kg.prereq.edges()],
    }


@app.get("/discover/{concept_id}")
def discover(concept_id: str, refresh: bool = False) -> dict[str, Any]:
    if concept_id not in engine.kg.concepts:
        raise HTTPException(404, f"unknown concept {concept_id!r}")
    from harvest.catalogue import CONCEPT_QUERY, discover_for_concept

    name = CONCEPT_QUERY.get(concept_id, engine.kg.concepts[concept_id].name)
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
                for rid in engine.kg.resources_for(concept_id)
                for r in [engine.kg.resources[rid]]
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


@app.post("/recommend")
def recommend(body: RecommendIn) -> dict[str, Any]:
    unknown = [c for c in body.goals if c not in engine.kg.concepts]
    if unknown:
        raise HTTPException(422, f"unknown concepts: {unknown}")
    tc = TeacherConstraints.make(ban=body.ban, lock=body.lock, force_order=body.force_order)
    plans = engine.recommend(
        body.learner_id,
        body.goals,
        time_budget_s=body.time_budget_min * 60,
        mode=body.mode,
        n_paths=body.n_paths,
        constraints=tc,
        speed=_SPEED_MULT[body.speed],
    )
    meta: dict[str, Any] = {"mode": body.mode, "returned": len(plans), "speed": body.speed}
    if plans and not plans[0].feasible:
        meta["infeasible_reason"] = plans[0].note
    return {"paths": [_plan_out(p) for p in plans], "meta": meta}


@app.post("/observe")
def observe(body: ObserveIn) -> dict[str, Any]:
    if body.resource_id not in engine.kg.resources:
        raise HTTPException(404, f"unknown resource {body.resource_id!r}")
    try:
        state = engine.observe(
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
    unknown = [c for c in body.goals if c not in engine.kg.concepts]
    if unknown:
        raise HTTPException(422, f"unknown concepts: {unknown}")
    session = engine.start_assessment(body.learner_id, body.goals)
    return _assess_out(session)


@app.post("/assess/answer")
def assess_answer(body: AssessAnswerIn) -> dict[str, Any]:
    try:
        session = engine.answer_assessment(body.learner_id, body.item_id, body.response)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _assess_out(session)


@app.get("/assess/{learner_id}")
def assess_state(learner_id: str) -> dict[str, Any]:
    try:
        return _assess_out(engine.assessment(learner_id))
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
