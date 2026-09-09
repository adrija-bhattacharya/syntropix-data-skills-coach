"""VELPO - Personalised Learning-Path Optimisation.

A learner must reach a set of goal concepts. Concepts have prerequisites (a DAG).
For each concept the learner picks one of several candidate resources (a lesson,
a shorter practice set, ...), each with a difficulty and an expected study time.

VELPO returns the ordered sequence of resources that is best for *this* learner
- fastest mastery gain, least time, least cognitive overload, smooth difficulty,
timely review - subject to hard constraints: never study a resource before its
prerequisites are mastered, and never exceed the time budget.

The core is a Design-and-Analysis-of-Algorithms contribution (see ``velpo.algorithms``):

* graph traversal   - cycle removal, ancestor extraction, topological sort
* dynamic programming - a constrained multiple-choice-knapsack DP over the
  topological order that returns the provably optimal feasible plan in
  ``O(V * R * B)`` time
* A* search         - the same optimum, explored best-first, for sub-100 ms re-planning
* Pareto DP         - the non-dominated set of plans when the objectives are kept separate
"""

__version__ = "1.0.0"
