"""Curated, verified, free learning resources for the data-analytics track, with
an explicit **profile -> resource** recommendation table.

Why a hand-labelled table rather than a trained model: VELPO has no real click
logs yet, so this file *is* the training data - an expert-labelled mapping from
learner profile (role / domain x self-reported band, refined by measured
mastery) to a ranked resource list.  It serves as the cold-start recommendation
prior; the online signals (learning velocity, the PFA refiner) personalise from
here, and a real feedback loop can later replace these labels wholesale.

Every URL was verified to exist (Sept 2026).  YouTube entries are flagship
full-courses / channel playlists from well-known creators (freeCodeCamp, Alex
The Analyst, Luke Barousse, StatQuest, Corey Schafer, ExcelIsFun); when no
curated resource covers a concept, :func:`recommend_resources` synthesises a
scoped YouTube search link so the learner is never left without one.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

Band = str  # "beginner" | "intermediate" | "advanced"

_YT_VIDEO = re.compile(r"[?&]v=([\w-]{11})")
_YT_LIST = re.compile(r"[?&]list=([\w-]+)")


def _youtube_embed(url: str) -> tuple[str, str]:
    """(embed_url, thumbnail_url) for a YouTube ``watch?v=`` or ``playlist?list=``
    link, using the privacy-preserving ``youtube-nocookie.com`` host.  ``("", "")``
    for anything not embeddable as a player (channels, docs, search)."""
    v = _YT_VIDEO.search(url)
    if v:
        vid = v.group(1)
        lst = _YT_LIST.search(url)
        tail = f"?list={lst.group(1)}" if lst else ""
        return (
            f"https://www.youtube-nocookie.com/embed/{vid}{tail}",
            f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        )
    lst = _YT_LIST.search(url)
    if lst and "/playlist" in url:
        return (f"https://www.youtube-nocookie.com/embed/videoseries?list={lst.group(1)}", "")
    return ("", "")


@dataclass(frozen=True, slots=True)
class LearnResource:
    id: str
    title: str
    channel: str
    url: str
    kind: str  # "video" | "playlist" | "channel" | "course" | "docs" | "practice"
    minutes: float
    level: int  # 1 (gentle) .. 5 (deep)
    bands: tuple[Band, ...]
    domains: tuple[str, ...]
    concepts: tuple[str, ...]  # bare concept ids; () == "covers the whole domain(s)"
    note: str

    @property
    def free(self) -> bool:
        return True  # everything in this file is free

    @property
    def embed_url(self) -> str:
        """A ``youtube-nocookie.com`` player URL when this resource can play
        in-app (video / playlist), else ``""`` (channels, docs, practice)."""
        return _youtube_embed(self.url)[0]

    @property
    def thumbnail(self) -> str:
        return _youtube_embed(self.url)[1]


# --------------------------------------------------------------------------- #
# the library  (all links verified Sept 2026)
# --------------------------------------------------------------------------- #
_ALL_SQL = (
    "select_from", "where", "order_limit", "distinct", "null_logic", "aggregates",
    "group_by", "having", "inner_join", "outer_join", "self_join", "subqueries",
    "ctes", "case_when", "window_functions", "set_ops", "ddl",
)  # fmt: skip
_ALL_PY = (
    "variables", "operators", "strings", "fstrings", "conditionals", "loops", "lists",
    "dicts", "tuples_sets", "comprehensions", "functions", "modules", "exceptions",
    "files_csv", "venv_pip", "jupyter", "oop_lite",
)  # fmt: skip
_ALL_PD = (
    "numpy_arrays", "array_ops", "pandas_series", "dataframe", "read_write_data",
    "selecting", "filtering", "new_columns", "missing_data", "groupby_agg", "merge_join",
    "concat", "pivot_melt", "apply_map", "datetime_pd", "string_methods_pd", "sort_rank",
    "plot_pandas",
)  # fmt: skip
_ALL_STATS = (
    "descriptive", "quartiles", "probability_basics", "distributions", "sampling", "clt",
    "standard_error", "confidence_intervals", "hypothesis_testing", "p_value", "t_test",
    "chi_square", "correlation", "corr_causation", "linear_regression", "r_squared",
    "ab_testing", "stat_power",
)  # fmt: skip
_ALL_VIZ = (
    "chart_types", "choosing_chart", "matplotlib_basics", "axes_titles", "subplots",
    "seaborn_basics", "dist_plots", "cat_plots", "rel_plots", "annotation", "storytelling",
    "dashboards",
)  # fmt: skip

RESOURCES: tuple[LearnResource, ...] = (
    LearnResource(
        "fcc_sql_full",
        "SQL Tutorial - Full Database Course for Beginners",
        "freeCodeCamp",
        "https://www.youtube.com/watch?v=HXV3zeQKqGY",
        "video",
        240,
        1,
        ("beginner", "intermediate"),
        ("sql",),
        _ALL_SQL,
        "Zero-to-joins SQL in one sitting - the standard first SQL course.",
    ),
    LearnResource(
        "fcc_da_bootcamp",
        "Data Analyst Bootcamp for Beginners (SQL, Excel, Power BI, Python)",
        "freeCodeCamp",
        "https://www.youtube.com/watch?v=PSNXoAs2FtQ",
        "video",
        1140,
        1,
        ("beginner",),
        ("sql", "spreadsheets", "dataviz", "python_data"),
        (),
        "One long guided bootcamp across every core analyst tool - best if you are starting cold.",
    ),
    LearnResource(
        "alex_analyst",
        "Alex The Analyst - Data Analyst Bootcamp playlists",
        "Alex The Analyst",
        "https://www.youtube.com/@AlexTheAnalyst/playlists",
        "channel",
        0,
        2,
        ("beginner", "intermediate"),
        ("sql", "spreadsheets", "dataviz", "python"),
        (),
        "Structured, job-focused playlists for SQL, Excel, Power BI and Tableau.",
    ),
    LearnResource(
        "fcc_python_full",
        "Learn Python - Full Course for Beginners",
        "freeCodeCamp",
        "https://www.youtube.com/watch?v=rfscVS0vtbw",
        "video",
        268,
        1,
        ("beginner",),
        ("python",),
        _ALL_PY,
        "The standard first Python course - all core syntax with small projects.",
    ),
    LearnResource(
        "luke_python_da",
        "Python for Data Analytics - Full Course for Beginners",
        "Luke Barousse",
        "https://www.youtube.com/watch?v=wUSDVGivd-8",
        "video",
        660,
        2,
        ("beginner", "intermediate"),
        ("python", "python_data", "dataviz"),
        (),
        "Python taught end-to-end for analytics: pandas, matplotlib, seaborn, a real project.",
    ),
    LearnResource(
        "fcc_data_analysis_python",
        "Data Analysis with Python - NumPy, Pandas, Matplotlib, Seaborn",
        "freeCodeCamp",
        "https://www.youtube.com/watch?v=r-uOLxNrNk8",
        "video",
        240,
        2,
        ("beginner", "intermediate"),
        ("python_data", "dataviz"),
        (*_ALL_PD, *_ALL_VIZ),
        "Cleaning and transforming with pandas, then plotting - the analyst core loop.",
    ),
    LearnResource(
        "corey_pandas",
        "Python Pandas Tutorials (full playlist)",
        "Corey Schafer",
        "https://www.youtube.com/playlist?list=PL-osiE80TeTsWmV9i9c58mdDCSskIFdDS",
        "playlist",
        180,
        3,
        ("intermediate", "advanced"),
        ("python_data",),
        _ALL_PD,
        "Deeper, careful pandas: indexes, filtering, grouping, cleaning - one topic per video.",
    ),
    LearnResource(
        "statquest_stats",
        "Statistics Fundamentals (playlist)",
        "StatQuest with Josh Starmer",
        "https://www.youtube.com/playlist?list=PLblh5JKOoLUIcdlgu78MnlATeyx4cEVeR",
        "playlist",
        480,
        2,
        ("beginner", "intermediate", "advanced"),
        ("stats",),
        _ALL_STATS,
        "Clear, visual explanations of every core statistics idea - rigour without the pain.",
    ),
    LearnResource(
        "statquest_channel",
        "StatQuest with Josh Starmer",
        "StatQuest",
        "https://www.youtube.com/@statquest",
        "channel",
        0,
        4,
        ("intermediate", "advanced"),
        ("stats",),
        (),
        "Go here for regression, A/B testing and modelling explained the same clear way.",
    ),
    LearnResource(
        "exceisfun",
        "ExcelIsFun (Mike Girvin)",
        "ExcelIsFun",
        "https://www.youtube.com/@ExcelIsFun",
        "channel",
        0,
        2,
        ("beginner", "intermediate", "advanced"),
        ("spreadsheets",),
        (),
        "The deepest free Excel library - lookups, pivot tables, cleaning, data analysis.",
    ),
    LearnResource(
        "fcc_git",
        "Git & GitHub Crash Course for Beginners",
        "freeCodeCamp",
        "https://www.youtube.com/watch?v=mAFoROnOfHs",
        "video",
        90,
        1,
        ("beginner",),
        ("git",),
        (
            "vcs_idea",
            "git_config",
            "init_clone",
            "stage_commit",
            "branches",
            "merge",
            "remotes",
            "push_pull",
            "pull_requests",
        ),
        "Enough git to version a project and push it to GitHub.",
    ),
    # --- docs & practice ---------------------------------------------------
    LearnResource(
        "mode_sql",
        "Mode SQL Tutorial (Basic -> Advanced -> Analytics)",
        "Mode",
        "https://mode.com/sql-tutorial/",
        "docs",
        300,
        3,
        ("beginner", "intermediate", "advanced"),
        ("sql",),
        _ALL_SQL,
        "Reads like a course, runs queries in the browser - the reference analysts keep open.",
    ),
    LearnResource(
        "pgexercises",
        "PostgreSQL Exercises",
        "pgexercises.com",
        "https://pgexercises.com/",
        "practice",
        240,
        3,
        ("intermediate", "advanced"),
        ("sql",),
        (
            "inner_join",
            "outer_join",
            "subqueries",
            "ctes",
            "aggregates",
            "window_functions",
            "case_when",
            "date_fns_sql",
        ),
        "Graded SQL problems from joins to window functions - the way to actually get fast.",
    ),
    LearnResource(
        "datalemur",
        "DataLemur - SQL & Analytics interview questions",
        "DataLemur (Nick Singh)",
        "https://datalemur.com/",
        "practice",
        180,
        3,
        ("intermediate", "advanced"),
        ("sql",),
        (
            "group_by",
            "having",
            "inner_join",
            "outer_join",
            "subqueries",
            "ctes",
            "window_functions",
        ),
        "Real company SQL interview questions with a free tier - analyst-focused.",
    ),
    LearnResource(
        "leetcode_sql50",
        "LeetCode - Top SQL 50 study plan",
        "LeetCode",
        "https://leetcode.com/studyplan/top-sql-50/",
        "practice",
        150,
        2,
        ("beginner", "intermediate"),
        ("sql",),
        ("select_from", "where", "group_by", "inner_join", "outer_join", "subqueries", "case_when"),
        "50 curated SQL problems, free - the fastest way to drill the core query patterns.",
    ),
    LearnResource(
        "stratascratch",
        "StrataScratch - SQL & Python interview practice",
        "StrataScratch",
        "https://www.stratascratch.com/",
        "practice",
        300,
        4,
        ("intermediate", "advanced"),
        ("sql", "python_data"),
        ("window_functions", "ctes", "subqueries", "groupby_agg", "merge_join", "apply_map"),
        "500+ real interview problems across SQL and pandas, with a free tier.",
    ),
    LearnResource(
        "pandas_docs",
        "pandas User Guide",
        "pandas.pydata.org",
        "https://pandas.pydata.org/docs/user_guide/index.html",
        "docs",
        0,
        4,
        ("intermediate", "advanced"),
        ("python_data",),
        _ALL_PD,
        "The authoritative reference once you know what you're looking for.",
    ),
    LearnResource(
        "matplotlib_docs",
        "Matplotlib Tutorials",
        "matplotlib.org",
        "https://matplotlib.org/stable/tutorials/index.html",
        "docs",
        0,
        4,
        ("intermediate", "advanced"),
        ("dataviz",),
        ("matplotlib_basics", "axes_titles", "subplots", "annotation"),
        "Official, example-driven - the pyplot and artist layers explained.",
    ),
    LearnResource(
        "seaborn_tutorial",
        "seaborn: statistical data visualization - tutorial",
        "seaborn.pydata.org",
        "https://seaborn.pydata.org/tutorial.html",
        "docs",
        0,
        3,
        ("intermediate", "advanced"),
        ("dataviz",),
        ("seaborn_basics", "dist_plots", "cat_plots", "rel_plots"),
        "How to pick and build every statistical plot type.",
    ),
    LearnResource(
        "python_docs_tutorial",
        "The Python Tutorial (official)",
        "docs.python.org",
        "https://docs.python.org/3/tutorial/",
        "docs",
        0,
        3,
        ("beginner", "intermediate"),
        ("python",),
        _ALL_PY,
        "The canonical walkthrough of the language and standard library.",
    ),
    LearnResource(
        "khan_stats",
        "Statistics and Probability",
        "Khan Academy",
        "https://www.khanacademy.org/math/statistics-probability",
        "course",
        0,
        2,
        ("beginner", "intermediate"),
        ("stats",),
        _ALL_STATS,
        "Full course with practice problems and mastery checks - good if video isn't enough.",
    ),
    LearnResource(
        "kaggle_learn",
        "Kaggle Learn micro-courses (Python, Pandas, SQL, Data Viz)",
        "Kaggle",
        "https://www.kaggle.com/learn",
        "course",
        420,
        2,
        ("beginner", "intermediate"),
        ("python", "python_data", "sql", "dataviz"),
        (),
        "Short, hands-on, free completion certificates - a fast way to bank early wins.",
    ),
    LearnResource(
        "leila_gharani",
        "Leila Gharani - Excel, Power Query & Power BI",
        "Leila Gharani",
        "https://www.youtube.com/@LeilaGharani",
        "channel",
        0,
        3,
        ("beginner", "intermediate", "advanced"),
        ("spreadsheets", "powerbi"),
        (),
        "Clear, modern Excel: XLOOKUP, dynamic arrays, Power Query, dashboards.",
    ),
    LearnResource(
        "kevin_stratvert",
        "Kevin Stratvert - Excel & Power BI for beginners",
        "Kevin Stratvert",
        "https://www.youtube.com/@KevinStratvert",
        "channel",
        0,
        1,
        ("beginner",),
        ("spreadsheets", "powerbi"),
        (),
        "Gentle, step-by-step tool tutorials - a good very first stop.",
    ),
    LearnResource(
        "ms_excel_help",
        "Microsoft Excel help & learning",
        "Microsoft",
        "https://support.microsoft.com/excel",
        "docs",
        0,
        2,
        ("beginner", "intermediate", "advanced"),
        ("spreadsheets",),
        (),
        "Official function reference and short how-to guides.",
    ),
    LearnResource(
        "guy_in_a_cube",
        "Guy in a Cube - Power BI",
        "Guy in a Cube",
        "https://www.youtube.com/@GuyInACube",
        "channel",
        0,
        3,
        ("intermediate", "advanced"),
        ("powerbi",),
        (),
        "Practical Power BI and DAX from people who build it daily.",
    ),
    LearnResource(
        "ms_learn_pl300",
        "Microsoft Learn - PL-300 Power BI Data Analyst course",
        "Microsoft Learn",
        "https://learn.microsoft.com/training/courses/pl-300t00",
        "course",
        1440,
        2,
        ("beginner", "intermediate"),
        ("powerbi",),
        (),
        "The official, free path behind the PL-300 exam: model, DAX, visuals, deploy.",
    ),
    LearnResource(
        "dax_guide",
        "DAX Guide (SQLBI)",
        "SQLBI",
        "https://dax.guide/",
        "docs",
        0,
        4,
        ("intermediate", "advanced"),
        ("powerbi",),
        (
            "dax_basics",
            "dax_aggregations",
            "filter_context",
            "calculate",
            "iterators",
            "time_intelligence",
        ),
        "Every DAX function with its filter-context behaviour - the reference to keep open.",
    ),
    LearnResource(
        "tableau_training",
        "Tableau free training videos",
        "Tableau",
        "https://www.tableau.com/learn/training",
        "course",
        600,
        2,
        ("beginner", "intermediate"),
        ("tableau",),
        (),
        "Official free videos from connecting data to LOD expressions and dashboards.",
    ),
    LearnResource(
        "tableau_help",
        "Tableau Desktop help",
        "Tableau",
        "https://help.tableau.com/current/pro/desktop/en-us/",
        "docs",
        0,
        3,
        ("intermediate", "advanced"),
        ("tableau",),
        (),
        "The official reference: calculations, LOD expressions, table calculations.",
    ),
    LearnResource(
        "de_zoomcamp",
        "Data Engineering Zoomcamp (DataTalksClub)",
        "DataTalksClub",
        "https://github.com/DataTalksClub/data-engineering-zoomcamp",
        "course",
        3000,
        3,
        ("intermediate", "advanced"),
        ("data_eng",),
        (),
        "Free course: Docker, warehouses, dbt, orchestration, batch and streaming, with projects.",
    ),
    LearnResource(
        "dbt_learn",
        "dbt Learn (free courses)",
        "dbt Labs",
        "https://learn.getdbt.com/",
        "course",
        300,
        2,
        ("beginner", "intermediate"),
        ("data_eng",),
        ("dbt_models", "dbt_tests", "dimensional_modeling", "incremental_loads", "data_quality"),
        "dbt Fundamentals and beyond - models, refs, tests, docs, incremental models.",
    ),
    LearnResource(
        "dbt_docs",
        "dbt documentation",
        "dbt Labs",
        "https://docs.getdbt.com/",
        "docs",
        0,
        3,
        ("intermediate", "advanced"),
        ("data_eng",),
        ("dbt_models", "dbt_tests", "incremental_loads", "scd"),
        "Reference for models, tests, snapshots (SCD) and incremental strategies.",
    ),
    LearnResource(
        "airflow_tutorial",
        "Apache Airflow tutorial",
        "Apache Airflow",
        "https://airflow.apache.org/docs/apache-airflow/stable/tutorial/index.html",
        "docs",
        120,
        3,
        ("intermediate", "advanced"),
        ("data_eng",),
        ("orchestration", "idempotency"),
        "Official walkthrough: DAGs, tasks, scheduling, retries.",
    ),
    LearnResource(
        "spark_quickstart",
        "Apache Spark quick start",
        "Apache Spark",
        "https://spark.apache.org/docs/latest/quick-start.html",
        "docs",
        60,
        3,
        ("intermediate", "advanced"),
        ("data_eng",),
        ("spark_basics", "partitioning"),
        "The official first steps with DataFrames and the distributed model.",
    ),
    LearnResource(
        "seattle_data_guy",
        "Seattle Data Guy - data engineering",
        "Seattle Data Guy",
        "https://www.youtube.com/@SeattleDataGuy",
        "channel",
        0,
        2,
        ("beginner", "intermediate"),
        ("data_eng",),
        (),
        "Career-oriented data engineering: pipelines, modelling, tools and interviews.",
    ),
)

_BY_ID: dict[str, LearnResource] = {r.id: r for r in RESOURCES}


# --------------------------------------------------------------------------- #
# the profile -> resource labels (the "training data")
# --------------------------------------------------------------------------- #
# key: "<role-or-domain>:<band>"  ->  ordered resource ids (best first) for that
# exact learner profile.  A "<domain>:*" key applies to every band.
PROFILE_RECOMMENDATIONS: dict[str, tuple[str, ...]] = {
    "data analyst:beginner": (
        "fcc_da_bootcamp",
        "alex_analyst",
        "fcc_sql_full",
        "kaggle_learn",
        "leetcode_sql50",
    ),
    "data analyst:intermediate": (
        "luke_python_da",
        "corey_pandas",
        "statquest_stats",
        "mode_sql",
        "datalemur",
    ),
    "data analyst:advanced": (
        "statquest_channel",
        "datalemur",
        "stratascratch",
        "pgexercises",
        "pandas_docs",
    ),
    "analytics engineer:beginner": ("fcc_sql_full", "dbt_learn", "fcc_git", "kaggle_learn"),
    "analytics engineer:intermediate": ("dbt_learn", "mode_sql", "de_zoomcamp", "pgexercises"),
    "analytics engineer:advanced": ("dbt_docs", "stratascratch", "de_zoomcamp", "mode_sql"),
    "sql:beginner": ("fcc_sql_full", "kaggle_learn", "leetcode_sql50", "mode_sql"),
    "sql:intermediate": ("mode_sql", "leetcode_sql50", "datalemur", "pgexercises"),
    "sql:advanced": ("datalemur", "stratascratch", "pgexercises", "mode_sql"),
    "python:beginner": ("fcc_python_full", "kaggle_learn", "python_docs_tutorial"),
    "python:intermediate": ("python_docs_tutorial", "luke_python_da"),
    "python:advanced": ("python_docs_tutorial",),
    "python_data:beginner": ("fcc_data_analysis_python", "luke_python_da", "kaggle_learn"),
    "python_data:intermediate": ("corey_pandas", "pandas_docs", "stratascratch"),
    "python_data:advanced": ("pandas_docs", "stratascratch", "corey_pandas"),
    "stats:beginner": ("statquest_stats", "khan_stats"),
    "stats:intermediate": ("statquest_stats", "khan_stats"),
    "stats:advanced": ("statquest_channel", "statquest_stats"),
    "dataviz:beginner": ("fcc_data_analysis_python", "alex_analyst"),
    "dataviz:intermediate": ("seaborn_tutorial", "matplotlib_docs"),
    "dataviz:advanced": ("matplotlib_docs", "seaborn_tutorial"),
    "spreadsheets:beginner": ("kevin_stratvert", "fcc_da_bootcamp", "exceisfun", "alex_analyst"),
    "spreadsheets:intermediate": ("leila_gharani", "exceisfun", "ms_excel_help"),
    "spreadsheets:advanced": ("leila_gharani", "exceisfun", "ms_excel_help"),
    "powerbi:beginner": ("kevin_stratvert", "ms_learn_pl300", "alex_analyst"),
    "powerbi:intermediate": ("ms_learn_pl300", "guy_in_a_cube", "dax_guide"),
    "powerbi:advanced": ("dax_guide", "guy_in_a_cube"),
    "tableau:beginner": ("tableau_training", "alex_analyst"),
    "tableau:intermediate": ("tableau_training", "tableau_help"),
    "tableau:advanced": ("tableau_help",),
    "data_eng:beginner": ("seattle_data_guy", "dbt_learn", "fcc_sql_full"),
    "data_eng:intermediate": ("de_zoomcamp", "dbt_learn", "airflow_tutorial"),
    "data_eng:advanced": ("de_zoomcamp", "dbt_docs", "spark_quickstart", "airflow_tutorial"),
    "bi analyst:beginner": (
        "fcc_da_bootcamp",
        "kevin_stratvert",
        "ms_learn_pl300",
        "tableau_training",
    ),
    "bi analyst:intermediate": ("ms_learn_pl300", "guy_in_a_cube", "tableau_training", "mode_sql"),
    "bi analyst:advanced": ("dax_guide", "guy_in_a_cube", "tableau_help", "datalemur"),
    "data engineer:beginner": ("fcc_sql_full", "fcc_python_full", "seattle_data_guy", "fcc_git"),
    "data engineer:intermediate": ("de_zoomcamp", "airflow_tutorial", "pgexercises", "dbt_learn"),
    "data engineer:advanced": ("de_zoomcamp", "spark_quickstart", "dbt_docs", "stratascratch"),
    "git:beginner": ("fcc_git",),
    "foundations:beginner": ("fcc_da_bootcamp", "kaggle_learn"),
}

_BAND_LEVEL = {"beginner": 1.7, "intermediate": 3.0, "advanced": 4.3}


def _search_resource(concept_name: str, band: Band, domain: str) -> LearnResource:
    q = urllib.parse.quote_plus(f"{concept_name} {domain} tutorial {band}")
    return LearnResource(
        id=f"search:{concept_name}",
        title=f'Search YouTube: "{concept_name}" ({band})',
        channel="YouTube",
        url=f"https://www.youtube.com/results?search_query={q}",
        kind="video",
        minutes=0,
        level=round(_BAND_LEVEL[band]),
        bands=(band,),
        domains=(domain,),
        concepts=(),
        note="No hand-picked video for this exact skill yet - a scoped search to fill the gap.",
    )


def recommend_resources(
    *,
    profile: str,
    band: Band,
    concepts: set[str],
    concept_names: dict[str, str],
    domains: set[str],
    mastery: float | None = None,
    limit: int = 4,
    require_touch: bool = False,
) -> list[LearnResource]:
    """Resources for one learner profile and a set of target concepts.

    ``profile`` is ``"<role-or-domain>"`` (e.g. ``"data analyst"``, ``"sql"``).
    Starts from the hand-labelled :data:`PROFILE_RECOMMENDATIONS` for
    ``f"{profile}:{band}"``, then fills with a level- and concept-matched score
    over the rest of the library, then guarantees at least one link by adding a
    scoped YouTube search.  ``require_touch`` makes even the hand-labelled picks
    prove they cover the requested concepts/domains - use it for per-phase
    recommendations, leave it off for a whole-track "start here" list.
    """
    bare = {c.split(".")[-1] for c in concepts}
    target = _BAND_LEVEL.get(band, 3.0)
    if mastery is not None:
        target = max(1.0, min(5.0, 1.0 + 3.4 * (1.0 - mastery)))

    picked: list[LearnResource] = []
    seen: set[str] = set()

    def _consider(r: LearnResource, *, from_label: bool) -> None:
        if r.id in seen:
            return
        touches = bool(set(r.concepts) & bare) or bool(set(r.domains) & domains)
        generic = not r.concepts and bool(set(r.domains) & domains)
        if not (touches or generic) and (require_touch or not from_label):
            return
        seen.add(r.id)
        picked.append(r)

    for rid in PROFILE_RECOMMENDATIONS.get(f"{profile}:{band}", ()):
        if rid in _BY_ID:
            _consider(_BY_ID[rid], from_label=True)

    ranked = sorted(
        (r for r in RESOURCES if r.id not in seen),
        key=lambda r: (
            -len(set(r.concepts) & bare),
            -int(band in r.bands),
            abs(r.level - target),
        ),
    )
    for r in ranked:
        if len(picked) >= limit:
            break
        _consider(r, from_label=False)

    picked = picked[:limit]
    if not any(r.kind in ("video", "playlist") for r in picked):
        one = sorted(bare)[0] if bare else ""
        name = concept_names.get(one, one) or (next(iter(domains), "data analytics"))
        picked.append(_search_resource(name, band, next(iter(domains), "data")))
    return picked


def resource_by_id(rid: str) -> LearnResource | None:
    return _BY_ID.get(rid)
