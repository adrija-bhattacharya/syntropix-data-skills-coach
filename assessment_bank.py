"""Difficulty-calibrated item bank for the algebra curriculum's adaptive test.

Three items per concept - two multiple-choice, one free-response **task** (the
"timed hands-on" item: higher discrimination, graded server-side).  Each item's
difficulty ``b`` is anchored to the concept's depth in the prerequisite graph
(deeper concept -> harder item) and then spread by +/- ~1 logit so a single
concept's items span an easy / medium / hard band - which is what lets the CAT
actually adapt.

Hand-authored and clearly synthetic, exactly like ``curriculum.py``.
"""

from __future__ import annotations

import random

from curriculum import build_curriculum
from model.assessment import Item, ItemBank

# concept -> (easy mcq, hard mcq, task) as
#   (stem, choices, answer_index)  and  (stem, answer_text, tolerance)
_MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "integers": [
        ("Which is smallest?", ("-5", "-1", "0", "3"), 0),
        ("Evaluate  -7 + 12 - 4", ("1", "-1", "9", "-9"), 0),
    ],
    "fractions": [
        ("Which is largest?", ("1/2", "2/5", "3/8", "4/9"), 0),
        ("Compute  2/3 + 1/6", ("5/6", "3/9", "1/2", "3/6"), 0),
    ],
    "decimals": [
        ("Write 3/4 as a percentage.", ("75%", "34%", "0.75%", "43%"), 0),
        ("Increase 80 by 15%.", ("92", "95", "88", "120"), 0),
    ],
    "exponents": [
        ("Evaluate  2^5", ("32", "10", "25", "16"), 0),
        ("Simplify  x^3 * x^4", ("x^7", "x^12", "x", "2x^7"), 0),
    ],
    "roots": [
        ("Evaluate  sqrt(144)", ("12", "14", "72", "24"), 0),
        ("Simplify  sqrt(50)", ("5*sqrt(2)", "25*sqrt(2)", "sqrt(25)", "10"), 0),
    ],
    "order_ops": [
        ("Evaluate  6 + 2 * 3", ("12", "24", "10", "18"), 0),
        ("Evaluate  (8 - 2)^2 / 4 + 1", ("10", "9", "8", "13"), 0),
    ],
    "expressions": [
        ("Simplify  3a + 2a - a", ("4a", "5a", "6a", "3a"), 0),
        ("Expand  2(x + 5) - x", ("x + 10", "2x + 10", "x + 5", "3x + 10"), 0),
    ],
    "linear_eq": [
        ("Solve  x + 4 = 9", ("5", "13", "-5", "4"), 0),
        ("Solve  5x - 3 = 2x + 9", ("4", "2", "6", "3"), 0),
    ],
    "inequalities": [
        ("Solve  x + 2 > 5", ("x > 3", "x < 3", "x > 7", "x < 7"), 0),
        ("Solve  -2x <= 6", ("x >= -3", "x <= -3", "x >= 3", "x <= 3"), 0),
    ],
    "systems": [
        ("If  x + y = 10  and  x - y = 4,  find x.", ("7", "6", "5", "3"), 0),
        ("Solve  y = 2x,  x + y = 9.  Find y.", ("6", "3", "9", "4.5"), 0),
    ],
    "quadratics": [
        ("Solve  x^2 = 49", ("x = +/-7", "x = 7", "x = 24.5", "x = +/-24.5"), 0),
        ("Factor  x^2 - 5x + 6", ("(x-2)(x-3)", "(x+2)(x+3)", "(x-1)(x-6)", "(x-5)(x-6)"), 0),
    ],
    "functions": [
        ("If  f(x) = 3x - 1,  find f(4).", ("11", "12", "10", "7"), 0),
        ("For  f(x) = x^2 + 1,  find f(-2).", ("5", "-3", "3", "-5"), 0),
    ],
    "graphing": [
        ("What is the slope of  y = 4x - 2 ?", ("4", "-2", "2", "1/4"), 0),
        (
            "Where does  y = -x + 3  cross the y-axis?",
            ("(0, 3)", "(3, 0)", "(0, -1)", "(-1, 0)"),
            0,
        ),
    ],
    "word_problems": [
        (
            "A taxi costs $3 plus $2 per km. Which models the cost of d km?",
            ("3 + 2d", "2 + 3d", "5d", "6d"),
            0,
        ),
        (
            "Two numbers sum to 20; one is 4 more than the other. The larger is:",
            ("12", "10", "8", "16"),
            0,
        ),
    ],
}

_TASKS: dict[str, tuple[str, str, float]] = {
    "integers": ("Compute  -3 - (-8) + 2", "7", 0.0),
    "fractions": ("Compute  3/4 - 1/6  (give a fraction a/b)", "7/12", 0.0),
    "decimals": ("A $50 item is 20% off. Final price in dollars?", "40", 0.0),
    "exponents": ("Evaluate  3^4", "81", 0.0),
    "roots": ("Evaluate  sqrt(196)", "14", 0.0),
    "order_ops": ("Evaluate  2 + 3 * (4^2 - 6)", "32", 0.0),
    "expressions": ("Expand and simplify  4(2x - 3) - 5x  (form: ax + b)", "3x-12", 0.0),
    "linear_eq": ("Solve for x:  3x + 7 = 22", "5", 0.0),
    "inequalities": ("Solve  4x - 1 < 11 . Give the bound value for x.", "3", 0.0),
    "systems": ("Solve  x + y = 12,  2x - y = 3 . Give x.", "5", 0.0),
    "quadratics": ("Solve  x^2 - 9 = 0 . Give the positive root.", "3", 0.0),
    "functions": ("f(x) = 2x^2 - x . Compute f(3).", "15", 0.0),
    "graphing": ("Line through (0,1) and (2,7): give the slope.", "3", 0.0),
    "word_problems": (
        "Pens cost $2, notebooks $5. 3 pens + n notebooks cost $31. Find n.",
        "5",
        0.0,
    ),
}


# --------------------------------------------------------------------------- #
# SQL - the assessable core (concept ids match domain_data.SQL)
# --------------------------------------------------------------------------- #
_SQL_MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "select_from": [
        (
            "Which returns every column of `orders`?",
            ("SELECT * FROM orders", "GET orders", "SELECT orders", "FROM orders *"),
            0,
        ),
        (
            "Pick just `name` and `city`:",
            (
                "SELECT name, city FROM customers",
                "SELECT (name, city)",
                "GET name city",
                "SELECT name+city",
            ),
            0,
        ),
    ],
    "where": [
        (
            "Rows where price is over 100:",
            (
                "... WHERE price > 100",
                "... IF price > 100",
                "... HAVING price > 100",
                "... WHERE price => 100",
            ),
            0,
        ),
        (
            "Match names starting with 'A':",
            (
                "WHERE name LIKE 'A%'",
                "WHERE name = 'A*'",
                "WHERE name STARTS 'A'",
                "WHERE name IN 'A%'",
            ),
            0,
        ),
    ],
    "order_limit": [
        (
            "Top 5 most expensive products:",
            (
                "ORDER BY price DESC LIMIT 5",
                "LIMIT 5 ORDER BY price",
                "TOP 5 ORDER price",
                "ORDER price MAX 5",
            ),
            0,
        ),
    ],
    "aggregates": [
        (
            "Count the rows in `sales`:",
            (
                "SELECT COUNT(*) FROM sales",
                "SELECT ROWS(sales)",
                "SELECT SUM(*) FROM sales",
                "COUNT sales",
            ),
            0,
        ),
        (
            "Average order value:",
            (
                "SELECT AVG(total) FROM orders",
                "SELECT MEAN(total)",
                "SELECT total/COUNT(*)",
                "AVG orders total",
            ),
            0,
        ),
    ],
    "group_by": [
        (
            "Revenue per region:",
            (
                "SELECT region, SUM(rev) FROM t GROUP BY region",
                "SELECT SUM(rev) FROM t",
                "GROUP region SUM rev",
                "SELECT region SUM(rev)",
            ),
            0,
        ),
    ],
    "having": [
        (
            "Regions with more than 10 orders:",
            (
                "... GROUP BY region HAVING COUNT(*) > 10",
                "... WHERE COUNT(*) > 10",
                "... GROUP BY region WHERE COUNT > 10",
                "... HAVING region > 10",
            ),
            0,
        ),
    ],
    "inner_join": [
        (
            "Combine `orders` with `customers` on `customer_id`:",
            (
                "orders o JOIN customers c ON o.customer_id = c.id",
                "orders JOIN customers",
                "orders + customers",
                "JOIN orders customers customer_id",
            ),
            0,
        ),
    ],
    "outer_join": [
        (
            "Keep all customers even with no orders:",
            (
                "customers c LEFT JOIN orders o ON ...",
                "customers c INNER JOIN orders o",
                "customers c JOIN orders o",
                "customers c CROSS JOIN orders o",
            ),
            0,
        ),
    ],
    "ctes": [
        (
            "A named temporary result set uses:",
            (
                "WITH cte AS (SELECT ...)",
                "TEMP cte = SELECT ...",
                "DEFINE cte SELECT ...",
                "LET cte SELECT ...",
            ),
            0,
        ),
    ],
    "window_functions": [
        (
            "Running total by date without collapsing rows:",
            (
                "SUM(x) OVER (ORDER BY date)",
                "SUM(x) GROUP BY date",
                "SUM(x) PARTITION date",
                "RUNNING SUM(x)",
            ),
            0,
        ),
        (
            "Rank rows within each group:",
            (
                "RANK() OVER (PARTITION BY g ORDER BY v)",
                "RANK(g, v)",
                "ORDER BY v RANK g",
                "GROUP BY g RANK(v)",
            ),
            0,
        ),
    ],
}
_SQL_TASK: dict[str, tuple[str, str]] = {
    "select_from": (
        "Write the query that returns every column from a table called `users`.",
        "select*fromusers",
    ),
    "where": ("Complete: SELECT * FROM t WHERE status ___ 'active'   (the operator)", "="),
    "aggregates": ("Function name that returns the number of rows:", "count"),
    "group_by": ("Keyword pair used to aggregate per category:", "groupby"),
    "inner_join": ("Keyword that combines rows from two tables on a matching key:", "join"),
    "window_functions": ("Keyword that follows an aggregate to make it a window function:", "over"),
    "outer_join": ("JOIN type that keeps unmatched rows from the left table:", "left"),
    "ctes": ("Keyword that starts a common table expression:", "with"),
    "having": ("Clause that filters *after* GROUP BY:", "having"),
    "order_limit": ("Keyword that sorts results:", "orderby"),
}

# --------------------------------------------------------------------------- #
# Python (concept ids match domain_data.PYTHON)
# --------------------------------------------------------------------------- #
_PY_MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "variables": [
        ("`type(3 / 2)` is:", ("float", "int", "str", "error"), 0),
        ("Which is a valid variable name?", ("total_2", "2total", "total-2", "class"), 0),
    ],
    "strings": [
        ("`'ab' * 3` gives:", ("'ababab'", "'ab3'", "error", "'aaabbb'"), 0),
        ("`'Hello'[1:3]` gives:", ("'el'", "'ell'", "'He'", "'l'"), 0),
    ],
    "fstrings": [
        (
            "Insert `name` into a string:",
            ('f"hi {name}"', '"hi {name}"', '"hi " + name()', 'f"hi name"'),
            0,
        ),
    ],
    "conditionals": [
        (
            "`elif` is used to:",
            (
                "test another condition if the first was False",
                "loop while true",
                "end an if block",
                "define a function",
            ),
            0,
        ),
    ],
    "loops": [
        ("`for i in range(3)` iterates i over:", ("0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "3"), 0),
    ],
    "lists": [
        (
            "Add `x` to the end of list `xs`:",
            ("xs.append(x)", "xs.add(x)", "xs + x", "xs.push(x)"),
            0,
        ),
        ("`len([[1,2],[3]])` is:", ("2", "3", "1", "error"), 0),
    ],
    "dicts": [
        ("Get the value for key 'a' in dict d:", ("d['a']", "d.a", "d(a)", "d->a"), 0),
        ("`d.get('missing', 0)` returns:", ("0", "None", "KeyError", "'missing'"), 0),
    ],
    "comprehensions": [
        (
            "Squares of 0..4 as a list:",
            (
                "[i*i for i in range(5)]",
                "{i*i for i in range(5)}",
                "(i*i for i in range(5))",
                "list(i*i, range(5))",
            ),
            0,
        ),
    ],
    "functions": [
        ("A function returns nothing explicitly. It returns:", ("None", "0", "''", "error"), 0),
        (
            "Default argument syntax:",
            ("def f(x, n=1):", "def f(x, n:1):", "def f(x, n==1):", "def f(x, default n):"),
            0,
        ),
    ],
    "exceptions": [
        (
            "Catch a possible error around risky code:",
            (
                "try: ... except ValueError: ...",
                "if error: ...",
                "catch ValueError { }",
                "on error resume",
            ),
            0,
        ),
    ],
}
_PY_TASK: dict[str, tuple[str, str]] = {
    "variables": ("What does `len('data')` evaluate to?", "4"),
    "strings": ("`'a,b,c'.split(',')` has how many elements?", "3"),
    "loops": ("Sum 1..10 with a loop — what is the total?", "55"),
    "lists": ("`[1,2,3][-1]` is:", "3"),
    "dicts": ("`len({'a':1,'b':2})` is:", "2"),
    "comprehensions": ("How many items in `[x for x in range(10) if x % 2 == 0]`?", "5"),
    "functions": ("`def f(x): return x*x` — what is `f(4)`?", "16"),
    "conditionals": ("`1 if 3 > 2 else 0` evaluates to:", "1"),
    "fstrings": ("Result of `f'{2+3}'`:", "5"),
    "exceptions": ("Keyword that always runs after try/except:", "finally"),
}


def _shuffled(item_id: str, choices: tuple[str, ...], ans: int) -> tuple[tuple[str, ...], int]:
    """Authors write the correct choice first; show the choices in a fixed,
    per-item random order so the answer's position gives nothing away."""
    order = list(range(len(choices)))
    random.Random(item_id).shuffle(order)
    return tuple(choices[i] for i in order), order.index(ans)


def _mk_bank(
    concept_ids: list[str],
    mcq: dict[str, list[tuple[str, tuple[str, ...], int]]],
    task: dict[str, tuple[str, str]],
    depth: dict[str, int],
    prefix: str = "",
) -> ItemBank:
    """``prefix`` namespaces skills and item ids (``"sql."``) for role graphs."""
    dmax = max(depth.values(), default=1) or 1
    items: list[Item] = []
    for cid in concept_ids:
        base = -1.4 + 3.0 * depth.get(cid, 0) / dmax
        skill = f"{prefix}{cid}"
        for k, (stem, choices, ans) in enumerate(mcq.get(cid, [])):
            off = (-0.9, 0.9)[k] if k < 2 else 1.4
            iid = f"{skill}:q{k + 1}"
            shown, idx = _shuffled(iid, tuple(choices), ans)
            items.append(Item(iid, skill, 1.1, round(base + off, 2), stem, "mcq", shown, idx))
        if cid in task:
            stem, ans_text = task[cid]
            items.append(
                Item(
                    f"{skill}:task",
                    skill,
                    1.9,
                    round(base + 0.3, 2),
                    stem,
                    "task",
                    answer_text=ans_text,
                )
            )
    return ItemBank(items)


def _algebra_depth() -> dict[str, int]:
    kg = build_curriculum()
    return {c: len(kg.all_prerequisites(c)) for c in kg.concept_ids}


def _seed_depth(name: str) -> dict[str, int]:
    from domains import seed_graph

    kg = seed_graph(name)
    return {c: len(kg.all_prerequisites(c)) for c in kg.concept_ids}


def _seed_bank(
    domain: str,
) -> tuple[dict[str, list[tuple[str, tuple[str, ...], int]]], dict[str, tuple[str, str]]] | None:
    from banks import BANKS

    if domain == "sql":
        return _SQL_MCQ, _sql_tasks()
    if domain == "python":
        return _PY_MCQ, _py_tasks()
    return BANKS.get(domain)


def build_item_bank(domain: str = "algebra") -> ItemBank | None:
    """Calibrated item bank for a domain - a seed graph, a target role (the
    union of its domains' banks, skills prefixed like the role graph), or the
    legacy algebra curriculum.  ``None`` where none exists yet: the plan then
    starts from Bayesian cold-start priors."""
    if domain == "algebra":
        return _mk_bank(list(_MCQ), _MCQ, _mk_algebra_tasks(), _algebra_depth())
    seed = _seed_bank(domain)
    if seed is not None:
        mcq, task = seed
        return _mk_bank(list(mcq), mcq, task, _seed_depth(domain))
    return _role_bank(domain)


def _role_bank(role_name: str) -> ItemBank | None:
    from domain_data import ROLES
    from domains import role_graph

    role = next((r for r in ROLES if r.name == role_name), None)
    if role is None:
        return None
    kg, _goals = role_graph(role)
    depth = {c: len(kg.all_prerequisites(c)) for c in kg.concept_ids}
    items: list[Item] = []
    for d in sorted({d for d, _c, _w in role.skills}):
        seed = _seed_bank(d)
        if seed is None:
            continue
        mcq, task = seed
        sub = {c: depth.get(f"{d}.{c}", 0) for c in mcq}
        items += _mk_bank(list(mcq), mcq, task, sub, prefix=f"{d}.").items.values()
    return ItemBank(items) if items else None


def _mk_algebra_tasks() -> dict[str, tuple[str, str]]:
    return {cid: (stem, ans) for cid, (stem, ans, _tol) in _TASKS.items()}


def _sql_tasks() -> dict[str, tuple[str, str]]:
    return dict(_SQL_TASK)


def _py_tasks() -> dict[str, tuple[str, str]]:
    return dict(_PY_TASK)
