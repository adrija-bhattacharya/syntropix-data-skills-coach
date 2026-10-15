"""Does optimising the **order** (not just the selection) actually pay off?

    python -m benchmarks.sequencing_bench      # -> results/sequencing.{json,csv}

For every goal in a dataset we score three plans with the *same* position-aware
cost model (:func:`model.cost.sequence_step_cost` - the one that penalises a
concept taught before its prerequisites are solid or long after they decayed):

* ``velpo_seq``  - the sequencing DP over order ideals (it optimises this cost)
* ``velpo_knapsack`` - pick one resource per concept optimally, then order by the
  difficulty-smoothing heuristic (the previous VELPO core)
* ``greedy``     - shortest resource per concept, plain topological order

and report the mean position-aware cost, the mean difficulty-jump, and each
baseline's gap above ``velpo_seq``.
"""

from __future__ import annotations

import json
from pathlib import Path

from algorithms.dynamic_programming import solve_optimal
from algorithms.graph_traversal import ancestors_subgraph, topological_order
from algorithms.sequencing import _levels, plan_sequence
from benchmarks.datasets import DATASETS, load
from config import SEED, seed_everything, settings
from model.cost import build_cost_vectors, sequence_step_cost
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState

RESULTS = Path(__file__).resolve().parents[1] / "results"
_W = settings.weights
_HL = settings.seq_half_life_steps


def _score(
    kg: KnowledgeGraph, goal: str, ordered_resources: list[str], state: LearnerState
) -> dict[str, float]:
    """Position-aware cost + difficulty-jump total for an ordered resource list."""
    dag = ancestors_subgraph(kg.prereq, [goal])
    level = _levels(dag, topological_order(dag))
    prev_d = 1.0
    cost = jumps = 0.0
    for i, rid in enumerate(ordered_resources):
        c = kg.resources[rid].concepts[0]
        cv = sequence_step_cost(
            kg,
            c,
            rid,
            state,
            position=i,
            taught_at=level,
            prev_difficulty=prev_d,
            half_life_steps=_HL,
        )
        cost += cv.scalarise(_W)
        jumps += cv.diff_jump
        prev_d = kg.resources[rid].difficulty
    return {"cost": cost, "jumps": jumps}


def _knapsack_ordered(kg: KnowledgeGraph, goal: str, state: LearnerState) -> list[str]:
    costs = build_cost_vectors(kg, state)
    p = solve_optimal(kg, [goal], state, costs, budget_buckets=60)
    return list(p.steps) if p.feasible else []


def _greedy_ordered(kg: KnowledgeGraph, goal: str) -> list[str]:
    order = topological_order(ancestors_subgraph(kg.prereq, [goal]))
    return [min(kg.resources_for(c), key=lambda r: kg.resources[r].minutes) for c in order]


def run(dataset: str = "synthetic") -> dict[str, object]:
    seed_everything(SEED)
    kg, goals = load(dataset)
    rows: list[dict[str, object]] = []
    for goal in goals:
        order = topological_order(ancestors_subgraph(kg.prereq, [goal]))
        min_s = sum(min(kg.resources[r].seconds for r in kg.resources_for(c)) for c in order)
        state = LearnerState.cold_start(kg.concept_ids, time_budget_s=min_s * 2.5)

        seq = plan_sequence(kg, [goal], state, budget_seconds=min_s * 2.5, reviews=True)
        if not seq.feasible or not seq.steps:
            continue
        seq_new = [s.resource_id for s in seq.steps if not s.review]
        s_seq = _score(kg, goal, seq_new, state)
        s_knap = _score(kg, goal, _knapsack_ordered(kg, goal, state), state)
        s_greedy = _score(kg, goal, _greedy_ordered(kg, goal), state)
        rows.append(
            {
                "goal": goal,
                "concepts": len(order),
                "reviews": sum(s.review for s in seq.steps),
                "sessions": len(seq.sessions),
                "seq_cost": round(s_seq["cost"], 3),
                "knapsack_cost": round(s_knap["cost"], 3),
                "greedy_cost": round(s_greedy["cost"], 3),
                "seq_jumps": round(s_seq["jumps"], 2),
                "knapsack_jumps": round(s_knap["jumps"], 2),
            }
        )

    def gap(key: str) -> float:
        num = sum(float(r[key]) - float(r["seq_cost"]) for r in rows)
        den = sum(abs(float(r["seq_cost"])) for r in rows) or 1.0
        return round(num / den, 4)

    summary: dict[str, object] = {
        "dataset": dataset,
        "goals_scored": len(rows),
        "knapsack_cost_gap_vs_seq": gap("knapsack_cost"),
        "greedy_cost_gap_vs_seq": gap("greedy_cost"),
        "mean_seq_jumps": round(sum(float(r["seq_jumps"]) for r in rows) / max(1, len(rows)), 2),
        "mean_knapsack_jumps": round(
            sum(float(r["knapsack_jumps"]) for r in rows) / max(1, len(rows)), 2
        ),
        "total_reviews_inserted": sum(int(r["reviews"]) for r in rows),
        "per_goal": rows,
    }
    RESULTS.mkdir(exist_ok=True)
    tag = "" if dataset == "synthetic" else f"_{dataset}"
    (RESULTS / f"sequencing{tag}.json").write_text(json.dumps(summary, indent=2))
    cols = ["goal", "concepts", "reviews", "sessions", "seq_cost", "knapsack_cost", "greedy_cost"]
    lines = [",".join(cols)] + [",".join(str(r[c]) for c in cols) for r in rows]
    (RESULTS / f"sequencing{tag}.csv").write_text("\n".join(lines) + "\n")
    return summary


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=(*DATASETS, "all"), default="synthetic")
    args = ap.parse_args()
    for ds in DATASETS if args.dataset == "all" else (args.dataset,):
        s = run(ds)
        print(
            f"\n[{ds}]  goals={s['goals_scored']}  reviews={s['total_reviews_inserted']}\n"
            f"  position-aware cost gap vs the sequencing DP:  "
            f"knapsack+heuristic +{s['knapsack_cost_gap_vs_seq']:.0%}   "
            f"greedy +{s['greedy_cost_gap_vs_seq']:.0%}\n"
            f"  mean difficulty-jump total:  seq {s['mean_seq_jumps']}   "
            f"knapsack {s['mean_knapsack_jumps']}"
        )
