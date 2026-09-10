"""VELPO command line - one easy entry point for every task.

    python velpo.py <command>

Commands
    setup        install Python deps (editable) + frontend npm packages
    doctor       check the environment is ready
    demo         solve one learning path and print it in the terminal (no server)
    plan         demo with options (--goal / --minutes / --speed / --mode / --catalogue)
    assess       run the adaptive capability diagnostic in the terminal, then plan from it
    schedule     place the plan on a real calendar for a deadline (--goal / --by / --hours-per-week)
    roadmap      full personalised roadmap: phases, pace, certifications, finish estimate
    graph-health self-healing prerequisite graph - what learner trajectories say about the edges
    harvest      discover real open resources (Wikipedia / Wikibooks / MIT / arXiv / YouTube)
    test         run the test suite (pytest)
    lint         ruff check + ruff format --check + mypy --strict
    fmt          auto-format and auto-fix (ruff)
    api          run the API with autoreload at http://localhost:8000  (/docs for the UI)
    ui           run the React dev server at http://localhost:5173  (needs `api` in another shell)
    ui-test      typecheck (strict tsc) + run the React tests (vitest + Testing Library + MSW)
    serve        build the React UI and serve it + the API at http://localhost:8000
    benchmark    VELPO vs greedy / ACO / DQN   (--dataset synthetic|junyi|all  --runs N)
    ablation     N2 check - does learning velocity change the plan?
    seqbench     N1 check - does optimising the sequence (not just selection) pay off?
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


def cmd_harvest(args: argparse.Namespace) -> int:
    """Discover real open resources for a concept (or the whole curriculum)."""
    from curriculum import build_curriculum
    from harvest.catalogue import CONCEPT_QUERY, discover_catalogue, discover_for_concept

    kg = build_curriculum()
    if args.concept:
        name = CONCEPT_QUERY.get(args.concept, args.concept)
        print(f"\ndiscovering open resources for: {name}\n")
        for r, lvl in discover_for_concept(name, domain=args.domain, k=args.k):
            print(f"  [{r.source:9}|{r.kind:7}] level {lvl.difficulty}  (FK grade {lvl.fk_grade})")
            print(f"      {r.title}")
            print(f"      {r.url}\n")
        return 0
    dkg = discover_catalogue(kg, snapshot="algebra", domain=args.domain, refresh=args.refresh)
    from collections import Counter

    by_src = Counter(r.source or "fallback" for r in dkg.resources.values())
    print(f"\n{len(dkg.resources)} resources / {len(dkg.concepts)} concepts  |  {dict(by_src)}\n")
    for cid in dkg.concept_ids:
        rs = [dkg.resources[r] for r in dkg.resources_for(cid)]
        print(f"  {cid:14} " + "  ".join(f"{r.source or 'synthetic'}:d{r.difficulty}" for r in rs))
    return 0


def _role_demo(resolved: object, goal_text: str, minutes: float) -> int:
    """Role-gap plan for the terminal: readiness before -> after + the sequence."""
    from algorithms.roleplan import solve_role_plan
    from domain_data import ROLES, role_profile
    from model.learner import LearnerState

    r = resolved  # domains.Resolved
    kg = r.kg  # type: ignore[attr-defined]
    role = next(x for x in ROLES if x.name == r.domain)  # type: ignore[attr-defined]
    prof = {k: v for k, v in role_profile(role).items() if k in kg.concepts}
    st = LearnerState.cold_start(kg.concept_ids, time_budget_s=minutes * 60)
    rp = solve_role_plan(kg, role.name, prof, st, budget_minutes=minutes)
    print(f"\nrole: {role.name}   budget {minutes:.0f} min   ({rp.method})")
    print(f"hiring readiness:  {rp.readiness_before:.0%}  ->  {rp.readiness:.0%}\n")
    for i, s in enumerate(rp.sequence.steps, 1):
        m, ready = rp.steps_curve[i]
        tag = " (review)" if s.review else " (check)" if s.check else ""
        name = kg.concepts[s.concept].name + tag
        print(f"  {i:2}. {name:<46} {ready:>4.0%} ready  ({m:.0f} min in)")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from engine import Engine

    catalogue = getattr(args, "catalogue", "curriculum")
    kg = None
    goal_hint = ""
    goal_text = args.goal or ("" if args.dataset != "synthetic" else "SQL joins and aggregates")

    if catalogue == "discovered":
        from harvest import algebra_catalogue

        kg = algebra_catalogue()
        goals = kg.sink_concepts()
    elif goal_text and args.dataset == "synthetic" and (" " in goal_text or not args.goal):
        from domains import resolve  # free-text goal -> seed graph, role, or dynamic

        r = resolve(goal_text)
        if r.source == "role":
            return _role_demo(r, goal_text, args.minutes)
        kg, goals = r.kg, r.goals
        goal_hint = f"  [{r.source}: {r.domain}]"
    else:
        from benchmarks.datasets import load

        kg, goals = load(args.dataset)

    if args.goal and args.goal in kg.concepts:
        goal = args.goal
    elif args.goal and goal_hint:  # a free-text goal that was routed to a graph
        goal = goals[0]
    elif args.goal:
        choices = ", ".join(list(kg.concepts)[:10])
        print(f"unknown goal {args.goal!r}. try a phrase, or one of: {choices}")
        return 2
    else:
        goal = goals[0]
    speed = {"slow": 0.45, "normal": 1.0, "fast": 3.0}[args.speed]
    eng = Engine(kg)
    plans = eng.recommend(
        "demo", [goal], time_budget_s=args.minutes * 60, mode=args.mode, speed=speed
    )
    plan = plans[0]
    print(
        f"\ngoal={goal}{goal_hint}  budget={args.minutes} min  "
        f"solver={args.mode}  speed={args.speed}\n"
    )
    if not plan.feasible:
        print(f"no feasible plan: {plan.note}")
        return 0
    if plan.note:
        print(f"note: {plan.note}\n")

    reasons = plan.reasons or [""] * len(plan.steps)
    session_start = {a: k + 1 for k, (a, _) in enumerate(plan.sessions)}
    for i, (rid, reason) in enumerate(zip(plan.steps, reasons)):
        if i in session_start:
            print(f"\n  -- session {session_start[i]} --")
        tag = "R" if plan.is_review(i) else "C" if plan.is_check(i) else " "
        res = kg.resources[rid]
        label = f"{res.source}: {res.title}" if res.title else rid
        print(f" {tag}{i + 1:2}. {label}")
        print(f"       {reason}")
        if res.url:
            print(f"       {res.url}")

    o = plan.objective
    n_rev = sum(plan.reviews) if plan.reviews else 0
    n_chk = sum(plan.checks) if plan.checks else 0
    rev_txt = f" ({n_rev} spaced review{'s' if n_rev != 1 else ''})" if n_rev else ""
    rev_txt += f" ({n_chk} confidence check{'s' if n_chk != 1 else ''})" if n_chk else ""
    print(
        f"\n{len(plan.steps)} steps{rev_txt} - {plan.total_seconds / 60:.0f} min "
        f"over {len(plan.sessions) or 1} session(s) | "
        f"mastery gain {-o.neg_gain:.2f}  load {o.load:.2f}  diff-jumps {o.diff_jump:.2f}"
    )
    return 0


def cmd_assess(args: argparse.Namespace) -> int:
    """Run the adaptive capability diagnostic in the terminal, then plan from it."""
    from assessment_bank import build_item_bank
    from domains import resolve
    from engine import Engine

    r = resolve(args.goal or "learn sql")
    bank = build_item_bank(r.domain)
    if bank is None:
        print(f"no calibrated diagnostic for {r.domain!r} yet - try: sql, python, algebra")
        return 2
    kg = r.kg
    goal = r.goals[0]
    eng = Engine(kg, item_bank=bank)
    session = eng.start_assessment("me", [goal], time_budget_s=args.minutes * 60)
    print(f"\nAdaptive diagnostic - goal: {kg.concepts[goal].name}  ({r.domain})")
    print("Each question is chosen to be maximally informative at your current estimate.\n")

    while not session.done:
        q = session.next_question()
        if q is None:
            break
        print(f"[{q.skill}]  {q.stem}")
        if q.kind == "mcq":
            for i, ch in enumerate(q.choices):
                print(f"   {i}) {ch}")
            ans = input("   answer # > ").strip()
        else:
            ans = input("   your answer > ").strip()
        eng.answer_assessment("me", q.id, ans)
        e = session.estimate(q.skill)
        print(f"   -> {q.skill}: theta={e.theta:+.2f} se={e.se:.2f} mastery~{e.mastery:.0%}\n")

    print("estimated level per skill:")
    for e in session.estimates().values():
        bar = "#" * round(e.mastery * 20)
        print(f"  {e.skill:<14} {bar:<20} {e.mastery:.0%}  (se {e.se:.2f}, {e.n_items} items)")

    plan = eng.recommend("me", [goal], time_budget_s=args.minutes * 60, mode="sequence")[0]
    mins = plan.total_seconds / 60
    print(f"\nplan from your measured level - {len(plan.steps)} steps, {mins:.0f} min:")
    for i, (rid, reason) in enumerate(zip(plan.steps, plan.reasons or [""] * len(plan.steps))):
        print(f"  {i + 1:2}. {rid:<32} {reason}")
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    """Sequence the goal, then embed it on a real calendar for a deadline."""
    from datetime import date, datetime, timedelta

    from algorithms.scheduling import Availability
    from domains import resolve
    from engine import Engine

    goal_text = args.goal or "learn sql"
    r = resolve(goal_text)
    kg = r.kg
    if args.by:
        deadline = datetime.strptime(args.by, "%Y-%m-%d").date()
    else:
        deadline = date.today() + timedelta(days=args.days)
    avail = Availability.weekdays(args.hours_per_week * 60.0 / 5.0)
    eng = Engine(kg)
    cp = eng.calendar_plan("me", r.goals, deadline=deadline, availability=avail, start=date.today())
    print(f"\ngoal: {', '.join(kg.concepts[g].name for g in r.goals if g in kg.concepts)}")
    print(
        f"deadline {deadline.isoformat()}  |  {args.hours_per_week:.0f} h/week weekdays  "
        f"|  {cp.weeks:.0f} weeks\n"
    )
    if not cp.feasible:
        print(f"NOT ON TRACK: {cp.note}")
        if cp.hours_per_week_needed > cp.hours_per_week:
            print(
                f"  -> you offered {cp.hours_per_week:.1f} h/week; "
                f"about {cp.hours_per_week_needed:.1f} h/week is needed for this date."
            )
        return 0
    from algorithms.scheduling import CalendarStep

    by_week: dict[int, list[CalendarStep]] = {}
    for s in cp.steps:
        wk = (s.day - cp.start).days // 7 + 1
        by_week.setdefault(wk, []).append(s)
    for wk, steps in sorted(by_week.items()):
        print(f"  week {wk}")
        for s in steps:
            tag = {"teach": " ", "review": "R", "check": "C", "retention": "*"}[s.kind]
            nm = kg.concepts[s.concept].name
            print(f"   {tag} {s.day.isoformat()}  {nm}  ({s.minutes:.0f}m)")
    finish = cp.finish.isoformat() if cp.finish else "?"
    print(f"\nON TRACK: last study day {finish}, {cp.slack_days} day(s) to spare.")
    for g, m in sorted(cp.goal_mastery.items(), key=lambda kv: kv[1]):
        print(f"  {kg.concepts[g].name}: predicted {m:.0%} on the deadline")
    return 0


def cmd_roadmap(args: argparse.Namespace) -> int:
    from datetime import datetime

    from domains import resolve
    from model.learner import LearnerState
    from roadmap import build_roadmap

    r = resolve(args.goal or "become a data analyst")
    st = LearnerState.cold_start(r.kg.concept_ids, time_budget_s=3600)
    deadline = datetime.strptime(args.by, "%Y-%m-%d").date() if args.by else None
    rm = build_roadmap(r.kg, r, st, weekly_hours=args.hours_per_week, deadline=deadline)

    head = rm.role or rm.domain
    print(f"\nRoadmap: {head}   pace {rm.pace}   {args.hours_per_week:.0f} h/week")
    print(
        f"~{rm.total_hours:.0f} study hours over ~{rm.total_weeks:.0f} weeks"
        + (f"  ->  ~{rm.finish_estimate}" if rm.finish_estimate else "")
    )
    if rm.already_have:
        extra = " ..." if len(rm.already_have) > 6 else ""
        print(f"already have: {', '.join(rm.already_have[:6])}{extra}")
    for p in rm.phases:
        print(
            f"\n  PHASE {p.index} - {p.title}   ({p.new_skills} skills, ~{p.est_hours:.0f} h,"
            f" ~{p.est_weeks:.1f} wk, from week {p.start_week:.0f})"
        )
        print(f"     {p.focus}")
        print(f"     skills: {', '.join(p.concept_names)}")
        for cert in p.certifications:
            tag = "free" if cert.free else cert.price_note
            print(f"     >> sit here: {cert.name} ({cert.provider}) - {tag}")
    print("\nCertifications for this track:")
    for cert in rm.certifications:
        tag = "FREE" if cert.free else "paid"
        print(f"  [{tag}] {cert.name} - {cert.provider}")
        print(f"         {cert.blurb}")
        print(f"         {cert.url}   ({cert.price_note})")
    print()
    for n in rm.notes:
        print(f"note: {n}")
    return 0


def cmd_graph_health(args: argparse.Namespace) -> int:
    from algorithms.graph_health import simulate_recovery
    from domains import resolve

    r = resolve(args.goal or "learn sql")
    print(f"\nSelf-healing prerequisite graph - {r.domain} ({r.source})")
    print(
        f"controlled experiment: hide {args.perturb} real edges, inject {args.perturb} spurious "
        f"ones, simulate {args.learners} learners, then heal.\n"
    )
    rec = simulate_recovery(r.kg, learners=args.learners, perturb=args.perturb, seed=args.seed)
    rep = rec.report
    print(f"observations {rep.observations:,}   watched non-edges {rep.watched}\n")
    if rep.pruned:
        print("PRUNED (edge not backed by the data):")
        for c in rep.pruned:
            print(f"  - {c.summary}")
    if rep.added:
        print("ADDED (missing prerequisite discovered):")
        for c in rep.added:
            print(f"  + {c.summary}")
    if rep.suggested:
        print("SUGGESTED (borderline - needs review):")
        for c in rep.suggested:
            print(f"  ? {c.summary}")
    print(
        f"\nrecovery: {len(rec.hidden_recovered)}/{len(rec.hidden)} hidden edges found "
        f"({rec.recall:.0%}), {len(rec.injected_pruned)}/{len(rec.injected)} spurious edges "
        f"dropped ({rec.precision_drop:.0%})"
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
        "certifications.py",
        "engine.py",
        "explain.py",
        "roadmap.py",
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
        "certifications.py",
        "engine.py",
        "explain.py",
        "roadmap.py",
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


def cmd_seqbench(args: argparse.Namespace) -> int:
    return _run([*PY, "-m", "benchmarks.sequencing_bench", *args.rest])


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
        d.add_argument(
            "--catalogue",
            default="curriculum",
            choices=("curriculum", "discovered"),
            help="'discovered' plans against real harvested open resources",
        )
        d.add_argument("--goal", default=None)
        d.add_argument("--minutes", type=float, default=120)
        d.add_argument(
            "--mode",
            default="sequence",
            choices=("sequence", "optimal", "interactive", "pareto"),
        )
        d.add_argument("--speed", default="normal", choices=("slow", "normal", "fast"))
        d.set_defaults(fn=cmd_demo)

    h = sub.add_parser("harvest")
    h.add_argument("--concept", default=None, help="one concept id; omit for the whole curriculum")
    h.add_argument("--domain", default="math", choices=("math", "science", "cs", "web", "general"))
    h.add_argument("--k", type=int, default=8)
    h.add_argument("--refresh", action="store_true", help="re-harvest instead of the snapshot")
    h.set_defaults(fn=cmd_harvest)

    a = sub.add_parser("assess")
    a.add_argument("--goal", default=None)
    a.add_argument("--minutes", type=float, default=120)
    a.set_defaults(fn=cmd_assess)

    sc = sub.add_parser("schedule")
    sc.add_argument("--goal", default=None)
    sc.add_argument("--by", default=None, help="deadline date YYYY-MM-DD (overrides --days)")
    sc.add_argument("--days", type=int, default=28, help="days from today to the deadline")
    sc.add_argument("--hours-per-week", type=float, default=5.0, dest="hours_per_week")
    sc.set_defaults(fn=cmd_schedule)

    rd = sub.add_parser("roadmap")
    rd.add_argument("--goal", default=None)
    rd.add_argument("--hours-per-week", type=float, default=5.0, dest="hours_per_week")
    rd.add_argument("--by", default=None, help="optional target date YYYY-MM-DD")
    rd.set_defaults(fn=cmd_roadmap)

    gh = sub.add_parser("graph-health")
    gh.add_argument("--goal", default=None)
    gh.add_argument("--learners", type=int, default=6000)
    gh.add_argument("--perturb", type=int, default=2)
    gh.add_argument("--seed", type=int, default=0)
    gh.set_defaults(fn=cmd_graph_health)

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

    sb = sub.add_parser("seqbench")
    sb.add_argument("rest", nargs=argparse.REMAINDER)
    sb.set_defaults(fn=cmd_seqbench)

    ds = sub.add_parser("datasets")
    ds.add_argument("--full", action="store_true", help="download the complete Junyi graph")
    ds.set_defaults(fn=cmd_datasets)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
