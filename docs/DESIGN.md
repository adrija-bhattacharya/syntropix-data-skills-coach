# VELPO - design notes

## Problem

Given a catalogue of learning resources connected by prerequisite relationships, a
learner whose knowledge and learning speed we estimate and continuously update, a
target set of skills, and a study-time budget: **produce the ordered sequence of
resources that best helps this learner reach the target** - maximum mastery gain,
minimum time, minimum cognitive overload, smooth difficulty, timely review -
such that the sequence never asks the learner to study something before its
prerequisites are met and never exceeds the budget, every step is explainable, and
a teacher can constrain the result.

### Formal

* `G = (C, E)` - a DAG of concepts; edge `(u, v)` means `u` is a prerequisite of `v`.
* Each concept `c` has a candidate set `R(c)` of resources; resource `r` has a
  difficulty `d(r)` and an expected study time `t(r)`.
* A learner is `(m, v, h, T)`: per-concept mastery `m`, per-concept velocity `v`
  (mastery gained per study hour), retention half-lives `h`, remaining budget `T`.
* A **plan** chooses one `r ∈ R(c)` for every concept in
  `relevant = goals ∪ ancestors(goals)`.
* **Feasible** iff, presented in a topological order of `G`, every resource's
  prerequisite concepts are covered by earlier steps, and `Σ t(r) ≤ T`.
* **Objective vector** (all "lower is better"):
  `⟨ −Σ Δmastery(r | m, v),  Σ t(r),  Σ load(r | m),  Σ |Δdifficulty|,  −Σ reviewGain(r | m, h) ⟩`
* **Single-objective**: minimise `w·F(plan)`.  Solved exactly by DP in `O(V·R·B)`.
* **Multi-objective**: return the Pareto set.

## Why dynamic programming (the DAA contribution)

`relevant` is prerequisite-closed (backward BFS), so any topological order of it is a
valid study order - *prerequisite validity is structural, not a runtime check*.
What is left to decide is **which resource per concept**, under a global time
budget.  That is a **multiple-choice knapsack**, and a knapsack over a topological
order is a clean 1-D DP:

```
dp[b] = min scalar cost of choosing resources for concepts c_1..c_i (topo order)
        using at most b time buckets
dp[b] = min over r in R(c_i) of  dp[b - buckets(r)] + w·cost(r)
```

* budget-exceeding transitions are never generated ⇒ over-budget plans are
  **unrepresentable**;
* the recurrence is exact ⇒ the result is the **global optimum**;
* `O(V·R·B)` time, `O(V·B)` space; drops to `O(V·R)` when the budget cannot bind.

`solve_astar` explores the identical state space best-first with an admissible
`suffix-min` heuristic - same optimum, fewer expansions, for interactive re-planning.
`solve_pareto` keeps a non-dominated *set* per state and returns the front.

Difficulty-smoothing (ordering the chosen resources so consecutive difficulties are
close) is a separate, clearly-labelled heuristic layer in `_order_for_smoothness`;
it is **not** part of the optimality claim.

## Learner model (lightweight, CPU-only)

* **mastery** - Bayesian Knowledge Tracing (a 2-state HMM); cold-start priors from
  item difficulty.
* **velocity** (claim **N2**) - `v ← (1−α)·v + α·(Δmastery / Δhours)`, per concept,
  clipped.  It enters the edge cost directly through
  `expected_mastery_gain(current, velocity, seconds) = (1−current)·(1−e^{−v·h/τ})`,
  so the *same* catalogue + goal produces a compressed, lesson-heavy plan for a
  fast learner and a shorter, practice-heavy one for a slow learner.
  `benchmarks/ablation_velocity.py` measures this: with the signal on the optimal
  solver picks a different resource for ~60 % of concepts (4 of 5 goals get a
  different plan); flatten every velocity to 1.0 and the divergence drops to 0,
  proving velocity - not some incidental tie-break - is what personalises the plan.
  `test_velocity_ablation.py` asserts both halves.  The API exposes it as a
  `speed` ∈ {slow, normal, fast} knob; the React *Learner* view as a dropdown.
* **forgetting** - `m(t) = m₀·exp(−Δt / h)`.
* **cognitive load** - sensor-free proxy from recent error rate + hint usage.

## Teacher constraints (hard, not post-processing)

`ban` removes a resource from candidate sets; `lock` restricts a concept to one
resource; `force_order` adds a prerequisite edge (rejected if it creates a cycle).
The solver simply re-solves.  If a constraint admits no plan the solver returns
`Plan.infeasible(...)`.

## Not claimed as new

Knowledge tracing, prerequisite graphs, the forgetting curve, A\*, Pareto DP - all
exist.  The contribution is applying constrained multiple-choice-knapsack DP to
*this* problem to obtain guarantees the RL / metaheuristic literature lacks
(feasibility, optimality, a complexity bound), plus learning-velocity as a
first-class per-concept cost driver.
