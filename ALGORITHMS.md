# The DAA algorithms - where they are

All of them live in **`algorithms/`**.  Each function's docstring states its
worst-case complexity; each has a test that proves the property it must have.

| DAA topic | file · function | complexity | test |
|---|---|---|---|
| **Graph traversal** - cycle removal (Tarjan SCC + greedy feedback-arc-set) | [`graph_traversal.py`](algorithms/graph_traversal.py) · `remove_cycles` | `O(V+E)` | `tests/test_graph_traversal.py` |
| **Graph traversal** - ancestor extraction (backward BFS) | `graph_traversal.py` · `ancestors_subgraph` | `O(V+E)` | ″ |
| **Graph traversal** - topological sort (Kahn, deterministic) | `graph_traversal.py` · `topological_order` | `O(V+E)` | ″ |
| **Dynamic programming** - constrained multiple-choice knapsack over the topological order (the core; provably optimal, feasible by construction) | [`dynamic_programming.py`](algorithms/dynamic_programming.py) · `solve_optimal` | `O(V·R·B)` time, `O(V·B)` space | `tests/test_dp_optimality.py`, `tests/test_dp_feasibility.py` |
| **Dynamic programming** - Pareto version (non-dominated set per state) | `dynamic_programming.py` · `solve_pareto` | `O(V·R·B·F²·d)` | `tests/test_dp_feasibility.py` |
| **A\* search (anytime)** - feasible incumbent instantly, then branch-and-bound to the same proven optimum; admissible suffix-min heuristic; optional wall-clock `deadline_s` | [`astar.py`](algorithms/astar.py) · `solve_astar` | anytime; ≤ DP worst case | `tests/test_astar.py` |
| **Pareto / multi-objective** - dominance, non-dominated filter, ε-prune | [`pareto.py`](algorithms/pareto.py) | `O(n²·d)` | `tests/test_pareto.py` |

## The learner model (what the costs condition on)

| topic | file · function | note |
|---|---|---|
| **Bayesian Knowledge Tracing** (2-state HMM), difficulty-scaled cold-start priors | [`model/learner.py`](model/learner.py) · `bkt_update`, `LearnerState.cold_start` | valid plan at interaction 0 (N4) |
| **Learning velocity** - mastery gain per study hour, online EW estimate, feeds the edge cost | `learner.py` · `velocity_update`; [`model/cost.py`](model/cost.py) · `expected_mastery_gain` | N2 - `tests/test_velocity_ablation.py` |
| **DKT-lite refinement** - per-concept online PFA logistic model, blended into the mastery estimate as evidence accumulates | [`model/refine.py`](model/refine.py) · `MasteryRefiner` | N4 - refines, does not replace, the cold-start estimate |
| **Forgetting** - Ebbinghaus exponential decay | `learner.py` · `decay` | |

## Why the guarantees hold

* **Prerequisite validity** - `ancestors_subgraph` returns exactly the goal concepts
  plus their ancestors: a prerequisite-*closed* set.  Presenting it in a
  topological order means no resource is ever shown before a resource covering its
  prerequisites.  Structural, not a runtime check.
* **Budget** - the DP state is `(concept_index, buckets_used)`; a transition that
  would exceed `B` buckets is never generated, so an over-budget plan is
  *unrepresentable*.  No plan fits ⇒ the solver returns `Plan.infeasible(...)`.
* **Optimality** - `solve_optimal` is a multiple-choice-knapsack DP over a
  topological order ⇒ the exact global optimum.  `tests/test_dp_optimality.py`
  checks it equals exhaustive search on random curricula × 5 weight vectors.
* **Complexity** - `O(V·R·B)` time, `O(V·B)` space, in the docstring of every solver.

## Pipeline

```
KnowledgeGraph  (model/knowledge_graph.py  <-  curriculum.py  or  benchmarks/datasets.py: real Junyi graph)
   remove_cycles           algorithms/graph_traversal.py    O(V+E)   (real graphs can have cycles)
   ancestors_subgraph      algorithms/graph_traversal.py    O(V+E)
   topological_order       algorithms/graph_traversal.py    O(V+E)
   build_cost_vectors      model/cost.py    <-gain(m, VELOCITY), time, load, |Δd|, -review>
                                            m = BKT prior -> forgetting decay -> DKT-lite refine
   solve_optimal / solve_pareto   algorithms/dynamic_programming.py   O(V·R·B)
   solve_astar             algorithms/astar.py    anytime; feasible now, proven-optimal in <1 ms
   explain_plan            explain.py    knowledge-graph-grounded reason per step
```

Run it end to end and print the result:  `python velpo.py demo --goal quadratics`
