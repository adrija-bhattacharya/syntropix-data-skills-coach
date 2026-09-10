"""VELPO command line - one easy entry point for every task.

    python velpo.py <command>

Commands
    setup        install Python deps (editable) + frontend npm packages
    doctor       check the environment is ready
    demo         solve one learning path and print it in the terminal (no server)
    plan         demo with options (--goal / --minutes / --speed / --mode / --dataset)
    test         run the test suite (pytest)
    lint         ruff check + ruff format --check + mypy --strict
    fmt          auto-format and auto-fix (ruff)
    api          run the API with autoreload at http://localhost:8000  (/docs for the UI)
    ui           run the React dev server at http://localhost:5173  (needs `api` in another shell)
    ui-test      typecheck (strict tsc) + run the React tests (vitest + Testing Library + MSW)
    serve        build the React UI and serve it + the API at http://localhost:8000
    benchmark    VELPO vs greedy / ACO / DQN   (--dataset synthetic|junyi|all  --runs N)
    ablation     N2 check - does learning velocity change the plan?
    datasets     download / inspect the benchmark datasets (--full for the whole Junyi graph)

Everything works on Windows PowerShell, macOS and Linux with no `make`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
PY = [sys.executable]


def _run(cmd: list[str], *, cwd: Path | None = None) -> int:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd or ROOT).returncode


def _npm() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


# --------------------------------------------------------------------------- #
def cmd_setup(_: argparse.Namespace) -> int:
    rc = _run([*PY, "-m", "pip", "install", "-e", ".[dev]"])
    if rc:
        return rc
    if (FRONTEND / "package.json").exists():
        rc = _run([_npm(), "install"], cwd=FRONTEND)
    return rc


def cmd_doctor(_: argparse.Namespace) -> int:
    ok = True
    print(f"python      {sys.version.split()[0]}  ({sys.executable})   [need >= 3.11]")
    for mod in ("networkx", "numpy", "scipy", "pandas", "sklearn", "pydantic", "fastapi"):
        try:
            __import__(mod)
            print(f"  ok  {mod}")
        except ImportError:
            print(f"  !!  {mod} missing - run:  python velpo.py setup")
            ok = False
    node = subprocess.run([_npm(), "--version"], capture_output=True, text=True)
    print(f"npm         {node.stdout.strip() or 'not found (frontend build will not work)'}")
    print(
        "web/ built"
        if (ROOT / "web" / "index.html").exists()
        else "web/ not built (run: python velpo.py serve)"
    )
    return 0 if ok else 1


def cmd_demo(args: argparse.Namespace) -> int:
    from benchmarks.datasets import load
    from engine import Engine

    kg, goals = load(args.dataset)
    goal = args.goal or goals[0]
    if goal not in kg.concepts:
        print(f"unknown goal {goal!r}. choices: {', '.join(goals)}")
        return 2
    speed = {"slow": 0.45, "normal": 1.0, "fast": 3.0}[args.speed]
    eng = Engine(kg)
    plans = eng.recommend(
        "demo", [goal], time_budget_s=args.minutes * 60, mode=args.mode, speed=speed
    )
    plan = plans[0]
    print(
        f"\ndataset={args.dataset}  goal={goal}  budget={args.minutes} min  "
        f"solver={args.mode}  speed={args.speed}\n"
    )
    if not plan.feasible:
        print(f"no feasible plan: {plan.note}")
        return 0
    for i, (rid, reason) in enumerate(zip(plan.steps, plan.reasons or [""] * len(plan.steps)), 1):
        print(f"{i:2}. {rid:<34} {reason}")
    o = plan.objective
    print(
        f"\n{len(plan.steps)} steps - {plan.total_seconds / 60:.0f} min | "
        f"mastery gain {-o.neg_gain:.2f}  load {o.load:.2f}  diff-jumps {o.diff_jump:.2f}"
    )
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    return _run([*PY, "-m", "pytest", *args.rest])


def cmd_lint(_: argparse.Namespace) -> int:
    targets = [
        "algorithms",
        "model",
        "tests",
        "benchmarks",
        "config.py",
        "curriculum.py",
        "engine.py",
        "explain.py",
        "api.py",
        "velpo.py",
    ]
    rc = _run([*PY, "-m", "ruff", "check", *targets])
    rc |= _run([*PY, "-m", "ruff", "format", "--check", *targets])
    rc |= _run([*PY, "-m", "mypy"])
    return rc


def cmd_fmt(_: argparse.Namespace) -> int:
    targets = [
        "algorithms",
        "model",
        "tests",
        "benchmarks",
        "config.py",
        "curriculum.py",
        "engine.py",
        "explain.py",
        "api.py",
        "velpo.py",
    ]
    rc = _run([*PY, "-m", "ruff", "format", *targets])
    rc |= _run([*PY, "-m", "ruff", "check", "--fix", *targets])
    return rc


def cmd_api(_: argparse.Namespace) -> int:
    return _run([*PY, "-m", "uvicorn", "api:app", "--reload", "--port", "8000"])


def cmd_ui(_: argparse.Namespace) -> int:
    return _run([_npm(), "run", "dev"], cwd=FRONTEND)


def cmd_ui_test(_: argparse.Namespace) -> int:
    rc = _run([_npm(), "run", "lint"], cwd=FRONTEND)  # tsc --noEmit (strict)
    rc |= _run([_npm(), "run", "test"], cwd=FRONTEND)  # vitest + RTL + MSW
    return rc


def cmd_serve(_: argparse.Namespace) -> int:
    if (FRONTEND / "package.json").exists():
        rc = _run([_npm(), "run", "build"], cwd=FRONTEND)
        if rc:
            return rc
    return _run([*PY, "-m", "uvicorn", "api:app", "--port", "8000"])


def cmd_benchmark(args: argparse.Namespace) -> int:
    return _run([*PY, "-m", "benchmarks.benchmark", *args.rest])


def cmd_ablation(_: argparse.Namespace) -> int:
    return _run([*PY, "-m", "benchmarks.ablation_velocity"])


def cmd_datasets(args: argparse.Namespace) -> int:
    from benchmarks.datasets import DATASETS, load

    for name in DATASETS:
        try:
            kg, goals = load(name, full=args.full) if name == "junyi" else load(name)
        except Exception as exc:
            print(f"{name:<10} ERROR: {exc}")
            continue
        print(
            f"{name:<10} {len(kg.concepts):>4} concepts  {len(kg.resources):>4} resources  "
            f"{len(goals):>3} goals  (e.g. {', '.join(goals[:3])})"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="velpo", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup").set_defaults(fn=cmd_setup)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)

    for name in ("demo", "plan"):
        d = sub.add_parser(name)
        d.add_argument("--dataset", default="synthetic", choices=("synthetic", "junyi"))
        d.add_argument("--goal", default=None)
        d.add_argument("--minutes", type=float, default=120)
        d.add_argument("--mode", default="optimal", choices=("optimal", "interactive", "pareto"))
        d.add_argument("--speed", default="normal", choices=("slow", "normal", "fast"))
        d.set_defaults(fn=cmd_demo)

    t = sub.add_parser("test")
    t.add_argument("rest", nargs=argparse.REMAINDER)
    t.set_defaults(fn=cmd_test)

    sub.add_parser("lint").set_defaults(fn=cmd_lint)
    sub.add_parser("fmt").set_defaults(fn=cmd_fmt)
    sub.add_parser("api").set_defaults(fn=cmd_api)
    sub.add_parser("ui").set_defaults(fn=cmd_ui)
    sub.add_parser("ui-test").set_defaults(fn=cmd_ui_test)
    sub.add_parser("serve").set_defaults(fn=cmd_serve)

    b = sub.add_parser("benchmark")
    b.add_argument("rest", nargs=argparse.REMAINDER)
    b.set_defaults(fn=cmd_benchmark)

    sub.add_parser("ablation").set_defaults(fn=cmd_ablation)

    ds = sub.add_parser("datasets")
    ds.add_argument("--full", action="store_true", help="download the complete Junyi graph")
    ds.set_defaults(fn=cmd_datasets)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
