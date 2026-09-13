from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from assessment_bank import build_item_bank
from curriculum import build_curriculum
from engine import Engine, MemoryStore


@pytest.fixture
def client():
    import api

    api.engine = Engine(build_curriculum(), store=MemoryStore(), item_bank=build_item_bank())
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


def test_speed_knob_changes_the_plan(client: TestClient) -> None:
    body = {"learner_id": "s", "goals": ["quadratics"], "time_budget_min": 150}
    fast = client.post("/recommend", json={**body, "learner_id": "f", "speed": "fast"}).json()
    slow = client.post("/recommend", json={**body, "learner_id": "s", "speed": "slow"}).json()
    assert fast["meta"]["speed"] == "fast"
    fast_res = [s["resource_id"] for s in fast["paths"][0]["steps"]]
    slow_res = [s["resource_id"] for s in slow["paths"][0]["steps"]]
    assert fast_res != slow_res


def test_adaptive_assessment_drives_the_cold_start(client: TestClient) -> None:
    start = client.post("/assess/start", json={"learner_id": "a", "goals": ["linear_eq"]}).json()
    assert start["question"] is not None and not start["done"]
    assert {"skill", "kind", "stem"} <= start["question"].keys()

    data = start
    guard = 0
    while not data["done"] and guard < 40:
        q = data["question"]
        # always answer wrong: bad MCQ index, nonsense task text
        resp = "-1" if q["kind"] == "mcq" else "xxx"
        data = client.post(
            "/assess/answer", json={"learner_id": "a", "item_id": q["item_id"], "response": resp}
        ).json()
        guard += 1

    assert data["done"] and data["answered"] > 0
    low = {e["skill"]: e["mastery"] for e in data["estimates"]}
    assert low["integers"] < 0.45  # measured as weak, not a fixed prior

    plan = client.post(
        "/recommend", json={"learner_id": "a", "goals": ["linear_eq"], "time_budget_min": 120}
    ).json()
    assert plan["paths"][0]["feasible"]


def test_assess_state_404_without_a_session(client: TestClient) -> None:
    assert client.get("/assess/nobody").status_code == 404


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


def test_schedule_endpoint_meets_the_deadline(client: TestClient) -> None:
    from datetime import date, timedelta

    body = {
        "learner_id": "cal1",
        "goals": ["quadratics"],
        "deadline": (date.today() + timedelta(days=49)).isoformat(),
        "weekly_minutes": 240,
    }
    cal = client.post("/schedule", json=body).json()["calendar"]
    assert cal["feasible"], cal["note"]
    assert cal["finish"] <= cal["deadline"]
    assert cal["slack_days"] >= 0
    assert all(m >= 0.75 for m in cal["goal_mastery"].values())
    kinds = {s["kind"] for s in cal["steps"]}
    assert "teach" in kinds and "retention" in kinds


def test_schedule_infeasible_reports_hours_gap(client: TestClient) -> None:
    from datetime import date, timedelta

    body = {
        "learner_id": "cal2",
        "goals": ["quadratics"],
        "deadline": (date.today() + timedelta(days=3)).isoformat(),
        "weekday_minutes": [10, 10, 10, 10, 10, 0, 0],
    }
    cal = client.post("/schedule", json=body).json()["calendar"]
    assert not cal["feasible"]
    assert cal["hours_per_week_needed"] > cal["hours_per_week"]


def test_graph_health_recovers_a_corrupted_graph(client: TestClient) -> None:
    body = {"goal": "learn sql", "learners": 5000, "perturb": 2}
    h = client.post("/graph/health", json=body).json()
    assert h["domain"] == "sql"
    assert h["recovery"]["recall"] >= 0.5
    assert h["recovery"]["precision_drop"] == 1.0
    for change in (*h["pruned"], *h["added"]):
        assert change["summary"] and "->" in change["summary"]


def test_graph_health_live_is_clean_without_evidence(client: TestClient) -> None:
    h = client.post("/graph/health", json={"goal": "learn sql", "learners": 0}).json()
    assert h["observations"] == 0
    assert h["clean"] is True


def test_roadmap_endpoint(client: TestClient) -> None:
    body = {"learner_id": "rm1", "goal": "become a data analyst", "weekly_hours": 6}
    rm = client.post("/roadmap", json=body).json()["roadmap"]
    assert rm["role"] == "data analyst"
    assert rm["total_weeks"] > 0 and rm["finish_estimate"]
    assert len(rm["phases"]) >= 3
    assert any(p["certifications"] for p in rm["phases"])
    assert rm["certifications"][0]["url"].startswith("https://")


def test_roadmap_speed_knob_changes_the_estimate(client: TestClient) -> None:
    base = {"learner_id": "rm-speed", "goal": "learn sql", "weekly_hours": 5}
    slow = client.post("/roadmap", json={**base, "speed": "slow"}).json()["roadmap"]
    normal = client.post("/roadmap", json={**base, "speed": "normal"}).json()["roadmap"]
    fast = client.post("/roadmap", json={**base, "speed": "fast"}).json()["roadmap"]
    assert slow["total_hours"] > normal["total_hours"] > fast["total_hours"]
    assert slow["pace"] == "deliberate"
    assert fast["pace"] == "fast"
