from __future__ import annotations

import numpy as np

from benchmarks.benchmark import aco, dqn, greedy, run
from curriculum import build_curriculum
from model.cost import build_cost_vectors
from model.learner import LearnerState


def test_baselines_are_prerequisite_valid_full_plans() -> None:
    from benchmarks.benchmark import _prereq_violations

    kg = build_curriculum()
    state = LearnerState.cold_start(kg.concept_ids, time_budget_s=9000)
    costs = build_cost_vectors(kg, state)
    goals = ["quadratics"]
    n = len(greedy(kg, goals))
    for plan in (
        greedy(kg, goals),
        aco(kg, goals, costs=costs, budget_s=9000, n_iter=8),
        dqn(kg, goals, costs=costs, budget_s=9000, episodes=50),
    ):
        assert len(plan) == n
        assert _prereq_violations(kg, plan) == 0


def test_benchmark_summary_velpo_dominates() -> None:
    summary = run(runs=12)
    for m in ("velpo_dp", "velpo_astar"):
        assert summary[m]["safe_behaviour_rate"] == 1.0
        assert summary[m]["over_budget_rate"] == 0.0
        assert summary[m]["mean_optimality_gap"] <= 1e-6
        assert summary[m]["mean_prereq_violations"] == 0.0
    assert summary["aco"]["over_budget_rate"] > 0.0
    assert summary["velpo_astar"]["mean_latency_ms"] < summary["aco"]["mean_latency_ms"]


def test_velocity_ablation_signal_on_diverges_off_does_not() -> None:
    from benchmarks.ablation_velocity import run as ablation

    s = ablation()
    assert s["divergence_rate_signal_off"] == 0.0
    assert s["divergence_rate_signal_on"] > 0.2
    assert s["goals_with_a_different_plan"] >= 1


def test_benchmark_is_reproducible() -> None:
    # latency is wall-clock, so compare everything except that
    def without_latency(s: dict) -> dict:
        return {
            k: {kk: vv for kk, vv in v.items() if kk != "mean_latency_ms"} for k, v in s.items()
        }

    assert without_latency(run(runs=6)) == without_latency(run(runs=6))
    _ = np
