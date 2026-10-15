"""Data visualisation skill-check items."""

from __future__ import annotations

MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "chart_types": [
        (
            "A histogram shows:",
            (
                "the distribution of one numeric variable",
                "parts of a whole",
                "a trend over time",
                "a correlation matrix",
            ),
            0,
        ),
        (
            "A scatter plot shows:",
            (
                "the relation between two numeric variables",
                "category counts",
                "a running total",
                "one value",
            ),
            0,
        ),
    ],
    "choosing_chart": [
        (
            "Compare sales across 12 product categories:",
            ("a sorted bar chart", "a pie chart", "a line chart", "a 3-D pie"),
            0,
        ),
        (
            "Show market share of 3 brands in one year:",
            ("a bar or pie chart", "a scatter plot", "a histogram", "a box plot"),
            0,
        ),
    ],
    "matplotlib_basics": [
        (
            "In matplotlib, fig, ax = plt.subplots() gives:",
            ("a figure and one axes", "two figures", "a list of plots", "a DataFrame"),
            0,
        ),
        (
            "Draw a line on an axes:",
            ("ax.plot(x, y)", "ax.line(x, y)", "plt.draw_line(x, y)", "ax.show(x, y)"),
            0,
        ),
    ],
    "axes_titles": [
        (
            "Set the y-axis label:",
            (
                "ax.set_ylabel('Sales')",
                "ax.ylabel = 'Sales'",
                "plt.y('Sales')",
                "ax.label_y('Sales')",
            ),
            0,
        ),
        (
            "A bar chart's value axis should normally start at:",
            ("zero", "the minimum value", "the mean", "anywhere"),
            0,
        ),
    ],
    "subplots": [
        (
            "plt.subplots(2, 3) creates:",
            ("6 axes in 2 rows and 3 columns", "2 figures", "3 axes", "a 2x3 table"),
            0,
        ),
        (
            "sharey=True makes subplots:",
            ("use the same y scale", "share colours", "share titles", "overlap"),
            0,
        ),
    ],
    "seaborn_basics": [
        (
            "sns.barplot(data=df, x='region', y='sales') shows by default:",
            (
                "the mean sales per region with a CI",
                "total sales",
                "one bar per row",
                "a histogram",
            ),
            0,
        ),
        (
            "Seaborn's hue= argument:",
            (
                "colours by a category",
                "sets transparency",
                "sets the title",
                "changes the axis scale",
            ),
            0,
        ),
    ],
    "dist_plots": [
        (
            "Compare the spread and outliers of salary across 4 departments:",
            ("box plot", "pie chart", "line chart", "stacked bar"),
            0,
        ),
        (
            "A histogram's bin width mainly changes:",
            ("how smooth or detailed it looks", "the data", "the mean", "the axis labels"),
            0,
        ),
    ],
    "cat_plots": [
        (
            "Long category names on a bar chart fit best on:",
            ("a horizontal bar chart", "a vertical bar chart", "a pie chart", "a line chart"),
            0,
        ),
        (
            "Sort bars by value because it:",
            (
                "makes ranking easy to read",
                "is required by matplotlib",
                "changes the data",
                "removes outliers",
            ),
            0,
        ),
    ],
    "rel_plots": [
        (
            "Add a trend line to a scatter plot to show:",
            ("the overall linear relation", "every outlier", "the category", "the total"),
            0,
        ),
        (
            "Overplotting in a scatter of 1 million points is reduced by:",
            ("transparency or a hexbin/density plot", "a pie chart", "bigger markers", "3-D"),
            0,
        ),
    ],
    "color_access": [
        (
            "Red/green-only colour coding is a problem because:",
            (
                "it is hard for colour-blind readers",
                "printers can't print it",
                "it is too bright",
                "screens can't show it",
            ),
            0,
        ),
        (
            "For a value that goes from low to high use:",
            ("a sequential palette", "a categorical palette", "rainbow colours", "random colours"),
            0,
        ),
    ],
    "annotation": [
        (
            "Annotating the peak value on a line chart helps:",
            ("point the reader to the key fact", "hide the data", "change the scale", "add colour"),
            0,
        ),
        (
            "A good chart title states:",
            ("the takeaway", "only the variable names", "the file name", "nothing"),
            0,
        ),
    ],
    "storytelling": [
        (
            "Data storytelling puts first:",
            (
                "the main insight and what to do",
                "every chart you made",
                "the raw table",
                "the methodology",
            ),
            0,
        ),
        (
            "Removing gridlines, borders and 3-D effects reduces:",
            ("clutter (chart junk)", "accuracy", "the data", "colour contrast"),
            0,
        ),
    ],
    "dashboards": [
        (
            "The most important KPI on a dashboard goes:",
            ("top-left", "bottom-right", "in a tooltip", "on page 2"),
            0,
        ),
        (
            "A dashboard for executives should show:",
            ("a few KPIs and trends", "every table", "raw logs", "code"),
            0,
        ),
    ],
}

TASK: dict[str, tuple[str, str]] = {
    "chart_types": (
        "Name the chart: bars of counts for ranges of a numeric variable.",
        "histogram",
    ),
    "subplots": ("How many axes does plt.subplots(3, 2) create?", "6"),
}
