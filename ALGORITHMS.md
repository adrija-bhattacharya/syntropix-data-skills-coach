# The DAA algorithms - where they are

All of them live in **`velpo/algorithms/`**.  Each function's docstring states its
worst-case complexity; each has a test that proves the property it must have.

| DAA topic | file · function | complexity | test |
|---|---|---|---|
| **Graph traversal** - cycle removal (Tarjan SCC + greedy feedback-arc-set) | [`graph_traversal.py`](velpo/algorithms/graph_traversal.py) · `remove_cycles` | `O(V+E)` | `tests/test_graph_traversal.py` |
| **Graph traversal** - ancestor extraction (backward BFS) | `graph_traversal.py` · `ancestors_subgraph` | `O(V+E)` | ″ |
| **Graph traversal** - topological sort (Kahn, deterministic) | `graph_traversal.py` · `topological_order` | `O(V+E)` | ″ |
| **Dynamic programming** - constrained multiple-choice knapsack over the topological order (the core; provably optimal, feasible by construction) | [`dynamic_programming.py`](velpo/algorithms/dynamic_programming.py) · `solve_optimal` | `O(V·R·B)` time, `O(V·B)` space | `tests/test_dp_optimality.py`, `tests/test_dp_feasibility.py` |
| **Dynamic programming** - Pareto version (non-dominated set per state) | `dynamic_programming.py` · `solve_pareto` | `O(V·R·B·F²·d)` | `tests/test_dp_feasibility.py` |
| **A\* search** - same optimum, best-first, admissible suffix-min heuristic | [`astar.py`](velpo/algorithms/astar.py) · `solve_astar` | anytime; ≤ DP worst case | `tests/test_astar.py` |
| **Pareto / multi-objective** - dominance, non-dominated filter, ε-prune | [`pareto.py`](velpo/algorithms/pareto.py) | `O(n²·d)` | `tests/test_pareto.py` |

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
KnowledgeGraph  (velpo/model/knowledge_graph.py)
   remove_cycles           velpo/algorithms/graph_traversal.py    O(V+E)
   ancestors_subgraph      velpo/algorithms/graph_traversal.py    O(V+E)
   topological_order       velpo/algorithms/graph_traversal.py    O(V+E)
   build_cost_vectors      velpo/model/cost.py    <-gain(m,VELOCITY), time, load, |Δd|, -review>
   solve_optimal / solve_pareto   velpo/algorithms/dynamic_programming.py   O(V·R·B)
   solve_astar             velpo/algorithms/astar.py    anytime, == solve_optimal
   explain_plan            velpo/explain.py    knowledge-graph-grounded reason per step
```
