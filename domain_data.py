"""Curated seed prerequisite graphs for the data-analytics / job-skills track,
plus target-role skill profiles.

Each domain is ``(concepts, prereqs)`` - a hand-authored DAG.  Kept in a data
module so :mod:`domains` stays logic.  A ``role`` is a target job: a weighted
set of goal concepts across domains (used by the role-gap sequencing claim).
"""

from __future__ import annotations

from dataclasses import dataclass

C = tuple[str, str]  # (concept id, label)
E = tuple[str, str]  # (earlier, later)


@dataclass(frozen=True, slots=True)
class SeedSpec:
    name: str
    hint: str  # harvester domain: cs | web | math | science | general
    aliases: tuple[str, ...]
    concepts: tuple[C, ...]
    prereqs: tuple[E, ...]
    beginner: bool = False  # part of the zero-knowledge on-ramp


# --------------------------------------------------------------------------- #
FOUNDATIONS = SeedSpec(
    name="foundations",
    hint="general",
    beginner=True,
    aliases=("beginner", "no experience", "complete beginner", "from scratch", "zero", "basics"),
    concepts=(
        ("files_folders", "Files, folders & the operating system"),
        ("web_browser", "Using the web & installing tools"),
        ("what_is_data", "What data is (rows, columns, types)"),
        ("tables", "Reading a table / dataset"),
        ("spreadsheet_intro", "Opening a spreadsheet"),
        ("cell_formula", "A first formula"),
        ("if_then", "If-then thinking"),
        ("algorithm_idea", "What an algorithm is"),
        ("terminal_intro", "The command line, gently"),
    ),
    prereqs=(
        ("files_folders", "web_browser"),
        ("files_folders", "terminal_intro"),
        ("what_is_data", "tables"),
        ("tables", "spreadsheet_intro"),
        ("spreadsheet_intro", "cell_formula"),
        ("if_then", "algorithm_idea"),
        ("cell_formula", "if_then"),
    ),
)

SPREADSHEETS = SeedSpec(
    name="spreadsheets",
    hint="general",
    aliases=("excel", "google sheets", "spreadsheet", "sheets"),
    concepts=(
        ("cells_ranges", "Cells, ranges & references"),
        ("formulas", "Formulas & the formula bar"),
        ("agg_functions", "SUM / AVERAGE / COUNT / MIN / MAX"),
        ("abs_refs", "Relative vs absolute references"),
        ("text_functions", "Text functions (LEFT, TRIM, CONCAT)"),
        ("date_functions_ss", "Date functions"),
        ("logical_functions", "IF / IFS / AND / OR"),
        ("lookups", "VLOOKUP / XLOOKUP / INDEX-MATCH"),
        ("sort_filter", "Sorting & filtering"),
        ("conditional_formatting", "Conditional formatting"),
        ("pivot_tables", "Pivot tables"),
        ("charts_ss", "Charts"),
        ("cleaning_ss", "Cleaning messy data"),
    ),
    prereqs=(
        ("cells_ranges", "formulas"),
        ("formulas", "agg_functions"),
        ("formulas", "abs_refs"),
        ("formulas", "text_functions"),
        ("formulas", "date_functions_ss"),
        ("formulas", "logical_functions"),
        ("logical_functions", "lookups"),
        ("abs_refs", "lookups"),
        ("agg_functions", "pivot_tables"),
        ("sort_filter", "pivot_tables"),
        ("agg_functions", "charts_ss"),
        ("text_functions", "cleaning_ss"),
        ("sort_filter", "cleaning_ss"),
    ),
)

SQL = SeedSpec(
    name="sql",
    hint="cs",
    aliases=("sql", "postgres", "mysql", "queries", "database", "databases"),
    concepts=(
        ("select_from", "SELECT ... FROM"),
        ("where", "WHERE & comparison operators"),
        ("order_limit", "ORDER BY & LIMIT"),
        ("distinct", "DISTINCT"),
        ("null_logic", "NULL & three-valued logic"),
        ("aggregates", "COUNT / SUM / AVG / MIN / MAX"),
        ("group_by", "GROUP BY"),
        ("having", "HAVING"),
        ("inner_join", "INNER JOIN"),
        ("outer_join", "LEFT / RIGHT / FULL JOIN"),
        ("self_join", "Self joins"),
        ("subqueries", "Subqueries"),
        ("ctes", "Common table expressions (WITH)"),
        ("case_when", "CASE WHEN"),
        ("string_fns_sql", "String functions"),
        ("date_fns_sql", "Date / time functions"),
        ("window_functions", "Window functions (OVER, PARTITION BY)"),
        ("set_ops", "UNION / INTERSECT / EXCEPT"),
        ("ddl", "CREATE / INSERT / UPDATE / DELETE"),
        ("indexes_sql", "Indexes & query performance"),
    ),
    prereqs=(
        ("select_from", "where"),
        ("select_from", "distinct"),
        ("where", "order_limit"),
        ("where", "null_logic"),
        ("select_from", "aggregates"),
        ("aggregates", "group_by"),
        ("group_by", "having"),
        ("where", "inner_join"),
        ("inner_join", "outer_join"),
        ("inner_join", "self_join"),
        ("where", "subqueries"),
        ("subqueries", "ctes"),
        ("where", "case_when"),
        ("select_from", "string_fns_sql"),
        ("select_from", "date_fns_sql"),
        ("group_by", "window_functions"),
        ("ctes", "window_functions"),
        ("select_from", "set_ops"),
        ("select_from", "ddl"),
        ("ddl", "indexes_sql"),
        ("inner_join", "indexes_sql"),
    ),
)

PYTHON = SeedSpec(
    name="python",
    hint="cs",
    aliases=("python", "learn python", "python programming", "scripting"),
    concepts=(
        ("setup_repl", "Install Python & the REPL"),
        ("variables", "Variables & data types"),
        ("operators", "Operators & expressions"),
        ("strings", "Strings"),
        ("fstrings", "f-strings & formatting"),
        ("conditionals", "if / elif / else"),
        ("loops", "for & while loops"),
        ("lists", "Lists"),
        ("dicts", "Dictionaries"),
        ("tuples_sets", "Tuples & sets"),
        ("comprehensions", "List / dict comprehensions"),
        ("functions", "Functions"),
        ("args_kwargs", "*args / **kwargs & defaults"),
        ("scope", "Scope & closures"),
        ("modules", "Modules, imports & the standard library"),
        ("exceptions", "Exceptions (try / except)"),
        ("files_csv", "Reading & writing files / CSV"),
        ("venv_pip", "Virtual environments & pip"),
        ("jupyter", "Jupyter notebooks"),
        ("oop_lite", "Classes (a working minimum)"),
    ),
    prereqs=(
        ("setup_repl", "variables"),
        ("variables", "operators"),
        ("variables", "strings"),
        ("strings", "fstrings"),
        ("operators", "conditionals"),
        ("conditionals", "loops"),
        ("variables", "lists"),
        ("lists", "dicts"),
        ("lists", "tuples_sets"),
        ("loops", "comprehensions"),
        ("lists", "comprehensions"),
        ("loops", "functions"),
        ("functions", "args_kwargs"),
        ("functions", "scope"),
        ("functions", "modules"),
        ("functions", "exceptions"),
        ("exceptions", "files_csv"),
        ("modules", "venv_pip"),
        ("venv_pip", "jupyter"),
        ("functions", "oop_lite"),
    ),
)

PYTHON_DATA = SeedSpec(
    name="python_data",
    hint="cs",
    aliases=("pandas", "numpy", "python for data", "data wrangling", "data cleaning"),
    concepts=(
        ("numpy_arrays", "NumPy arrays"),
        ("array_ops", "Vectorised array operations"),
        ("pandas_series", "pandas Series"),
        ("dataframe", "DataFrame basics"),
        ("read_write_data", "read_csv / read_excel / read_sql"),
        ("selecting", "Selecting with loc & iloc"),
        ("filtering", "Boolean filtering"),
        ("new_columns", "Creating & transforming columns"),
        ("missing_data", "Missing data (NaN, fillna, dropna)"),
        ("groupby_agg", "groupby + aggregate"),
        ("merge_join", "merge / join"),
        ("concat", "concat & append"),
        ("pivot_melt", "pivot_table / melt (reshaping)"),
        ("apply_map", "apply / map / vectorised functions"),
        ("datetime_pd", "Datetime handling"),
        ("string_methods_pd", "String methods (.str)"),
        ("sort_rank", "Sorting & ranking"),
        ("plot_pandas", "Quick plots from pandas"),
    ),
    prereqs=(
        ("numpy_arrays", "array_ops"),
        ("numpy_arrays", "pandas_series"),
        ("pandas_series", "dataframe"),
        ("dataframe", "read_write_data"),
        ("dataframe", "selecting"),
        ("selecting", "filtering"),
        ("filtering", "new_columns"),
        ("new_columns", "missing_data"),
        ("filtering", "groupby_agg"),
        ("dataframe", "merge_join"),
        ("dataframe", "concat"),
        ("groupby_agg", "pivot_melt"),
        ("new_columns", "apply_map"),
        ("new_columns", "datetime_pd"),
        ("new_columns", "string_methods_pd"),
        ("filtering", "sort_rank"),
        ("groupby_agg", "plot_pandas"),
    ),
)

STATS = SeedSpec(
    name="stats",
    hint="science",
    aliases=("statistics", "stats", "probability", "hypothesis testing", "a/b testing", "ab test"),
    concepts=(
        ("data_types_stats", "Categorical vs numeric data"),
        ("descriptive", "Mean, median, mode, std dev"),
        ("quartiles", "Percentiles, quartiles & outliers"),
        ("probability_basics", "Probability basics"),
        ("distributions", "Common distributions (normal, binomial)"),
        ("sampling", "Populations, samples & bias"),
        ("clt", "Sampling distribution & the CLT"),
        ("standard_error", "Standard error"),
        ("confidence_intervals", "Confidence intervals"),
        ("hypothesis_testing", "Hypothesis testing framework"),
        ("p_value", "p-values & significance"),
        ("t_test", "t-tests"),
        ("chi_square", "Chi-square test"),
        ("correlation", "Correlation"),
        ("corr_causation", "Correlation vs causation"),
        ("linear_regression", "Simple linear regression"),
        ("r_squared", "R-squared & residuals"),
        ("ab_testing", "A/B testing"),
        ("stat_power", "Statistical power & sample size"),
    ),
    prereqs=(
        ("data_types_stats", "descriptive"),
        ("descriptive", "quartiles"),
        ("probability_basics", "distributions"),
        ("descriptive", "distributions"),
        ("sampling", "clt"),
        ("distributions", "clt"),
        ("clt", "standard_error"),
        ("standard_error", "confidence_intervals"),
        ("confidence_intervals", "hypothesis_testing"),
        ("hypothesis_testing", "p_value"),
        ("p_value", "t_test"),
        ("p_value", "chi_square"),
        ("descriptive", "correlation"),
        ("correlation", "corr_causation"),
        ("correlation", "linear_regression"),
        ("linear_regression", "r_squared"),
        ("hypothesis_testing", "ab_testing"),
        ("t_test", "ab_testing"),
        ("hypothesis_testing", "stat_power"),
    ),
)

DATAVIZ = SeedSpec(
    name="dataviz",
    hint="cs",
    aliases=("data visualization", "data viz", "matplotlib", "seaborn", "charts", "dashboards"),
    concepts=(
        ("chart_types", "Chart types & what they show"),
        ("choosing_chart", "Choosing the right chart"),
        ("matplotlib_basics", "matplotlib basics"),
        ("axes_titles", "Axes, labels, titles, legends"),
        ("subplots", "Subplots & figure layout"),
        ("seaborn_basics", "seaborn"),
        ("dist_plots", "Distribution plots (hist, box, violin)"),
        ("cat_plots", "Categorical plots (bar, count)"),
        ("rel_plots", "Relationship plots (scatter, line)"),
        ("color_access", "Colour & accessibility"),
        ("annotation", "Annotating a chart"),
        ("storytelling", "Telling a story with data"),
        ("dashboards", "Dashboards (Tableau / Power BI idea)"),
    ),
    prereqs=(
        ("chart_types", "choosing_chart"),
        ("matplotlib_basics", "axes_titles"),
        ("axes_titles", "subplots"),
        ("matplotlib_basics", "seaborn_basics"),
        ("seaborn_basics", "dist_plots"),
        ("seaborn_basics", "cat_plots"),
        ("seaborn_basics", "rel_plots"),
        ("axes_titles", "color_access"),
        ("axes_titles", "annotation"),
        ("choosing_chart", "storytelling"),
        ("annotation", "storytelling"),
        ("storytelling", "dashboards"),
    ),
)

DSA_PYTHON = SeedSpec(
    name="dsa_python",
    hint="cs",
    aliases=(
        "dsa",
        "data structures",
        "algorithms",
        "leetcode",
        "coding interview",
        "dsa with python",
    ),
    concepts=(
        ("big_o", "Big-O notation"),
        ("py_collections_perf", "List / dict / set performance in Python"),
        ("strings_dsa", "String manipulation"),
        ("two_pointers", "Two pointers"),
        ("sliding_window", "Sliding window"),
        ("hashing_dsa", "Hash maps & frequency counting"),
        ("recursion_dsa", "Recursion"),
        ("sorting_dsa", "Sorting"),
        ("binary_search_dsa", "Binary search"),
        ("stack_queue", "Stacks & queues"),
        ("linked_list", "Linked lists"),
        ("trees_dsa", "Trees & traversals"),
        ("bst_dsa", "Binary search trees"),
        ("heap_dsa", "Heaps / priority queues"),
        ("graph_repr", "Graph representations"),
        ("bfs_dfs", "BFS & DFS"),
        ("topo_sort_dsa", "Topological sort"),
        ("dynamic_programming_dsa", "Dynamic programming"),
        ("greedy_dsa", "Greedy algorithms"),
        ("backtracking_dsa", "Backtracking"),
    ),
    prereqs=(
        ("py_collections_perf", "hashing_dsa"),
        ("big_o", "sorting_dsa"),
        ("big_o", "binary_search_dsa"),
        ("py_collections_perf", "strings_dsa"),
        ("strings_dsa", "two_pointers"),
        ("two_pointers", "sliding_window"),
        ("sorting_dsa", "binary_search_dsa"),
        ("recursion_dsa", "trees_dsa"),
        ("recursion_dsa", "backtracking_dsa"),
        ("recursion_dsa", "dynamic_programming_dsa"),
        ("py_collections_perf", "stack_queue"),
        ("stack_queue", "linked_list"),
        ("trees_dsa", "bst_dsa"),
        ("trees_dsa", "heap_dsa"),
        ("hashing_dsa", "graph_repr"),
        ("trees_dsa", "graph_repr"),
        ("graph_repr", "bfs_dfs"),
        ("bfs_dfs", "topo_sort_dsa"),
        ("sorting_dsa", "greedy_dsa"),
        ("dynamic_programming_dsa", "greedy_dsa"),
        ("backtracking_dsa", "dynamic_programming_dsa"),
    ),
)

GIT = SeedSpec(
    name="git",
    hint="cs",
    aliases=("git", "github", "version control", "source control"),
    concepts=(
        ("vcs_idea", "What version control is"),
        ("git_config", "Install & configure git"),
        ("init_clone", "init / clone"),
        ("stage_commit", "Staging & committing"),
        ("log_diff", "log / diff / status"),
        ("gitignore", ".gitignore"),
        ("branches", "Branches"),
        ("merge", "Merging"),
        ("merge_conflicts", "Resolving merge conflicts"),
        ("remotes", "Remotes"),
        ("push_pull", "push / pull / fetch"),
        ("pull_requests", "Pull requests & code review"),
        ("undo", "Undo: revert / reset / restore"),
    ),
    prereqs=(
        ("vcs_idea", "git_config"),
        ("git_config", "init_clone"),
        ("init_clone", "stage_commit"),
        ("stage_commit", "log_diff"),
        ("stage_commit", "gitignore"),
        ("stage_commit", "branches"),
        ("branches", "merge"),
        ("merge", "merge_conflicts"),
        ("init_clone", "remotes"),
        ("remotes", "push_pull"),
        ("push_pull", "pull_requests"),
        ("stage_commit", "undo"),
    ),
)

SEEDS: tuple[SeedSpec, ...] = (
    FOUNDATIONS,
    SPREADSHEETS,
    SQL,
    PYTHON,
    PYTHON_DATA,
    STATS,
    DATAVIZ,
    DSA_PYTHON,
    GIT,
)

# cross-domain prerequisite edges - which domains build on which
DOMAIN_PREREQS: tuple[tuple[str, str], ...] = (
    ("foundations", "spreadsheets"),
    ("foundations", "sql"),
    ("foundations", "python"),
    ("python", "python_data"),
    ("python", "dsa_python"),
    ("python", "git"),
    ("python_data", "dataviz"),
    ("python_data", "stats"),
    ("sql", "python_data"),
)


# --------------------------------------------------------------------------- #
# target roles - a weighted set of goal skills across domains
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Role:
    name: str
    aliases: tuple[str, ...]
    # (domain, concept id, importance weight 0-1)
    skills: tuple[tuple[str, str, float], ...]


DATA_ANALYST = Role(
    name="data analyst",
    aliases=("data analyst", "analyst", "junior data analyst", "business analyst"),
    skills=(
        ("sql", "window_functions", 1.0),
        ("sql", "outer_join", 0.9),
        ("sql", "ctes", 0.8),
        ("python_data", "groupby_agg", 1.0),
        ("python_data", "merge_join", 0.9),
        ("python_data", "missing_data", 0.8),
        ("python_data", "pivot_melt", 0.7),
        ("stats", "ab_testing", 0.9),
        ("stats", "hypothesis_testing", 0.85),
        ("stats", "confidence_intervals", 0.7),
        ("stats", "linear_regression", 0.6),
        ("dataviz", "storytelling", 0.9),
        ("dataviz", "rel_plots", 0.6),
        ("spreadsheets", "pivot_tables", 0.6),
        ("git", "push_pull", 0.5),
    ),
)

ANALYTICS_ENGINEER = Role(
    name="analytics engineer",
    aliases=("analytics engineer", "data engineer", "dbt", "etl developer"),
    skills=(
        ("sql", "window_functions", 1.0),
        ("sql", "ctes", 1.0),
        ("sql", "ddl", 0.9),
        ("sql", "indexes_sql", 0.8),
        ("python", "venv_pip", 0.8),
        ("python", "oop_lite", 0.6),
        ("python_data", "read_write_data", 0.9),
        ("python_data", "merge_join", 0.8),
        ("git", "pull_requests", 0.9),
        ("git", "merge_conflicts", 0.7),
        ("dsa_python", "big_o", 0.6),
        ("stats", "descriptive", 0.5),
    ),
)

ROLES: tuple[Role, ...] = (DATA_ANALYST, ANALYTICS_ENGINEER)


def role_profile(role: Role) -> dict[str, float]:
    """``{domain.concept: weight}`` - the ids match :func:`domains.role_graph`."""
    return {f"{d}.{c}": w for d, c, w in role.skills}
