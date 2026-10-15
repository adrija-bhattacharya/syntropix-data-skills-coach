"""Compute-or-predict tasks for skills without a runnable sandbox here
(statistics, Power BI / DAX, Tableau, chart choice, Git, data-engineering
concepts).  The learner computes a value from a small table or picks the
right option; a wrong answer is diagnosed by matching the value each known
mistake produces.  Statistics answers are computed from the data below, not
typed in by hand.
"""

from __future__ import annotations

import math
import statistics as st

from scipy import stats as sps

from practice.content import choice, number
from practice.tasks import Task

# ------------------------------------------------------------------ statistics
SALES = [12, 15, 11, 18, 22, 9, 30, 14]
_N = len(SALES)
_MEAN = st.mean(SALES)
_SD = st.stdev(SALES)
_PSD = st.pstdev(SALES)
_SE = _SD / math.sqrt(_N)
_T = float(sps.t.ppf(0.975, _N - 1))
_SALES_CTX = (("day", *[str(i) for i in range(1, _N + 1)]), ("sales", *[str(v) for v in SALES]))
_lo, _hi = sorted(SALES)[: _N // 2], sorted(SALES)[_N // 2 :]
_IQR = st.median(_hi) - st.median(_lo)

_X = [1, 2, 3, 4, 5, 6]
_Y = [2.0, 4.6, 5.1, 9.0, 8.7, 12.4]
_FIT = sps.linregress(_X, _Y)
_XY_CTX = (("ad spend (k)", *map(str, _X)), ("sales (k)", *map(str, _Y)))

_A = [23, 25, 21, 30, 27, 26]
_B = [31, 29, 35, 28, 33, 30]
_P_IND = float(sps.ttest_ind(_A, _B).pvalue)
_P_REL = float(sps.ttest_rel(_A, _B).pvalue)

STATS: tuple[Task, ...] = (
    number(
        "st_mean",
        "descriptive",
        "stats",
        "Daily sales for 8 days are below. What is the mean? (2 decimals)",
        round(_MEAN, 2),
        tol=0.01,
        wrong=[
            (
                st.median(SALES),
                "descriptive",
                "median_not_mean",
                "That's the median (the middle value); the mean adds all and divides by n.",
            )
        ],
        context=_SALES_CTX,
        hint="Mean = sum / n.",
    ),
    number(
        "st_sample_sd",
        "descriptive",
        "stats",
        "These 8 days are a sample. What is the sample standard deviation? (2 decimals)",
        round(_SD, 2),
        tol=0.01,
        wrong=[
            (
                round(_PSD, 2),
                "sampling",
                "population_sd",
                "That divides by n (population SD). A sample uses n − 1.",
            ),
            (
                round(_SD**2, 2),
                "descriptive",
                "variance",
                "That's the variance - take its square root.",
            ),
        ],
        context=_SALES_CTX,
        hint="Sample SD divides the squared deviations by n − 1, then takes the square root.",
    ),
    number(
        "st_iqr",
        "quartiles",
        "stats",
        "IQR of the 8 daily sales, taking Q1 and Q3 as the medians of the lower and upper halves.",
        _IQR,
        tol=0.01,
        wrong=[
            (
                max(SALES) - min(SALES),
                "quartiles",
                "range",
                "That's the range (max − min); the IQR is Q3 − Q1.",
            )
        ],
        context=_SALES_CTX,
        hint="Sort, split into halves, take each half's median.",
    ),
    number(
        "st_se",
        "standard_error",
        "stats",
        "Standard error of the mean of the 8 daily sales (sample SD / √n), 2 decimals.",
        round(_SE, 2),
        tol=0.01,
        wrong=[
            (round(_SD, 2), "standard_error", "forgot_sqrt_n", "That's the SD - divide it by √n."),
            (round(_SD / _N, 2), "standard_error", "divided_by_n", "Divide by √n, not n."),
        ],
        context=_SALES_CTX,
        hint="SE = s / √n.",
    ),
    number(
        "st_ci_low",
        "confidence_intervals",
        "stats",
        "Lower end of the 95% confidence interval for the mean daily sales (t distribution, df = 7). 2 decimals.",
        round(_MEAN - _T * _SE, 2),
        tol=0.02,
        wrong=[
            (
                round(_MEAN - 1.96 * _SE, 2),
                "confidence_intervals",
                "z_not_t",
                "With only 8 values use t (≈2.365 for df = 7), not z = 1.96.",
            )
        ],
        context=_SALES_CTX,
        hint="mean − t × SE, with t for 7 degrees of freedom.",
    ),
    number(
        "st_two_sixes",
        "probability_basics",
        "stats",
        "Roll two fair dice. Probability both show 6? (4 decimals)",
        round(1 / 36, 4),
        tol=0.0005,
        wrong=[
            (
                round(2 / 6, 4),
                "probability_basics",
                "added",
                "Independent events multiply: 1/6 × 1/6.",
            ),
            (round(1 / 6, 4), "probability_basics", "one_die", "That's one die; both must show 6."),
        ],
    ),
    number(
        "st_corr",
        "correlation",
        "stats",
        "Correlation r between ad spend and sales below (3 decimals).",
        round(_FIT.rvalue, 3),
        tol=0.002,
        wrong=[
            (
                round(_FIT.rvalue**2, 3),
                "r_squared",
                "r_squared",
                "That's r² - r is its square root, with the sign of the slope.",
            )
        ],
        context=_XY_CTX,
    ),
    number(
        "st_slope",
        "linear_regression",
        "stats",
        "Least-squares slope of sales on ad spend (2 decimals).",
        round(_FIT.slope, 2),
        tol=0.01,
        wrong=[
            (
                round(_FIT.intercept, 2),
                "linear_regression",
                "intercept",
                "That's the intercept (sales at zero spend); the slope is the change per unit of spend.",
            )
        ],
        context=_XY_CTX,
    ),
    number(
        "st_r2",
        "r_squared",
        "stats",
        "R² of the sales-on-ad-spend regression (3 decimals).",
        round(_FIT.rvalue**2, 3),
        tol=0.002,
        wrong=[(round(_FIT.rvalue, 3), "correlation", "r_not_r2", "That's r; R² is r squared.")],
        context=_XY_CTX,
    ),
    number(
        "st_ttest",
        "t_test",
        "stats",
        "Two independent groups of users (A and B). p-value of a two-sample t-test (3 decimals).",
        round(_P_IND, 3),
        tol=0.002,
        wrong=[
            (
                round(_P_REL, 3),
                "t_test",
                "paired",
                "That's a paired test - these are different users, so use an independent two-sample test.",
            )
        ],
        context=(("A", *map(str, _A)), ("B", *map(str, _B))),
    ),
    number(
        "st_chi_expected",
        "chi_square",
        "stats",
        "A 2×2 table: 60 mobile and 40 desktop users; 30 of all 100 bought. Expected count of mobile buyers if device and buying are independent?",
        18,
        wrong=[
            (
                30,
                "chi_square",
                "observed_total",
                "That's all buyers; expected = row total × column total / grand total.",
            )
        ],
        hint="expected = (row total × column total) / grand total",
    ),
    number(
        "st_lift",
        "ab_testing",
        "stats",
        "A converts 120 of 2,400 users; B converts 150 of 2,400. Relative lift of B over A in %?",
        25,
        tol=0.1,
        wrong=[
            (
                1.25,
                "ab_testing",
                "absolute_points",
                "That's the difference in percentage points; relative lift = (B − A) / A.",
            )
        ],
    ),
    choice(
        "st_pvalue",
        "p_value",
        "stats",
        "p = 0.04 with α = 0.05. What do you conclude?",
        "Reject the null hypothesis",
        [
            (
                "The null hypothesis is 4% likely to be true",
                "p_value",
                "p_is_prob_null",
                "A p-value is not the probability the null is true.",
            ),
            (
                "The effect is large and important",
                "p_value",
                "significance_is_size",
                "Significance says nothing about how big the effect is.",
            ),
            (
                "Fail to reject the null",
                "hypothesis_testing",
                "wrong_direction",
                "p < α means you reject the null.",
            ),
        ],
    ),
    choice(
        "st_null",
        "hypothesis_testing",
        "stats",
        "Testing whether a new checkout raises conversion. The null hypothesis is:",
        "The new checkout makes no difference",
        [
            (
                "The new checkout raises conversion",
                "hypothesis_testing",
                "null_is_claim",
                "That's the alternative; the null is 'no effect'.",
            ),
            ("The p-value is 0.05", "p_value", "alpha", "α is a threshold, not a hypothesis."),
        ],
    ),
    choice(
        "st_distribution",
        "distributions",
        "stats",
        "Roughly what share of a normal distribution lies within 1 SD of the mean?",
        "68%",
        [
            ("95%", "distributions", "two_sd", "95% is within 2 SD."),
            ("50%", "distributions", "median", "50% is below the median, not within 1 SD."),
        ],
    ),
    choice(
        "st_clt",
        "clt",
        "stats",
        "Daily order values are right-skewed. Means of samples of 50 orders will be:",
        "Approximately normal",
        [
            (
                "Right-skewed like the data",
                "clt",
                "same_shape",
                "The CLT: sample means become normal as n grows.",
            ),
            ("Uniform", "distributions", "uniform", "No - means pile up around the true mean."),
        ],
    ),
    choice(
        "st_sampling",
        "sampling",
        "stats",
        "You survey only people who already use your app about 'all phone users'. The main risk is:",
        "Selection bias",
        [
            (
                "Too much precision",
                "sampling",
                "precision",
                "Precision isn't the issue; who was asked is.",
            ),
            (
                "A type II error",
                "hypothesis_testing",
                "type2",
                "That's a testing error, not a sampling problem.",
            ),
        ],
    ),
    choice(
        "st_types",
        "data_types_stats",
        "stats",
        "A satisfaction score from 1 (bad) to 5 (great) is:",
        "Ordinal",
        [
            (
                "Nominal",
                "data_types_stats",
                "nominal",
                "The values have an order, so it's not nominal.",
            ),
            (
                "Continuous",
                "data_types_stats",
                "continuous",
                "Only 5 ordered levels - not continuous.",
            ),
        ],
    ),
    choice(
        "st_causation",
        "corr_causation",
        "stats",
        "Cities with more ice-cream sales have more drownings. Best explanation:",
        "A confounder: hot weather drives both",
        [
            (
                "Ice cream causes drowning",
                "corr_causation",
                "causal",
                "Correlation alone doesn't show causation.",
            ),
            (
                "It must be chance",
                "p_value",
                "chance",
                "It's a real pattern - explained by a third variable.",
            ),
        ],
    ),
    choice(
        "st_power",
        "stat_power",
        "stats",
        "To detect a smaller effect with the same power and α you need:",
        "A larger sample",
        [
            (
                "A smaller sample",
                "stat_power",
                "smaller",
                "Smaller effects need more data, not less.",
            ),
            (
                "A higher p-value",
                "p_value",
                "pvalue",
                "Power is set by sample size, effect size and α.",
            ),
        ],
    ),
)

# -------------------------------------------------------------------- Power BI
_PBI_CTX = (
    ("Product", "Category", "Qty", "Price"),
    ("Pen", "Stationery", "10", "2"),
    ("Notebook", "Stationery", "4", "5"),
    ("SQL book", "Books", "2", "30"),
    ("Stats book", "Books", "1", "28"),
    ("Headphones", "Electronics", "1", "45"),
)
_PBI_NOTE = "Table Sales. [Total Qty] = SUM(Sales[Qty])."

POWERBI: tuple[Task, ...] = (
    number(
        "pbi_total_qty",
        "dax_aggregations",
        "powerbi",
        "What does SUM(Sales[Qty]) return in a card?",
        18,
        wrong=[(5, "dax_aggregations", "countrows", "That's COUNTROWS - SUM adds the Qty values.")],
        context=_PBI_CTX,
        note=_PBI_NOTE,
    ),
    number(
        "pbi_distinct_cat",
        "dax_aggregations",
        "powerbi",
        "DISTINCTCOUNT(Sales[Category]) returns:",
        3,
        wrong=[
            (
                5,
                "dax_aggregations",
                "count",
                "COUNT counts every row; DISTINCTCOUNT counts different values.",
            )
        ],
        context=_PBI_CTX,
        note=_PBI_NOTE,
    ),
    number(
        "pbi_revenue_sumx",
        "iterators",
        "powerbi",
        "Revenue = SUMX(Sales, Sales[Qty] * Sales[Price]). What is it?",
        173,
        wrong=[
            (
                18 * 110,
                "iterators",
                "sum_times_sum",
                "SUM(Qty) × SUM(Price) multiplies the totals - SUMX multiplies row by row, then adds.",
            )
        ],
        context=_PBI_CTX,
        note=_PBI_NOTE,
    ),
    number(
        "pbi_books_row",
        "filter_context",
        "powerbi",
        "A table visual has Category on rows. What does [Total Qty] show in the Books row?",
        3,
        wrong=[
            (
                18,
                "filter_context",
                "ignored_filter",
                "The row's filter context limits the measure to Books.",
            )
        ],
        context=_PBI_CTX,
        note=_PBI_NOTE,
    ),
    number(
        "pbi_pct_total",
        "calculate",
        "powerbi",
        "In the Books row: DIVIDE([Total Qty], CALCULATE([Total Qty], ALL(Sales[Category]))). Answer to 4 decimals.",
        round(3 / 18, 4),
        tol=0.0005,
        wrong=[
            (
                1,
                "calculate",
                "no_all",
                "Without ALL the denominator keeps the Books filter, so it divides Books by Books.",
            ),
            (
                round(18 / 3, 4),
                "calculate",
                "inverted",
                "The fraction is upside down - the row goes on top.",
            ),
        ],
        context=_PBI_CTX,
        note=_PBI_NOTE,
    ),
    number(
        "pbi_ytd",
        "time_intelligence",
        "powerbi",
        "Monthly sales: Jan 100, Feb 120, Mar 90. TOTALYTD([Sales], 'Date'[Date]) for March is:",
        310,
        wrong=[
            (
                90,
                "time_intelligence",
                "month_only",
                "That's March alone - year-to-date accumulates from January.",
            )
        ],
    ),
    choice(
        "pbi_measure_vs_col",
        "dax_basics",
        "powerbi",
        "A total that must change with slicers should be a:",
        "Measure",
        [
            (
                "Calculated column",
                "dax_basics",
                "column",
                "Columns are computed at refresh, row by row; they don't react to slicers.",
            ),
            (
                "New table",
                "pbi_modeling",
                "table",
                "A table isn't the right tool for a responsive total.",
            ),
        ],
    ),
    choice(
        "pbi_star",
        "star_schema",
        "powerbi",
        "Sales (one row per sale) and Product, Customer, Date tables. Sales is the:",
        "Fact table",
        [
            (
                "Dimension table",
                "star_schema",
                "dimension",
                "Dimensions describe; the fact table records events with measures.",
            ),
            (
                "Bridge table",
                "relationships_cardinality",
                "bridge",
                "A bridge resolves many-to-many relationships.",
            ),
        ],
    ),
    choice(
        "pbi_cardinality",
        "relationships_cardinality",
        "powerbi",
        "Product (one row per product) to Sales (many rows per product) is:",
        "One-to-many",
        [
            (
                "Many-to-many",
                "relationships_cardinality",
                "m2m",
                "Each product appears once in Product.",
            ),
            ("One-to-one", "relationships_cardinality", "o2o", "One product has many sales."),
        ],
    ),
    choice(
        "pbi_relationship",
        "pbi_modeling",
        "powerbi",
        "Why does a slicer on Product[Category] filter a Sales visual?",
        "A relationship lets the filter flow from Product to Sales",
        [
            (
                "Power BI copies the column into Sales",
                "pbi_modeling",
                "copy",
                "Nothing is copied; filters flow along relationships.",
            ),
            (
                "The slicer edits the data",
                "pbi_visuals",
                "edit",
                "Slicers filter, they never change data.",
            ),
        ],
    ),
    choice(
        "pbi_get_data",
        "pbi_get_data",
        "powerbi",
        "Where do you remove blank rows and fix data types before modelling?",
        "Power Query",
        [
            (
                "A DAX measure",
                "dax_basics",
                "dax",
                "DAX calculates; cleaning belongs in Power Query.",
            ),
            (
                "The report canvas",
                "pbi_visuals",
                "canvas",
                "Visuals display data, they don't clean it.",
            ),
        ],
    ),
    choice(
        "pbi_interactions",
        "pbi_visuals",
        "powerbi",
        "Clicking a bar filters the other visuals on the page. This is:",
        "Cross-filtering (visual interactions)",
        [
            (
                "Drill-through",
                "pbi_dashboards",
                "drillthrough",
                "Drill-through jumps to another page.",
            ),
            ("Row-level security", "rls", "rls", "RLS restricts data by user."),
        ],
    ),
    choice(
        "pbi_card",
        "pbi_dashboards",
        "powerbi",
        "Best visual for one headline number, like total revenue:",
        "Card",
        [
            ("Table", "pbi_dashboards", "table", "A table buries the number among rows."),
            ("Pie chart", "pbi_visuals", "pie", "A pie shows parts of a whole."),
        ],
    ),
    choice(
        "pbi_rls",
        "rls",
        "powerbi",
        "Regional managers must only see their own region's rows. Use:",
        "Row-level security with a DAX filter per role",
        [
            (
                "A slicer set to their region",
                "pbi_visuals",
                "slicer",
                "A user can just change the slicer - that's not security.",
            ),
            (
                "A separate report per region",
                "pbi_publish",
                "copies",
                "That's hard to maintain; RLS does it in one model.",
            ),
        ],
    ),
    choice(
        "pbi_gateway",
        "pbi_publish",
        "powerbi",
        "Scheduled refresh of a dataset that reads an on-premises SQL Server needs:",
        "An on-premises data gateway",
        [
            ("A bookmark", "pbi_dashboards", "bookmark", "Bookmarks save report state."),
            (
                "Nothing extra",
                "pbi_publish",
                "nothing",
                "The cloud service can't reach your network without a gateway.",
            ),
        ],
    ),
)

# --------------------------------------------------------------------- Tableau
_TAB_CTX = (
    ("Customer", "Region", "Sales", "Profit"),
    ("A", "East", "10", "2"),
    ("A", "East", "20", "6"),
    ("B", "East", "5", "1"),
    ("C", "West", "40", "4"),
    ("C", "West", "15", "9"),
)

TABLEAU: tuple[Task, ...] = (
    number(
        "tab_fixed",
        "lod",
        "tableau",
        "{FIXED [Customer] : SUM([Sales])} on customer A's rows is:",
        30,
        wrong=[
            (10, "lod", "row_value", "That's one row; FIXED sums all of A's rows."),
            (
                35,
                "tab_aggregation",
                "region_total",
                "That's the East total - FIXED here is per customer.",
            ),
        ],
        context=_TAB_CTX,
    ),
    number(
        "tab_region_sum",
        "tab_aggregation",
        "tableau",
        "Region on Rows, SUM([Sales]) on Columns. The West bar is:",
        55,
        wrong=[(27.5, "tab_aggregation", "avg_not_sum", "That's AVG; SUM adds West's rows.")],
        context=_TAB_CTX,
    ),
    number(
        "tab_profit_ratio",
        "tab_calcs",
        "tableau",
        "Profit ratio for the whole table as SUM([Profit]) / SUM([Sales]) (3 decimals).",
        round(22 / 90, 3),
        tol=0.001,
        wrong=[
            (
                round((0.2 + 0.3 + 0.2 + 0.1 + 0.6) / 5, 3),
                "tab_calcs",
                "avg_of_ratios",
                "That averages each row's ratio - aggregate first, then divide.",
            )
        ],
        context=_TAB_CTX,
    ),
    number(
        "tab_running",
        "table_calcs",
        "tableau",
        "Monthly sales are 5, 7, 3. RUNNING_SUM(SUM([Sales])) in the 3rd month is:",
        15,
        wrong=[
            (
                3,
                "table_calcs",
                "no_running",
                "That's the month's own value; the running sum adds every month so far.",
            )
        ],
    ),
    number(
        "tab_pct_total",
        "table_calcs",
        "tableau",
        "Percent of total (table calc) for East SUM(Sales) across regions, in % (1 decimal).",
        round(35 / 90 * 100, 1),
        tol=0.1,
        wrong=[
            (
                round(35 / 55 * 100, 1),
                "table_calcs",
                "wrong_partition",
                "That divides by West's total - percent of total uses the whole table.",
            )
        ],
        context=_TAB_CTX,
    ),
    choice(
        "tab_measure",
        "dims_measures",
        "tableau",
        "Sales is usually a ___ and Region a ___.",
        "measure; dimension",
        [
            (
                "dimension; measure",
                "dims_measures",
                "swapped",
                "Numbers you aggregate are measures; categories are dimensions.",
            ),
            ("parameter; set", "tab_parameters", "param", "Those are separate Tableau objects."),
        ],
    ),
    choice(
        "tab_order_ops",
        "tab_filters",
        "tableau",
        "A dimension filter on Region doesn't change a FIXED LOD's result. To make it apply first:",
        "Add the filter to context",
        [
            (
                "Turn the filter into a measure",
                "dims_measures",
                "measure",
                "The fix is the order of operations, not the field type.",
            ),
            (
                "Use a table calculation",
                "table_calcs",
                "tablecalc",
                "Table calcs run last, after the LOD.",
            ),
        ],
    ),
    choice(
        "tab_extract",
        "tab_connect",
        "tableau",
        "A Tableau extract is:",
        "A snapshot copy of the data that you refresh",
        [
            (
                "A live connection queried on every click",
                "tab_connect",
                "live",
                "That's a live connection.",
            ),
            ("A calculated field", "tab_calcs", "calc", "Calculated fields compute new values."),
        ],
    ),
    choice(
        "tab_bar",
        "tab_basic_charts",
        "tableau",
        "Category on Rows and SUM(Sales) on Columns gives:",
        "A horizontal bar chart",
        [
            (
                "A line chart",
                "tab_basic_charts",
                "line",
                "Lines need a continuous date or axis on Columns.",
            ),
            ("A map", "tab_maps", "map", "Maps need geographic fields."),
        ],
    ),
    choice(
        "tab_param",
        "tab_parameters",
        "tableau",
        "Let users choose N in 'Top N customers'. Use:",
        "A parameter in the Top N filter",
        [
            (
                "A FIXED LOD",
                "lod",
                "lod",
                "LODs compute at a level of detail, they don't take user input.",
            ),
            (
                "An extract filter",
                "tab_connect",
                "extract",
                "Extract filters are fixed at refresh.",
            ),
        ],
    ),
    choice(
        "tab_geo",
        "tab_maps",
        "tableau",
        "To plot State on a map it needs:",
        "A geographic role",
        [
            (
                "A green (continuous) pill",
                "dims_measures",
                "continuous",
                "The role, not the pill colour, makes it mappable.",
            ),
            ("A parameter", "tab_parameters", "param", "Parameters are user inputs."),
        ],
    ),
    choice(
        "tab_action",
        "tab_dashboards",
        "tableau",
        "Clicking a region in one sheet should filter another sheet. Use:",
        "A dashboard filter action",
        [
            (
                "A story point",
                "tab_stories",
                "story",
                "Stories sequence views; actions make them interactive.",
            ),
            (
                "A context filter",
                "tab_filters",
                "context",
                "Context filters change computation order, not interactivity.",
            ),
        ],
    ),
    choice(
        "tab_story",
        "tab_stories",
        "tableau",
        "A Tableau story is:",
        "A sequence of sheets or dashboards that tells a narrative",
        [
            ("A calculated field", "tab_calcs", "calc", "No - stories are made of views."),
            (
                "A data source",
                "tab_connect",
                "source",
                "Stories present analysis, they don't hold data.",
            ),
        ],
    ),
)

# -------------------------------------------------------------- visualisation
_VIZ = "dataviz"
DATAVIZ: tuple[Task, ...] = (
    choice(
        "viz_trend",
        "choosing_chart",
        _VIZ,
        "Show monthly revenue over two years.",
        "Line chart",
        [
            (
                "Pie chart",
                "chart_types",
                "pie",
                "Pies show parts of a whole at one moment, not change over time.",
            ),
            (
                "Scatter plot",
                "rel_plots",
                "scatter",
                "Scatters relate two variables; time trends read best as lines.",
            ),
        ],
    ),
    choice(
        "viz_compare",
        "choosing_chart",
        _VIZ,
        "Compare sales across 12 product categories.",
        "Sorted bar chart",
        [
            (
                "Pie chart with 12 slices",
                "chart_types",
                "pie",
                "Twelve slices are hard to compare - bars are easier.",
            ),
            ("Line chart", "chart_types", "line", "Categories have no order in time; use bars."),
        ],
    ),
    choice(
        "viz_dist",
        "dist_plots",
        _VIZ,
        "See the spread and outliers of salary in 4 departments.",
        "Box plot",
        [
            ("Stacked bar chart", "cat_plots", "stacked", "Stacked bars show totals, not spread."),
            ("Pie chart", "chart_types", "pie", "Pies can't show a distribution."),
        ],
    ),
    choice(
        "viz_hist",
        "chart_types",
        _VIZ,
        "Show how one numeric variable (order value) is distributed.",
        "Histogram",
        [
            (
                "Bar chart of categories",
                "cat_plots",
                "bar",
                "Bars count categories; a histogram bins numbers.",
            ),
            ("Line chart", "chart_types", "line", "Lines connect ordered points over time."),
        ],
    ),
    choice(
        "viz_rel",
        "rel_plots",
        _VIZ,
        "Is there a relation between ad spend and sales across 200 campaigns?",
        "Scatter plot with a trend line",
        [
            ("Pie chart", "chart_types", "pie", "A pie can't show two numeric variables."),
            (
                "Two separate histograms",
                "dist_plots",
                "hists",
                "Histograms show each variable alone, not the relation.",
            ),
        ],
    ),
    choice(
        "viz_zero",
        "axes_titles",
        _VIZ,
        "Where should the value axis of a bar chart start?",
        "At zero",
        [
            (
                "At the smallest value",
                "axes_titles",
                "truncated",
                "A truncated bar axis exaggerates differences.",
            )
        ],
    ),
    choice(
        "viz_palette",
        "color_access",
        _VIZ,
        "Colour a map by unemployment rate (low → high).",
        "A sequential palette",
        [
            (
                "A categorical palette",
                "color_access",
                "categorical",
                "Categorical colours imply unrelated groups, not an order.",
            ),
            (
                "Red vs green only",
                "color_access",
                "redgreen",
                "Red/green is hard for colour-blind readers.",
            ),
        ],
    ),
    choice(
        "viz_title",
        "annotation",
        _VIZ,
        "The best chart title is:",
        "Revenue fell 12% after the price change",
        [
            (
                "Revenue by month",
                "annotation",
                "descriptive",
                "A descriptive title makes the reader find the point.",
            ),
            ("Chart 3", "annotation", "label", "Says nothing."),
        ],
    ),
    choice(
        "viz_story",
        "storytelling",
        _VIZ,
        "An executive update should open with:",
        "The main insight and the decision it supports",
        [
            (
                "Every chart you made",
                "storytelling",
                "all_charts",
                "Lead with the point; supporting charts come after.",
            ),
            ("The methodology", "storytelling", "method", "Method belongs in the appendix."),
        ],
    ),
    choice(
        "viz_kpi",
        "dashboards",
        _VIZ,
        "Where does the most important KPI go on a dashboard?",
        "Top-left",
        [
            ("Bottom-right", "dashboards", "bottom", "Readers scan from the top-left."),
            ("In a tooltip", "dashboards", "tooltip", "Hidden KPIs get missed."),
        ],
    ),
    choice(
        "viz_subplots",
        "subplots",
        _VIZ,
        "plt.subplots(2, 3) creates how many axes?",
        "6",
        [
            ("5", "subplots", "five", "2 rows × 3 columns = 6."),
            ("2", "subplots", "rows", "That's the number of rows."),
        ],
    ),
    choice(
        "viz_mpl",
        "matplotlib_basics",
        _VIZ,
        "fig, ax = plt.subplots(); which call draws a line?",
        "ax.plot(x, y)",
        [
            ("ax.line(x, y)", "matplotlib_basics", "line", "There is no ax.line - use ax.plot."),
            (
                "plt.show(x, y)",
                "matplotlib_basics",
                "show",
                "show() displays the figure, it doesn't draw data.",
            ),
        ],
    ),
    choice(
        "viz_sns",
        "seaborn_basics",
        _VIZ,
        "sns.barplot(data=df, x='region', y='sales') draws, by default:",
        "The mean sales per region with a confidence interval",
        [
            (
                "The total sales per region",
                "seaborn_basics",
                "sum",
                "barplot's default estimator is the mean.",
            ),
            ("One bar per row", "cat_plots", "rows", "Rows are aggregated per category."),
        ],
    ),
    choice(
        "viz_cat",
        "cat_plots",
        _VIZ,
        "Long category names on a bar chart are easiest to read on:",
        "Horizontal bars",
        [
            ("Vertical bars", "cat_plots", "vertical", "Vertical bars force slanted labels."),
            ("A pie chart", "chart_types", "pie", "Pies don't fix label length."),
        ],
    ),
    choice(
        "viz_types",
        "chart_types",
        _VIZ,
        "Market share of 3 brands this year - which is acceptable?",
        "Bar or pie chart",
        [
            ("Line chart", "chart_types", "line", "One time point has no line to draw."),
            ("Histogram", "dist_plots", "hist", "Histograms bin numeric data."),
        ],
    ),
)

# ------------------------------------------------------------------------- Git
_GIT = "git"
GIT: tuple[Task, ...] = (
    choice(
        "git_stage",
        "stage_commit",
        _GIT,
        "You edited a.py. Which sequence records it in history?",
        "git add a.py, then git commit -m 'msg'",
        [
            (
                "git commit -m 'msg' only",
                "stage_commit",
                "no_add",
                "Nothing is staged yet - commit records only staged changes.",
            ),
            ("git push", "push_pull", "push", "Push sends commits; it doesn't create one."),
        ],
    ),
    choice(
        "git_pull",
        "push_pull",
        _GIT,
        "git push is rejected: the remote has commits you don't. First:",
        "git pull (fetch and merge), then push",
        [
            ("git push --force", "undo", "force", "Force-pushing overwrites others' work."),
            (
                "Delete the remote",
                "remotes",
                "delete",
                "Never needed - integrate the remote changes.",
            ),
        ],
    ),
    choice(
        "git_branch",
        "branches",
        _GIT,
        "Start work on a new feature without touching main:",
        "git switch -c feature",
        [
            (
                "git merge feature",
                "merge",
                "merge",
                "Merge combines branches; it doesn't create one.",
            ),
            ("git clone", "init_clone", "clone", "Clone copies a repository."),
        ],
    ),
    choice(
        "git_conflict",
        "merge_conflicts",
        _GIT,
        "After editing the conflict markers in a file you:",
        "git add the file, then commit",
        [
            ("git reset --hard", "undo", "reset", "That throws your resolution away."),
            ("git push --force", "push_pull", "force", "First finish the merge with add + commit."),
        ],
    ),
    choice(
        "git_revert",
        "undo",
        _GIT,
        "Undo a commit that teammates have already pulled:",
        "git revert <commit>",
        [
            (
                "git reset --hard and push --force",
                "undo",
                "rewrite",
                "Rewriting shared history breaks your teammates' copies.",
            )
        ],
    ),
    choice(
        "git_ignore",
        "gitignore",
        _GIT,
        "data.csv is already committed. You add data.csv to .gitignore. Git now:",
        "Still tracks data.csv until you git rm --cached it",
        [
            (
                "Stops tracking it immediately",
                "gitignore",
                "auto_untrack",
                ".gitignore only affects untracked files.",
            )
        ],
    ),
    choice(
        "git_ff",
        "merge",
        _GIT,
        "main has no new commits since feature branched. Merging feature is a:",
        "Fast-forward",
        [
            ("Conflict", "merge_conflicts", "conflict", "Conflicts need changes on both sides."),
            ("Rebase", "branches", "rebase", "Rebase is a different operation."),
        ],
    ),
    choice(
        "git_diff",
        "log_diff",
        _GIT,
        "See your unstaged changes line by line:",
        "git diff",
        [
            ("git log", "log_diff", "log", "log lists commits."),
            ("git status", "stage_commit", "status", "status lists files, not lines."),
        ],
    ),
    choice(
        "git_origin",
        "remotes",
        _GIT,
        "'origin' usually refers to:",
        "The remote repository you cloned from",
        [
            ("The main branch", "branches", "branch", "main is a branch; origin is a remote."),
            (
                "Your first commit",
                "vcs_idea",
                "commit",
                "Commits have hashes, not names like origin.",
            ),
        ],
    ),
    choice(
        "git_pr",
        "pull_requests",
        _GIT,
        "A pull request is for:",
        "Reviewing and merging a branch",
        [
            ("Downloading a repository", "init_clone", "clone", "That's git clone."),
            ("Deleting a branch", "branches", "delete", "PRs propose changes for review."),
        ],
    ),
    choice(
        "git_config",
        "git_config",
        _GIT,
        "Set your name on all your commits on this machine:",
        'git config --global user.name "Asha"',
        [
            (
                'git config user.name "Asha" in every repo',
                "git_config",
                "local",
                "--global sets it once for all repos.",
            )
        ],
    ),
    choice(
        "git_init",
        "init_clone",
        _GIT,
        "Turn the current folder into a new repository:",
        "git init",
        [
            ("git clone", "init_clone", "clone", "clone copies an existing repo."),
            ("git commit", "stage_commit", "commit", "You need a repository first."),
        ],
    ),
    choice(
        "git_vcs",
        "vcs_idea",
        _GIT,
        "A commit is:",
        "A saved snapshot of the project with a message",
        [
            ("A copy of a branch", "branches", "branch", "A branch points to a commit."),
            ("A remote server", "remotes", "remote", "Remotes host repositories."),
        ],
    ),
)

# ------------------------------------------------------------ data engineering
_DE = "data_eng"
DATA_ENG: tuple[Task, ...] = (
    number(
        "de_scd2_rows",
        "scd",
        _DE,
        "A customer moved city twice. How many rows do they have in an SCD type 2 dimension?",
        3,
        wrong=[
            (1, "scd", "type1", "One row is type 1 (overwrite); type 2 adds a row per change."),
            (2, "scd", "changes_only", "Type 2 keeps the original row plus one per change."),
        ],
    ),
    number(
        "de_rerun_rows",
        "idempotency",
        _DE,
        "A daily job does a plain INSERT of 500 rows. It fails after loading, and the retry runs it again. How many rows for that day?",
        1000,
        wrong=[
            (
                500,
                "idempotency",
                "assumed_idempotent",
                "Plain INSERT isn't idempotent - delete-then-insert or MERGE would leave 500.",
            )
        ],
    ),
    number(
        "de_partitions",
        "partitioning",
        _DE,
        "A table is partitioned by day (30 partitions). A query filters on one day. How many partitions are scanned?",
        1,
        wrong=[(30, "partitioning", "full_scan", "Partition pruning skips the other 29 days.")],
    ),
    number(
        "de_watermark",
        "incremental_loads",
        _DE,
        "Watermark = 2025-06-01. Source rows dated 05-30, 06-01, 06-02, 06-03. How many does the next load read (strictly after)?",
        2,
        wrong=[
            (
                3,
                "incremental_loads",
                "inclusive",
                "'>=' re-reads the watermark day's row - use strictly after.",
            ),
            (4, "incremental_loads", "full", "That's a full load."),
        ],
    ),
    choice(
        "de_parquet",
        "file_formats",
        _DE,
        "Best file format for analytical queries on a large table:",
        "Parquet",
        [
            ("CSV", "file_formats", "csv", "CSV is row-based and untyped - slow to scan columns."),
            ("JSON", "file_formats", "json", "JSON is verbose and row-based."),
        ],
    ),
    choice(
        "de_elt",
        "etl_elt",
        _DE,
        "In ELT, where are transformations run?",
        "Inside the warehouse, after loading",
        [
            ("Before extracting", "etl_elt", "before", "Extraction comes first in both."),
            (
                "In the BI tool",
                "pbi_modeling",
                "bi",
                "BI tools visualise; the warehouse transforms.",
            ),
        ],
    ),
    choice(
        "de_warehouse",
        "warehouses",
        _DE,
        "BigQuery and Snowflake separate:",
        "Storage from compute",
        [
            (
                "Rows from columns",
                "file_formats",
                "rows",
                "That's columnar storage, a different idea.",
            ),
            ("SQL from Python", "warehouses", "lang", "Not the key design choice."),
        ],
    ),
    choice(
        "de_stream",
        "batch_stream",
        _DE,
        "Flag fraudulent card payments within seconds:",
        "Stream processing",
        [("A nightly batch job", "batch_stream", "batch", "A batch would flag fraud hours later.")],
    ),
    choice(
        "de_dedup",
        "dedup_keys",
        _DE,
        "Keep only each customer's latest row:",
        "ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) = 1",
        [
            (
                "SELECT DISTINCT *",
                "dedup_keys",
                "distinct",
                "DISTINCT only removes fully identical rows.",
            ),
            (
                "... ORDER BY updated_at ASC) = 1",
                "dedup_keys",
                "ascending",
                "Ascending keeps the oldest row.",
            ),
        ],
    ),
    choice(
        "de_test",
        "data_quality",
        _DE,
        "Every orders.customer_id must exist in customers. Which test?",
        "A relationships (referential integrity) test",
        [
            ("A unique test", "dbt_tests", "unique", "Uniqueness doesn't check the other table."),
            ("A not_null test", "dbt_tests", "not_null", "Not-null allows ids that don't exist."),
        ],
    ),
    choice(
        "de_ref",
        "dbt_models",
        _DE,
        "Why use {{ ref('stg_orders') }} instead of a table name in dbt?",
        "dbt learns the dependency and builds models in order",
        [
            (
                "It makes the query faster",
                "dbt_models",
                "speed",
                "ref is about lineage and order, not speed.",
            ),
            ("It skips tests", "dbt_tests", "skip", "Tests run regardless."),
        ],
    ),
    choice(
        "de_dbt_tests",
        "dbt_tests",
        _DE,
        "dbt's four built-in generic tests are unique, not_null, accepted_values and:",
        "relationships",
        [
            (
                "freshness",
                "data_quality",
                "freshness",
                "Freshness is a source check, not a generic test.",
            ),
            ("volume", "data_quality", "volume", "Not a built-in generic test."),
        ],
    ),
    choice(
        "de_dag",
        "orchestration",
        _DE,
        "Airflow: extract >> transform >> load. If transform fails, load:",
        "Does not run",
        [
            (
                "Runs anyway",
                "orchestration",
                "runs",
                "Downstream tasks wait for upstream success by default.",
            ),
            ("Runs before transform", "orchestration", "order", ">> sets the order."),
        ],
    ),
    choice(
        "de_spark",
        "spark_basics",
        _DE,
        "df.filter(...).select(...) in Spark runs when:",
        "An action like count() or write() is called",
        [
            ("Immediately", "spark_basics", "eager", "Transformations are lazy."),
            ("Never", "spark_basics", "never", "An action triggers the job."),
        ],
    ),
    choice(
        "de_docker",
        "containers_cloud",
        _DE,
        "A Docker image packages:",
        "Your code with its dependencies",
        [
            (
                "Only the data",
                "containers_cloud",
                "data",
                "Images hold code and runtime, not data.",
            ),
            ("A cloud account", "containers_cloud", "cloud", "It runs anywhere Docker runs."),
        ],
    ),
    choice(
        "de_grain",
        "dimensional_modeling",
        _DE,
        "The grain of a fact table is:",
        "What one row represents",
        [
            (
                "How many columns it has",
                "dimensional_modeling",
                "columns",
                "Grain is about meaning, not width.",
            ),
            ("How often it refreshes", "orchestration", "refresh", "That's scheduling."),
        ],
    ),
    choice(
        "de_pk",
        "de_data_modeling",
        _DE,
        "A primary key must be:",
        "Unique and not null",
        [
            ("A number", "de_data_modeling", "number", "Keys can be text."),
            ("The first column", "de_data_modeling", "first", "Position doesn't matter."),
        ],
    ),
)

# ----------------------------------------- the rest of Excel, pandas, Python
_SS = "spreadsheets"
MISC: tuple[Task, ...] = (
    number(
        "xl_range_cells",
        "cells_ranges",
        _SS,
        "How many cells are in E2:F11?",
        20,
        wrong=[
            (
                10,
                "cells_ranges",
                "one_column",
                "The range spans two columns (E and F), 10 rows each.",
            )
        ],
    ),
    choice(
        "xl_cf",
        "conditional_formatting",
        _SS,
        "Highlight units above 10 in green without changing them:",
        "A conditional formatting rule (cell value > 10)",
        [
            (
                "An IF formula in the cell",
                "logical_functions",
                "if",
                "IF changes the value; formatting only changes the look.",
            )
        ],
    ),
    choice(
        "xl_chart",
        "charts_ss",
        _SS,
        "Monthly units for a year in Excel - which chart?",
        "Line chart",
        [("Pie chart", "charts_ss", "pie", "Pies don't show change over time.")],
    ),
    choice(
        "xl_table",
        "excel_tables",
        _SS,
        "A structured reference to the Units column of a table called Sales:",
        "Sales[Units]",
        [
            (
                "E2:E11",
                "cells_ranges",
                "range",
                "That's a plain range; it won't grow with new rows.",
            ),
            ("$E$2", "abs_refs", "cell", "That's one cell."),
        ],
    ),
    choice(
        "xl_pq",
        "power_query",
        _SS,
        "Combine 12 monthly files that share the same columns in Power Query:",
        "Append them (combine files from a folder)",
        [
            (
                "Merge on a key",
                "power_query",
                "merge",
                "Merge joins side by side; append stacks rows.",
            ),
            (
                "Copy and paste each month",
                "power_query",
                "manual",
                "Not repeatable - Power Query re-runs on refresh.",
            ),
        ],
    ),
    choice(
        "pd_read_csv",
        "read_write_data",
        "python_data",
        "Read sales.csv into a DataFrame:",
        "pd.read_csv('sales.csv')",
        [
            ("pd.open('sales.csv')", "read_write_data", "open", "There is no pd.open."),
            (
                "df.load('sales.csv')",
                "read_write_data",
                "load",
                "DataFrames are created by pd.read_*.",
            ),
        ],
    ),
    choice(
        "pd_plot",
        "plot_pandas",
        "python_data",
        "df.plot(x='month', y='sales') draws, by default:",
        "A line chart",
        [
            ("A bar chart", "plot_pandas", "bar", "Use kind='bar' for bars."),
            ("A histogram", "plot_pandas", "hist", "Histograms are .plot.hist()."),
        ],
    ),
    choice(
        "py_modules",
        "modules",
        "python",
        "Use sqrt from the math module:",
        "import math, then math.sqrt(16)",
        [
            (
                "sqrt(16) with no import",
                "modules",
                "no_import",
                "sqrt isn't a built-in; import math first.",
            )
        ],
    ),
    choice(
        "py_oop",
        "oop_lite",
        "python",
        "In class Order: def total(self): ..., self is:",
        "The instance the method is called on",
        [
            ("The class itself", "oop_lite", "class", "That would be cls in a classmethod."),
            ("A global variable", "scope", "global", "self is the first parameter of the method."),
        ],
    ),
    choice(
        "py_venv",
        "venv_pip",
        "python",
        "Why create a virtual environment for a project?",
        "To keep its package versions separate from other projects",
        [
            (
                "To make Python faster",
                "venv_pip",
                "speed",
                "venvs isolate dependencies; they don't change speed.",
            )
        ],
    ),
    choice(
        "py_scope",
        "scope",
        "python",
        "x = 1; def f(): x = 2; f(); print(x) prints:",
        "1",
        [
            (
                "2",
                "scope",
                "global",
                "Assigning inside f makes a new local x; the global x is unchanged.",
            )
        ],
    ),
    choice(
        "py_kwargs",
        "args_kwargs",
        "python",
        "def f(*args, **kwargs): f(1, 2, a=3). kwargs is:",
        "{'a': 3}",
        [
            ("(1, 2)", "args_kwargs", "args", "That's args; keyword arguments go to kwargs."),
            (
                "[1, 2, 3]",
                "args_kwargs",
                "list",
                "Positional and keyword arguments are kept apart.",
            ),
        ],
    ),
    choice(
        "py_csv",
        "files_csv",
        "python",
        "Read a CSV file row by row with the standard library:",
        "csv.reader(open('f.csv'))",
        [
            (
                "open('f.csv').split(',')",
                "strings",
                "split",
                "A file object has no split; read lines, or use csv.",
            )
        ],
    ),
    choice(
        "py_jupyter",
        "jupyter",
        "python",
        "In Jupyter, the last expression in a cell is:",
        "Displayed as the cell's output",
        [
            (
                "Ignored unless printed",
                "jupyter",
                "ignored",
                "Jupyter shows the last expression's value automatically.",
            )
        ],
    ),
    choice(
        "sql_alter",
        "ddl",
        "sql",
        "Add a nullable email column to an existing customers table:",
        "ALTER TABLE customers ADD COLUMN email TEXT",
        [
            (
                "UPDATE customers SET email = NULL",
                "ddl",
                "dml_not_ddl",
                "UPDATE changes rows; changing the table's structure is ALTER TABLE.",
            ),
            (
                "CREATE TABLE customers (email TEXT)",
                "ddl",
                "recreate",
                "CREATE TABLE makes a new table - it fails because customers exists.",
            ),
        ],
    ),
    choice(
        "sql_index",
        "indexes_sql",
        "sql",
        "An index on orders(customer_id) mainly speeds up:",
        "WHERE customer_id = 42 and joins on customer_id",
        [
            (
                "SELECT * FROM orders with no filter",
                "indexes_sql",
                "full_scan",
                "Reading every row can't use the index.",
            ),
            (
                "INSERT INTO orders",
                "indexes_sql",
                "writes",
                "Indexes make writes a little slower, not faster.",
            ),
        ],
    ),
    choice(
        "py_repl",
        "setup_repl",
        "python",
        "Typing 2 + 3 at the Python >>> prompt:",
        "Shows 5",
        [
            (
                "Does nothing until you save a file",
                "setup_repl",
                "file",
                "The REPL evaluates each line immediately.",
            )
        ],
    ),
)

TASKS: tuple[Task, ...] = STATS + POWERBI + TABLEAU + DATAVIZ + GIT + DATA_ENG + MISC
