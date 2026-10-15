"""Every practice task, across all domains, and one grader for all of them.

``grade_task(task, answer)`` runs the answer the way its kind needs - SQL in
the SQLite sandbox, Python in the Python sandbox, a formula on the Excel
sheet, or a computed / chosen value - and returns a :class:`Graded`: the
learner's result as a table, pass/fail checks, per-row status, and the
diagnoses (which concept the mistake points to).

Diagnosis has two layers everywhere:

1. **known mistakes** - a task's ``distractors`` are wrong solutions (queries,
   code, formulas or values); if the learner's output equals the output of one,
   that mistake is named exactly;
2. **structural fingerprints** - the general rules (row fan-out, dropped
   unmatched rows, NULL comparisons, missing GROUP BY, error types...).
"""

from __future__ import annotations

import ast
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from domain_data import SEEDS
from practice import excel as xl
from practice.content import de_sql_tasks, excel_tasks, python_tasks, value_tasks
from practice.fingerprint import (
    Check,
    Diagnosis,
    _inflated,
    _norm_rows,
    _numeric_pairs,
    checks,
    diagnose,
    expected,
    results_match,
    row_status,
    skeleton,
)
from practice.pyrun import run_python, run_reference
from practice.sandbox import ExecResult, run_sql
from practice.tasks import CONCEPT_HINTS, SHOP_DB, Task
from practice.tasks import TASKS as SQL_TASKS

ALL_TASKS: tuple[Task, ...] = (
    SQL_TASKS + de_sql_tasks.TASKS + python_tasks.TASKS + excel_tasks.TASKS + value_tasks.TASKS
)
BY_ID: dict[str, Task] = {t.id: t for t in ALL_TASKS}
CONCEPT_DOMAIN: dict[str, str] = {cid: s.name for s in SEEDS for cid, _ in s.concepts}


def tasks_for(concept_id: str) -> list[Task]:
    """Tasks for a concept, given as a bare id or a role-graph ``domain.id``."""
    bare = concept_id.split(".", 1)[1] if "." in concept_id else concept_id
    return [t for t in ALL_TASKS if t.concept == bare]


def hints_for(task: Task) -> list[str]:
    """Two levels: the idea, then the shape of a solution (never the answer)."""
    if task.kind == "sql":
        return [task.hint or CONCEPT_HINTS.get(task.concept, ""), skeleton(task.reference)]
    if task.kind == "python":
        return [
            task.hint,
            "Uses: " + ", ".join(_calls(task.reference)) if _calls(task.reference) else "",
        ]
    if task.kind == "excel":
        return [task.hint, task.hint2]
    return [task.hint or "Work it out from the table step by step.", task.hint2]


def _calls(code: str) -> list[str]:
    """Method / function names a reference uses, in order - a shape hint."""
    names: list[str] = []
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Call):
            f = node.func
            n = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if n and n not in names:
                names.append(f".{n}()" if isinstance(f, ast.Attribute) else f"{n}()")
    return names


@dataclass(frozen=True, slots=True)
class Graded:
    correct: bool
    result: ExecResult
    diagnoses: tuple[Diagnosis, ...] = ()
    checks: tuple[Check, ...] = ()
    row_status: list[str] = field(default_factory=list)
    missing_rows: int = 0
    expected_rows: int = 0

    @property
    def blamed(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for d in self.diagnoses:
            out[d.concept] = max(out.get(d.concept, 0.0), d.weight)
        return out


def _same(a: ExecResult, b: ExecResult) -> bool:
    return (
        a.ok
        and b.ok
        and len(a.columns) == len(b.columns)
        and Counter(_norm_rows(a.rows)) == Counter(_norm_rows(b.rows))
    )


def _known(task: Task, got: ExecResult, run: object) -> list[Diagnosis]:
    """Distractor solutions whose output equals the learner's."""
    out = []
    for i, d in enumerate(task.distractors):
        wrong = run(i, d)  # type: ignore[operator]
        if _same(got, wrong):
            out.append(Diagnosis(d.code, d.concept, 1.0, d.message))
    return out


def _dedupe(ds: list[Diagnosis]) -> tuple[Diagnosis, ...]:
    seen: dict[str, Diagnosis] = {}
    for d in sorted(ds, key=lambda d: -d.weight):
        seen.setdefault(d.code, d)
    return tuple(seen.values())


def grade_task(task: Task, answer: str) -> Graded:
    if task.kind == "python":
        return _grade_python(task, answer)
    if task.kind == "excel":
        return _grade_excel(task, answer)
    if task.kind == "value":
        return _grade_value(task, answer)
    return _grade_sql(task, answer)


# ------------------------------------------------------------------------ SQL
_DISTRACTOR_CACHE: dict[str, ExecResult] = {}


def _grade_sql(task: Task, query: str) -> Graded:
    got = run_sql(SHOP_DB, query)
    want = expected(task)
    v = diagnose(task, query, got, want)

    def run(i: int, d: object) -> ExecResult:
        key = f"{task.id}#{i}"
        if key not in _DISTRACTOR_CACHE:
            _DISTRACTOR_CACHE[key] = run_sql(SHOP_DB, d.value)  # type: ignore[attr-defined]
        return _DISTRACTOR_CACHE[key]

    diags = list(v.diagnoses)
    if not v.correct:
        known = _known(task, got, run)
        if known:  # an exact known mistake beats the generic "result differs"
            diags = [d for d in diags if d.code != "result_differs"] + known
    status, missing = row_status(got, want)
    return Graded(
        v.correct,
        got,
        _dedupe(diags) if not v.correct else (),
        checks(task, got, want),
        status,
        missing,
        len(want.rows),
    )


# --------------------------------------------------------------------- Python
def _grade_python(task: Task, code: str) -> Graded:
    env = dict(task.env)
    got = run_python(code, env).exec
    want = run_reference(task.id, task.reference, env)
    correct = results_match(got, want, ordered=task.ordered)
    diags: list[Diagnosis] = []
    if not correct:
        diags = _known(task, got, lambda i, d: run_reference(f"{task.id}#d{i}", d.value, env))
        diags += _py_rules(task, code, got, want)
        if not diags:
            diags = [
                Diagnosis(
                    "result_differs", task.concept, 1.0, "The result differs from the expected one."
                )
            ]
    status, missing = row_status(got, want)
    return Graded(
        correct, got, _dedupe(diags), checks(task, got, want), status, missing, len(want.rows)
    )


def _py_rules(task: Task, code: str, got: ExecResult, want: ExecResult) -> list[Diagnosis]:
    out: list[Diagnosis] = []
    pandas = task.domain == "python_data"

    def add(code_: str, concept: str, w: float, msg: str) -> None:
        out.append(Diagnosis(code_, concept, w, msg))

    if re.search(r"(==|!=)\s*(None|np\.nan|numpy\.nan|float\(['\"]nan['\"]\))", code):
        add(
            "nan_equality",
            "missing_data" if pandas else "conditionals",
            1.0,
            "Missing values never compare equal - use .isna() / `is None`.",
        )
    if not got.ok:
        e = got.error
        if got.error_kind == "forbidden":
            add("forbidden", task.concept, 0.2, e)
        elif "truth value of a Series is ambiguous" in e:
            add(
                "series_and_or",
                "filtering",
                1.0,
                "`and` / `or` don't work on whole columns - use & and | with each "
                "condition in brackets.",
            )
        elif e.startswith("KeyError"):
            add(
                "unknown_key",
                "selecting" if pandas else "dicts",
                0.6,
                f"{e} - check the column or key name.",
            )
        elif e.startswith(("NameError", "AttributeError")):
            add("unknown_name", "variables", 0.6, f"{e}.")
        elif e.startswith("SyntaxError"):
            add("syntax", task.concept, 0.5, e)
        elif "result" in e and "set a variable" in e:
            add("no_result", "variables", 0.4, "Assign your answer to a variable called result.")
        elif got.error_kind == "timeout":
            add("timeout", "loops", 0.5, "The code ran too long - look for a loop that never ends.")
        else:
            add("error", task.concept, 0.5, e)
        return out
    g, w = _norm_rows(got.rows), _norm_rows(want.rows)
    if len(got.columns) != len(want.columns):
        add(
            "wrong_columns",
            "selecting" if pandas else task.concept,
            0.6,
            f"Returns {len(got.columns)} column(s); the question asks for {len(want.columns)}.",
        )
        return out
    gc, wc = Counter(g), Counter(w)
    if gc == wc:
        add(
            "wrong_order",
            "sort_rank" if pandas else task.concept,
            1.0,
            "Right values, wrong order.",
        )
        return out
    if pandas and ".merge(" in code and _inflated(_numeric_pairs(g, w)):
        add(
            "merge_fanout",
            "merge_join",
            1.0,
            "Totals are whole multiples of the truth: a one-to-many merge repeated "
            "rows before aggregating.",
        )
    if len(g) == 1 and len(w) > 1 and pandas and "groupby" not in code:
        add(
            "missing_groupby",
            "groupby_agg",
            0.9,
            "One row came back - group by the key before aggregating.",
        )
    return out


# ---------------------------------------------------------------------- Excel
_SHEET = excel_tasks.SHEET


def _xl_eval(formula: str) -> tuple[xl.Value, str]:
    try:
        return xl.evaluate(formula, _SHEET), ""
    except xl.ExcelError as e:
        return None, f"{e.code} {e}".strip()


def _xl_same(a: xl.Value, b: xl.Value) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return xl.display(a) == xl.display(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
    return xl.display(a).strip() == xl.display(b).strip()


def _grade_excel(task: Task, formula: str) -> Graded:
    f = formula.strip()
    if f and not f.startswith("="):
        f = "=" + f  # a forgotten '=' is diagnosed below, but still evaluated
    want, _ = _xl_eval(task.reference)
    got, err = _xl_eval(f)
    rows = [[err or xl.display(got)]]
    cols = [task.cell or "value"]
    down_ok = True
    if task.fill_down and not err:
        cell2 = f"{task.cell[0]}{int(task.cell[1:]) + 1}"
        got2, err2 = _xl_eval(xl.shift(f, 1))
        want2, _ = _xl_eval(xl.shift(task.reference, 1))
        down_ok = not err2 and _xl_same(got2, want2)
        cols.append(f"{cell2} (copied down)")
        rows[0].append(err2 or xl.display(got2))
    correct = not err and _xl_same(got, want) and down_ok
    diags: list[Diagnosis] = []
    upper = f.upper()
    if not formula.strip().startswith("="):
        diags.append(
            Diagnosis(
                "no_equals",
                "formulas",
                0.8,
                "A formula starts with = - without it Excel treats the entry as text.",
            )
        )
    if not correct:
        if re.search(r"VLOOKUP\([^()]*,[^(),]*,[^(),]*\)", upper):
            diags.append(
                Diagnosis(
                    "vlookup_approx",
                    "lookups",
                    1.0,
                    "VLOOKUP without FALSE does an approximate match on unsorted data - "
                    "add FALSE as the 4th argument.",
                )
            )
        if err:
            code = err.split()[0]
            concept = {"#NAME?": "formulas", "#N/A": "lookups", "#DIV/0!": "agg_functions"}.get(
                code, task.concept
            )
            diags.append(Diagnosis("excel_error", concept, 0.6, f"The formula returns {err}."))
        elif not _xl_same(got, want):
            for d in task.distractors:
                v, e = _xl_eval(d.value)
                if not e and _xl_same(got, v):
                    diags.append(Diagnosis(d.code, d.concept, 1.0, d.message))
        elif not down_ok:
            diags.append(
                Diagnosis(
                    "missing_anchor",
                    "abs_refs",
                    1.0,
                    "Right in the first cell, wrong when copied down: anchor the total's "
                    "range with $ (e.g. $E$2:$E$11).",
                )
            )
        if not diags:
            diags.append(
                Diagnosis(
                    "result_differs", task.concept, 1.0, "The value differs from the expected one."
                )
            )
    result = ExecResult(tuple(cols), (tuple(rows[0]),), err, "other" if err else "")
    cks = [
        Check("runs", "Formula calculates", not err, err or "No Excel error."),
        Check(
            "value",
            f"Right value in {task.cell}",
            not err and _xl_same(got, want),
            "Compared with the expected result.",
        ),
    ]
    if task.fill_down:
        cks.append(
            Check(
                "fill",
                "Still right when copied down",
                down_ok and not err,
                "The formula is re-evaluated one row lower, as fill-down would.",
            )
        )
    return Graded(
        correct,
        result,
        _dedupe(diags),
        tuple(cks),
        ["ok" if correct else "extra"],
        0 if correct else 1,
        1,
    )


# ---------------------------------------------------------------------- value
def _parse_num(s: str) -> float | None:
    t = s.strip().replace(",", "").rstrip("%").strip()
    try:
        return float(t)
    except ValueError:
        return None


def _value_eq(task: Task, answer: str, target: str) -> bool:
    if task.options:
        return answer.strip().lower() == target.strip().lower()
    a, b = _parse_num(answer), _parse_num(target)
    if a is None or b is None:
        return answer.strip().lower() == target.strip().lower()
    return abs(a - b) <= max(task.tolerance, 1e-9)


def _grade_value(task: Task, answer: str) -> Graded:
    correct = _value_eq(task, answer, task.reference)
    diags: list[Diagnosis] = []
    parsed = bool(task.options) or _parse_num(answer) is not None
    if not correct:
        for d in task.distractors:
            if _value_eq(task, answer, d.value):
                diags.append(Diagnosis(d.code, d.concept, 1.0, d.message))
        if not parsed:
            diags.append(
                Diagnosis(
                    "not_a_number",
                    task.concept,
                    0.3,
                    "Type a number (decimals with a point, no units).",
                )
            )
        if not diags:
            diags.append(
                Diagnosis("result_differs", task.concept, 1.0, "That's not the expected answer.")
            )
    result = ExecResult(("Your answer",), ((answer.strip(),),))
    cks = (
        Check(
            "parsed",
            "Answer recognised",
            parsed,
            "A number was read."
            if parsed and not task.options
            else "An option was chosen."
            if task.options
            else "Couldn't read a number.",
        ),
        Check(
            "value",
            "Correct answer",
            correct,
            f"Tolerance ±{task.tolerance:g}." if task.tolerance and not task.options else "Exact.",
        ),
    )
    return Graded(
        correct, result, _dedupe(diags), cks, ["ok" if correct else "extra"], 0 if correct else 1, 1
    )
