# Syntropix - your data-skills coach

*(the engine underneath is VELPO, the personalised learning-path optimiser)*

Give it a **data-analytics goal or a target role** ("become a data analyst",
"SQL window functions", "A/B testing", *"I'm a complete beginner"*).  It measures
where you are with a short **adaptive test**, discovers the best **open**
resources, and produces the **provably-optimal ordered sequence** to your goal -
using classic **Design-and-Analysis-of-Algorithms** machinery (graph traversal +
dynamic programming + A\*) instead of black-box reinforcement learning.

Then it keeps you on track: practice that is **run and graded** (SQL, Python,
pandas, Excel and more), with each mistake named and linked to **the exact minute
of a checked YouTube video** that explains it; a study plan that **reads your real
calendar back** and is sized to **your own learning speed**; reviews booked
**just before you'd forget** a topic you need next; and a **proof-of-skill
portfolio** whose answers anyone can **re-test on data they have never seen**.

Domains: `sql`, `python`, `python_data` (pandas/NumPy), `stats`, `dataviz`,
`spreadsheets` (Excel), `powerbi`, `tableau`, `data_eng`, `git`, `dsa_python`,
`foundations` (zero-knowledge on-ramp), plus target roles (data analyst, BI
analyst, data engineer, analytics engineer), plus
the legacy `algebra` curriculum.  Unknown goals get a graph **built from
Wikipedia**.

> **DAA course project.**  The algorithm map is [`ALGORITHMS.md`](ALGORITHMS.md);
> the research design notes are in [`docs/DESIGN.md`](docs/DESIGN.md).

## What makes it different

| Property | VELPO | typical RL / metaheuristic system |
|---|---|---|
| what is optimised (N1) | the **whole sequence** - order *and* resources - by a DP over the poset's order ideals, with **position-aware** costs | a resource set, or "a good path", no guarantee |
| prerequisite / budget validity | **structural**: the plan is a linear extension of the prerequisite poset | soft reward term - can be violated |
| worst-case cost | **`O(#ideals · W · R)`, `#ideals = O((n/w+1)^w)`** for width `w` (+ knapsack fallback) | not stated |
| learning speed (N2) | **first-class per-concept velocity** in the step cost - changes the order and the review count | implicit at best |
| spaced review | the sequence **re-inserts** a concept when it will decay before the goal | none |
| study sessions | a partition DP splits the plan into sessions under time + load caps | none |
| capability input | an **adaptive test** (2PL IRT + max-information item selection) *measures* the learner's level per skill; nothing is self-rated | the learner picks a level, or picks topics |
| resources | **discovered live** from open sources (Wikipedia, Wikibooks, MIT, arXiv, YouTube) and **auto-level-estimated** (readability + jargon + source priors) | a fixed, hand-built catalogue |
| any goal | a **router**: 12 curated seed graphs (SQL / Python / pandas / stats / viz / DSA / …) + **target roles** that union the domains a job needs, else a graph **built from Wikipedia** | one hard-coded curriculum |
| a job role (claim A) | picks the **prerequisite-closed concept set of maximum hiring-readiness inside the budget** — a knapsack over the order-ideal lattice of a weighted poset — and reports a readiness curve | not addressed |
| measurement risk (claim B) | the adaptive test returns mastery **± a standard error**; the planner acts on the **pessimistic lower confidence bound**, reports `P(ready)` per goal skill, and **splices a confidence check** before the concepts that build on a pivotal prerequisite the test left uncertain — two learners with the *same* point mastery get *different* plans | point estimate only; uncertainty discarded |
| a deadline (claim C) | give a **target date** + **weekly availability** and VELPO embeds the plan on a **real calendar** — precedence list-scheduling of the steps plus **expanding-interval reinforcements** — with a guarantee that every goal skill is **≥ threshold on the date** (forgetting between slots modelled), or a precise diagnostic (*"needs ≈ 6.5 h/week for this date"*) | a flat list, no dates, no retention math |
| the graph itself (claim D) | every prerequisite edge carries a **Bayesian confidence** revised from learner trajectories (*did attempting B without A actually predict failure?*); the graph **prunes** edges the data doesn't support, **discovers missing** ones, and the cost model scales prerequisite debt by edge confidence — a **self-healing** knowledge graph | the graph is fixed and trusted as authored |
| the whole picture | a **personalised roadmap**: the full skill set as ordered **phases**, time estimates scaled by your **measured pace**, **real certifications** placed at the phase where you've covered enough to sit them, verified **YouTube courses / playlists** picked for your level and phase, and a **finish estimate** / calendar check | a single next-step list |
| resource recommendations | a curated, verified library — YouTube full-courses (freeCodeCamp, Alex The Analyst, Luke Barousse, StatQuest, Corey Schafer) that **play inline in the app**, SQL practice (LeetCode SQL 50, DataLemur, StrataScratch, PGExercises), official docs, and **real certifications** (HackerRank skill badges, Microsoft PL-300 / DP-900, Coursera Google / IBM / Meta / UC Davis, freeCodeCamp) — driven by an explicit **profile → resource** table: different picks for a beginner vs an advanced learner, per phase | "here are some links" |
| practice (claim E) | every data-analytics / data-engineering skill has graded tasks (174 in all; every concept in SQL, Excel, Python, pandas, statistics, data viz, Power BI, Tableau, data engineering and Git is covered). **SQL** runs in a **read-only SQLite sandbox**, **Python/pandas** in an isolated, time-boxed subprocess (import allow-list, no files or dunders), **Excel formulas** in a built-in evaluator over a practice sheet (fill-down re-checked for `$` anchors), and concept questions (DAX filter context, LOD expressions, SCDs, idempotent loads, p-values, merge conflicts, …) as numeric or multiple-choice answers. Each is graded by its **result**, not its text, and known wrong answers are recognised as the mistake they are (VLOOKUP without FALSE, `== np.nan`, `and` on a Series, a missing `$`, ALL vs ALLEXCEPT, …). A wrong result is **fingerprinted** (fan-out join, `= NULL`, `COUNT(*)` on an outer join, GROUP BY instead of a window, …) into the **prerequisite concept** it implicates; that blame lowers the learner's mastery of the culprit, counts as direct evidence on the graph edge (claim D), and the re-plan routes through a **repair task** before retrying | right / wrong only; no diagnosis of *which* prerequisite failed |
| reading the calendar back (claim F) | **bi-directional**: the learner logs done / half / missed sessions and can import their calendar (`.ics`). Adherence (an exponentially-weighted share of planned minutes actually studied) inflates the remaining work; a **fatigue index** (how much busier a day is than the learner's usual day) lowers that day's cap and shortens its blocks; the rest of the plan is **split into micro-blocks and fitted earliest-first** into free gaps inside the learner's availability, never above the weekly hours offered. Earliest-fit is optimal for a fixed (prerequisite) order of preemptible work (exchange argument) | push-only: a missed day breaks the schedule |
| does a video teach the topic? | every library video is **checked against what it says**: transcript when YouTube serves captions, else the creator's description + chapter list. A discriminative judge (TF-IDF over rich topic profiles built from the skill-check questions and practice tasks; or **Claude** when `ANTHROPIC_API_KEY` is set) keeps a lesson only if it is about *its* topic rather than the skill in general, and finds the **chapter where it's taught** so the player starts there | keyword search results |
| proof of skill | every answer the app **runs and checks correct** goes into a portfolio; the shareable page **re-runs each answer** when it is built, so the proof is the working code, re-checked - plus projects with checked links. Private until the learner publishes it; also downloadable as one self-contained HTML file | self-reported skills, badges |
| a wrong answer (claim H1) | the diagnosed mistake opens **the chapter of a checked video that explains it** (start to next chapter, ~3 min), even when the mistake belongs to a different topic than the task | "watch the lesson again" |
| proof on new data (claim H2) | portfolio answers are **re-tested on freshly generated variants of the practice database**; memorised or lucky answers fail, results are signed and reproducible from their seeds | re-runs on the same data, or a badge |
| forgetting (claim H3) | a **half-life per learner per topic**, fitted from their own answers after a pause (prior from the prerequisites); 10-minute reviews go into **free calendar gaps just before a lesson that needs a fading topic** | one forgetting rate for everyone |
| cold-start (N4) | the adaptive test seeds mastery at interaction #0; then DKT-lite refinement | usually unsolved |
| re-plan (N6) | **anytime A\***: feasible plan instantly, proven-optimal in <1 ms, no retraining | policy retraining, instability |
| evidence (N7) | one benchmark harness over synthetic **and the real Junyi graph** | "no standard benchmark" |

## Easy commands - `python velpo.py <cmd>`

No `make` needed; works the same in Windows PowerShell, macOS and Linux.

```bash
python velpo.py setup       # install Python deps (editable) + frontend npm packages
python velpo.py doctor      # check the environment is ready
python velpo.py demo        # solve ONE path and print it in the terminal (no server)
python velpo.py assess      # take the adaptive diagnostic in the terminal, then plan from your measured level
python velpo.py harvest     # discover real open resources (Wikipedia / Wikibooks / MIT / arXiv / YouTube)
python velpo.py demo --catalogue discovered   # plan against the discovered open resources (with real links)
python velpo.py plan --goal "become a data analyst"   # a role -> the union of the skills it needs
python velpo.py plan --goal "SQL window functions"    # free-text goal -> seed graph, or built from Wikipedia
python velpo.py schedule --goal "learn sql" --by 2026-11-01 --hours-per-week 5   # plan on a real calendar for a deadline
python velpo.py roadmap --goal "become a data analyst" --band beginner --hours-per-week 8   # full roadmap: phases, pace, YouTube + certs
python velpo.py graph-health --goal "learn sql"                                  # self-healing prerequisite graph (recovery demo)
python velpo.py practice --target outer_join                                     # write SQL, get diagnosed, watch the plan adapt
python velpo.py practice --target lookups                                        # same for Excel (any concept id: groupby_agg, lod, scd, ...)
python velpo.py practicebench                                                    # claim E evidence: diagnosis vs right/wrong grading
python velpo.py library                                                          # re-collect LeetCode/HackerRank problems + YouTube lessons
python velpo.py verify-videos                                                    # check each video teaches its topic (+ where), -> harvest/data/video_checks.json
python velpo.py reschedulebench                                                  # claim F evidence: calendar feedback loop vs a fixed calendar
python velpo.py mistakebench                                                     # claim H1: a wrong answer -> the video chapter that explains it
python velpo.py freshbench                                                       # claim H2: re-testing on new data vs memorised / lucky answers
python velpo.py forgetbench                                                      # claim H3: learned per-topic forgetting + just-in-time reviews
python velpo.py velocitybench                                                    # claim G evidence: velocity-sized plans + calibrated forecasts
python velpo.py test        # the whole test suite
python velpo.py lint        # ruff + ruff format --check + mypy --strict
python velpo.py serve       # build the React UI + serve it & the API at http://localhost:8000
python velpo.py api         # API only (autoreload)  -> http://localhost:8000/docs
python velpo.py ui          # React dev server        -> http://localhost:5173  (needs `api` too)
python velpo.py ui-test     # strict tsc + the React test suite (vitest + Testing Library + MSW)
python velpo.py benchmark --dataset all   # VELPO vs greedy / ACO / DQN  -> results/summary*.csv
python velpo.py ablation    # N2 check: does learning velocity change the plan?
python velpo.py datasets    # list / download the benchmark datasets  (--full = whole Junyi graph)
```

See the whole pipeline in one command:

```bash
python velpo.py assess --goal "SQL window functions"              # adaptive test -> plan
python velpo.py demo --goal "pandas groupby" --speed fast
python velpo.py demo --goal "pandas groupby" --speed slow          # different plan - that's N2
python velpo.py seqbench                                           # does optimising the order pay off?
```

(`make` still works too - it just forwards to `python velpo.py`.)

### In VS Code

Open **`velpo.code-workspace`** (recommends the Python / Pylance / Ruff / Mypy extensions).
`Ctrl+Shift+P → Tasks: Run Task` lists **setup / doctor / demo / test / lint / benchmark /
ablation / datasets**; **Run and Debug** has the API and pytest launchers; the Test Explorer
discovers the suite; Ruff formats on save.

## Layout

The code sits **directly at the repo root** - no nesting:

```
velpo.py        the CLI - every task is one command
algorithms/     poset.py (Dilworth + order ideals) · sequencing.py (the core: order-ideal DP + review + sessions)
                graph_traversal.py · dynamic_programming.py (knapsack fallback) · astar.py (anytime) · pareto.py
algorithms/     reschedule.py (calendar loop) · velocity_schedule.py · calibration.py · slowdown.py · chance_goals.py
                study_context.py · forgetting.py (per-topic half-lives + just-in-time reviews, H3)
model/          knowledge_graph.py · learner.py (BKT + velocity + forgetting) · refine.py (DKT-lite) · cost.py
engine.py       orchestration
mistake_moments.py  wrong answer -> the video chapter that explains the mistake (H1)
portfolio.py    proof-of-skill portfolio, signed re-tests on new data (H2) · practice/mutate.py builds the new data
telemetry.py    practice answers with time of day and session clock (study context, forgetting)
explain.py      knowledge-graph-grounded reason strings
domain_data.py  9 curated seed graphs (SQL, Python, pandas, stats, ...) + target roles
domains.py      goal router;  dynamic.py = Wikipedia-built graphs
curriculum.py   legacy algebra curriculum
api.py          FastAPI  (+ serves the built SPA at /)
config.py       tunable constants + weights
frontend/       React 18 + TS + Vite · Tailwind (Stitch theme) · TanStack Query · Router · Zod · Vitest · ⌘K
benchmarks/     benchmark.py · sequencing_bench.py · ablation_velocity.py · datasets.py (synthetic + real Junyi graph)
                reschedule / velocity / velocity_plus / mistake_moments / fresh_proof / forgetting benches
harvest/        library.py (LeetCode, HackerRank, open sites, YouTube) · verify.py (does the video teach it?) · segments.py
tests/          the guarantees
```

### The app

The UI follows the Google Stitch designs in `../assets/stitch_designs/` (the
"DAG runtime" theme, ported to Tailwind). Every number on screen comes from the
API: where a Stitch mock showed a figure VELPO doesn't compute, the screen shows
the nearest real quantity or leaves it out.

| page (sidebar, in order) | what it does |
|---|---|
| **opening page** `/` | the animated Syntropix logo; a live "setting up your space" checklist and start-up log, every number from a real call (topics loaded, links in your map, videos and problems collected, your measured level); quick goal buttons |
| **Today** `/today` | today's session, *how did your last session go?* (one tap feeds the calendar loop), today's re-planned study blocks with times, the next unwatched video, three problems to solve next, day streak, days to the deadline, your pace |
| **Roadmap** `/roadmap` (+ study plan `/plan`, sessions `/session/:n`) | phases to scale in weeks; sessions on real days with typed steps, "Why this now?", what changed since last time, .ics export |
| **Skill Map** `/map` | set a goal, level, hours and date; how the topics connect, coloured by what you know; "is the map right?" (claim D) |
| **Learn (Videos)** `/learn` | every video to watch, in order: full courses beginner → advanced, then one lesson per topic in the order your plan needs; plays inside the site; tick off watched |
| **Practice** `/practice` | two tabs: *Practise here* (SQL / Python / Excel / concept questions run and checked instantly, mistakes named and repaired, and **Watch the fix**: the video chapter that explains your mistake, played in the page) and *LeetCode, HackerRank & more* (real problems, week by week or topic by topic, paced by your velocity; Stretch, Review and More-practice lists) |
| **Projects** `/projects` | 13 portfolio projects on real public datasets, beginner → advanced, filtered to your goal |
| **Portfolio** `/portfolio` | your solved problems (answers re-run and checked, and **re-tested on new data** with one click - by you or anyone viewing your public page), projects with links, a public page at `/p/<name>` when you choose, or a downloadable page. The first browser to open a portfolio gets a private edit key (only its hash is stored on the server); reading the private view or changing anything needs it |
| **Interview Prep** `/interview` | a 30-minute mock interview from the built-in graded tasks, the questions interviewers ask per skill, HackerRank certificate tests, the classic lists (SQL 50, 30 Days of Pandas, 10 Days of Statistics) |
| **Certifications** `/certifications` | real certificates for your goal, start-here → stand-out, free-only filter |
| **Progress** `/progress` | topics known per skill, videos watched, problems solved, streak, skill-check results |
| **Calendar** `/calendar` | your sessions on a calendar; **Your week, re-planned** (sized to your measured speed per topic, with a 50/80% finish forecast): mark sessions done / half / missed, add your calendar (.ics), and the rest is split into blocks around your real week (two-week timeline, export to your calendar); slowdown alerts, your best study times and focus span, and **how long topics stay with you** with 10-minute reviews booked in your free time |
| skill check `/assess`, for teachers `/teacher` | adaptive quiz; class rules + the best plans to choose from (Pareto front) |

All wording is written for beginners; the method names (BKT, IRT, Pareto, …)
appear only in the optional **Design notes** (top-bar toggle) and in
"What do these numbers mean?" (footer).

### The skill library (real problems and videos)

`python velpo.py library` re-collects `harvest/data/library.json`, which the app
reads offline:

* **LeetCode**: the SQL 50, Introduction to Pandas and 30 Days of Pandas study
  plans, plus every other *free* problem in the Database and pandas categories
  (listed for both SQL and pandas, since each can be solved either way), from
  LeetCode's own API;
* **HackerRank**: the SQL, Python (incl. NumPy) and Databases tracks, and the
  10 Days of Statistics challenges, from HackerRank's API;
* **open sites**: SQLBolt, SQLZoo, PostgreSQL Exercises, Kaggle Learn, DataLemur,
  Exercism, w3resource, Khan Academy, OpenIntro, Microsoft Learn (PL-300), DAX
  Guide, Workout Wednesday, the DE Zoomcamp, dbt Learn, Learn Git Branching,
  GitHub Skills…  Each link is fetched at harvest time and dropped if it doesn't answer;
* **YouTube**: four full courses per skill (beginner → advanced) and one lesson
  per topic.  Ids, titles, channels and lengths come from YouTube's results page.
  The rule is: English title, sensible length, a trusted teaching channel first
  (freeCodeCamp, Alex The Analyst, StatQuest, Kevin Stratvert, SQLBI, Guy in a
  Cube, …) else the most-viewed, and the title must name the topic.  Topics with
  no match get no lesson rather than a wrong one.

Every problem and video is tagged with the concept it trains, so
`skill_library.build` lays them along the learner's own graph: concepts in
prerequisite order, Easy → Hard within a concept, mastered concepts moved to
Review.  The learner's **measured velocity** (mastery gained per hour) picks the
pace: *careful* gets every warm-up and parks Hard problems in Stretch; *fast*
gets one warm-up per topic and Hard problems right away, and needs fewer weeks.

`frontend/src` is feature-sliced: `lib/` (zod-validated API client, TanStack
Query hooks, the plan model, .ics export), `context/` (learner + track),
`components/` (the Stitch shell, primitives and the animated logo), `features/{welcome,today,map,assess,plan,learn,
practice,projects,interview,certifications,progress,calendar,teacher}/`.  `python velpo.py ui-test` runs the component
tests against a mock API (MSW).

## Reading the calendar back (claim F)

`python velpo.py reschedulebench` simulates 120 learners per scenario through
real-looking weeks (workdays 09:00-17:30, evening events, busy weekends, sick
days; a block that overlaps an event doesn't happen, and long blocks on draining
days are skipped more often).  Three policies re-plan every morning from the same
work, calendar and luck:

| scenario | policy | on time | days late (if late) | blocks clashing | busiest week vs hours offered |
|---|---|---|---|---|---|
| light calendar | fixed calendar | 92% | 2.4 | 9% | 1.93x |
| light calendar | adaptive, no calendar | 100% | 0 | 6% | 1.0x |
| light calendar | **adaptive + calendar** | **100%** | 0 | **0%** | 1.0x |
| busy calendar | fixed calendar | 57% | 4.7 | 23% | 1.8x |
| busy calendar | adaptive, no calendar | 100% | 0 | 15% | 1.0x |
| busy calendar | **adaptive + calendar** | **100%** | 0 | **0%** | 1.0x |
| very busy + tight deadline | fixed calendar | 24% | 9.6 | 34% | 1.65x |
| very busy + tight deadline | adaptive, no calendar | 89% | 2.7 | 22% | 1.0x |
| very busy + tight deadline | **adaptive + calendar** | **100%** | 0 | **0%** | 1.0x |

The fixed calendar keeps a set evening slot, keeps lessons whole and pushes
whatever was missed to the next day (and so overruns some weeks); the adaptive
loop re-fits the rest into free time within the learner's availability, capped
at the hours they offered.  Reading the calendar is what removes clashes; it
matters most when the learner is very busy (89% -> 100% on time).

## Planning in your own minutes (claim G)

The learner model already measures **velocity** - mastery gained per hour, per
topic.  Inverting the planner's own learning curve, `m(h) = 1 - (1 - m0) e^(-v h / tau)`,
gives the time *this* learner needs: `T = (tau / v) ln((1 - m0) / (1 - m*))`.  The
calendar loop now sizes every topic by it (topics never practised borrow the
speed shown on their prerequisites, shrunk toward the learner's mean), and a
Monte-Carlo over the uncertainty in velocity and adherence turns the plan into
**finish quantiles** (50 / 80 / 95 %) and P(done by the deadline).

`python velpo.py velocitybench` (100 simulated learners per row; true speed per
topic follows the prerequisites' speed with noise - the stated assumption):

| scenario | policy | on time | finish-date error at start | actually done by the "80%" date | late learners flagged by week 2 |
|---|---|---|---|---|---|
| light calendar | lesson minutes | 57% | 13.0 d | 22% | 26% |
| light calendar | **velocity-sized** | 57% | 12.6 d | **79%** | **86%** |
| busy calendar | lesson minutes | 53% | 14.0 d | 14% | 51% |
| busy calendar | **velocity-sized** | 53% | 12.8 d | **73%** | **81%** |
| very busy + tight | lesson minutes | 42% | 13.8 d | 15% | 76% |
| very busy + tight | **velocity-sized** | **49%** | 12.9 d | **77%** | **86%** |

Lesson-minute plans are systematically optimistic (their date holds for 14-22%
of learners); the velocity forecast's 80% date holds for 73-79%, close to its
promise, and it warns most late learners within two weeks.  A third policy,
**matching** slow topics to light days and quick ones to busy days, gave *no
consistent gain* (56 / 53 / 47% on time) and is left off in the app
(`reschedule(..., match=True)` keeps it available for study).

### Five more velocity-aware signals (claims G1-G5)

`python velpo.py velocityplusbench` (simulated learners; assumptions in the file):

| claim | what it does | result |
|---|---|---|
| G1 self-checking forecast | each week the forecast checks whether its own 80% date held for this learner, and widens its bands when it didn't | bursty learners done by the "80%" date: 71% -> **78%** (steady learners stay at 100%) |
| G2 slowdown diagnosis | a topic learned far slower than its prerequisites predict names the likely gap: a weak prerequisite, or a missing one the graph doesn't list (that becomes evidence for the self-healing graph, claim D) | slow topics flagged **98%**, false alarms 3%; missing prerequisite named first **68%** (random weak neighbour 42%), in the top 3 88% |
| G3 what fits | picks the goals that finish with 90% confidence (chance-constrained knapsack over prerequisite closures) instead of by expected time | chosen set actually finished **93%** vs 69% (at a lower share of goal value, 39% vs 64% - the honest trade) |
| G4 best study times | measures how well the learner answers by weekday/weekend x time of day and plans in the best slots | |
| G5 focus span | fits how fast accuracy fades within a session and sizes blocks to it | G4 + G5: days to finish 25 h of learning 51 -> **33** |

## Mistake -> video moment, proof on new data, learned forgetting (claims H1-H3)

**H1 - a wrong answer opens the minute of video that fixes it.**  The graders
already name *why* an answer is wrong and which topic that points at (often not
the task's own topic: a `GROUP BY` task failed because of NULLs).  Syntropix
matches that diagnosis against the chapter lists of the checked library videos
(`harvest/data/video_segments.json`, 1,202 chapters in 92 videos) and plays only
that chapter - start to next chapter - inside the practice page.  No chapter
good enough: the topic's checked lesson at its jump point.
`python velpo.py mistakebench` (43 real wrong answers run through the grader;
a clip is on target when its chapter names the blamed topic, by a fixed
pattern per topic):

| | clip for the mistake | today: video for the task's topic |
|---|---|---|
| on target, all mistakes | **93%** | 67% |
| on target, mistakes that point at *another* topic (11) | **100%** | 0% |
| video to watch (median) | **2.8 min** | 10 min |

**H2 - proof re-tested on data it has never seen.**  A portfolio that only
re-runs saved answers on the practice rows can be gamed: type in the expected
output, or filter on the ids that happen to work.  Syntropix generates a new
variant of the practice database from a seed (all original rows kept so the
traps stay; numbers rescaled; new rows with valid foreign keys, new names, new
categories and new NULLs) and runs the answer and the reference on three such
variants.  Anyone viewing a public portfolio can press **Re-test now**; each
result is signed by the server (HMAC, `POST /attest/verify`) and names its
seeds, so the same data can be rebuilt to reproduce it.  Works for every task
computed from the tables (23 SQL + 16 pandas).
`python velpo.py freshbench`:

| answers that pass the practice data | count | also pass 3 fresh datasets |
|---|---|---|
| memorised (the output typed in as constants) | 39 | **0%** |
| lucky (`WHERE id = 4`, `id IN (...)`, ...) | 12 | **0%** |
| correct, written differently from the reference | 15 | **100%** |

**H3 - forgetting learned per topic, reviews just before they're needed.**  The
planner modelled forgetting with one half-life for everyone and every topic.
Now every answer given after a pause of 12 h+ is a recall test; a Bayesian
grid fit gives each topic its own half-life, with the prior taken from the
topics it builds on (then the learner's average).  A known topic gets a
10-minute review when it would fall below 70% - or the day before a lesson
that needs it, if it wouldn't be 80% fresh by then - placed in a real free gap
of the calendar around the study blocks.
`python velpo.py forgetbench` (150 simulated learners, the 20-topic SQL graph,
a lesson every 2 days; true half-lives vary by learner and follow the
prerequisites - the stated assumption):

| policy | lessons starting with every prerequisite >= 70% remembered | reviews | wasted (still > 90%) |
|---|---|---|---|
| no reviews | 38% | 0 | - |
| one fixed half-life (before) | 70% | 70 | 13% |
| fixed + just in time | 75% | 73 | 18% |
| learned per topic | 69% | 63 | 6% |
| **learned + just in time** | **78%** | **63** | 9% |

A moderate gain: more lessons start ready with 14% fewer reviews than the
fixed model with just-in-time reviews, and half as many wasted ones.

## Benchmark

`python velpo.py benchmark --dataset all` - 60 seeded runs per dataset, tight and
comfortable budgets interleaved.  The optimality reference is exhaustive search
when tractable, else the DP (provably optimal).

**Synthetic algebra curriculum**

| method | safe-behaviour | over-budget | optimality gap | latency |
|---|---|---|---|---|
| **velpo_dp** | **1.00** | **0.00** | **0.000** | ~0.7 ms |
| **velpo_astar** | **1.00** | **0.00** | **0.000** | ~0.5 ms |
| greedy | 0.67 | 0.33 | 0.25 | ~0.2 ms |
| ant colony optimization | 0.67 | 0.33 | 0.00 | ~320 ms |
| Q-learning (DQN-style) | 0.67 | 0.33 | 0.01 | ~70 ms |

**Real Junyi Academy prerequisite graph** (57-concept offline sample; `--full` = 776 concepts)

| method | safe-behaviour | over-budget | optimality gap | latency |
|---|---|---|---|---|
| **velpo_dp** | **1.00** | **0.00** | **0.000** | ~13 ms |
| **velpo_astar** | **1.00** | **0.00** | **0.000** | ~3 ms |
| greedy | 1.00 | 0.00 | **0.27** | ~1 ms |
| ant colony optimization | 0.92 | 0.08 | 0.06 | ~490 ms |
| Q-learning (DQN-style) | 0.70 | 0.30 | 0.06 | ~200 ms |

Only VELPO never returns an over-budget plan **and** is never sub-optimal; A\* reaches
the proven optimum ~150× faster than ACO.  On the real graph greedy stays in budget
but is still 27 % from optimal, and ACO/DQN still overrun it.

## Optimising the *order* is worth it (claim N1)

`python velpo.py seqbench` scores three plans with the **same** position-aware cost
(one that penalises a concept taught before its prerequisites are solid, or long
after they have decayed):

| plan | synthetic | real Junyi graph |
|---|---|---|
| **sequencing DP over order ideals** | — (optimum) | — (optimum) |
| knapsack-select + difficulty-smoothing heuristic order | **+26 %** | **+38 %** |
| greedy (shortest per concept, topological order) | **+33 %** | **+70 %** |

On the real graph the DP also auto-inserts 16 spaced reviews across the 4 goals.
`tests/test_sequencing.py` proves the DP equals exhaustive search over every
linear extension × resource choice on 30 random curricula.

## Learning velocity is load-bearing (claim N2)

`python velpo.py ablation` plans the *same* goal for a fast learner (velocity ×3) and a
slow learner (velocity ×0.45):

| velocity signal | concepts given a different resource | plans differ for |
|---|---|---|
| **on** | **60 %** | **4 / 5 goals** (fast → fuller lessons, slow → shorter practice) |
| off (all velocity = 1.0) | 0 % | 0 / 5 goals |

So the personalisation comes from velocity itself, not an incidental tie-break.
`tests/test_velocity_ablation.py` asserts both rows; the UI exposes it as a
**Learning speed** dropdown in the Learner view.

## Tests

`python velpo.py test` - 129 Python tests + `python velpo.py ui-test` - 19 React tests;
`ruff` + `mypy --strict` + strict `tsc` all clean.  The ones that carry the claims:

* `test_sequencing.py` - the order-ideal DP equals exhaustive search over every linear extension × resource choice; reviews and sessions respect their invariants (N1)
* `test_poset.py` - Dilworth chain cover == max antichain; order-ideal enumeration is correct and complete
* `test_dp_optimality.py` / `test_dp_feasibility.py` - the knapsack fallback is selection-optimal and always prereq/budget-valid
* `test_velocity_ablation.py` - learning velocity changes the optimal plan; removing it removes the divergence (N2)
* `test_refine.py` - valid path at interaction 0, then the DKT-lite estimate tracks the learner (N4)
* `test_astar.py` - anytime A\* returns a feasible plan under any deadline and the proven optimum without one (N6)
* `test_datasets.py` - the real Junyi graph loads, cycles are removed, VELPO plans on it (N7)

## License

MIT.
