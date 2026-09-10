"""FastAPI service.  Endpoints:

    GET  /health
    GET  /catalogue     concepts, resources, sink (goal) concepts
    POST /recommend     {learner_id, goals[], time_budget_min, mode, n_paths, ban[], lock[], ...}
    POST /observe       {learner_id, resource_id, correct, minutes, hints}
    POST /explain       {learner_id, resource_id}

The built React SPA (``frontend/`` -> ``velpo/web``) is served at ``/`` when present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from algorithms.dynamic_programming import Plan, TeacherConstraints
from config import __version__
from curriculum import build_curriculum
from engine import Engine
from model.learner import Attempt

_OBJ_KEYS = ("neg_gain", "seconds", "load", "diff_jump", "neg_review")
_WEB = Path(__file__).resolve().parent / "web"

app = FastAPI(title="VELPO", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = Engine(build_curriculum())


# --------------------------------------------------------------- schemas
class RecommendIn(BaseModel):
    learner_id: str = Field(min_length=1)
    goals: list[str] = Field(min_length=1)
    time_budget_min: float = Field(gt=0)
    mode: Literal["optimal", "interactive", "pareto"] = "optimal"
    n_paths: int = Field(1, ge=1, le=20)
    ban: list[str] = []
    lock: list[str] = []
    force_order: list[tuple[str, str]] = []


class ObserveIn(BaseModel):
    learner_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    correct: bool
    minutes: float = Field(ge=0)
    hints: int = Field(0, ge=0)


class ExplainIn(BaseModel):
    learner_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)


def _plan_out(p: Plan) -> dict[str, Any]:
    return {
        "feasible": p.feasible,
        "note": p.note,
        "total_minutes": round(p.total_seconds / 60, 1),
        "objective": dict(zip(_OBJ_KEYS, p.objective)),
        "steps": [
            {"resource_id": r, "concept_id": c, "reason": reason}
            for r, c, reason in zip(p.steps, p.concepts, p.reasons or [""] * len(p.steps))
        ],
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
            }
            for r in kg.resources.values()
        ],
        "goals": kg.sink_concepts(),
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
    )
    meta: dict[str, Any] = {"mode": body.mode, "returned": len(plans)}
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

    uvicorn.run("velpo.api:app", host="127.0.0.1", port=8000)
