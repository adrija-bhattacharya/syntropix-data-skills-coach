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
| prerequisite / budget validity | **guaranteed by construction** (encoded in the DP state) | soft reward term - can be violated |
| optimality | **provably globally optimal** (matches brute force) | "a good path", no guarantee |
| worst-case cost | **documented `O(V·R·B)`** | not stated |
| multi-objective | explicit **Pareto front** the teacher chooses from | one hand-tuned weighted sum |
| learning speed | **first-class per-concept velocity** in the edge cost | implicit at best |
| cold-start | valid path at interaction #0 (graph + Bayesian priors) | usually unsolved |
| re-plan | deterministic, fast (A\* anytime), no retraining | policy retraining, instability |

## Quickstart

```bash
make setup       # pip install -e ".[dev]"  +  npm install in frontend/
make test        # pytest  (unit + Hypothesis property tests, incl. DP == brute force)
make benchmark   # VELPO vs greedy / ACO / DQN  ->  results/summary.csv (+ .png)
make serve       # build the React UI, then serve it + the API at http://localhost:8000
make api         # API only, http://localhost:8000/docs
```

For live front-end work: `make api` in one shell, `cd frontend && npm run dev` in another.
No GPU, no paid services, no network needed for the Python tests.

### In VS Code

Open **`velpo.code-workspace`**.  It recommends the extensions (Python, Pylance, Ruff, Mypy).

* `Ctrl+Shift+P → Python: Select Interpreter` → your env
* `Ctrl+Shift+P → Tasks: Run Task → setup`
* **Run and Debug** (`Ctrl+Shift+D`): *API (uvicorn --reload)*, *Pytest: current file*,
  *Pytest: all*, *Benchmark*
* Test Explorer (beaker icon) discovers the pytest suite; format + import-sort on save (Ruff)

## Layout

```
velpo/
  algorithms/   graph_traversal.py · dynamic_programming.py · astar.py · pareto.py   <- the DAA core
  model/        knowledge_graph.py · learner.py (BKT + velocity + forgetting + load) · cost.py
  engine.py     orchestration
  explain.py    knowledge-graph-grounded reason strings
  curriculum.py labelled synthetic algebra curriculum (demo / API / tests)
  api.py        FastAPI (+ serves the built SPA at /)
frontend/       React + TypeScript + Vite  ->  builds into velpo/web
benchmarks/     benchmark.py  (VELPO vs greedy / ACO / DQN)
tests/          the guarantees
```

## Benchmark (synthetic curriculum, 80 seeded runs)

| method | safe-behaviour | over-budget | optimality gap | latency |
|---|---|---|---|---|
| **velpo_dp** | **1.00** | **0.00** | **0.000** | ~0.6 ms |
| **velpo_astar** | **1.00** | **0.00** | **0.000** | ~0.4 ms |
| greedy | 0.66 | 0.34 | 0.26 | ~0.2 ms |
| ant colony optimization | 0.66 | 0.34 | 0.000 | ~235 ms |
| Q-learning (DQN-style) | 0.66 | 0.34 | 0.009 | ~52 ms |

Only VELPO never returns an over-budget plan; A\* reaches the proven optimum ~600× faster
than ACO; greedy is fast but 26 % sub-optimal.  Reproduce with `make benchmark`.

## Tests

`make test` - 56 tests, `ruff` + `mypy --strict` + `tsc` all clean.  The two that matter most:

* `tests/test_dp_optimality.py` - the DP equals exhaustive search on every random curriculum
* `tests/test_dp_feasibility.py` - 250+ random cases, every plan passes an independent
  prerequisite / budget / coverage checker

## License

MIT.
