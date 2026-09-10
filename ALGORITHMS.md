# The DAA algorithms - where they are

All of them live in **`algorithms/`**.  Each function's docstring states its
worst-case complexity; each has a test that proves the property it must have.

| DAA topic | file · function | complexity | test |
|---|---|---|---|
| **Graph traversal** - cycle removal (Tarjan SCC + greedy feedback-arc-set) | [`graph_traversal.py`](algorithms/graph_traversal.py) · `remove_cycles` | `O(V+E)` | `tests/test_graph_traversal.py` |
| **Graph traversal** - ancestor extraction (backward BFS) | `graph_traversal.py` · `ancestors_subgraph` | `O(V+E)` | ″ |
| **Graph traversal** - topological sort (Kahn, deterministic) | `graph_traversal.py` · `topological_order` | `O(V+E)` | ″ |
| **Graph / order theory** - minimum chain cover (Dilworth, via bipartite matching) + order-ideal enumeration | [`poset.py`](algorithms/poset.py) · `min_chain_cover`, `order_ideals` | matching `O(V·E)`; `#ideals ≤ ∏(chain+1)` | `tests/test_poset.py` |
| **Dynamic programming (the core)** - precedence-constrained **sequencing** DP over the lattice of order ideals: provably-optimal *linear extension* + resource choice, position-dependent costs | [`sequencing.py`](algorithms/sequencing.py) · `solve_sequence` | `O(#ideals · W · R)`, `#ideals = O((n/w+1)^w)` | `tests/test_sequencing.py` (== exhaustive search) |
| **Dynamic programming** - spaced-review insertion (1-D pass over the sequence) | `sequencing.py` · `insert_reviews` | `O(n · P)` | `tests/test_sequencing.py` |
| **Dynamic programming** - study-session packing (1-D partition DP) | `sequencing.py` · `pack_sessions` | `O(n²)` | `tests/test_sequencing.py` |
| **Dynamic programming** - multiple-choice knapsack over a topological order (selection-only; the tractable fallback) | [`dynamic_programming.py`](algorithms/dynamic_programming.py) · `solve_optimal` | `O(V·R·B)` time, `O(V·B)` space | `tests/test_dp_optimality.py`, `tests/test_dp_feasibility.py` |
| **Dynamic programming** - Pareto version (non-dominated set per state) | `dynamic_programming.py` · `solve_pareto` | `O(V·R·B·F²·d)` | `tests/test_dp_feasibility.py` |
| **A\* search (anytime)** - feasible incumbent instantly, then branch-and-bound to the same proven optimum; admissible suffix-min heuristic; optional wall-clock `deadline_s` | [`astar.py`](algorithms/astar.py) · `solve_astar` | anytime; ≤ DP worst case | `tests/test_astar.py` |
| **Pareto / multi-objective** - dominance, non-dominated filter, ε-prune | [`pareto.py`](algorithms/pareto.py) | `O(n²·d)` | `tests/test_pareto.py` |
| **Adaptive testing** - greedy **maximum-Fisher-information** item selection + EAP ability estimation (2PL IRT); measures the learner's level instead of asking | [`model/assessment.py`](model/assessment.py) · `select_next_item`, `eap_estimate`, `AdaptiveSession` | `O(items · grid)` per estimate | `tests/test_assessment.py` |

## The learner model (what the costs condition on)

| topic | file · function | note |
|---|---|---|
| **Adaptive capability test** (2PL IRT + max-information CAT) - the cold-start mastery is *measured*, not self-reported | [`model/assessment.py`](model/assessment.py), [`assessment_bank.py`](assessment_bank.py) | `python velpo.py assess` · `/assess/*` |
| **Open-resource discovery + auto level-estimation** - real resources (Wikipedia/Wikibooks/MIT/arXiv/YouTube), difficulty from Flesch-Kincaid readability + jargon density + title cues + source priors | [`harvest/`](harvest/) · `discover_catalogue`, `estimate_level` | `python velpo.py harvest` · `/discover/{id}` |
| **Goal routing + dynamic graph construction** - curated seed DAGs (algebra / DSA / Python); else a prerequisite graph built from Wikipedia lead-link asymmetry + N1 cycle removal | [`domains.py`](domains.py) · `resolve`; [`dynamic.py`](dynamic.py) · `build_dynamic_graph` | `python velpo.py plan --goal "..."` · `/resolve` |
| **Bayesian Knowledge Tracing** (2-state HMM), difficulty-scaled cold-start priors (used when no assessment was taken) | [`model/learner.py`](model/learner.py) · `bkt_update`, `LearnerState.cold_start` | valid plan at interaction 0 (N4) |
| **Learning velocity** - mastery gain per study hour, online EW estimate, feeds the edge cost | `learner.py` · `velocity_update`; [`model/cost.py`](model/cost.py) · `expected_mastery_gain` | N2 - `tests/test_velocity_ablation.py` |
| **DKT-lite refinement** - per-concept online PFA logistic model, blended into the mastery estimate as evidence accumulates | [`model/refine.py`](model/refine.py) · `MasteryRefiner` | N4 - refines, does not replace, the cold-start estimate |
| **Forgetting** - Ebbinghaus exponential decay | `learner.py` · `decay` | |

## Why the guarantees hold

* **Prerequisite validity** - the plan is a *linear extension* of the prerequisite
  poset: every prefix is an order ideal (down-set), so no concept is ever taught
  before its prerequisites.  Structural, not a runtime check.
* **Sequence optimality** - `solve_sequence` is a shortest-path DP over the lattice
  of order ideals with state `(ideal, last resource)`.  That state is a sufficient
  statistic for the remaining cost (prerequisite mastery is a function of the
  ideal and the step index), so the recurrence is exact ⇒ the returned
  **sequence** (order *and* resources) is the global optimum for the position-aware
  cost model.  `tests/test_sequencing.py` checks it equals exhaustive search over
  every linear extension × resource choice on 30 random curricula.
* **Tractability** - `#order-ideals ≤ ∏(chain length + 1)` over a minimum chain
  cover `= O((n/w+1)^w)` for poset width `w`.  Curricula are tall and narrow
  (`tests/test_poset.py` checks width ≤ 4), so this is polynomial.  Above
  `settings.seq_max_ideals` the engine falls back to `solve_optimal` (still
  selection-optimal, `O(V·R·B)`, budget-feasible by construction).
* **Budget** - a pre-check rejects goals whose minimal-time plan can't fit; if the
  cost-optimal sequence overruns the budget it is re-solved with shortest
  resources (feasible if any sequence is).

## Pipeline

```
KnowledgeGraph  (model/knowledge_graph.py  <-  curriculum.py  or  benchmarks/datasets.py: real Junyi graph)
   remove_cycles           algorithms/graph_traversal.py    O(V+E)   (real graphs can have cycles)
   ancestors_subgraph      algorithms/graph_traversal.py    O(V+E)   prerequisite-closed relevant set
   min_chain_cover         algorithms/poset.py              matching  -> poset width -> #ideals bound
   solve_sequence          algorithms/sequencing.py         O(#ideals · W · R)   the optimal linear extension
       step cost           model/cost.py::sequence_step_cost  <- prereq-freshness(pos), gain(VELOCITY), |Δd|
       m per concept       BKT prior -> forgetting decay -> DKT-lite (PFA) refine
   insert_reviews          algorithms/sequencing.py         O(n·P)   spaced review where mastery would decay
   pack_sessions           algorithms/sequencing.py         O(n²)    split into study sessions
   explain_plan            explain.py                       knowledge-graph-grounded reason per step
                           (solve_optimal / solve_astar / solve_pareto = selection-only modes / fallback)
```

Run it end to end and print the result:  `python velpo.py demo --goal quadratics`
Does the ordering matter?  `python velpo.py seqbench`
