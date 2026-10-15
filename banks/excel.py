"""Excel / spreadsheets skill-check items."""

from __future__ import annotations

MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "cells_ranges": [
        ("How many cells are in the range B2:C5?", ("8", "6", "10", "4"), 0),
        ("Which reference points to the whole column D?", ("D:D", "D1:D", "D*", "COL(D)"), 0),
    ],
    "formulas": [
        ("Every Excel formula starts with:", ("=", "#", "@", "$"), 0),
        ("A1 holds 4 and B1 holds 6. What does =A1*B1+2 return?", ("26", "32", "12", "36"), 0),
    ],
    "agg_functions": [
        (
            "Which function counts only cells that contain numbers?",
            ("COUNT", "COUNTA", "COUNTBLANK", "SUM"),
            0,
        ),
        (
            "A1:A4 holds 2, 4, (blank), 6. What does =AVERAGE(A1:A4) return?",
            ("4", "3", "6", "#DIV/0!"),
            0,
        ),
    ],
    "abs_refs": [
        (
            "You copy =A1*$B$1 from C1 down to C2. C2 becomes:",
            ("=A2*$B$1", "=A2*$B$2", "=A1*$B$1", "=B2*$B$1"),
            0,
        ),
        (
            "In =A$1, what stays fixed when you copy the formula?",
            ("the row", "the column", "both", "neither"),
            0,
        ),
    ],
    "text_functions": [
        ('=LEFT("Kolkata", 3) returns:', ('"Kol"', '"ata"', '"Kolk"', '"K"'), 0),
        (
            "Which function removes extra spaces from text?",
            ("TRIM", "CLEAN", "SUBSTITUTE", "LEN"),
            0,
        ),
    ],
    "date_functions_ss": [
        (
            "Which formula returns today's date and updates every day?",
            ("=TODAY()", "=NOW(0)", "=DATE()", "=DAY()"),
            0,
        ),
        ('=YEAR("2025-06-15") returns:', ("2025", "6", "15", "an error"), 0),
    ],
    "logical_functions": [
        ('A1 is 70. =IF(A1>=75,"pass","retry") returns:', ('"retry"', '"pass"', "TRUE", "75"), 0),
        ("=AND(TRUE, FALSE) returns:", ("FALSE", "TRUE", "#VALUE!", "0.5"), 0),
    ],
    "lookups": [
        (
            "VLOOKUP's 4th argument should be FALSE because:",
            (
                "it forces an exact match",
                "it sorts the table",
                "it searches right to left",
                "it ignores blanks",
            ),
            0,
        ),
        (
            "Which lookup can return a column to the LEFT of the search column?",
            ("XLOOKUP", "VLOOKUP", "HLOOKUP", "LOOKUP with 2 arguments"),
            0,
        ),
    ],
    "sort_filter": [
        (
            "Filtering a column to show only 'Mumbai' rows:",
            ("hides the other rows", "deletes the other rows", "sorts by city", "copies the rows"),
            0,
        ),
        (
            "Sorting by Region, then by Sales descending is called:",
            ("a multi-level sort", "a filter", "a pivot", "a lookup"),
            0,
        ),
    ],
    "conditional_formatting": [
        (
            "Conditional formatting changes:",
            ("how cells look", "the values in cells", "the formulas", "the sheet order"),
            0,
        ),
        (
            "A 'colour scale' rule colours cells by:",
            ("their value relative to the range", "their font", "their row number", "random order"),
            0,
        ),
    ],
    "pivot_tables": [
        (
            "In a pivot table, putting Region in Rows and Sales in Values gives:",
            (
                "total sales per region",
                "a list of every sale",
                "sales sorted by date",
                "a chart only",
            ),
            0,
        ),
        (
            "A pivot table's source data changed. To see the new numbers you:",
            (
                "refresh the pivot",
                "rebuild the workbook",
                "nothing - it updates live",
                "delete the source",
            ),
            0,
        ),
    ],
    "charts_ss": [
        (
            "Best chart for monthly sales over two years:",
            ("line chart", "pie chart", "scatter of random points", "table only"),
            0,
        ),
        (
            "A chart linked to a range updates when:",
            ("the range values change", "you rename the sheet", "you print", "never"),
            0,
        ),
    ],
    "cleaning_ss": [
        (
            "Which feature removes repeated rows?",
            ("Remove Duplicates", "Freeze Panes", "Flash Fill", "Goal Seek"),
            0,
        ),
        (
            "'Text to Columns' is used to:",
            ("split one column into several", "merge two sheets", "change font", "sort text"),
            0,
        ),
    ],
    "excel_tables": [
        ("A structured reference looks like:", ("Sales[Amount]", "A1:A100", "$A$1", "Sheet1!A"), 0),
        (
            "Turning a range into an Excel Table makes formulas:",
            ("extend to new rows automatically", "stop calculating", "absolute", "read-only"),
            0,
        ),
    ],
    "dynamic_arrays": [
        (
            "=UNIQUE(A2:A10) returns:",
            (
                "each distinct value once, spilling down",
                "the count of unique values",
                "only the first value",
                "a sorted copy with duplicates",
            ),
            0,
        ),
        (
            "A #SPILL! error means:",
            (
                "the result range is blocked by other data",
                "a divide by zero",
                "a missing name",
                "a circular reference",
            ),
            0,
        ),
    ],
    "power_query": [
        (
            "Power Query records your cleaning steps so that:",
            (
                "they re-run on refresh",
                "the source file is edited",
                "they run once only",
                "formulas are hidden",
            ),
            0,
        ),
        (
            "To combine 12 monthly CSV files with the same columns, Power Query uses:",
            ("Append (combine from folder)", "Merge on a key", "Pivot", "Transpose"),
            0,
        ),
    ],
}

TASK: dict[str, tuple[str, str]] = {
    "formulas": ("A1 = 10, A2 = 15. What does =A1+A2*2 return?", "40"),
    "agg_functions": ("A1:A5 holds 3, 7, 7, 1, 2. What does =MAX(A1:A5)-MIN(A1:A5) return?", "6"),
    "text_functions": ('What does =LEN("data") return?', "4"),
    "logical_functions": (
        'A1 = 9. What does =IF(A1>10,"big","small") return? (type the word)',
        "small",
    ),
}
