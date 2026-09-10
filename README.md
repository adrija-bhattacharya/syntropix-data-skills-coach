# VELPO - Personalised Learning-Path Optimiser

Generate the **optimal ordered sequence of learning resources** for a learner, from
their performance and learning speed, using classic **Design-and-Analysis-of-Algorithms**
machinery (graph traversal + dynamic programming + A\*) instead of black-box
reinforcement learning.

> **DAA course project.**  The algorithm map is [`ALGORITHMS.md`](ALGORITHMS.md);
> the research design notes are in [`docs/DESIGN.md`](docs/DESIGN.md).

## What makes it different

| Property | VELPO | typical RL / metaheuristic system |
|---|---|---|
| what is optimised (N1) | the **whole sequence** - order *and* resources - by a DP over the poset's order ideals, with **position-aware** costs | a resource set, or "a good path", no guarantee |
| prerequisite / budget validity | **structural**: the plan is a linear extension of the prerequisite poset | soft reward term - can be violated |
| worst-case cost | **`O(#ideals · W · R)`, `#ideals = O((n/w+1)^w)`** for width `w` (+ knapsack fallback) | not stated |
| learning speed (N2) | **first-class per-concept velocity** in the step cost - changes the order and the review count | implicit at best |
| spaced review | the sequence **re-inserts** a concept when it will decay before the goal | none |
| study sessions | a partition DP splits the plan into sessions under time + load caps | none |
| cold-start (N4) | valid path at interaction #0 (graph + Bayesian priors), then DKT-lite refinement | usually unsolved |
| re-plan (N6) | **anytime A\***: feasible plan instantly, proven-optimal in <1 ms, no retraining | policy retraining, instability |
| evidence (N7) | one benchmark harness over synthetic **and the real Junyi graph** | "no standard benchmark" |

## Easy commands - `python velpo.py <cmd>`

No `make` needed; works the same in Windows PowerShell, macOS and Linux.

```bash
python velpo.py setup       # install Python deps (editable) + frontend npm packages
python velpo.py doctor      # check the environment is ready
python velpo.py demo        # solve ONE path and print it in the terminal (no server)
python velpo.py test        # the whole test suite
python velpo.py lint        # ruff + ruff format --check + mypy --strict
python velpo.py serve       # build the React UI + serve it & the API at http://localhost:8000
python velpo.py api         # API only (autoreload)  -> http://localhost:8000/docs
python velpo.py ui          # React dev server        -> http://localhost:5173  (needs `api` too)
python velpo.py ui-test     # strict tsc + the React test suite (vitest + Testing Library + MSW)
python velpo.py benchmark --dataset all   # VELPO vs greedy / ACO / DQN  -> results/summary*.csv
python velpo.py ablation    # N2 check: does learning velocity change the plan?
python velpo.py datasets    # list / download the benchmark datasets  (--full = whole Junyi graph)
```

See the whole pipeline in one command:

```bash
python velpo.py demo --goal quadratics --minutes 90 --speed fast
python velpo.py demo --goal quadratics --minutes 90 --speed slow   # different plan - that's N2
python velpo.py demo --dataset junyi --goal multiplication_word_problems --minutes 400   # real graph, sessions + reviews
python velpo.py seqbench                                           # does optimising the order pay off?
```

(`make` still works too - it just forwards to `python velpo.py`.)

### In VS Code

Open **`velpo.code-workspace`** (recommends the Python / Pylance / Ruff / Mypy extensions).
`Ctrl+Shift+P → Tasks: Run Task` lists **setup / doctor / demo / test / lint / benchmark /
ablation / datasets**; **Run and Debug** has the API and pytest launchers; the Test Explorer
discovers the suite; Ruff formats on save.

## Layout

The code sits **directly at the repo root** - no nesting:

```
velpo.py        the CLI - every task is one command
algorithms/     poset.py (Dilworth + order ideals) · sequencing.py (the core: order-ideal DP + review + sessions)
                graph_traversal.py · dynamic_programming.py (knapsack fallback) · astar.py (anytime) · pareto.py
model/          knowledge_graph.py · learner.py (BKT + velocity + forgetting) · refine.py (DKT-lite) · cost.py
engine.py       orchestration
explain.py      knowledge-graph-grounded reason strings
curriculum.py   labelled synthetic algebra curriculum (demo / API / tests)
api.py          FastAPI  (+ serves the built SPA at /)
config.py       tunable constants + weights
frontend/       React 18 + TS + Vite  ·  TanStack Query · React Router · Zod · Recharts  ·  Vitest + RTL + MSW
benchmarks/     benchmark.py · sequencing_bench.py · ablation_velocity.py · datasets.py (synthetic + real Junyi graph)
tests/          the guarantees
```

### Frontend architecture

`frontend/src` is feature-sliced: `lib/` (a zod-validated API client + TanStack
Query hooks + a theme store), `context/` (shared learner identity), `components/`
(design-system primitives, an error boundary, the Recharts difficulty and Pareto
charts), and `features/{learner,teacher}/` (route-split pages; the teacher's
constraint builder is a `useReducer`).  Server state lives entirely in TanStack
Query - logging an attempt invalidates the cached recommendation so the plan
re-solves itself.  `python velpo.py ui-test` runs 19 component/integration tests
against a mock API (MSW).  Light/dark/system theme, persisted.

## Benchmark

`python velpo.py benchmark --dataset all` - 60 seeded runs per dataset, tight and
comfortable budgets interleaved.  The optimality reference is exhaustive search
when tractable, else the DP (provably optimal).

**Synthetic algebra curriculum**

| method | safe-behaviour | over-budget | optimality gap | latency |
|---|---|---|---|---|
| **velpo_dp** | **1.00** | **0.00** | **0.000** | ~0.7 ms |
| **velpo_astar** | **1.00** | **0.00** | **0.000** | ~0.5 ms |
| greedy | 0.67 | 0.33 | 0.25 | ~0.2 ms |
| ant colony optimization | 0.67 | 0.33 | 0.00 | ~320 ms |
| Q-learning (DQN-style) | 0.67 | 0.33 | 0.01 | ~70 ms |

**Real Junyi Academy prerequisite graph** (57-concept offline sample; `--full` = 776 concepts)

| method | safe-behaviour | over-budget | optimality gap | latency |
|---|---|---|---|---|
| **velpo_dp** | **1.00** | **0.00** | **0.000** | ~13 ms |
| **velpo_astar** | **1.00** | **0.00** | **0.000** | ~3 ms |
| greedy | 1.00 | 0.00 | **0.27** | ~1 ms |
| ant colony optimization | 0.92 | 0.08 | 0.06 | ~490 ms |
| Q-learning (DQN-style) | 0.70 | 0.30 | 0.06 | ~200 ms |

Only VELPO never returns an over-budget plan **and** is never sub-optimal; A\* reaches
the proven optimum ~150× faster than ACO.  On the real graph greedy stays in budget
but is still 27 % from optimal, and ACO/DQN still overrun it.

## Optimising the *order* is worth it (claim N1)

`python velpo.py seqbench` scores three plans with the **same** position-aware cost
(one that penalises a concept taught before its prerequisites are solid, or long
after they have decayed):

| plan | synthetic | real Junyi graph |
|---|---|---|
| **sequencing DP over order ideals** | — (optimum) | — (optimum) |
| knapsack-select + difficulty-smoothing heuristic order | **+26 %** | **+38 %** |
| greedy (shortest per concept, topological order) | **+33 %** | **+70 %** |

On the real graph the DP also auto-inserts 16 spaced reviews across the 4 goals.
`tests/test_sequencing.py` proves the DP equals exhaustive search over every
linear extension × resource choice on 30 random curricula.

## Learning velocity is load-bearing (claim N2)

`python velpo.py ablation` plans the *same* goal for a fast learner (velocity ×3) and a
slow learner (velocity ×0.45):

| velocity signal | concepts given a different resource | plans differ for |
|---|---|---|
| **on** | **60 %** | **4 / 5 goals** (fast → fuller lessons, slow → shorter practice) |
| off (all velocity = 1.0) | 0 % | 0 / 5 goals |

So the personalisation comes from velocity itself, not an incidental tie-break.
`tests/test_velocity_ablation.py` asserts both rows; the UI exposes it as a
**Learning speed** dropdown in the Learner view.

## Tests

`python velpo.py test` - 129 Python tests + `python velpo.py ui-test` - 19 React tests;
`ruff` + `mypy --strict` + strict `tsc` all clean.  The ones that carry the claims:

* `test_sequencing.py` - the order-ideal DP equals exhaustive search over every linear extension × resource choice; reviews and sessions respect their invariants (N1)
* `test_poset.py` - Dilworth chain cover == max antichain; order-ideal enumeration is correct and complete
* `test_dp_optimality.py` / `test_dp_feasibility.py` - the knapsack fallback is selection-optimal and always prereq/budget-valid
* `test_velocity_ablation.py` - learning velocity changes the optimal plan; removing it removes the divergence (N2)
* `test_refine.py` - valid path at interaction 0, then the DKT-lite estimate tracks the learner (N4)
* `test_astar.py` - anytime A\* returns a feasible plan under any deadline and the proven optimum without one (N6)
* `test_datasets.py` - the real Junyi graph loads, cycles are removed, VELPO plans on it (N7)

## License

MIT.
