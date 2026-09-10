"""N2 ablation - does learning-velocity actually drive the plan?

    python -m benchmarks.ablation_velocity      # -> results/ablation_velocity.{json,csv}

VELPO's one modelling novelty (claim **N2**) is that per-learner, per-concept
*learning velocity* enters the edge cost directly, through
``model.cost.expected_mastery_gain(current, velocity, seconds)``.  The claim is
only meaningful if turning that signal on actually changes the optimal plan.

This script measures it on the synthetic curriculum, for every goal concept:

* **signal ON**  - a fast learner (velocity x3) and a slow learner (velocity x0.45)
  are planned for the same goal and budget.  We report the fraction of concepts
  for which the optimal solver picks a *different* resource, and the difference
  in total study time.
* **signal OFF** - both learners are flattened to velocity 1.0 (the signal is
  removed).  The two plans must now be identical: divergence 0.

Expected story: ON -> the fast learner is steered to the fuller *lesson*
resources (they convert the extra minutes into mastery), the slow learner to the
shorter *practice* resources (diminishing returns aren't worth the time);
OFF -> one plan for everyone.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from algorithms.dynamic_programming import solve_optimal
from algorithms.graph_traversal import ancestors_subgraph, topological_order
from config import SEED, seed_everything, settings
from curriculum import build_curriculum
from model.cost import build_cost_vectors
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

RESULTS = Path(__file__).resolve().parents[1] / "results"
_BUCKETS = 40
FAST, SLOW = 3.0, 0.45


def _scaled_state(kg: KnowledgeGraph, *, budget_s: float, factor: float) -> LearnerState:
    base = LearnerState.cold_start(kg.concept_ids, time_budget_s=budget_s)
    lo, hi = settings.velocity_min, settings.velocity_max
    return replace(
        base, velocity={c: min(hi, max(lo, v * factor)) for c, v in base.velocity.items()}
    )


def _plan(kg: KnowledgeGraph, goal: str, state: LearnerState) -> dict[str, str]:
    """concept -> chosen resource id for the optimal plan (empty if infeasible)."""
    costs = build_cost_vectors(kg, state)
    p = solve_optimal(kg, [goal], state, costs, budget_buckets=_BUCKETS)
    return dict(zip(p.concepts, p.steps)) if p.feasible else {}


def _divergence(a: dict[str, str], b: dict[str, str]) -> tuple[int, int]:
    concepts = sorted(set(a) | set(b))
    diff = sum(1 for c in concepts if a.get(c) != b.get(c))
    return diff, len(concepts)


def _minutes(kg: KnowledgeGraph, plan: dict[str, str]) -> float:
    return round(sum(kg.resources[r].minutes for r in plan.values()), 1)


def run() -> dict[str, object]:
    seed_everything(SEED)
    kg = build_curriculum()
    order = topological_order(ancestors_subgraph(kg.prereq, kg.sink_concepts()))
    min_min = {c: min(kg.resources[r].minutes for r in kg.resources_for(c)) for c in order}

    rows: list[dict[str, object]] = []
    for goal in kg.sink_concepts():
        relevant = topological_order(ancestors_subgraph(kg.prereq, [goal]))
        budget_s = 2.0 * sum(min_min[c] for c in relevant) * 60.0

        fast_on = _plan(kg, goal, _scaled_state(kg, budget_s=budget_s, factor=FAST))
        slow_on = _plan(kg, goal, _scaled_state(kg, budget_s=budget_s, factor=SLOW))
        fast_off = _plan(kg, goal, _scaled_state(kg, budget_s=budget_s, factor=1.0))
        slow_off = _plan(kg, goal, _scaled_state(kg, budget_s=budget_s, factor=1.0))

        d_on, n = _divergence(fast_on, slow_on)
        d_off, _ = _divergence(fast_off, slow_off)
        rows.append(
            {
                "goal": goal,
                "concepts": n,
                "divergent_on": d_on,
                "divergent_off": d_off,
                "fast_minutes": _minutes(kg, fast_on),
                "slow_minutes": _minutes(kg, slow_on),
            }
        )

    tot_c = sum(int(r["concepts"]) for r in rows)
    tot_on = sum(int(r["divergent_on"]) for r in rows)
    tot_off = sum(int(r["divergent_off"]) for r in rows)
    summary = {
        "runs": len(rows),
        "divergence_rate_signal_on": round(tot_on / tot_c, 3) if tot_c else 0.0,
        "divergence_rate_signal_off": round(tot_off / tot_c, 3) if tot_c else 0.0,
        "goals_with_a_different_plan": sum(1 for r in rows if int(r["divergent_on"]) > 0),
        "per_goal": rows,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "ablation_velocity.json").write_text(json.dumps(summary, indent=2))
    _write_csv(rows)
    return summary


def _write_csv(rows: list[dict[str, object]]) -> None:
    cols = ["goal", "concepts", "divergent_on", "divergent_off", "fast_minutes", "slow_minutes"]
    lines = [",".join(cols)]
    lines += [",".join(str(r[c]) for c in cols) for r in rows]
    (RESULTS / "ablation_velocity.csv").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    s = run()
    print(
        f"goals={s['runs']}  "
        f"divergence(signal ON)={s['divergence_rate_signal_on']:.0%}  "
        f"divergence(signal OFF)={s['divergence_rate_signal_off']:.0%}  "
        f"different plan for fast vs slow: {s['goals_with_a_different_plan']}/{s['runs']} goals"
    )
    cols = ("goal", "concepts", "divergent_on", "divergent_off", "fast_minutes", "slow_minutes")
    print("\n" + "  ".join(f"{c:>13}" for c in cols))
    for r in s["per_goal"]:  # type: ignore[union-attr]
        print("  ".join(f"{r[c]!s:>13}" for c in cols))
