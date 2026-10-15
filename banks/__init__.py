"""Skill-check item banks for every data-analytics / data-engineering domain.

Each module exports ``MCQ`` (concept -> list of (stem, choices, correct index))
and ``TASK`` (concept -> (stem, typed answer)).  Difficulty and discrimination
are set by :func:`assessment_bank._mk_bank` from the concept's depth in its
graph, the same way as the SQL / Python banks.
"""

from __future__ import annotations

from banks import data_eng, dataviz, excel, git, pandas_bank, powerbi, stats, tableau

MCQ = dict[str, list[tuple[str, tuple[str, ...], int]]]
TASK = dict[str, tuple[str, str]]

BANKS: dict[str, tuple[MCQ, TASK]] = {
    "spreadsheets": (excel.MCQ, excel.TASK),
    "python_data": (pandas_bank.MCQ, pandas_bank.TASK),
    "stats": (stats.MCQ, stats.TASK),
    "dataviz": (dataviz.MCQ, dataviz.TASK),
    "powerbi": (powerbi.MCQ, powerbi.TASK),
    "tableau": (tableau.MCQ, tableau.TASK),
    "data_eng": (data_eng.MCQ, data_eng.TASK),
    "git": (git.MCQ, git.TASK),
}
