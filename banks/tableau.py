"""Tableau skill-check items."""

from __future__ import annotations

MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "tab_connect": [
        (
            "A Tableau extract is:",
            (
                "a snapshot copy of the data",
                "a live database connection",
                "a dashboard",
                "a calculated field",
            ),
            0,
        ),
        (
            "Relating two tables on the data source page uses:",
            ("relationships (noodles) or joins", "LOD expressions", "parameters", "filters"),
            0,
        ),
    ],
    "dims_measures": [
        ("Sales is usually a:", ("measure", "dimension", "parameter", "set"), 0),
        (
            "A green pill in Tableau is:",
            ("continuous", "discrete", "a dimension always", "an error"),
            0,
        ),
    ],
    "tab_basic_charts": [
        (
            "Category on Rows and SUM(Sales) on Columns draws:",
            ("a horizontal bar chart", "a line chart", "a map", "a scatter"),
            0,
        ),
        (
            "The Marks card controls:",
            ("colour, size, label and detail", "data connections", "users", "extract refresh"),
            0,
        ),
    ],
    "tab_filters": [
        (
            "In Tableau's order of operations, FIXED LOD is computed before:",
            ("dimension filters", "extract filters", "data source filters", "context filters"),
            0,
        ),
        (
            "To make a dimension filter apply before a FIXED LOD:",
            ("add it to context", "make it a measure", "hide it", "use a set"),
            0,
        ),
    ],
    "tab_calcs": [
        (
            "Profit ratio as a calculated field:",
            (
                "SUM([Profit]) / SUM([Sales])",
                "[Profit] / [Sales] summed",
                "AVG([Profit] / [Sales]) always",
                "RATIO([Profit])",
            ),
            0,
        ),
        (
            'IF [Sales] > 1000 THEN "Big" ELSE "Small" END is evaluated:',
            ("row by row", "once per view", "only in dashboards", "never"),
            0,
        ),
    ],
    "tab_aggregation": [
        (
            "The view's level of detail is set by:",
            ("the dimensions in the view", "the measures", "the colours", "the filters only"),
            0,
        ),
        (
            "AVG(Sales) with Region on Rows is the average:",
            (
                "of the sale rows within each region",
                "of the regional totals",
                "of all sales",
                "of the regions",
            ),
            0,
        ),
    ],
    "table_calcs": [
        (
            "RUNNING_SUM(SUM([Sales])) is a:",
            ("table calculation", "LOD expression", "data source filter", "parameter"),
            0,
        ),
        (
            "A table calculation's result depends on:",
            (
                "the marks in the view and its 'compute using'",
                "the database only",
                "the extract",
                "nothing",
            ),
            0,
        ),
    ],
    "lod": [
        (
            "{FIXED [Customer] : SUM([Sales])} gives:",
            (
                "each customer's total, whatever is in the view",
                "the view's total",
                "the running total",
                "the average sale",
            ),
            0,
        ),
        (
            "INCLUDE differs from FIXED because INCLUDE:",
            (
                "adds a dimension to the view's detail",
                "ignores the view",
                "only works on dates",
                "is a table calc",
            ),
            0,
        ),
    ],
    "tab_parameters": [
        (
            "A parameter is:",
            (
                "a user-controlled value used in calcs",
                "a filter on a dimension",
                "a data source",
                "a set",
            ),
            0,
        ),
        (
            "Top N with a user-chosen N uses:",
            ("a parameter in a Top filter or calc", "a FIXED LOD", "an extract", "a story"),
            0,
        ),
    ],
    "tab_maps": [
        (
            "To plot a field on a map it needs:",
            ("a geographic role", "a parameter", "a table calc", "a green pill"),
            0,
        ),
        (
            "A filled (choropleth) map is best for:",
            ("rates per region", "exact counts per point", "time trends", "rankings"),
            0,
        ),
    ],
    "tab_dashboards": [
        (
            "Clicking a sheet to filter another sheet uses:",
            ("a filter action", "a parameter only", "a story", "an extract"),
            0,
        ),
        (
            "A fixed dashboard size makes the layout:",
            ("the same on every screen", "resize automatically", "mobile-only", "hidden"),
            0,
        ),
    ],
    "tab_stories": [
        (
            "A Tableau story is:",
            (
                "a sequence of sheets/dashboards telling a narrative",
                "a calculated field",
                "a data source",
                "a set",
            ),
            0,
        ),
        (
            "Sharing a public workbook uses:",
            ("Tableau Public", "an extract filter", "a parameter", "a context filter"),
            0,
        ),
    ],
}

TASK: dict[str, tuple[str, str]] = {
    "lod": (
        "Customer A bought 10 and 20; B bought 5. {FIXED [Customer] : SUM([Sales])} for A's rows is:",
        "30",
    ),
    "table_calcs": ("Monthly sales 5, 7, 3. RUNNING_SUM(SUM([Sales])) in month 3 is:", "15"),
    "tab_calcs": ("Profit 50, Sales 200. SUM([Profit]) / SUM([Sales]) is? (decimal)", "0.25"),
}
