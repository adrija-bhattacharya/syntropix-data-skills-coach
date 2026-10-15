"""Output-diff fingerprinting: *why* a learner's query is wrong, as concepts.

A submission is graded by comparing its **result** with the reference query's
result, never the SQL text - any correct query passes.  When it fails, the way
the two results differ (plus a few lexical cues from the query) is matched
against a catalogue of error signatures.  Each signature names the concept
whose misunderstanding typically produces it:

==========================  ====================================================
signature                   typical cause -> blamed concept
==========================  ====================================================
``null_equality``           ``= NULL`` instead of ``IS NULL``      -> null_logic
``aggregate_in_where``      ``WHERE COUNT(*) > 1``                 -> having
``having_without_group``    HAVING with no GROUP BY                -> group_by
``join_fanout``             one-to-many join inflates SUM/COUNT    -> inner_join
``join_duplicates``         join repeats rows                      -> inner_join
``duplicates``              repeated rows, no join                 -> distinct
``dropped_unmatched``       INNER JOIN where LEFT JOIN is needed   -> outer_join
``count_star_outer``        COUNT(*) counts the NULL-padded row    -> null_logic
``collapsed_window``        GROUP BY where a window keeps rows     -> window_functions
``missing_partition``       OVER () without PARTITION BY           -> window_functions
``missing_group_by``        aggregate without GROUP BY             -> group_by
``wrong_grouping``          grouped at the wrong level             -> group_by
``unfiltered``              extra rows, no filter                  -> where
``unlimited``               extra rows, no LIMIT                   -> order_limit
``wrong_order``             right rows, wrong order                -> order_limit
``wrong_columns``           wrong number of columns                -> select_from
``unknown_name``            no such column / table                 -> select_from
``ambiguous_column``        unqualified column after a join        -> inner_join
``case_boundary``           CASE buckets differ                    -> case_when
==========================  ====================================================

Signatures are deterministic rules over structural features, so every
diagnosis can be shown to the learner and audited.  A failure that matches
nothing is blamed on the task's own concept (``result_differs``).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from practice.sandbox import ExecResult, Row, run_sql
from practice.tasks import SHOP_DB, Task

_Add = Callable[[str, str, float, str], None]  # (code, concept, weight, message)


@dataclass(frozen=True, slots=True)
class Diagnosis:
    code: str
    concept: str
    weight: float  # how strongly this signature implicates ``concept`` (0, 1]
    message: str


@dataclass(frozen=True, slots=True)
class Verdict:
    correct: bool
    diagnoses: tuple[Diagnosis, ...] = ()

    @property
    def blamed(self) -> dict[str, float]:
        """Concept -> strongest weight among the diagnoses that name it."""
        out: dict[str, float] = {}
        for d in self.diagnoses:
            out[d.concept] = max(out.get(d.concept, 0.0), d.weight)
        return out


# --------------------------------------------------------------------- lexing
_STRING = re.compile(r"'(?:[^']|'')*'")
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def _lex(sql: str) -> str:
    s = _BLOCK_COMMENT.sub(" ", _LINE_COMMENT.sub(" ", sql))
    s = _STRING.sub("''", s)
    return " " + " ".join(s.upper().split()) + " "


def _has(q: str, pattern: str) -> bool:
    return re.search(pattern, q) is not None


_AGG = r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\("


def _where_clause(q: str) -> str:
    m = re.search(r"\bWHERE\b(.*?)(\bGROUP BY\b|\bORDER BY\b|\bLIMIT\b|\bHAVING\b|$)", q)
    return m.group(1) if m else ""


def _joins(q: str) -> int:
    return len(re.findall(r"\bJOIN\b", q)) + len(re.findall(r"\bFROM\s+\w+(\s+\w+)?\s*,", q))


# ---------------------------------------------------------------- comparison
def _norm_value(v: object) -> object:
    if isinstance(v, bool):
        return v
    if isinstance(v, int | float):
        return round(float(v), 6)
    return v


def _norm_rows(rows: tuple[Row, ...]) -> list[Row]:
    return [tuple(_norm_value(v) for v in r) for r in rows]


def _is_num(v: object) -> bool:
    return isinstance(v, float)


def _keyed(rows: list[Row]) -> dict[Row, list[Row]]:
    """Group rows by their non-numeric cells (the 'label' part of the row)."""
    out: dict[Row, list[Row]] = {}
    for r in rows:
        out.setdefault(tuple(v for v in r if not _is_num(v)), []).append(r)
    return out


def _numeric_pairs(got: list[Row], want: list[Row]) -> list[tuple[float, float]]:
    """(got, want) numeric cells for rows whose label matches 1:1 in both."""
    gk, wk = _keyed(got), _keyed(want)
    pairs: list[tuple[float, float]] = []
    for key, wrows in wk.items():
        grows = gk.get(key)
        if grows is None or len(grows) != 1 or len(wrows) != 1:
            continue
        g, w = grows[0], wrows[0]
        if len(g) != len(w):
            continue
        for gv, wv in zip(g, w):
            if _is_num(gv) and _is_num(wv):
                pairs.append((float(gv), float(wv)))
    return pairs


def _inflated(pairs: list[tuple[float, float]]) -> bool:
    """Some cell is an integer multiple >= 2 of the truth and none shrank."""
    hit = False
    for g, w in pairs:
        if w == 0 or g < w - 1e-9:
            if not (w == 0 and g == 0):
                return False
            continue
        ratio = g / w
        if ratio >= 2 - 1e-9 and abs(ratio - round(ratio)) < 1e-6:
            hit = True
    return hit


def results_match(got: ExecResult, want: ExecResult, *, ordered: bool) -> bool:
    if not got.ok or len(got.columns) != len(want.columns):
        return False
    g, w = _norm_rows(got.rows), _norm_rows(want.rows)
    return g == w if ordered else Counter(g) == Counter(w)


# ------------------------------------------------------------------ diagnose
def diagnose(task: Task, query: str, got: ExecResult, want: ExecResult) -> Verdict:
    """Grade ``got`` against ``want`` and, if it fails, fingerprint the failure."""
    if results_match(got, want, ordered=task.ordered):
        return Verdict(correct=True)

    q, ref = _lex(query), _lex(task.reference)
    found: list[Diagnosis] = []

    def add(code: str, concept: str, weight: float, message: str) -> None:
        found.append(Diagnosis(code, concept, weight, message))

    # lexical cues that are wrong whatever the result
    if _has(q, r"(=|<>|!=)\s*NULL\b"):
        add(
            "null_equality",
            "null_logic",
            1.0,
            "Comparing with `= NULL` is never true - NULL means 'unknown'. Use `IS NULL`.",
        )

    if not got.ok:
        _diagnose_error(task, q, got, add)
    else:
        _diagnose_rows(task, q, ref, got, want, add)

    if not found:
        add("result_differs", task.concept, 1.0, "The result differs from the expected one.")
    # strongest first; one diagnosis per code
    uniq: dict[str, Diagnosis] = {}
    for d in sorted(found, key=lambda d: -d.weight):
        uniq.setdefault(d.code, d)
    return Verdict(correct=False, diagnoses=tuple(uniq.values()))


def _diagnose_error(task: Task, q: str, got: ExecResult, add: _Add) -> None:
    kind = got.error_kind
    if kind == "misuse_aggregate":
        if _has(_where_clause(q), _AGG):
            add(
                "aggregate_in_where",
                "having",
                1.0,
                "WHERE filters rows before grouping, so it can't test COUNT/SUM. "
                "Filter groups with HAVING.",
            )
        else:
            add("aggregate_misuse", "aggregates", 0.8, "An aggregate is used where it can't be.")
    elif kind == "having_without_group":
        add(
            "having_without_group",
            "group_by",
            1.0,
            "HAVING filters groups, but the query never forms any - add GROUP BY first.",
        )
    elif kind == "misuse_window":
        add(
            "window_misuse", "window_functions", 0.9, "A window function is used where it can't be."
        )
    elif kind in ("no_such_column", "no_such_table"):
        add("unknown_name", "select_from", 0.6, f"The database says: {got.error}.")
    elif kind == "ambiguous_column":
        add(
            "ambiguous_column",
            "inner_join",
            0.8,
            "After a join, a column that exists in both tables must be qualified (t.col).",
        )
    elif kind == "forbidden":
        add("forbidden", task.concept, 0.2, "Only read queries (SELECT / WITH) are allowed here.")
    elif kind == "multiple_statements":
        add("multiple_statements", task.concept, 0.2, "Submit a single query.")
    elif kind == "timeout":
        add(
            "timeout",
            task.concept,
            0.5,
            "The query ran too long - look for a missing join condition.",
        )
    else:
        add("syntax", task.concept, 0.5, f"The query didn't run: {got.error}.")


def _diagnose_rows(
    task: Task, q: str, ref: str, got: ExecResult, want: ExecResult, add: _Add
) -> None:
    g, w = _norm_rows(got.rows), _norm_rows(want.rows)
    ref_window = _has(ref, r"\bOVER\s*\(")
    q_window = _has(q, r"\bOVER\s*\(")
    if ref_window and not q_window and _has(q, r"\bGROUP BY\b") and len(g) < len(w):
        add(
            "collapsed_window",
            "window_functions",
            1.0,
            "GROUP BY collapses each group to one row; a window function (OVER) keeps every row.",
        )
        return
    if len(got.columns) != len(want.columns):
        add(
            "wrong_columns",
            "select_from",
            0.6,
            f"Returns {len(got.columns)} column(s); the question asks for {len(want.columns)}.",
        )
        return

    gc, wc = Counter(g), Counter(w)
    if gc == wc:  # right rows, wrong order (only reachable for ordered tasks)
        add("wrong_order", "order_limit", 1.0, "Right rows, wrong order - check ORDER BY / DESC.")
        return

    extra, missing = gc - wc, wc - gc
    joined = _joins(q) > 0
    pairs = _numeric_pairs(g, w)
    fired: list[str] = []

    def hit(code: str, concept: str, weight: float, message: str) -> None:
        fired.append(code)
        add(code, concept, weight, message)

    # a one-to-many join multiplied the rows that feed an aggregate
    if joined and _inflated(pairs):
        hit(
            "join_fanout",
            "inner_join",
            1.0,
            "Totals are whole multiples of the right answer: a one-to-many join repeated "
            "each row before it was summed. Join only the tables you need, or aggregate first.",
        )

    # duplicated rows: the right rows, too many times
    if extra and not missing and set(gc) == set(wc):
        if joined:
            hit("join_duplicates", "inner_join", 0.9, "A join repeats some rows.")
        else:
            hit("duplicates", "distinct", 0.9, "Some rows appear more than once - DISTINCT?")

    ref_left = _has(ref, r"\bLEFT( OUTER)? JOIN\b")
    q_left = _has(q, r"\b(LEFT|RIGHT|FULL)( OUTER)? JOIN\b")
    if ref_left and not q_left and missing and len(g) < len(w):
        hit(
            "dropped_unmatched",
            "outer_join",
            1.0,
            "Rows with no match on the other side disappeared - an INNER JOIN keeps only "
            "matches; LEFT JOIN keeps every row of the left table.",
        )
    if (
        ref_left
        and q_left
        and _has(q, r"COUNT\s*\(\s*\*\s*\)")
        and any(wv == 0 and gv == 1 for gv, wv in pairs)
    ):
        hit(
            "count_star_outer",
            "null_logic",
            0.9,
            "COUNT(*) counts the NULL-padded row an outer join adds for 'no match'; "
            "COUNT(column) skips NULLs.",
        )

    if (
        ref_window
        and q_window
        and _has(ref, r"\bPARTITION BY\b")
        and not _has(q, r"\bPARTITION BY\b")
    ):
        hit(
            "missing_partition",
            "window_functions",
            1.0,
            "OVER () spans the whole table; PARTITION BY restarts it per group.",
        )

    ref_group = _has(ref, r"\bGROUP BY\b")
    q_group = _has(q, r"\bGROUP BY\b")
    if ref_group and not q_group and _has(q, _AGG) and not q_window:
        hit(
            "missing_group_by",
            "group_by",
            1.0,
            "An aggregate without GROUP BY folds the whole table into one row.",
        )
    elif ref_group and q_group and len(g) != len(w) and not fired:
        hit(
            "wrong_grouping", "group_by", 0.7, "The groups are at the wrong level - check GROUP BY."
        )

    superset = not missing and bool(extra)
    if superset and not _has(q, r"\bWHERE\b") and _has(ref, r"\bWHERE\b|\bHAVING\b"):
        hit("unfiltered", "where", 0.9, "Extra rows: the condition that filters them is missing.")
    if superset and _has(ref, r"\bLIMIT\b") and not _has(q, r"\bLIMIT\b"):
        hit("unlimited", "order_limit", 0.9, "Too many rows - the question asks for the top few.")
    if (
        _has(ref, r"\bORDER BY\b.*\bDESC\b")
        and _has(q, r"\bORDER BY\b")
        and not _has(q, r"\bDESC\b")
    ):
        hit(
            "wrong_direction",
            "order_limit",
            1.0,
            "ORDER BY sorts ascending by default - add DESC for 'highest first'.",
        )

    if _has(ref, r"\bCASE\b") and len(g) == len(w) and _has(q, r"\bCASE\b"):
        hit(
            "case_boundary",
            "case_when",
            0.8,
            "Some rows land in the wrong bucket - check the CASE boundaries (< vs <=) and order.",
        )


# --------------------------------------------------------------------- grade
_EXPECTED: dict[str, ExecResult] = {}


def expected(task: Task) -> ExecResult:
    """The reference query's result (computed once per task)."""
    if task.id not in _EXPECTED:
        _EXPECTED[task.id] = run_sql(SHOP_DB, task.reference)
    return _EXPECTED[task.id]


def grade(task: Task, query: str) -> tuple[ExecResult, Verdict]:
    """Run ``query`` in the sandbox and fingerprint it against the reference."""
    got = run_sql(SHOP_DB, query)
    return got, diagnose(task, query, got, expected(task))


# -------------------------------------------------------------------- checks
@dataclass(frozen=True, slots=True)
class Check:
    id: str
    label: str
    passed: bool
    detail: str


def checks(task: Task, got: ExecResult, want: ExecResult) -> tuple[Check, ...]:
    """The structural checks a result must pass, each pass / fail - the same
    comparison :func:`results_match` makes, broken into parts a learner can read."""
    if not got.ok:
        return (Check("runs", "Runs without errors", False, got.error),)
    g, w = _norm_rows(got.rows), _norm_rows(want.rows)
    cols = len(got.columns) == len(want.columns)
    out = [
        Check("runs", "Runs without errors", True, f"Ran in {got.ms:.1f} ms."),
        Check(
            "columns",
            "Right number of columns",
            cols,
            f"{len(got.columns)} column(s); {len(want.columns)} expected.",
        ),
        Check(
            "rows",
            "Right number of rows",
            len(g) == len(w),
            f"{len(g)} row(s); {len(w)} expected.",
        ),
    ]
    same = cols and Counter(g) == Counter(w)
    missing = sum((Counter(w) - Counter(g)).values()) if cols else len(w)
    out.append(
        Check(
            "values",
            "Same rows and values",
            same,
            "Every expected row is there." if same else f"{missing} expected row(s) not matched.",
        )
    )
    if task.ordered:
        out.append(
            Check(
                "order",
                "Rows in the right order",
                same and g == w,
                "The question asks for an order.",
            )
        )
    return tuple(out)


def row_status(got: ExecResult, want: ExecResult) -> tuple[list[str], int]:
    """Per returned row: "ok" if it matches an expected row, else "extra"; plus
    how many expected rows were never matched."""
    if not got.ok or len(got.columns) != len(want.columns):
        return ["extra"] * len(got.rows), len(want.rows)
    left = Counter(_norm_rows(want.rows))
    status = []
    for r in _norm_rows(got.rows):
        if left[r] > 0:
            left[r] -= 1
            status.append("ok")
        else:
            status.append("extra")
    return status, sum(left.values())


_KEYWORDS = {
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP",
    "BY",
    "HAVING",
    "ORDER",
    "LIMIT",
    "JOIN",
    "LEFT",
    "RIGHT",
    "INNER",
    "OUTER",
    "ON",
    "AS",
    "AND",
    "OR",
    "NOT",
    "IS",
    "NULL",
    "IN",
    "DISTINCT",
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "WITH",
    "OVER",
    "PARTITION",
    "UNION",
    "INTERSECT",
    "EXCEPT",
    "DESC",
    "ASC",
    "UPPER",
    "LOWER",
    "STRFTIME",
}


def skeleton(sql: str) -> str:
    """The reference query's shape with every name blanked: a hint that shows
    the clauses to use without giving the answer away."""
    out: list[str] = []
    for tok in re.findall(r"'[^']*'|\w+|[^\w\s]", sql):
        if tok.upper() in _KEYWORDS:
            out.append(tok.upper())
        elif tok in "(),*=<>":
            out.append(tok)
        elif not out or out[-1] != "…":
            out.append("…")
    text = " ".join(out).replace(" )", ")").replace(" ,", ",")
    return re.sub(r"(\w|…) \(", r"\1(", text).replace("( ", "(")
