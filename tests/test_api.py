from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from velpo.curriculum import build_curriculum
from velpo.engine import Engine, MemoryStore


@pytest.fixture
def client():
    from velpo import api

    api.engine = Engine(build_curriculum(), store=MemoryStore())
    return TestClient(api.app)


def test_health_and_catalogue(client: TestClient) -> None:
    assert client.get("/health").json()["concepts"] == 14
    cat = client.get("/catalogue").json()
    assert len(cat["concepts"]) == 14
    assert "word_problems" in cat["goals"]
    assert {"id", "concepts", "difficulty", "minutes", "kind"} <= cat["resources"][0].keys()


def test_cold_start_recommend(client: TestClient) -> None:
    r = client.post(
        "/recommend",
        json={"learner_id": "u1", "goals": ["quadratics"], "time_budget_min": 120},
    )
    assert r.status_code == 200
    p = r.json()["paths"][0]
    assert p["feasible"]
    concepts = [s["concept_id"] for s in p["steps"]]
    assert concepts.index("integers") < concepts.index("quadratics")
    assert p["steps"][0]["reason"].endswith(".")
    assert set(p["objective"]) == {"neg_gain", "seconds", "load", "diff_jump", "neg_review"}


def test_unknown_goal_is_422(client: TestClient) -> None:
    assert (
        client.post(
            "/recommend", json={"learner_id": "u", "goals": ["nope"], "time_budget_min": 60}
        ).status_code
        == 422
    )


def test_observe_updates_then_still_feasible(client: TestClient) -> None:
    client.post(
        "/recommend", json={"learner_id": "u2", "goals": ["linear_eq"], "time_budget_min": 90}
    )
    r = client.post(
        "/observe",
        json={"learner_id": "u2", "resource_id": "integers:lesson", "correct": True, "minutes": 5},
    )
    assert r.json()["n_interactions"] == 1
    assert r.json()["mastery"]["integers"] > 0.15
    r2 = client.post(
        "/recommend", json={"learner_id": "u2", "goals": ["linear_eq"], "time_budget_min": 90}
    )
    assert r2.json()["paths"][0]["feasible"]


def test_observe_unknown_resource_404(client: TestClient) -> None:
    assert (
        client.post(
            "/observe",
            json={"learner_id": "u", "resource_id": "ghost", "correct": True, "minutes": 1},
        ).status_code
        == 404
    )


def test_pareto_mode_distinct_paths(client: TestClient) -> None:
    r = client.post(
        "/recommend",
        json={
            "learner_id": "u3",
            "goals": ["word_problems"],
            "time_budget_min": 150,
            "mode": "pareto",
            "n_paths": 6,
        },
    )
    paths = r.json()["paths"]
    assert len(paths) >= 2
    assert len({tuple(p["objective"].values()) for p in paths}) == len(paths)


def test_constraints_via_recommend(client: TestClient) -> None:
    r = client.post(
        "/recommend",
        json={
            "learner_id": "u4",
            "goals": ["linear_eq"],
            "time_budget_min": 100,
            "ban": ["linear_eq:lesson"],
        },
    )
    used = {s["resource_id"] for s in r.json()["paths"][0]["steps"]}
    assert "linear_eq:lesson" not in used and "linear_eq:practice" in used


def test_infeasible_budget_reported(client: TestClient) -> None:
    r = client.post(
        "/recommend", json={"learner_id": "u5", "goals": ["quadratics"], "time_budget_min": 0.02}
    )
    assert not r.json()["paths"][0]["feasible"]
    assert "infeasible_reason" in r.json()["meta"]


def test_explain_endpoint(client: TestClient) -> None:
    r = client.post("/explain", json={"learner_id": "u6", "resource_id": "quadratics:lesson"})
    assert "Quadratic" in r.json()["reason"]
