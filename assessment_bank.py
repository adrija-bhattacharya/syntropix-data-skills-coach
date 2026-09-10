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


def _concept_depth() -> dict[str, int]:
    """Transitive prerequisite count - a proxy for how advanced a concept is."""
    kg = build_curriculum()
    return {c: len(kg.all_prerequisites(c)) for c in kg.concept_ids}


def build_item_bank() -> ItemBank:
    depth = _concept_depth()
    dmax = max(depth.values()) or 1
    items: list[Item] = []
    for cid, mcqs in _MCQ.items():
        base = -1.4 + 3.0 * depth[cid] / dmax  # concept anchor on the logit scale
        offsets = (-0.9, 0.9)
        for k, (stem, choices, ans) in enumerate(mcqs):
            items.append(
                Item(
                    id=f"{cid}:q{k + 1}",
                    skill=cid,
                    a=1.1,
                    b=round(base + offsets[k], 2),
                    stem=stem,
                    kind="mcq",
                    choices=tuple(choices),
                    answer_index=ans,
                )
            )
        stem, ans_text, tol = _TASKS[cid]
        items.append(
            Item(
                id=f"{cid}:task",
                skill=cid,
                a=1.9,  # a worked answer is more discriminating than a guess-prone MCQ
                b=round(base + 0.3, 2),
                stem=stem,
                kind="task",
                answer_text=ans_text,
                tolerance=tol,
            )
        )
    return ItemBank(items)
