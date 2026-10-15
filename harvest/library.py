"""Build the skill library: real practice problems (LeetCode, HackerRank and
open sites) and real YouTube lessons for every data skill, each tied to a
concept of that skill's graph so the app can order them along a learner's path.

    python velpo.py library            # re-harvest -> harvest/data/library.json

Nothing here is invented: problem lists come from LeetCode's and HackerRank's
own APIs, every video id/title/channel/length comes from YouTube's results
page, and every open-site link is fetched once and kept only if it answers.
The app itself only reads the JSON snapshot, so it works offline.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parent / "data" / "library.json"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
DOMAINS = (
    "sql",
    "spreadsheets",
    "python",
    "python_data",
    "stats",
    "dataviz",
    "powerbi",
    "tableau",
    "data_eng",
    "git",
)


# ------------------------------------------------------------------ http
def _get(url: str, *, headers: dict[str, str] | None = None, timeout: float = 30) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA, "Accept-Language": "en", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - fixed https hosts
        return str(r.read().decode("utf-8", "replace"))


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> Any:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"User-Agent": _UA, "Content-Type": "application/json", **headers}
    )
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return json.loads(r.read())


def _alive(url: str) -> bool:
    try:
        _get(url, timeout=20)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ LeetCode
_LC = "https://leetcode.com/graphql"
_PLAN_Q = (
    "query p($s:String!){studyPlanV2Detail(planSlug:$s){name planSubGroups"
    "{name questions{titleSlug title difficulty paidOnly}}}}"
)
_LIST_Q = (
    "query l($c:String,$k:Int,$n:Int){questionList(categorySlug:$c,limit:$n,skip:$k,filters:{})"
    "{totalNum data{title titleSlug difficulty isPaidOnly}}}"
)

# study-plan section -> (domain, concept)
LC_PLANS: dict[str, dict[str, tuple[str, str] | None]] = {
    "top-sql-50": {
        "Select": ("sql", "where"),
        "Basic Joins": ("sql", "outer_join"),
        "Basic Aggregate Functions": ("sql", "aggregates"),
        "Sorting and Grouping": ("sql", "group_by"),
        "Advanced Select and Joins": ("sql", "self_join"),
        "Subqueries": ("sql", "subqueries"),
        "Advanced String Functions / Regex / Clause": ("sql", "string_fns_sql"),
    },
    "introduction-to-pandas": {
        "Pandas Data Structures": ("python_data", "dataframe"),
        "Data Inspection": ("python_data", "dataframe"),
        "Data Selecting": ("python_data", "selecting"),
        "Data Cleaning": ("python_data", "missing_data"),
        "Table Reshaping": ("python_data", "pivot_melt"),
        "Advanced Techniques": ("python_data", "apply_map"),
    },
    "30-days-of-pandas": {
        "Data Filtering": ("python_data", "filtering"),
        "String Methods": ("python_data", "string_methods_pd"),
        "Data Manipulation": ("python_data", "new_columns"),
        "Statistics": ("python_data", "sort_rank"),
        "Data Aggregation": ("python_data", "groupby_agg"),
        "Data Integration": ("python_data", "merge_join"),
    },
}


def _lc_item(
    q: dict[str, Any], plan: str, section: str, where: tuple[str, str] | None
) -> dict[str, Any]:
    return {
        "platform": "LeetCode",
        "set": plan,
        "section": section,
        "title": q["title"],
        "url": f"https://leetcode.com/problems/{q['titleSlug']}/",
        "difficulty": q["difficulty"],
        "domain": where[0] if where else None,
        "concept": where[1] if where else None,
        "free": not q.get("paidOnly", q.get("isPaidOnly", False)),
    }


def leetcode() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    names = {
        "top-sql-50": "SQL 50",
        "introduction-to-pandas": "Introduction to Pandas",
        "30-days-of-pandas": "30 Days of Pandas",
    }
    for plan, sections in LC_PLANS.items():
        d = _post_json(
            _LC,
            {"query": _PLAN_Q, "variables": {"s": plan}},
            {"Referer": f"https://leetcode.com/studyplan/{plan}/"},
        )
        for g in d["data"]["studyPlanV2Detail"]["planSubGroups"]:
            for q in g["questions"]:
                where = sections.get(g["name"]) or (
                    ("sql", "subqueries")
                    if plan == "top-sql-50"
                    else ("python_data", "groupby_agg")
                )
                if (q["titleSlug"], where[0]) in seen:
                    continue
                seen.add((q["titleSlug"], where[0]))
                items.append(_lc_item(q, names[plan], g["name"], where))
        time.sleep(1)
    # every other free problem in the Database and pandas categories, as mixed practice
    for cat, dom in (("database", "sql"), ("pandas", "python_data")):
        skip = 0
        while True:
            d = _post_json(
                _LC,
                {"query": _LIST_Q, "variables": {"c": cat, "k": skip, "n": 100}},
                {"Referer": "https://leetcode.com/problemset/"},
            )
            page = d["data"]["questionList"]
            for q in page["data"]:
                if (q["titleSlug"], dom) in seen or q["isPaidOnly"]:
                    continue
                seen.add((q["titleSlug"], dom))
                it = _lc_item(q, f"All {cat} problems", "Mixed practice", None)
                it["domain"] = dom
                items.append(it)
            skip += 100
            if skip >= page["totalNum"]:
                break
            time.sleep(1)
    return items


# ------------------------------------------------------------------ HackerRank
HR_SQL = {
    "select": "where",
    "aggregation": "aggregates",
    "join": "inner_join",
    "advanced-select": "case_when",
    "advanced-join": "self_join",
    "alternative-queries": "subqueries",
}
HR_PY: dict[str, tuple[str, str]] = {
    "py-introduction": ("python", "operators"),
    "py-basic-data-types": ("python", "lists"),
    "py-strings": ("python", "strings"),
    "py-sets": ("python", "tuples_sets"),
    "py-math": ("python", "operators"),
    "py-itertools": ("python", "modules"),
    "py-collections": ("python", "dicts"),
    "py-date-time": ("python", "modules"),
    "errors-exceptions": ("python", "exceptions"),
    "py-classes": ("python", "oop_lite"),
    "py-built-ins": ("python", "functions"),
    "py-functionals": ("python", "comprehensions"),
    "py-regex": ("python", "strings"),
    "xml": ("python", "files_csv"),
    "closures-and-decorators": ("python", "scope"),
    "numpy": ("python_data", "numpy_arrays"),
}
HR_DB = {  # Databases track: theory quizzes on modelling, indexes, OLAP
    "relational-algebra": ("sql", "set_ops"),
    "indexes": ("sql", "indexes_sql"),
    "olap": ("data_eng", "dimensional_modeling"),
    "database-normalization": ("data_eng", "de_data_modeling"),
    "set-and-algebra": ("sql", "set_ops"),
    "database-query-languages": ("sql", "select_from"),
    "x-normalization": ("data_eng", "de_data_modeling"),
}
_STATS_KEYS = (
    ("weighted-mean", "descriptive"),
    ("basic-statistics", "descriptive"),
    ("mean-median", "descriptive"),
    ("interquartile", "quartiles"),
    ("quartiles", "quartiles"),
    ("standard-deviation", "descriptive"),
    ("central-limit", "clt"),
    ("pearson", "correlation"),
    ("spearman", "correlation"),
    ("least-square", "linear_regression"),
    ("linear-regression", "linear_regression"),
    ("binomial", "distributions"),
    ("geometric", "distributions"),
    ("poisson", "distributions"),
    ("normal", "distributions"),
    ("probability", "probability_basics"),
    ("dice", "probability_basics"),
    ("mcq", "probability_basics"),
    ("conditional", "probability_basics"),
    ("drawing", "probability_basics"),
)


def _hr_models(path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    off = 0
    while True:
        d = json.loads(_get(f"https://www.hackerrank.com/rest/{path}?offset={off}&limit=50"))
        out += d.get("models", [])
        off += 50
        if off >= d.get("total", 0):
            return out
        time.sleep(1)


def _hr_item(
    m: dict[str, Any], set_name: str, contest: str, where: tuple[str, str] | None
) -> dict[str, Any]:
    base = "https://www.hackerrank.com"
    url = (
        f"{base}/challenges/{m['slug']}/problem"
        if contest == "master"
        else f"{base}/contests/{contest}/challenges/{m['slug']}"
    )
    return {
        "platform": "HackerRank",
        "set": set_name,
        "section": (m.get("track") or {}).get("name", ""),
        "title": m["name"],
        "url": url,
        "difficulty": {"Advanced": "Hard", "Expert": "Hard"}.get(
            str(m.get("difficulty_name") or "Easy").capitalize(),
            str(m.get("difficulty_name") or "Easy").capitalize(),
        ),
        "domain": where[0] if where else None,
        "concept": where[1] if where else None,
        "free": True,
    }


def hackerrank() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for m in _hr_models("contests/master/tracks/sql/challenges"):
        sub = (m.get("track") or {}).get("slug", "")
        items.append(_hr_item(m, "SQL track", "master", ("sql", HR_SQL.get(sub, "subqueries"))))
    for m in _hr_models("contests/master/tracks/python/challenges"):
        sub = (m.get("track") or {}).get("slug", "")
        items.append(_hr_item(m, "Python track", "master", HR_PY.get(sub, ("python", "functions"))))
    for m in _hr_models("contests/master/tracks/databases/challenges"):
        sub = (m.get("track") or {}).get("slug", "")
        items.append(
            _hr_item(
                m, "Databases track", "master", HR_DB.get(sub, ("data_eng", "de_data_modeling"))
            )
        )
    for slug in STATS_SLUGS:
        try:
            d = json.loads(
                _get(f"https://www.hackerrank.com/rest/contests/master/challenges/{slug}")
            )
        except Exception:
            continue
        m = d.get("model") or {}
        if not m.get("name"):
            continue
        concept = next((c for k, c in _STATS_KEYS if k in slug), "descriptive")
        items.append(_hr_item(m, "10 Days of Statistics", "master", ("stats", concept)))
        time.sleep(0.4)
    return items


# HackerRank "10 Days of Statistics" - each slug is looked up; unknown ones drop out
STATS_SLUGS = (
    "s10-basic-statistics",
    "s10-weighted-mean",
    "s10-quartiles",
    "s10-interquartile-range",
    "s10-standard-deviation",
    "s10-basic-probability",
    "s10-more-dice",
    "s10-mcq-1",
    "s10-mcq-2",
    "s10-mcq-3",
    "s10-binomial-distribution-1",
    "s10-binomial-distribution-2",
    "s10-geometric-distribution-1",
    "s10-geometric-distribution-2",
    "s10-poisson-distribution-1",
    "s10-poisson-distribution-2",
    "s10-normal-distribution-1",
    "s10-normal-distribution-2",
    "s10-the-central-limit-theorem-1",
    "s10-the-central-limit-theorem-2",
    "s10-the-central-limit-theorem-3",
    "s10-pearson-correlation-coefficient",
    "s10-spearman-rank-correlation-coefficient",
    "s10-least-square-regression-line",
    "s10-multiple-linear-regression",
    "s10-mcq-4",
    "s10-mcq-5",
    "s10-mcq-6",
    "s10-mcq-7",
    "s10-mcq-8",
    "s10-mcq-9",
)


# ------------------------------------------------------------------ open sites
# (platform, title, url, domain, concept, difficulty, minutes) - each link is
# fetched at harvest time and dropped if it doesn't answer.
OPEN_SETS: tuple[tuple[str, str, str, str, str, str, int], ...] = (
    # SQL
    (
        "SQLBolt",
        "Interactive lessons 1-5: SELECT, WHERE, ORDER BY",
        "https://sqlbolt.com/lesson/select_queries_introduction",
        "sql",
        "select_from",
        "Easy",
        40,
    ),
    (
        "SQLBolt",
        "Lessons 6-7: joins (inner and outer)",
        "https://sqlbolt.com/lesson/select_queries_with_joins",
        "sql",
        "inner_join",
        "Easy",
        30,
    ),
    (
        "SQLBolt",
        "Lesson 8: NULLs",
        "https://sqlbolt.com/lesson/select_queries_with_nulls",
        "sql",
        "null_logic",
        "Easy",
        15,
    ),
    (
        "SQLBolt",
        "Lessons 10-11: aggregates and GROUP BY",
        "https://sqlbolt.com/lesson/select_queries_with_aggregates",
        "sql",
        "group_by",
        "Easy",
        30,
    ),
    (
        "SQLBolt",
        "Lessons 16-18: creating and changing tables",
        "https://sqlbolt.com/lesson/creating_tables",
        "sql",
        "ddl",
        "Easy",
        30,
    ),
    (
        "SQLZoo",
        "SELECT basics",
        "https://sqlzoo.net/wiki/SELECT_basics",
        "sql",
        "select_from",
        "Easy",
        20,
    ),
    (
        "SQLZoo",
        "SELECT from World",
        "https://sqlzoo.net/wiki/SELECT_from_WORLD_Tutorial",
        "sql",
        "where",
        "Easy",
        30,
    ),
    (
        "SQLZoo",
        "SUM and COUNT",
        "https://sqlzoo.net/wiki/SUM_and_COUNT",
        "sql",
        "aggregates",
        "Easy",
        25,
    ),
    (
        "SQLZoo",
        "The JOIN operation",
        "https://sqlzoo.net/wiki/The_JOIN_operation",
        "sql",
        "inner_join",
        "Medium",
        40,
    ),
    (
        "SQLZoo",
        "Using NULL",
        "https://sqlzoo.net/wiki/Using_Null",
        "sql",
        "null_logic",
        "Medium",
        25,
    ),
    (
        "SQLZoo",
        "SELECT within SELECT (subqueries)",
        "https://sqlzoo.net/wiki/SELECT_within_SELECT_Tutorial",
        "sql",
        "subqueries",
        "Medium",
        35,
    ),
    ("SQLZoo", "Self join", "https://sqlzoo.net/wiki/Self_join", "sql", "self_join", "Hard", 40),
    (
        "SQLZoo",
        "Window functions",
        "https://sqlzoo.net/wiki/Window_functions",
        "sql",
        "window_functions",
        "Hard",
        35,
    ),
    (
        "PostgreSQL Exercises",
        "Basic queries",
        "https://pgexercises.com/questions/basic/",
        "sql",
        "where",
        "Easy",
        40,
    ),
    (
        "PostgreSQL Exercises",
        "Joins and subqueries",
        "https://pgexercises.com/questions/joins/",
        "sql",
        "outer_join",
        "Medium",
        60,
    ),
    (
        "PostgreSQL Exercises",
        "Aggregation (incl. window functions)",
        "https://pgexercises.com/questions/aggregates/",
        "sql",
        "window_functions",
        "Hard",
        90,
    ),
    (
        "PostgreSQL Exercises",
        "Working with timestamps",
        "https://pgexercises.com/questions/date/",
        "sql",
        "date_fns_sql",
        "Medium",
        45,
    ),
    (
        "PostgreSQL Exercises",
        "String operations",
        "https://pgexercises.com/questions/string/",
        "sql",
        "string_fns_sql",
        "Medium",
        30,
    ),
    (
        "PostgreSQL Exercises",
        "Recursive queries",
        "https://pgexercises.com/questions/recursive/",
        "sql",
        "ctes",
        "Hard",
        30,
    ),
    (
        "Kaggle Learn",
        "Intro to SQL (BigQuery, with exercises)",
        "https://www.kaggle.com/learn/intro-to-sql",
        "sql",
        "group_by",
        "Easy",
        180,
    ),
    (
        "Kaggle Learn",
        "Advanced SQL (joins, unions, window functions)",
        "https://www.kaggle.com/learn/advanced-sql",
        "sql",
        "window_functions",
        "Hard",
        240,
    ),
    (
        "DataLemur",
        "SQL interview questions (many free)",
        "https://datalemur.com/questions",
        "sql",
        "window_functions",
        "Medium",
        120,
    ),
    (
        "StrataScratch",
        "Real interview SQL and pandas questions",
        "https://platform.stratascratch.com/coding",
        "sql",
        "ctes",
        "Medium",
        120,
    ),
    # Excel
    (
        "Excel-Practice-Online",
        "Interactive Excel exercises in the browser",
        "https://excel-practice-online.com/",
        "spreadsheets",
        "formulas",
        "Easy",
        120,
    ),
    (
        "Chandoo.org",
        "Excel formula list with examples",
        "https://chandoo.org/wp/excel-formulas/",
        "spreadsheets",
        "agg_functions",
        "Easy",
        60,
    ),
    (
        "Exceljet",
        "500 Excel formula examples",
        "https://exceljet.net/formulas",
        "spreadsheets",
        "lookups",
        "Medium",
        120,
    ),
    (
        "Exceljet",
        "Dynamic array formulas",
        "https://exceljet.net/articles/dynamic-array-formulas-in-excel",
        "spreadsheets",
        "dynamic_arrays",
        "Hard",
        40,
    ),
    (
        "Microsoft Support",
        "Excel video training (with practice files)",
        "https://support.microsoft.com/en-us/office/excel-video-training-9bc05390-e94c-46af-a5b3-d7c22f6990bb",
        "spreadsheets",
        "pivot_tables",
        "Easy",
        120,
    ),
    (
        "Microsoft Support",
        "Power Query for Excel help",
        "https://support.microsoft.com/en-us/office/power-query-for-excel-help-2b30c6b6-1c7a-4c4c-9a4f-7a6d5c7d2a3a",
        "spreadsheets",
        "power_query",
        "Hard",
        60,
    ),
    # Python / pandas
    (
        "Exercism",
        "Python track: 140+ exercises with mentoring",
        "https://exercism.org/tracks/python",
        "python",
        "functions",
        "Easy",
        600,
    ),
    (
        "Kaggle Learn",
        "Python (with exercises)",
        "https://www.kaggle.com/learn/python",
        "python",
        "loops",
        "Easy",
        300,
    ),
    (
        "Kaggle Learn",
        "pandas (with exercises)",
        "https://www.kaggle.com/learn/pandas",
        "python_data",
        "groupby_agg",
        "Easy",
        240,
    ),
    (
        "Kaggle Learn",
        "Data Cleaning",
        "https://www.kaggle.com/learn/data-cleaning",
        "python_data",
        "missing_data",
        "Medium",
        240,
    ),
    (
        "w3resource",
        "pandas exercises with solutions",
        "https://www.w3resource.com/python-exercises/pandas/index.php",
        "python_data",
        "filtering",
        "Medium",
        300,
    ),
    (
        "GitHub (guipsamora)",
        "pandas_exercises notebooks",
        "https://github.com/guipsamora/pandas_exercises",
        "python_data",
        "merge_join",
        "Medium",
        300,
    ),
    (
        "GitHub (rougier)",
        "100 NumPy exercises",
        "https://github.com/rougier/numpy-100",
        "python_data",
        "array_ops",
        "Hard",
        300,
    ),
    # Statistics
    (
        "Khan Academy",
        "Statistics and probability (with practice)",
        "https://www.khanacademy.org/math/statistics-probability",
        "stats",
        "descriptive",
        "Easy",
        900,
    ),
    (
        "Khan Academy",
        "Significance tests (hypothesis testing)",
        "https://www.khanacademy.org/math/statistics-probability/significance-tests-one-sample",
        "stats",
        "hypothesis_testing",
        "Medium",
        240,
    ),
    (
        "OpenIntro",
        "OpenIntro Statistics (free book + exercises)",
        "https://www.openintro.org/book/os/",
        "stats",
        "confidence_intervals",
        "Medium",
        900,
    ),
    (
        "Seeing Theory",
        "Visual probability and statistics",
        "https://seeing-theory.brown.edu/",
        "stats",
        "probability_basics",
        "Easy",
        60,
    ),
    # Data viz
    (
        "Storytelling with Data",
        "Monthly community challenges",
        "https://community.storytellingwithdata.com/challenges",
        "dataviz",
        "storytelling",
        "Medium",
        120,
    ),
    (
        "Makeover Monday",
        "Weekly redesign-a-chart challenge",
        "https://makeovermonday.co.uk/",
        "dataviz",
        "choosing_chart",
        "Medium",
        120,
    ),
    (
        "Kaggle Learn",
        "Data Visualization (seaborn, with exercises)",
        "https://www.kaggle.com/learn/data-visualization",
        "dataviz",
        "seaborn_basics",
        "Easy",
        240,
    ),
    (
        "From Data to Viz",
        "Which chart for which data?",
        "https://www.data-to-viz.com/",
        "dataviz",
        "chart_types",
        "Easy",
        45,
    ),
    (
        "matplotlib",
        "Official tutorials",
        "https://matplotlib.org/stable/tutorials/index.html",
        "dataviz",
        "matplotlib_basics",
        "Easy",
        120,
    ),
    # Power BI
    (
        "Microsoft Learn",
        "PL-300 learning paths (modules with knowledge checks)",
        "https://learn.microsoft.com/en-us/credentials/certifications/data-analyst-associate/",
        "powerbi",
        "pbi_get_data",
        "Easy",
        1800,
    ),
    (
        "Microsoft Learn",
        "Get started with Power BI",
        "https://learn.microsoft.com/en-us/training/modules/get-started-with-power-bi/",
        "powerbi",
        "pbi_get_data",
        "Easy",
        60,
    ),
    (
        "Microsoft Learn",
        "Design a semantic model in Power BI",
        "https://learn.microsoft.com/en-us/training/modules/design-model-power-bi/",
        "powerbi",
        "star_schema",
        "Medium",
        90,
    ),
    (
        "Microsoft Learn",
        "Write DAX formulas",
        "https://learn.microsoft.com/en-us/training/modules/dax-power-bi-write-formulas/",
        "powerbi",
        "dax_basics",
        "Medium",
        60,
    ),
    (
        "Microsoft Learn",
        "Modify DAX filter context",
        "https://learn.microsoft.com/en-us/training/modules/dax-power-bi-modify-filter/",
        "powerbi",
        "calculate",
        "Hard",
        60,
    ),
    (
        "Microsoft Learn",
        "Use DAX time intelligence functions",
        "https://learn.microsoft.com/en-us/training/modules/dax-power-bi-time-intelligence/",
        "powerbi",
        "time_intelligence",
        "Hard",
        60,
    ),
    (
        "Microsoft Learn",
        "Enforce row-level security",
        "https://learn.microsoft.com/en-us/training/modules/enforce-power-bi-model-security/",
        "powerbi",
        "rls",
        "Hard",
        45,
    ),
    (
        "DAX Guide",
        "Every DAX function with examples",
        "https://dax.guide/",
        "powerbi",
        "iterators",
        "Medium",
        60,
    ),
    (
        "Workout Wednesday",
        "Weekly Power BI challenges",
        "https://workout-wednesday.com/power-bi-challenges/",
        "powerbi",
        "pbi_dashboards",
        "Medium",
        120,
    ),
    # Tableau
    (
        "Tableau",
        "Free training videos",
        "https://www.tableau.com/learn/training",
        "tableau",
        "tab_basic_charts",
        "Easy",
        300,
    ),
    (
        "Tableau Help",
        "Level of Detail expressions",
        "https://help.tableau.com/current/pro/desktop/en-us/calculations_calculatedfields_lod.htm",
        "tableau",
        "lod",
        "Hard",
        45,
    ),
    (
        "Tableau Help",
        "Table calculations",
        "https://help.tableau.com/current/pro/desktop/en-us/calculations_tablecalculations.htm",
        "tableau",
        "table_calcs",
        "Hard",
        45,
    ),
    (
        "Workout Wednesday",
        "Weekly Tableau challenges (with solutions)",
        "https://workout-wednesday.com/",
        "tableau",
        "tab_dashboards",
        "Medium",
        120,
    ),
    (
        "Tableau Public",
        "Viz of the Day gallery (study and rebuild)",
        "https://public.tableau.com/app/discover/viz-of-the-day",
        "tableau",
        "tab_stories",
        "Medium",
        60,
    ),
    # Data engineering
    (
        "DataTalksClub",
        "Data Engineering Zoomcamp (homework each module)",
        "https://github.com/DataTalksClub/data-engineering-zoomcamp",
        "data_eng",
        "orchestration",
        "Medium",
        3000,
    ),
    (
        "dbt Learn",
        "dbt Fundamentals (free course)",
        "https://learn.getdbt.com/courses/dbt-fundamentals",
        "data_eng",
        "dbt_models",
        "Medium",
        300,
    ),
    (
        "dbt Docs",
        "Add data tests to your DAG",
        "https://docs.getdbt.com/docs/build/data-tests",
        "data_eng",
        "dbt_tests",
        "Medium",
        30,
    ),
    (
        "Apache Airflow",
        "Fundamental concepts tutorial",
        "https://airflow.apache.org/docs/apache-airflow/stable/tutorial/fundamentals.html",
        "data_eng",
        "orchestration",
        "Medium",
        60,
    ),
    (
        "Apache Spark",
        "Quick start",
        "https://spark.apache.org/docs/latest/quick-start.html",
        "data_eng",
        "spark_basics",
        "Medium",
        60,
    ),
    (
        "Docker Docs",
        "Get started",
        "https://docs.docker.com/get-started/",
        "data_eng",
        "containers_cloud",
        "Easy",
        90,
    ),
    (
        "Kimball Group",
        "Dimensional modeling techniques",
        "https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/",
        "data_eng",
        "dimensional_modeling",
        "Medium",
        90,
    ),
    # Git
    (
        "Learn Git Branching",
        "Interactive levels: commits, branches, rebase, remotes",
        "https://learngitbranching.js.org/",
        "git",
        "branches",
        "Easy",
        180,
    ),
    (
        "GitHub Skills",
        "Introduction to GitHub",
        "https://github.com/skills/introduction-to-github",
        "git",
        "pull_requests",
        "Easy",
        60,
    ),
    (
        "GitHub Skills",
        "Resolve merge conflicts",
        "https://github.com/skills/resolve-merge-conflicts",
        "git",
        "merge_conflicts",
        "Medium",
        30,
    ),
    (
        "GitHub Skills",
        "Review pull requests",
        "https://github.com/skills/review-pull-requests",
        "git",
        "pull_requests",
        "Medium",
        30,
    ),
    (
        "Oh My Git!",
        "A game for learning Git",
        "https://ohmygit.org/",
        "git",
        "stage_commit",
        "Easy",
        120,
    ),
    (
        "Pro Git",
        "Free book (with exercises in each chapter)",
        "https://git-scm.com/book/en/v2",
        "git",
        "undo",
        "Medium",
        600,
    ),
)


def open_sets() -> tuple[list[dict[str, Any]], list[str]]:
    keep: list[dict[str, Any]] = []
    dropped: list[str] = []
    for platform, title, url, dom, concept, diff, minutes in OPEN_SETS:
        if _alive(url):
            keep.append(
                {
                    "platform": platform,
                    "set": platform,
                    "section": "",
                    "title": title,
                    "url": url,
                    "difficulty": diff,
                    "domain": dom,
                    "concept": concept,
                    "free": True,
                    "minutes": minutes,
                }
            )
        else:
            dropped.append(url)
        time.sleep(0.3)
    return keep, dropped


# ------------------------------------------------------------------ YouTube
TRUSTED = (
    "freecodecamp",
    "alex the analyst",
    "luke barousse",
    "programming with mosh",
    "corey schafer",
    "statquest",
    "kevin stratvert",
    "leila gharani",
    "excelisfun",
    "guy in a cube",
    "tableau",
    "microsoft power bi",
    "data with baraa",
    "techtfq",
    "keith galli",
    "bro code",
    "ken jee",
    "seattle data guy",
    "datatalksclub",
    "dbt",
    "khan academy",
    "3blue1brown",
    "crashcourse",
    "fireship",
    "data school",
    "sentdex",
    "chandoo",
    "myonlinetraininghub",
    "excel campus",
    "sqlbi",
    "curbal",
    "how to power bi",
    "darshil parmar",
    "joey blue",
    "socratica",
    "zedstatistics",
    "jbstatistics",
    "ritvikmath",
    "kahan data solutions",
    "techworld with nana",
    "databricks",
    "the net ninja",
    "traversy media",
    "cs dojo",
    "simon sez it",
    "andy kriebel",
    "tableau tim",
    "avi singh",
    "simplilearn",
    "edureka",
    "great learning",
    "codebasics",
    "mo chen",
    "rob mulla",
    "neuralnine",
    "kunal kushwaha",
    "academind",
    "github",
    "atlassian",
    "data engineering",
    "andreas kretz",
    "marc lamberti",
    "very normal",
    "matt brattin",
)
DOMAIN_WORD = {
    "sql": "SQL",
    "spreadsheets": "Excel",
    "python": "Python",
    "python_data": "pandas",
    "stats": "statistics",
    "dataviz": "data visualization",
    "powerbi": "Power BI",
    "tableau": "Tableau",
    "data_eng": "data engineering",
    "git": "Git",
}
# whole-skill videos, in the order one should watch them
COURSES: dict[str, tuple[tuple[str, str], ...]] = {
    "sql": (
        ("SQL full course for beginners", "Beginner"),
        ("SQL for data analysis project", "Intermediate"),
        ("advanced SQL window functions CTE tutorial", "Advanced"),
        ("SQL interview questions data analyst", "Advanced"),
    ),
    "spreadsheets": (
        ("Excel tutorial for beginners", "Beginner"),
        ("Excel for data analysis full course", "Intermediate"),
        ("advanced Excel formulas XLOOKUP dynamic arrays", "Advanced"),
        ("Excel dashboard project", "Advanced"),
    ),
    "python": (
        ("Python full course for beginners", "Beginner"),
        ("Python intermediate tutorial", "Intermediate"),
        ("Python projects for beginners data", "Intermediate"),
    ),
    "python_data": (
        ("pandas tutorial for beginners", "Beginner"),
        ("data analysis with python full course", "Intermediate"),
        ("pandas data cleaning project", "Intermediate"),
        ("advanced pandas tips", "Advanced"),
    ),
    "stats": (
        ("statistics full course for beginners", "Beginner"),
        ("statistics for data science", "Intermediate"),
        ("A/B testing explained data science", "Advanced"),
    ),
    "dataviz": (
        ("data visualization principles", "Beginner"),
        ("matplotlib tutorial full course", "Intermediate"),
        ("seaborn tutorial", "Intermediate"),
        ("storytelling with data talk", "Advanced"),
    ),
    "powerbi": (
        ("Power BI tutorial for beginners", "Beginner"),
        ("Power BI full course", "Intermediate"),
        ("DAX tutorial CALCULATE filter context", "Advanced"),
        ("Power BI dashboard project", "Advanced"),
    ),
    "tableau": (
        ("Tableau tutorial for beginners", "Beginner"),
        ("Tableau full course", "Intermediate"),
        ("Tableau LOD expressions explained", "Advanced"),
        ("Tableau dashboard project", "Advanced"),
    ),
    "data_eng": (
        ("data engineering full course", "Beginner"),
        ("data engineering zoomcamp", "Intermediate"),
        ("dbt tutorial for beginners", "Intermediate"),
        ("Apache Airflow tutorial", "Advanced"),
        ("PySpark full course", "Advanced"),
    ),
    "git": (
        ("Git and GitHub for beginners crash course", "Beginner"),
        ("Git tutorial branching merging", "Intermediate"),
        ("Git rebase merge conflicts explained", "Advanced"),
    ),
}


def _yt_search(query: str) -> list[dict[str, Any]]:
    html = _get(
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote_plus(query)
        + "&sp=EgIQAQ%253D%253D&hl=en&gl=US"
    )
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))
    out: list[dict[str, Any]] = []

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            vr = o.get("videoRenderer")
            if isinstance(vr, dict) and "videoId" in vr:
                out.append(vr)
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


def _seconds(text: str) -> int:
    parts = [int(p) for p in text.split(":") if p.isdigit()]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s


def _views(vr: dict[str, Any]) -> int:
    t = (vr.get("viewCountText") or {}).get("simpleText", "")
    digits = re.sub(r"\D", "", t)
    return int(digits) if digits else 0


_NOT_ENGLISH = re.compile(
    r"\b(hindi|tamil|telugu|kannada|malayalam|marathi|bangla|bengali|urdu|gujarati|punjabi|"
    r"español|espanol|português|portugues|français|deutsch|italiano|türkçe|bahasa|tagalog|arabic)\b",
    re.I,
)


def _english(title: str) -> bool:
    if _NOT_ENGLISH.search(title):
        return False
    letters = [ch for ch in title if ch.isalpha()]
    return not letters or sum(ch.isascii() for ch in letters) / len(letters) > 0.9


_GENERIC = {
    "data",
    "with",
    "using",
    "the",
    "and",
    "your",
    "basics",
    "basic",
    "intro",
    "idea",
    "what",
    "working",
    "minimum",
    "vs",
    "how",
    "from",
    "into",
    "for",
    "of",
    "a",
    "an",
    "to",
    "in",
    "on",
    "&",
    "the",
    "is",
    "it",
    "its",
    "this",
    "that",
    "part",
    "view",
    "views",
}


_SUFFIXES = ("ations", "ation", "ings", "ing", "ies", "es", "s", "ed", "ency", "ent")
_SPELLING = (
    ("isation", "ization"),
    ("ise", "ize"),
    ("modell", "model"),
    ("colour", "color"),
    ("vectoris", "vectoriz"),
)


def _norm(text: str) -> str:
    """Lower-case, British -> American spelling (modelling/modeling, colour/color)."""
    t = text.lower()
    for a, b in _SPELLING:
        t = t.replace(a, b)
    return t


_SYNONYMS = {"clt": "central limit", "datetime": "date", "vs": "versus"}


def _stem(w: str) -> str:
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            return w[:-1] if len(w) > 4 and w[-1] == w[-2] else w  # committ -> commit
    return w


def _keywords(name: str) -> set[str]:
    """Distinctive words of a concept name, stemmed (sorting -> sort, keys -> key)."""
    words = re.findall(r"[a-z][a-z0-9+#]*", _norm(name))
    keys = {_stem(w) for w in words if len(w) >= 2 and w not in _GENERIC}
    return keys | {_SYNONYMS[w] for w in words if w in _SYNONYMS}


def relevant(title: str, name: str) -> bool:
    """A lesson's title must mention at least one distinctive word of its topic
    (short words such as IF or OR must appear as whole words)."""
    t = _norm(title)
    for k in _keywords(name):
        if len(k) <= 3:
            if re.search(r"\b" + re.escape(k) + r"\b", t):
                return True
        elif k in t:
            return True
    return False


def _pick(
    query: str, *, min_s: int, max_s: int, used: set[str], topic: str | None = None
) -> dict[str, Any] | None:
    """Among the top results that fit the length and are in English: the first
    from a trusted teaching channel, else the most viewed (if well viewed)."""
    cands: list[dict[str, Any]] = []
    for vr in _yt_search(query)[:12]:
        vid = vr["videoId"]
        channel = "".join(r.get("text", "") for r in (vr.get("ownerText") or {}).get("runs", []))
        title = "".join(r.get("text", "") for r in (vr.get("title") or {}).get("runs", []))
        length = _seconds((vr.get("lengthText") or {}).get("simpleText", ""))
        if vid in used or not (min_s <= length <= max_s) or not _english(title):
            continue
        if topic is not None and not relevant(title, topic):
            continue
        cands.append(
            {
                "video_id": vid,
                "title": title,
                "channel": channel,
                "minutes": round(length / 60, 1),
                "views": _views(vr),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "trusted": any(t in channel.lower() for t in TRUSTED),
            }
        )
    popular = sorted((c for c in cands if c["views"] >= 50_000), key=lambda c: -int(c["views"]))
    ranked = [c for c in cands if c["trusted"]] + popular
    if not ranked:
        return None
    best = ranked[0]
    used.add(best["video_id"])
    best.pop("trusted")
    return best


def youtube(
    concepts: dict[str, list[tuple[str, str]]], old: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Whole-skill courses + one focused lesson per concept, real ids only.
    Videos already in ``old`` are kept; only the gaps are searched again."""
    names = {(d, c): n for d, cs in concepts.items() for c, n in cs}
    # drop earlier lessons whose title doesn't match their topic: they get re-searched
    videos: list[dict[str, Any]] = [
        v
        for v in (old or [])
        if v["kind"] != "lesson" or relevant(v["title"], names.get((v["domain"], v["concept"]), ""))
    ]
    used: set[str] = {v["video_id"] for v in videos}
    have_course = {(v["domain"], v["order"]) for v in videos if v["kind"] == "course"}
    have_lesson = {(v["domain"], v["concept"]) for v in videos if v["kind"] == "lesson"}
    for dom in DOMAINS:
        for order, (q, level) in enumerate(COURSES[dom]):
            if (dom, order) in have_course:
                continue
            v = _pick(q, min_s=20 * 60, max_s=14 * 3600, used=used)
            if v:
                videos.append(
                    {
                        **v,
                        "domain": dom,
                        "concept": None,
                        "level": level,
                        "kind": "course",
                        "order": order,
                    }
                )
            time.sleep(0.7)
        for cid, name in concepts[dom]:
            if (dom, cid) in have_lesson:
                continue
            clean = " ".join(re.sub(r"[()/&,.:]", " ", name).split())
            word = DOMAIN_WORD[dom]
            for q in (f"{clean} {word} tutorial", f"{word} {clean} explained", f"{clean} {word}"):
                v = _pick(q, min_s=2 * 60, max_s=120 * 60, used=used, topic=name)
                time.sleep(0.7)
                if v:
                    videos.append(
                        {
                            **v,
                            "domain": dom,
                            "concept": cid,
                            "level": "",
                            "kind": "lesson",
                            "order": 0,
                        }
                    )
                    break
    return videos


# ------------------------------------------------------------------ build
def build(old: dict[str, Any] | None = None) -> dict[str, Any]:
    from domains import seed_graph

    concepts = {
        d: [(c, seed_graph(d).concepts[c].name) for c in seed_graph(d).concept_ids] for d in DOMAINS
    }
    lc = leetcode()
    print(f"LeetCode: {len(lc)} problems", flush=True)
    hr = hackerrank()
    print(f"HackerRank: {len(hr)} challenges", flush=True)
    sites, dropped = open_sets()
    print(f"open sites: {len(sites)} kept, {len(dropped)} dropped {dropped}")
    vids = youtube(concepts, (old or {}).get("videos"))
    print(f"YouTube: {len(vids)} videos", flush=True)
    return {
        "harvested": dt.date.today().isoformat(),
        "problems": lc + hr + sites,
        "videos": vids,
        "dropped_links": dropped,
    }


def main(argv: list[str] | None = None) -> int:
    import sys

    args = sys.argv[1:] if argv is None else argv
    old = None
    if "--fresh" not in args and OUT.exists():  # keep found videos, search only the gaps
        old = json.loads(OUT.read_text(encoding="utf-8"))
    lib = build(old)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(lib, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
