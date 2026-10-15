"""The Design-and-Analysis-of-Algorithms core.

* :mod:`graph_traversal`     - cycle removal (Tarjan SCC + greedy feedback-arc-set),
  ancestor extraction (backward BFS), topological sort (Kahn).  All ``O(V + E)``.
* :mod:`pareto`              - non-dominated set utilities for 5-D cost vectors.
* :mod:`dynamic_programming` - the constrained multiple-choice-knapsack DP over the
  topological order.  Feasible by construction; provably optimal;
  ``O(V * R * B)`` time, ``O(V * B)`` space.
* :mod:`astar`              - the same optimum, best-first, for fast re-planning.
"""

from algorithms.astar import solve_astar
from algorithms.dynamic_programming import (
    InfeasibleError,
    Plan,
    PlanContext,
    TeacherConstraints,
    solve_optimal,
    solve_pareto,
)
from algorithms.graph_traversal import (
    ancestors_subgraph,
    remove_cycles,
    topological_order,
)
from algorithms.pareto import dominates, epsilon_prune, non_dominated

__all__ = [
    "InfeasibleError",
    "Plan",
    "PlanContext",
    "TeacherConstraints",
    "ancestors_subgraph",
    "dominates",
    "epsilon_prune",
    "non_dominated",
    "remove_cycles",
    "solve_astar",
    "solve_optimal",
    "solve_pareto",
    "topological_order",
]
