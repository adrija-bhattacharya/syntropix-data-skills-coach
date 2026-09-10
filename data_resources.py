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

import urllib.parse
from dataclasses import dataclass

Band = str  # "beginner" | "intermediate" | "advanced"


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
)

_BY_ID: dict[str, LearnResource] = {r.id: r for r in RESOURCES}


# --------------------------------------------------------------------------- #
# the profile -> resource labels (the "training data")
# --------------------------------------------------------------------------- #
# key: "<role-or-domain>:<band>"  ->  ordered resource ids (best first) for that
# exact learner profile.  A "<domain>:*" key applies to every band.
PROFILE_RECOMMENDATIONS: dict[str, tuple[str, ...]] = {
    "data analyst:beginner": ("fcc_da_bootcamp", "alex_analyst", "fcc_sql_full", "kaggle_learn"),
    "data analyst:intermediate": ("luke_python_da", "corey_pandas", "statquest_stats", "mode_sql"),
    "data analyst:advanced": ("statquest_channel", "pgexercises", "pandas_docs", "corey_pandas"),
    "analytics engineer:beginner": ("fcc_sql_full", "fcc_python_full", "fcc_git", "kaggle_learn"),
    "analytics engineer:intermediate": ("mode_sql", "luke_python_da", "pgexercises", "fcc_git"),
    "analytics engineer:advanced": ("pgexercises", "pandas_docs", "mode_sql"),
    "sql:beginner": ("fcc_sql_full", "kaggle_learn", "mode_sql"),
    "sql:intermediate": ("mode_sql", "alex_analyst", "pgexercises"),
    "sql:advanced": ("pgexercises", "mode_sql"),
    "python:beginner": ("fcc_python_full", "kaggle_learn", "python_docs_tutorial"),
    "python:intermediate": ("python_docs_tutorial", "luke_python_da"),
    "python:advanced": ("python_docs_tutorial",),
    "python_data:beginner": ("fcc_data_analysis_python", "luke_python_da", "kaggle_learn"),
    "python_data:intermediate": ("corey_pandas", "pandas_docs"),
    "python_data:advanced": ("pandas_docs", "corey_pandas"),
    "stats:beginner": ("statquest_stats", "khan_stats"),
    "stats:intermediate": ("statquest_stats", "khan_stats"),
    "stats:advanced": ("statquest_channel", "statquest_stats"),
    "dataviz:beginner": ("fcc_data_analysis_python", "alex_analyst"),
    "dataviz:intermediate": ("seaborn_tutorial", "matplotlib_docs"),
    "dataviz:advanced": ("matplotlib_docs", "seaborn_tutorial"),
    "spreadsheets:beginner": ("fcc_da_bootcamp", "exceisfun", "alex_analyst"),
    "spreadsheets:intermediate": ("exceisfun",),
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
