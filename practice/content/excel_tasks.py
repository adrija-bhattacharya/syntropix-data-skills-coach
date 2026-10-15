"""Excel practice: a small sales sheet and formula tasks.

The learner types a formula for ``cell``; it is evaluated against :data:`SHEET`.
``fill_down`` tasks also evaluate the formula as Excel would after copying it
one row down - that is how a missing ``$`` anchor is caught.  Wrong formulas
are recognised by the value a known mistake produces (``distractors`` are
formulas) and by a few lexical cues (VLOOKUP without FALSE).
"""

from __future__ import annotations

import datetime as dt

from practice.content import D
from practice.excel import Sheet
from practice.tasks import Task

_ROWS = [
    # Date, Region, Rep, Product, Units, Price
    (dt.date(2025, 1, 6), "East", "  asha  rao ", "Pens", 12, 2.5),
    (dt.date(2025, 1, 19), "West", "Bilal Khan", "Paper", 10, 4.0),
    (dt.date(2025, 2, 3), "East", "Chen Li", "Ink", 6, 9.0),
    (dt.date(2025, 2, 14), "North", "Dana Roy", "Pens", None, 2.5),
    (dt.date(2025, 3, 2), "West", "Bilal Khan", "Stapler", 3, 7.5),
    (dt.date(2025, 3, 21), "East", "Chen Li", "Paper", 15, 4.0),
    (dt.date(2025, 4, 8), "North", "Dana Roy", "Ink", 4, 9.0),
    (dt.date(2025, 4, 30), "West", "Farah Ali", "Pens", 20, 2.5),
    (dt.date(2025, 5, 12), "East", "  asha  rao ", "Stapler", 2, 7.5),
    (dt.date(2025, 5, 27), "North", "Dana Roy", "Paper", 8, 4.0),
]
_LOOKUP = [("Pens", "Writing"), ("Paper", "Office"), ("Ink", "Writing"), ("Stapler", "Office")]

HEADERS = ("Date", "Region", "Rep", "Product", "Units", "Price")


def _sheet() -> Sheet:
    cells: dict[str, object] = {}
    for c, h in zip("ABCDEF", HEADERS):
        cells[f"{c}1"] = h
    for i, row in enumerate(_ROWS, start=2):
        for c, v in zip("ABCDEF", row):
            cells[f"{c}{i}"] = float(v) if isinstance(v, int) else v
    cells["H1"], cells["I1"] = "Product", "Category"
    for i, (p, cat) in enumerate(_LOOKUP, start=2):
        cells[f"H{i}"], cells[f"I{i}"] = p, cat
    return Sheet(cells)


SHEET = _sheet()


def grid() -> tuple[tuple[str, ...], ...]:
    """The sheet as display rows (A..I, rows 1..11) for the practice UI."""
    from practice.excel import display

    rows = []
    for r in range(1, 12):
        rows.append(tuple(display(SHEET.cells.get(f"{c}{r}")) for c in "ABCDEFGHI"))
    return tuple(rows)


def xl(
    id_: str,
    concept: str,
    prompt: str,
    formula: str,
    *,
    cell: str = "G2",
    fill_down: bool = False,
    wrong: tuple[tuple[str, str, str, str], ...] = (),
    hint: str = "",
    hint2: str = "",
) -> Task:
    return Task(
        id=id_,
        concept=concept,
        prompt=prompt,
        reference=formula,
        kind="excel",
        domain="spreadsheets",
        cell=cell,
        fill_down=fill_down,
        distractors=tuple(D(*w) for w in wrong),
        hint=hint,
        hint2=hint2,
    )


TASKS: tuple[Task, ...] = (
    xl(
        "xl_revenue",
        "formulas",
        "In G2, the revenue of row 2: units times price.",
        "=E2*F2",
        hint="Start with =, then multiply the two cells.",
        hint2="=E2*…",
    ),
    xl(
        "xl_total_units",
        "agg_functions",
        "In G2, the total units sold (E2:E11).",
        "=SUM(E2:E11)",
        wrong=(
            (
                "=SUM(E2:E10)",
                "cells_ranges",
                "short_range",
                "The range stops one row early - it should end at E11.",
            ),
        ),
        hint="SUM over a range.",
        hint2="=SUM(E2:E…)",
    ),
    xl(
        "xl_avg_units",
        "agg_functions",
        "In G2, the average units per sale. The blank Units cell is a missing value, not zero.",
        "=AVERAGE(E2:E11)",
        wrong=(
            (
                "=SUM(E2:E11)/10",
                "agg_functions",
                "blank_as_zero",
                "Dividing by 10 treats the blank as a zero sale - AVERAGE skips blanks.",
            ),
        ),
        hint="AVERAGE ignores blank cells.",
        hint2="=AVERAGE(…)",
    ),
    xl(
        "xl_share",
        "abs_refs",
        "In G2, row 2's share of all units, written so it still works when copied down to G3.",
        "=E2/SUM($E$2:$E$11)",
        fill_down=True,
        hint="The total's range must not move when the formula is copied.",
        hint2="=E2/SUM($E$…:$E$…)",
    ),
    xl(
        "xl_clean_rep",
        "text_functions",
        "In G2, the rep name from C2 with extra spaces removed and each word capitalised.",
        "=PROPER(TRIM(C2))",
        wrong=(
            (
                "=PROPER(C2)",
                "cleaning_ss",
                "no_trim",
                "The extra spaces are still there - wrap the text in TRIM.",
            ),
        ),
        hint="TRIM removes extra spaces; PROPER capitalises words.",
        hint2="=PROPER(TRIM(…))",
    ),
    xl(
        "xl_month",
        "date_functions_ss",
        "In G2, the month number of the date in A6.",
        "=MONTH(A6)",
        hint="MONTH(date) gives 1-12.",
        hint2="=MONTH(…)",
    ),
    xl(
        "xl_bulk_flag",
        "logical_functions",
        'In G3, "Bulk" if the units in E3 are 10 or more, otherwise "Single".',
        '=IF(E3>=10,"Bulk","Single")',
        cell="G3",
        wrong=(
            (
                '=IF(E3>10,"Bulk","Single")',
                "logical_functions",
                "boundary",
                "Exactly 10 should count as Bulk - use >= not >.",
            ),
        ),
        hint="IF(test, value_if_true, value_if_false)",
        hint2='=IF(E3…10,"Bulk","Single")',
    ),
    xl(
        "xl_category",
        "lookups",
        "In G4, the category of the product in D4, looked up in the table H2:I5.",
        "=XLOOKUP(D4,$H$2:$H$5,$I$2:$I$5)",
        cell="G4",
        hint="Look the product up in H, return the matching value from I. VLOOKUP needs FALSE for an exact match.",
        hint2="=XLOOKUP(D4, …, …)  or  =VLOOKUP(D4, …, 2, FALSE)",
    ),
    xl(
        "xl_east_units",
        "pivot_tables",
        "In G2, the total units sold in the East region (what a pivot table would show for East).",
        '=SUMIF(B2:B11,"East",E2:E11)',
        wrong=(
            (
                '=COUNTIF(B2:B11,"East")',
                "agg_functions",
                "count_not_sum",
                "That counts East rows; the question asks for the sum of their units.",
            ),
        ),
        hint="SUMIF(criteria_range, criterion, sum_range)",
        hint2='=SUMIF(B2:B11,"East",…)',
    ),
    xl(
        "xl_big_sales",
        "sort_filter",
        "In G2, how many sales had more than 10 units?",
        '=COUNTIF(E2:E11,">10")',
        hint='COUNTIF with a criterion like ">10".',
        hint2='=COUNTIF(…,">10")',
    ),
    xl(
        "xl_distinct_regions",
        "dynamic_arrays",
        "In G2, the number of distinct regions in B2:B11.",
        "=COUNTA(UNIQUE(B2:B11))",
        wrong=(
            (
                "=COUNTA(B2:B11)",
                "dynamic_arrays",
                "duplicates_counted",
                "That counts every row - UNIQUE first removes repeats.",
            ),
        ),
        hint="UNIQUE returns each value once; COUNTA counts them.",
        hint2="=COUNTA(UNIQUE(…))",
    ),
    xl(
        "xl_trim_len",
        "cleaning_ss",
        "In G2, the length of the rep name in C2 after removing extra spaces.",
        "=LEN(TRIM(C2))",
        wrong=(
            (
                "=LEN(C2)",
                "cleaning_ss",
                "no_trim",
                "The leading, trailing and double spaces were counted - TRIM first.",
            ),
        ),
        hint="TRIM, then LEN.",
        hint2="=LEN(TRIM(…))",
    ),
    xl(
        "xl_west_avg_price",
        "formulas",
        "In G2, the average price of the West region's sales.",
        '=AVERAGEIF(B2:B11,"West",F2:F11)',
        hint="AVERAGEIF(criteria_range, criterion, average_range)",
        hint2='=AVERAGEIF(B2:B11,"West",…)',
    ),
)
