"""Power BI / DAX skill-check items."""

from __future__ import annotations

MCQ: dict[str, list[tuple[str, tuple[str, ...], int]]] = {
    "pbi_get_data": [
        (
            "Cleaning steps in Power BI are recorded in:",
            ("Power Query", "the DAX editor", "the report canvas", "the Format pane"),
            0,
        ),
        (
            "Import mode means data is:",
            (
                "loaded into the model and refreshed",
                "queried live every click",
                "never stored",
                "typed in by hand",
            ),
            0,
        ),
    ],
    "pbi_modeling": [
        (
            "Relationships in the model let a filter on Product:",
            ("flow to the Sales table", "delete products", "sort the report", "change DAX syntax"),
            0,
        ),
        (
            "A relationship needs columns that:",
            (
                "hold matching key values",
                "have the same name",
                "are both text",
                "are both measures",
            ),
            0,
        ),
    ],
    "star_schema": [
        (
            "In a star schema, Sales (one row per sale) is the:",
            ("fact table", "dimension table", "bridge table", "calendar"),
            0,
        ),
        (
            "Product, Customer and Date tables are:",
            ("dimension tables", "fact tables", "measures", "visuals"),
            0,
        ),
    ],
    "relationships_cardinality": [
        (
            "Product (one row per product) to Sales (many per product) is:",
            ("one-to-many", "many-to-many", "one-to-one", "none"),
            0,
        ),
        (
            "Bidirectional cross-filtering everywhere can cause:",
            ("ambiguous and slow models", "faster reports", "smaller files", "nothing"),
            0,
        ),
    ],
    "dax_basics": [
        (
            "A total that must respond to slicers should be a:",
            ("measure", "calculated column", "new table", "static value"),
            0,
        ),
        (
            "A calculated column is computed:",
            (
                "row by row at refresh",
                "every time a visual renders",
                "only in Excel",
                "by the slicer",
            ),
            0,
        ),
    ],
    "dax_aggregations": [
        (
            "Count the rows of the Sales table:",
            ("COUNTROWS(Sales)", "COUNT(Sales)", "ROWS(Sales)", "SUM(Sales)"),
            0,
        ),
        (
            "Number of different customers who bought:",
            (
                "DISTINCTCOUNT(Sales[CustomerID])",
                "COUNT(Sales[CustomerID])",
                "SUM(Sales[CustomerID])",
                "COUNTROWS(Customer)",
            ),
            0,
        ),
    ],
    "filter_context": [
        (
            "In a matrix with Year on rows, [Total Sales] for 2024 is computed with:",
            (
                "a filter context of Year = 2024",
                "no filter",
                "a row context only",
                "the whole table always",
            ),
            0,
        ),
        (
            "A calculated column's formula runs in:",
            ("row context", "filter context only", "query context", "no context"),
            0,
        ),
    ],
    "calculate": [
        (
            "CALCULATE([Sales], ALL(Product)) in a Product row returns:",
            ("total sales over all products", "that product's sales", "blank", "an error"),
            0,
        ),
        (
            "% of total = DIVIDE([Sales], CALCULATE([Sales], ALL(Product))). The denominator is:",
            ("the grand total", "the row's sales", "1", "the count of products"),
            0,
        ),
    ],
    "iterators": [
        (
            "Revenue from Price and Qty columns as a measure:",
            (
                "SUMX(Sales, Sales[Price] * Sales[Qty])",
                "SUM(Sales[Price]) * SUM(Sales[Qty])",
                "SUM(Sales[Price] * Sales[Qty])",
                "PRODUCT(Sales)",
            ),
            0,
        ),
        (
            "Rows (Price 5, Qty 2) and (Price 10, Qty 1): what does SUM(Price) * SUM(Qty) return?",
            ("45", "20", "15", "30"),
            0,
        ),
    ],
    "time_intelligence": [
        (
            "TOTALYTD and SAMEPERIODLASTYEAR need:",
            ("a marked date table", "a text date column", "a fact table only", "DirectQuery"),
            0,
        ),
        (
            "Prior-year sales:",
            (
                "CALCULATE([Sales], SAMEPERIODLASTYEAR('Date'[Date]))",
                "[Sales] - 1",
                "PREVIOUSDAY([Sales])",
                "SUM(LastYear)",
            ),
            0,
        ),
    ],
    "pbi_visuals": [
        (
            "Clicking a bar in one visual and seeing others filter is:",
            ("cross-filtering (interactions)", "drill-through", "bookmarks", "RLS"),
            0,
        ),
        (
            "A slicer is used to:",
            ("filter the report interactively", "format numbers", "write DAX", "load data"),
            0,
        ),
    ],
    "pbi_dashboards": [
        (
            "Card visuals are best for:",
            ("single headline numbers (KPIs)", "long tables", "maps", "trends"),
            0,
        ),
        (
            "Drill-through pages let users:",
            ("jump to detail for one item", "edit data", "export the model", "change the theme"),
            0,
        ),
    ],
    "rls": [
        (
            "Row-level security restricts:",
            (
                "which rows each user sees",
                "which visuals exist",
                "refresh times",
                "who can edit DAX",
            ),
            0,
        ),
        (
            "RLS roles are defined with:",
            ("DAX filter expressions", "Power Query steps", "themes", "bookmarks"),
            0,
        ),
    ],
    "pbi_publish": [
        (
            "Scheduled refresh for on-premises data needs:",
            ("a gateway", "a slicer", "a bookmark", "a theme"),
            0,
        ),
        (
            "Reports are shared with others through:",
            (
                "the Power BI service (workspaces / apps)",
                "the .pbix file only",
                "email attachments only",
                "Power Query",
            ),
            0,
        ),
    ],
}

TASK: dict[str, tuple[str, str]] = {
    "dax_aggregations": (
        "Sales has 3 rows with CustomerID 7, 7, 9. What does DISTINCTCOUNT(Sales[CustomerID]) return?",
        "2",
    ),
    "iterators": (
        "Two sales rows: Price 4 × Qty 3, and Price 2 × Qty 5. What does SUMX(Sales, Price * Qty) return?",
        "22",
    ),
    "calculate": (
        "Books sold 30, Pens 70. In the Books row, DIVIDE([Sales], CALCULATE([Sales], ALL(Product))) is? (decimal)",
        "0.3",
    ),
}
