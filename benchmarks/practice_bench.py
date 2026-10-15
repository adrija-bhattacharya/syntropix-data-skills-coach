"""Claim E - does execution-verified diagnosis get learners to the goal faster?

    python -m benchmarks.practice_bench      # -> results/practice.{json,csv}

Simulated learners with a **hidden misconception**: the adaptive test rated
every prerequisite of the goal as known (estimate 0.9), but one prerequisite is
in fact not understood.  Each learner works SQL tasks until they pass the goal
task, or run out of attempts.

Two conditions on the *same* learners (same seeds):

* **outcome-only** - submissions are graded right / wrong, nothing more.  This is
  what a knowledge-tracing system sees: the goal concept takes the blame for
  every failure, and the next task is the failed one again.
* **execution-verified** - the output-diff fingerprint names the prerequisite
  behind the failure; its mastery drops, a repair task is routed in first, and
  the graph edge evidence is updated (claim D).

Learner model (stated, so the comparison can be audited):

* a learner passes a task iff they know every concept it needs; otherwise they
  write the characteristic wrong query for the first concept they lack (with
  probability ``noise`` an *uninformative* wrong query instead), and a learner
  who knows everything still slips with probability ``slip``;
* after a failed attempt, a concept the task *targets* is learned with
  probability ``p_learn`` (the feedback is about it); a concept the task only
  *depends on* is learned with ``p_incidental`` (feedback on an outer-join task
  rarely teaches NULL semantics).

Reported per scenario: success rate within ``max_attempts``; mean attempts to
the goal (a learner who never gets there counts as ``max_attempts``); how often
the hidden concept was identified (its estimate dropped below threshold); and
the posterior of the edge from the hidden concept to the goal after the cohort
(``-`` when that pair is neither an edge nor a watched candidate).
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

from config import seed_everything, settings
from domains import seed_graph
from engine import Engine
from practice import TASKS_BY_ID

RESULTS = Path(__file__).resolve().parents[1] / "results"

# concepts a task needs beyond its target and ``uses`` (what the data exposes)
_EXTRA_NEEDS: dict[str, tuple[str, ...]] = {
    "orders_per_customer": ("null_logic",),
}

# the wrong query a learner writes when they lack a concept, per task
_BUGGY: dict[tuple[str, str], str] = {
    ("orders_per_customer", "outer_join"): (
        "SELECT c.name, COUNT(o.id) FROM customers c JOIN orders o ON o.customer_id = c.id "
        "GROUP BY c.name"
    ),
    ("orders_per_customer", "null_logic"): (
        "SELECT c.name, COUNT(*) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id "
        "GROUP BY c.name"
    ),
    ("orders_per_customer", "group_by"): (
        "SELECT c.name, COUNT(o.id) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id"
    ),
    ("unknown_city", "null_logic"): "SELECT name FROM customers WHERE city = NULL",
    ("spend_per_customer", "inner_join"): (
        "SELECT c.name, SUM(o.amount) FROM customers c JOIN orders o ON o.customer_id = c.id "
        "JOIN order_items i ON i.order_id = o.id GROUP BY c.name"
    ),
    ("spend_per_customer", "group_by"): (
        "SELECT c.name, SUM(o.amount) FROM customers c JOIN orders o ON o.customer_id = c.id"
    ),
    ("order_customer", "inner_join"): (
        "SELECT id, name FROM orders o JOIN customers c ON c.id = o.customer_id"
    ),
    ("orders_per_status", "group_by"): "SELECT status, COUNT(*) FROM orders",
    ("order_vs_customer_total", "window_functions"): (
        "SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id"
    ),
    ("repeat_customers", "group_by"): "SELECT customer_id FROM orders HAVING COUNT(*) > 1",
    ("repeat_customers", "having"): (
        "SELECT customer_id FROM orders WHERE COUNT(*) > 1 GROUP BY customer_id"
    ),
}


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    goal_task: str
    hidden: str | None  # the prerequisite the learner secretly lacks


SCENARIOS: tuple[Scenario, ...] = (
    Scenario("NULL logic behind LEFT JOIN", "orders_per_customer", "null_logic"),
    Scenario("join fan-out behind GROUP BY", "spend_per_customer", "inner_join"),
    Scenario("GROUP BY behind HAVING", "repeat_customers", "group_by"),
    Scenario("control: no misconception", "orders_per_customer", None),
)


def _needs(task_id: str) -> list[str]:
    t = TASKS_BY_ID[task_id]
    return [t.concept, *t.uses, *_EXTRA_NEEDS.get(task_id, ())]


def _attempt(
    task_id: str, known: set[str], rng: random.Random, *, noise: float, slip: float
) -> str:
    t = TASKS_BY_ID[task_id]
    missing = [c for c in _needs(task_id) if c not in known]
    if not missing:
        # a slip: an uninformative wrong answer (right rows, one column short)
        return "SELECT 1 AS slip" if rng.random() < slip else t.reference
    # the concept furthest upstream is the one that shows in the output
    for c in reversed(missing):
        if (task_id, c) in _BUGGY and rng.random() >= noise:
            return _BUGGY[(task_id, c)]
    return "SELECT 1 AS wrong"


def _run_learner(
    eng: Engine,
    lid: str,
    sc: Scenario,
    *,
    attribute: bool,
    seed: int,
    max_attempts: int,
    p_learn: float,
    p_incidental: float,
    noise: float,
    slip: float,
) -> tuple[int | None, int | None]:
    """(attempts to pass the goal or None, attempt at which hidden was identified or None)."""
    rng = random.Random(seed)
    goal = TASKS_BY_ID[sc.goal_task]
    needs = set(_needs(sc.goal_task))
    known = {c for c in eng.kg.concepts if c != goal.concept and c != sc.hidden}
    # the adaptive test rated every prerequisite as known - including the hidden one
    state = eng.ensure(lid, time_budget_s=3600.0)
    for c in needs - {goal.concept}:
        state.mastery[c] = 0.9
    state.mastery[goal.concept] = 0.1
    eng.store.put(lid, state)

    task_id: str | None = goal.id
    identified: int | None = None
    for n in range(1, max_attempts + 1):
        assert task_id is not None
        query = _attempt(task_id, known, rng, noise=noise, slip=slip)
        out = eng.submit_practice(lid, task_id, query, goals=[goal.concept], attribute=attribute)
        if sc.hidden and identified is None:
            st = eng.store.get(lid)
            if st is not None and not st.is_mastered(sc.hidden):
                identified = n
        if out.correct and task_id == goal.id:
            return n, identified
        if not out.correct:
            t = TASKS_BY_ID[task_id]
            for c in _needs(task_id):
                if c in known:
                    continue
                p = p_learn if c == t.concept else p_incidental
                if rng.random() < p:
                    known.add(c)
        task_id = out.next_task or goal.id
    return None, identified


def run(
    *,
    learners: int = 200,
    max_attempts: int = 20,
    p_learn: float = 0.4,
    p_incidental: float = 0.05,
    noise: float = 0.1,
    slip: float = 0.03,
    seed: int = 0,
    write: bool = True,
) -> dict[str, object]:
    seed_everything()
    rows: list[dict[str, object]] = []
    for si, sc in enumerate(SCENARIOS):
        for attribute in (False, True):
            eng = Engine(seed_graph("sql"))
            results = [
                _run_learner(
                    eng,
                    f"s{si}-l{i}",
                    sc,
                    attribute=attribute,
                    seed=seed * 100_003 + si * 10_007 + i,
                    max_attempts=max_attempts,
                    p_learn=p_learn,
                    p_incidental=p_incidental,
                    noise=noise,
                    slip=slip,
                )
                for i in range(learners)
            ]
            done = [a for a, _i in results if a is not None]
            ident = [i for _a, i in results if i is not None]
            goal_concept = TASKS_BY_ID[sc.goal_task].concept
            edge = None
            if sc.hidden:
                belief = eng.evidence.edges.get((sc.hidden, goal_concept)) or (
                    eng.evidence.candidates.get((sc.hidden, goal_concept))
                )
                edge = round(belief.mean, 3) if belief else None
            rows.append(
                {
                    "scenario": sc.name,
                    "condition": "execution-verified" if attribute else "outcome-only",
                    "learners": learners,
                    "success_rate": round(len(done) / learners, 3),
                    "mean_attempts": round(
                        statistics.fmean(a if a is not None else max_attempts for a, _ in results),
                        2,
                    ),
                    "mean_attempts_successful": round(statistics.fmean(done), 2) if done else None,
                    "median_attempts": statistics.median(done) if done else None,
                    "identified_rate": round(len(ident) / learners, 3) if sc.hidden else None,
                    "mean_attempts_to_identify": (
                        round(statistics.fmean(ident), 2) if ident else None
                    ),
                    "edge_hidden_to_goal": edge,
                    "edge_in_curated_graph": (
                        eng.kg.prereq.has_edge(sc.hidden, goal_concept) if sc.hidden else None
                    ),
                }
            )
    summary: dict[str, object] = {
        "params": {
            "learners": learners,
            "max_attempts": max_attempts,
            "p_learn": p_learn,
            "p_incidental": p_incidental,
            "noise": noise,
            "slip": slip,
            "mastery_threshold": settings.mastery_threshold,
        },
        "rows": rows,
    }
    if write:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "practice.json").write_text(json.dumps(summary, indent=2) + "\n")
        cols = list(rows[0])
        lines = [",".join(cols)] + [
            ",".join("" if r[c] is None else str(r[c]) for c in cols) for r in rows
        ]
        (RESULTS / "practice.csv").write_text("\n".join(lines) + "\n")
    return summary


def main() -> None:
    summary = run()
    rows = summary["rows"]
    assert isinstance(rows, list)
    print(
        f"{'scenario':36} {'condition':19} {'success':>8} {'attempts':>9} {'found':>6} {'edge':>6}"
    )
    for r in rows:
        att = f"{r['mean_attempts']:.1f}"
        found = "-" if r["identified_rate"] is None else f"{r['identified_rate']:.0%}"
        edge = "-" if r["edge_hidden_to_goal"] is None else f"{r['edge_hidden_to_goal']:.2f}"
        print(
            f"{r['scenario']:36} {r['condition']:19} {r['success_rate']:>8.0%} {att:>9} "
            f"{found:>6} {edge:>6}"
        )
    print(f"\nwritten to {RESULTS / 'practice.csv'}")


if __name__ == "__main__":
    main()
