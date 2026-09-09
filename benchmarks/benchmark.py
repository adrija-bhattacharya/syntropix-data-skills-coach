"""VELPO vs. baselines, on the synthetic curriculum, seeded and reproducible.

    python -m benchmarks.benchmark            # 80 runs -> results/summary.csv (+ .png)

Two regimes are interleaved: a comfortable time budget, and a deliberately tight
one.  Baselines return a plan regardless; VELPO returns nothing when the
discretised budget cannot fit any plan (a *principled refusal*, not an invalid
plan).  We therefore report:

* safe-behaviour rate  - fraction of runs where the method returned a valid plan
  OR correctly refused
* over-budget rate     - fraction of runs where the returned plan exceeds the budget
* optimality gap        - (method cost - brute-force cost) / |brute-force cost|
* latency (ms)          - per plan
"""

from __future__ import annotations

import itertools
import json
import math
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path

import numpy as np

from velpo.algorithms.astar import solve_astar
from velpo.algorithms.dynamic_programming import Plan, build_plan_context, solve_optimal
from velpo.algorithms.graph_traversal import ancestors_subgraph, topological_order
from velpo.config import SEED, seed_everything, settings
from velpo.curriculum import build_curriculum
from velpo.model.cost import CostVector, build_cost_vectors
from velpo.model.knowledge_graph import KnowledgeGraph
from velpo.model.learner import LearnerState

RESULTS = Path(__file__).resolve().parents[1] / "results"
_BUCKETS = 40
_W = settings.weights


# --------------------------------------------------------------------------- #
# baselines  (return a resource id per relevant concept, in topological order)
# --------------------------------------------------------------------------- #
def greedy(kg: KnowledgeGraph, goals: list[str], **_: object) -> list[str]:
    """Greedy prerequisite traversal (ref. 26): shortest resource per concept."""
    order = topological_order(ancestors_subgraph(kg.prereq, goals))
    return [min(kg.resources_for(c), key=lambda r: kg.resources[r].minutes) for c in order]


def aco(
    kg: KnowledgeGraph,
    goals: list[str],
    *,
    costs: dict[str, CostVector],
    budget_s: float,
    n_ants: int = 20,
    n_iter: int = 40,
    rho: float = 0.1,
    seed: int = 0,
) -> list[str]:
    """Ant Colony Optimization over per-concept resource choice (refs. 4, 6-8, 15).
    Budget is a *soft* penalty - the metaheuristic cannot guarantee it."""
    rng = np.random.default_rng(seed)
    order = topological_order(ancestors_subgraph(kg.prereq, goals))
    cand = {c: kg.resources_for(c) for c in order}
    tau = {c: np.ones(len(cand[c])) for c in order}

    def score(choice: dict[str, str]) -> float:
        t = sum(kg.resources[r].seconds for r in choice.values())
        over = max(0.0, t - budget_s) / max(budget_s, 1.0)
        return sum(costs[r].scalarise(_W) for r in choice.values()) + 50.0 * over

    best_choice: dict[str, str] = {}
    best = math.inf
    for _ in range(n_iter):
        rows = []
        for _ in range(n_ants):
            choice = {
                c: cand[c][int(rng.choice(len(cand[c]), p=tau[c] / tau[c].sum()))] for c in order
            }
            s = score(choice)
            rows.append((choice, s))
            if s < best:
                best, best_choice = s, dict(choice)
        worst = max(s for _, s in rows)
        span = max(worst - min(s for _, s in rows), 1e-9)
        for c in order:
            tau[c] *= 1 - rho
        for choice, s in rows:
            dep = (worst - s) / span
            for c, r in choice.items():
                tau[c][cand[c].index(r)] += dep
        for c in order:
            np.clip(tau[c], 1e-6, None, out=tau[c])
    return [best_choice[c] for c in order]


def dqn(
    kg: KnowledgeGraph,
    goals: list[str],
    *,
    costs: dict[str, CostVector],
    budget_s: float,
    episodes: int = 400,
    seed: int = 0,
) -> list[str]:
    """Tabular Q-learning sequential recommender (refs. 9, 16, 18).
    State = (concept index, time-bucket used); reward = -cost; big penalty if over budget."""
    rng = np.random.default_rng(seed)
    order = topological_order(ancestors_subgraph(kg.prereq, goals))
    cand = {c: kg.resources_for(c) for c in order}
    bs = max(budget_s, 1.0) / _BUCKETS

    def bucket(r: str) -> int:
        return max(1, math.ceil(kg.resources[r].seconds / bs))

    n = len(order)
    q: dict[tuple[int, int], np.ndarray] = {}

    def qv(i: int, b: int) -> np.ndarray:
        return q.setdefault((i, b), np.zeros(len(cand[order[i]]) if i < n else 1))

    alpha, gamma, eps = 0.2, 0.95, 0.2
    for _ in range(episodes):
        b = 0
        for i in range(n):
            acts = qv(i, b)
            a = int(rng.integers(len(acts))) if rng.random() < eps else int(np.argmax(acts))
            r = cand[order[i]][a]
            nb = min(_BUCKETS, b + bucket(r))
            reward = -costs[r].scalarise(_W) - (20.0 if i == n - 1 and nb >= _BUCKETS else 0.0)
            future = 0.0 if i == n - 1 else float(np.max(qv(i + 1, nb)))
            acts[a] += alpha * (reward + gamma * future - acts[a])
            b = nb
        eps = max(0.02, eps * 0.997)

    plan, b = [], 0
    for i in range(n):
        r = cand[order[i]][int(np.argmax(qv(i, b)))]
        plan.append(r)
        b = min(_BUCKETS, b + bucket(r))
    return plan


# --------------------------------------------------------------------------- #
def _velpo_dp(kg: KnowledgeGraph, goals: list[str], state: LearnerState, costs: dict) -> list[str]:
    p = solve_optimal(kg, goals, state, costs, budget_buckets=_BUCKETS)
    return list(p.steps) if p.feasible else []


def _velpo_astar(
    kg: KnowledgeGraph, goals: list[str], state: LearnerState, costs: dict
) -> list[str]:
    r = solve_astar(kg, goals, state, costs, budget_buckets=_BUCKETS)
    p = r if isinstance(r, Plan) else r[0]
    return list(p.steps) if p.feasible else []


def _brute(kg, goals, state, costs) -> float:
    order = topological_order(ancestors_subgraph(kg.prereq, goals))
    if not order:
        return 0.0
    cand = [kg.resources_for(c) for c in order]
    if np.prod([len(c) for c in cand]) > 200_000:
        return math.nan
    ctx = build_plan_context(kg, goals, state, costs, budget_buckets=_BUCKETS)
    best = math.inf
    for combo in itertools.product(*cand):
        if sum(ctx.buckets_for(r) for r in combo) > ctx.budget_buckets:
            continue
        best = min(best, sum(costs[r].scalarise(_W) for r in combo))
    return best


def _plan_seconds(kg, plan: list[str]) -> float:
    return sum(kg.resources[r].seconds for r in plan)


def _prereq_violations(kg, plan: list[str]) -> int:
    mastered: set[str] = set()
    v = 0
    for r in plan:
        for req in kg.prerequisites_of_resource(r):
            if req not in mastered:
                v += 1
        mastered.update(kg.resources[r].concepts)
    return v


def run(runs: int = 80) -> dict[str, dict[str, float]]:
    seed_everything(SEED)
    rng = np.random.default_rng(SEED)
    kg = build_curriculum()
    sinks = kg.sink_concepts()

    acc: dict[str, dict[str, list[float]]] = {}
    for i in range(runs):
        goals = [str(rng.choice(sinks))]
        relevant = topological_order(ancestors_subgraph(kg.prereq, goals))
        min_s = sum(min(kg.resources[r].seconds for r in kg.resources_for(c)) for c in relevant)
        tight = i % 3 == 0
        budget_s = float(min_s * (rng.uniform(0.6, 0.92) if tight else rng.uniform(1.3, 2.2)))
        state = LearnerState.cold_start(kg.concept_ids, time_budget_s=budget_s)
        costs = build_cost_vectors(kg, state)
        opt = _brute(kg, goals, state, costs)

        planners: dict[str, Callable[[], list[str]]] = {
            "velpo_dp": partial(_velpo_dp, kg, goals, state, costs),
            "velpo_astar": partial(_velpo_astar, kg, goals, state, costs),
            "greedy": partial(greedy, kg, goals),
            "aco": partial(aco, kg, goals, costs=costs, budget_s=budget_s),
            "dqn": partial(dqn, kg, goals, costs=costs, budget_s=budget_s),
        }
        for name, fn in planners.items():
            t0 = time.perf_counter()
            plan = fn()
            dt_ms = (time.perf_counter() - t0) * 1000
            slot = acc.setdefault(name, {"safe": [], "over": [], "gap": [], "lat": [], "viol": []})
            over = bool(plan) and _plan_seconds(kg, plan) > budget_s + 1e-6
            slot["over"].append(1.0 if over else 0.0)
            slot["safe"].append(
                1.0 if (not plan or (not over and _prereq_violations(kg, plan) == 0)) else 0.0
            )
            slot["viol"].append(float(_prereq_violations(kg, plan)) if plan else 0.0)
            slot["lat"].append(dt_ms)
            if plan and np.isfinite(opt) and opt != 0:
                cost = sum(costs[r].scalarise(_W) for r in plan)
                slot["gap"].append((cost - opt) / abs(opt))

    summary = {
        name: {
            "safe_behaviour_rate": round(float(np.mean(s["safe"])), 3),
            "over_budget_rate": round(float(np.mean(s["over"])), 3),
            "mean_prereq_violations": round(float(np.mean(s["viol"])), 3),
            "mean_optimality_gap": round(float(np.mean(s["gap"])) if s["gap"] else 0.0, 4),
            "mean_latency_ms": round(float(np.mean(s["lat"])), 3),
        }
        for name, s in acc.items()
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2))
    _write_csv(summary)
    _plot(summary)
    return summary


def _write_csv(summary: dict[str, dict[str, float]]) -> None:
    cols = next(iter(summary.values())).keys()
    lines = ["method," + ",".join(cols)]
    for name, row in summary.items():
        lines.append(name + "," + ",".join(str(row[c]) for c in cols))
    (RESULTS / "summary.csv").write_text("\n".join(lines) + "\n")


def _plot(summary: dict[str, dict[str, float]]) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover
        return
    names = list(summary)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].bar(names, [summary[n]["safe_behaviour_rate"] for n in names], color="#1a73e8")
    ax[0].set_ylim(0, 1.08)
    ax[0].set_title("safe-behaviour rate (higher better)")
    ax[1].bar(names, [summary[n]["over_budget_rate"] for n in names], color="#d93025")
    ax[1].set_title("over-budget plans (lower better)")
    for a in ax:
        a.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(RESULTS / "summary.png", dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    result = run()
    width = max(len(k) for k in result)
    print(f"{'method':<{width}}  safe  over  viol  gap     lat_ms")
    for name, row in result.items():
        print(
            f"{name:<{width}}  {row['safe_behaviour_rate']:.2f}  {row['over_budget_rate']:.2f}  "
            f"{row['mean_prereq_violations']:.2f}  {row['mean_optimality_gap']:+.4f}  "
            f"{row['mean_latency_ms']:.2f}"
        )
