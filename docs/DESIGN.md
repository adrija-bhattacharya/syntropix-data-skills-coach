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

* `G = (C, E)` - a DAG of concepts; edge `(u, v)` means `u` is a prerequisite of
  `v`.  `(C, ≤)` is the induced partial order (`u ≤ v` iff `u` is a transitive
  prerequisite of `v`).
* Each concept `c` has a candidate set `R(c)` of resources; resource `r` has a
  difficulty `d(r)` and an expected study time `t(r)`.
* A learner is `(m, v, h, T)`: per-concept mastery `m`, per-concept velocity `v`
  (mastery gained per study hour), retention half-lives `h`, budget `T`.
* Let `relevant = goals ∪ ancestors(goals)` (prerequisite-closed).
* A **plan** is a sequence `π = ⟨(c₁, r₁), …, (c_k, r_k)⟩` that is a **linear
  extension** of `(relevant, ≤)` - each `cᵢ ∈ relevant` appears once (plus
  optional review repeats), `rᵢ ∈ R(cᵢ)`, and `cᵢ ≤ cⱼ ⇒ i < j`.
* **Feasible** iff `Σ t(rᵢ) ≤ T` (linear-extension ⇒ prerequisites always precede,
  by construction).
* **Position-aware step cost** `f(cᵢ, rᵢ | π₍<ᵢ₎)` depends on the position `i`:
  prerequisite mastery is `m₀ · 2^{-(i − depth(prereq)) / h_steps}`, so cost rises
  if `cᵢ` is scheduled too early (weak prereqs) or too late (decayed prereqs).
* **Objective vector** `F(π)` (all "lower is better"):
  `⟨ −Σ Δmastery,  Σ t,  Σ load,  Σ |Δdifficulty|,  −Σ reviewGain ⟩`, each term
  summed over the position-aware step costs.
* **Single-objective**: minimise `w·F(π)` over all linear extensions and resource
  choices.  Solved **exactly** by the order-ideal DP in `O(#ideals · W · R)`,
  `#ideals = O((n/w+1)^w)`.
* **Multi-objective**: return the Pareto set (`solve_pareto`, selection-only).

## Why dynamic programming (the DAA contribution, claim N1)

`relevant` is prerequisite-closed (backward BFS), so a valid learning path is a
**linear extension** of the prerequisite partial order, and every *prefix* of a
path is an **order ideal** (down-set) of that poset.  We do not just pick a
resource per concept - we choose the **order itself**, because the cost of a step
depends on where it sits: a concept taught before its prerequisites are solid, or
long after they have decayed, costs more (`model/cost.py::sequence_step_cost`).

`solve_sequence` is a shortest-path DP over the lattice of order ideals:

```
dp[(I, r_last)] = min cost to have taught exactly the concept set I,
                  ending on resource r_last
dp[(I ∪ {c}, r)] = min over ℓ of  dp[(I, ℓ)] + stepCost(c, r | position |I|, prev diff of ℓ)
                   for every c whose prerequisites ⊆ I,  every r ∈ R(c)
```

* `(I, r_last)` is a **sufficient statistic** for the remaining cost - prerequisite
  mastery is a function of `I` and the step index `|I|` - so the recurrence is
  exact ⇒ the returned **sequence** is the global optimum.
  `tests/test_sequencing.py` checks it against exhaustive search over every linear
  extension × resource choice.
* Order ideals are represented as integer bitmasks; the DP is a BFS over the
  ideal lattice, smallest-first.
* **Complexity**: `#ideals ≤ ∏(chain length + 1)` over a minimum chain cover
  (Dilworth) `= O((n/w + 1)^w)` for width `w`.  Curricula are tall and narrow
  (width ≤ 4 for the course curriculum), so it is polynomial.  Time
  `O(#ideals · W · R)`.
* **Fallback**: above `settings.seq_max_ideals` order ideals the engine drops to
  `solve_optimal` - the multiple-choice-knapsack DP over a topological order
  (`dp[b] = min over r of dp[b − buckets(r)] + w·cost(r)`, `O(V·R·B)`, budget
  feasible by construction, selection-optimal) plus a difficulty-smoothing
  heuristic order.  `benchmarks/sequencing_bench.py` measures the price of that
  degradation: the knapsack + heuristic sits ~26 % (synthetic) / ~38 % (real
  Junyi graph) above the sequencing DP on the position-aware cost.
* Two follow-on DPs finish the plan: `insert_reviews` (1-D pass, splices spaced
  review steps where a concept would decay below threshold before it is needed)
  and `pack_sessions` (1-D partition DP, `O(n²)`, splits the sequence into study
  sessions under per-session time and load caps).

`solve_astar` (claim **N6**) explores the identical state space best-first with an
admissible `suffix-min` heuristic.  It is **anytime**: a feasible incumbent (the
per-concept cheapest-by-time choice) is available before the search starts, then
branch-and-bound improves it and - with no `deadline_s` - proves it optimal,
identical to `solve_optimal`, in well under 1 ms on the course curriculum (~3 ms on
a 40-concept slice of the real Junyi graph).  So "re-plan after every interaction"
needs no retraining, no policy instability, no sim-to-real gap.
`solve_pareto` keeps a non-dominated *set* per state and returns the front.

Difficulty-smoothing (ordering the chosen resources so consecutive difficulties are
close) is a separate, clearly-labelled heuristic layer in `_order_for_smoothness`;
it is **not** part of the optimality claim.

## Learner model (lightweight, CPU-only)

* **mastery** - Bayesian Knowledge Tracing (a 2-state HMM); cold-start priors from
  item difficulty, so there is a valid, near-optimal path at **interaction 0**
  (claim **N4**).  As attempts arrive, `model/refine.py` (a compact online
  Performance-Factors-Analysis model - "DKT-lite", pure NumPy, no RNN) is blended
  into the estimate with a weight that ramps from 0 to 1 over the first few
  attempts per concept: the learned model *refines*, never *replaces*, the
  cold-start estimate.  `tests/test_refine.py` checks both ends.
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

## Benchmark harness (claim N7)

`benchmarks/datasets.py` reduces every dataset to the pair `(KnowledgeGraph,
goals)` so `benchmarks/benchmark.py` runs **one** metric set - safe-behaviour,
over-budget, optimality gap (vs exhaustive search when tractable, else the
provably-optimal DP), latency - across all of them.  Two datasets ship:

* `synthetic` - the hand-authored algebra curriculum.
* `junyi` - the **real** Junyi Academy prerequisite graph (776 concepts, 985
  edges; a 57-concept offline sample is bundled, `--full` downloads the rest from
  the open mirror).  The prerequisite edges are real; the per-resource difficulty
  and time are synthesised from DAG depth and clearly labelled.  Real graphs can
  carry annotation cycles, so `remove_cycles` (N1) runs on the way in.

Adding ASSISTments / EdNet is one more `load_*` that ends in
`knowledge_graph_from_edges`; their logs carry no prerequisite graph, so they
need an inferred one - the hook is in place, the inference is future work.

## Not claimed as new

Knowledge tracing, prerequisite graphs, the forgetting curve, A\*, Pareto DP, PFA,
DP over order ideals (it appears in project scheduling / RCPSP) - all exist.  The
contribution is bringing the **precedence-constrained sequencing DP over order
ideals** to learning-path optimisation with a **position-aware** cost, so the
*sequence* (order + resources) is provably optimal - not just the selection - with
a width-based complexity bound and a documented fallback; plus learning-velocity
as a first-class per-concept cost driver that changes the order and the number of
review insertions; plus in-sequence spaced review and session-packing DPs; plus
the anytime re-plan and the one-metric synthetic + real-graph harness.
