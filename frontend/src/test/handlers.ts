import { http, HttpResponse } from "msw";

import type { Catalogue } from "../lib/api";

export const catalogueFixture: Catalogue = {
  concepts: [
    { id: "integers", name: "Integers & number line" },
    { id: "fractions", name: "Fractions" },
    { id: "linear_eq", name: "Linear equations" },
    { id: "quadratics", name: "Quadratic equations" },
  ],
  resources: [
    { id: "integers:lesson", concepts: ["integers"], difficulty: 1, minutes: 6, kind: "lesson" },
    { id: "integers:practice", concepts: ["integers"], difficulty: 1, minutes: 3.6, kind: "practice" },
    { id: "fractions:lesson", concepts: ["fractions"], difficulty: 2, minutes: 9, kind: "lesson" },
    { id: "linear_eq:lesson", concepts: ["linear_eq"], difficulty: 3, minutes: 12, kind: "lesson" },
    { id: "quadratics:lesson", concepts: ["quadratics"], difficulty: 4, minutes: 15, kind: "lesson" },
  ],
  goals: ["quadratics", "linear_eq"],
  discovered: false,
};

function step(id: string, concept: string, reason: string, extra: Record<string, unknown> = {}) {
  return {
    resource_id: id,
    concept_id: concept,
    reason,
    review: false,
    title: `${concept} — an open article`,
    url: `https://en.wikipedia.org/wiki/${concept}`,
    source: "wikipedia",
    kind: "article",
    difficulty: 2.4,
    ...extra,
  };
}

function planFor(speed: string) {
  return {
    feasible: true,
    note: "",
    total_minutes: speed === "fast" ? 40 : 26,
    objective: { neg_gain: -2.1, seconds: 1600, load: 1.2, diff_jump: 3, neg_review: 0 },
    steps: [
      step("integers::wikipedia:0", "integers", "Builds **Integers & number line**; no prerequisites."),
      step("fractions::wikipedia:0", "fractions", "Spaced review of **Fractions**.", {
        review: true,
        difficulty: 1.8,
      }),
      step("quadratics::wikipedia:0", "quadratics", "Builds **Quadratic equations**; prerequisites covered."),
    ],
    sessions: [
      { start: 0, end: 2 },
      { start: 2, end: 3 },
    ],
  };
}

const RESOLVE = {
  goal: "quadratic equations",
  domain: "algebra",
  source: "seed" as const,
  assessable: true,
  goals: ["quadratics"],
  concepts: catalogueFixture.concepts,
  prerequisites: [
    ["integers", "fractions"],
    ["fractions", "quadratics"],
  ],
};

let lastBand = "intermediate";

function assessState(answered: number, band = "intermediate") {
  const done = answered >= 2;
  return {
    done,
    band,
    answered,
    progress: Math.min(1, answered / 2),
    style: done ? { hands_on: 0.6, recall: 0.5, note: "balanced" } : null,
    question: done
      ? null
      : {
          item_id: `q${answered}`,
          skill: "integers",
          kind: "mcq" as const,
          stem: "Which is smallest?",
          choices: ["-5", "-1", "0", "3"],
        },
    estimates: [
      { skill: "integers", theta: 0.2, se: 0.7, mastery: 0.55, n_items: answered, confident: false },
      { skill: "quadratics", theta: -0.3, se: 0.8, mastery: 0.4, n_items: answered, confident: false },
    ],
  };
}

export const handlers = [
  http.get("/catalogue", () => HttpResponse.json(catalogueFixture)),

  http.post("/resolve", async ({ request }) => {
    const b = (await request.json()) as { goal: string };
    if (b.goal.includes("__boom__"))
      return HttpResponse.json({ detail: "could not resolve" }, { status: 502 });
    return HttpResponse.json({ ...RESOLVE, goal: b.goal });
  }),

  http.post("/assess/start", async ({ request }) => {
    const b = (await request.json()) as { band?: string };
    lastBand = b.band ?? "intermediate";
    return HttpResponse.json(assessState(0, lastBand));
  }),
  http.post("/assess/answer", () => HttpResponse.json(assessState(2, lastBand))),

  http.post("/recommend", async ({ request }) => {
    const body = (await request.json()) as { mode?: string; speed?: string; goals: string[] };
    if (body.goals.includes("__boom__"))
      return HttpResponse.json({ detail: "unknown concepts" }, { status: 422 });
    if (body.mode === "pareto")
      return HttpResponse.json({
        paths: [planFor("fast"), planFor("slow")],
        meta: { mode: "pareto", returned: 2 },
      });
    return HttpResponse.json({
      paths: [planFor(body.speed ?? "normal")],
      meta: { mode: body.mode ?? "sequence", returned: 1, speed: body.speed ?? "normal" },
    });
  }),

  http.post("/roadmap", async ({ request }) => {
    const b = (await request.json()) as {
      goal: string;
      weekly_hours?: number;
      band?: string;
      speed?: "slow" | "normal" | "fast";
    };
    const speed = b.speed ?? "normal";
    const pace = { slow: "deliberate", normal: "steady", fast: "fast" }[speed];
    const hoursMult = { slow: 1.3, normal: 1.0, fast: 0.78 }[speed];
    const vid = {
      id: "fcc_sql_full",
      title: "SQL Tutorial - Full Database Course for Beginners",
      channel: "freeCodeCamp",
      url: "https://www.youtube.com/watch?v=HXV3zeQKqGY",
      kind: "video",
      minutes: 240,
      level: 1,
      note: "The standard first SQL course.",
      free: true,
      embed_url: "https://www.youtube-nocookie.com/embed/HXV3zeQKqGY",
      thumbnail: "https://i.ytimg.com/vi/HXV3zeQKqGY/hqdefault.jpg",
    };
    return HttpResponse.json({
      roadmap: {
        goal: "quadratics",
        domain: "algebra",
        role: null,
        pace,
        weekly_hours: b.weekly_hours ?? 5,
        band: b.band ?? "intermediate",
        starting_readiness: 0.1,
        target_readiness: 1,
        already_have: [],
        you_are_here: {},
        total_hours: Math.round(40 * hoursMult),
        total_weeks: Math.round(8 * hoursMult),
        finish_estimate: "2026-05-01",
        deadline: null,
        on_track: null,
        notes: [`Pace: ${pace} - estimates assume an average learning speed.`],
        recommended: [vid],
        phases: [
          {
            index: 1,
            title: "Foundations of algebra",
            domain: "algebra",
            concept_ids: ["integers", "fractions"],
            concept_names: ["Integers & number line", "Fractions"],
            new_skills: 2,
            est_hours: 16,
            est_weeks: 3.2,
            start_week: 0,
            focus: "Work through Integers & number line, Fractions.",
            checkpoint: "Checkpoint: you can use Fractions confidently.",
            resources: [],
            videos: [vid],
            certifications: [],
          },
          {
            index: 2,
            title: "Applying algebra",
            domain: "algebra",
            concept_ids: ["quadratics"],
            concept_names: ["Quadratic equations"],
            new_skills: 1,
            est_hours: 24,
            est_weeks: 4.8,
            start_week: 3.2,
            focus: "Work through Quadratic equations.",
            checkpoint: "Checkpoint: you can solve quadratics.",
            resources: [],
            videos: [],
            certifications: [
              {
                id: "kaggle_sql",
                name: "Intro to SQL + Advanced SQL",
                provider: "Kaggle Learn",
                url: "https://www.kaggle.com/learn/intro-to-sql",
                level: "entry",
                free: true,
                price_note: "Free — free completion certificates",
                hours: 8,
                blurb: "Two short hands-on courses.",
              },
            ],
          },
        ],
        certifications: [
          {
            id: "kaggle_sql",
            name: "Intro to SQL + Advanced SQL",
            provider: "Kaggle Learn",
            url: "https://www.kaggle.com/learn/intro-to-sql",
            level: "entry",
            free: true,
            price_note: "Free — free completion certificates",
            hours: 8,
            blurb: "Two short hands-on courses.",
          },
        ],
      },
    });
  }),

  http.post("/schedule", async ({ request }) => {
    const b = (await request.json()) as { deadline: string; goals: string[] };
    if (b.goals.includes("__boom__"))
      return HttpResponse.json({ detail: "unknown concepts" }, { status: 422 });
    return HttpResponse.json({
      calendar: {
        feasible: true,
        note: "",
        start: "2026-01-05",
        deadline: b.deadline,
        finish: "2026-01-28",
        slack_days: 3,
        weeks: 4.5,
        hours_per_week: 5,
        hours_per_week_needed: 0,
        n_retention: 2,
        goal_mastery: { "Quadratic equations": 0.86 },
        reasons: ["On the deadline every goal skill is at or above the 75% mastery threshold."],
        steps: [
          {
            day: "2026-01-05",
            weekday: 0,
            slot_index: 0,
            concept_id: "integers",
            concept: "Integers & number line",
            resource_id: "integers::wikipedia:0",
            title: "Integers",
            url: "https://en.wikipedia.org/wiki/Integer",
            source: "wikipedia",
            kind: "teach",
            minutes: 12,
          },
          {
            day: "2026-01-12",
            weekday: 0,
            slot_index: 5,
            concept_id: "quadratics",
            concept: "Quadratic equations",
            resource_id: "quadratics::wikipedia:0",
            title: "Quadratic equation",
            url: "https://en.wikipedia.org/wiki/Quadratic_equation",
            source: "wikipedia",
            kind: "retention",
            minutes: 11,
          },
        ],
      },
      meta: { domain: "algebra" },
    });
  }),

  http.post("/observe", () =>
    HttpResponse.json({
      n_interactions: 1,
      time_budget_min: 115,
      mean_velocity: 1.08,
      mastery: { integers: 0.52 },
    }),
  ),

  http.post("/explain", async ({ request }) => {
    const b = (await request.json()) as { resource_id: string };
    return HttpResponse.json({
      resource_id: b.resource_id,
      reason: `Why ${b.resource_id}: grounded in the graph.`,
    });
  }),

  http.get("/health", () =>
    HttpResponse.json({ status: "ok", version: "1.0.0", concepts: 4, resources: 5 }),
  ),

  http.post("/graph/health", async ({ request }) => {
    const b = (await request.json()) as { learners: number };
    return HttpResponse.json({
      domain: "algebra",
      source: "seed",
      observations: b.learners ? 18000 : 3,
      watched: 4,
      clean: !b.learners,
      pruned: [],
      added: [],
      suggested: [],
      reweighted: [],
      recovery: b.learners
        ? { recall: 1, precision_drop: 0.5, hidden: [], injected: [], hidden_recovered: [], injected_pruned: [] }
        : null,
    });
  }),

  http.get("/practice/tasks", () => HttpResponse.json(practiceTasksFixture)),
  http.post("/practice/submit", () => HttpResponse.json(practiceFailFixture)),
  http.get("/library", ({ request }) => {
    const pace = new URL(request.url).searchParams.get("pace");
    return HttpResponse.json({ ...libraryFixture, pace: pace && pace !== "auto" ? pace : "steady" });
  }),
  http.get("/portfolio/:id", () => HttpResponse.json(portfolioFixture)),
  http.put("/portfolio/:id/profile", async ({ request }) => {
    const b = (await request.json()) as { name: string; public: boolean };
    return HttpResponse.json({ ...portfolioFixture, name: b.name, public: b.public, slug: "ada", share_path: "/p/ada" });
  }),
  http.post("/portfolio/:id/projects", async ({ request }) => {
    const b = (await request.json()) as { project_id: string; title: string; repo_url: string; skills: string[] };
    return HttpResponse.json({
      ...portfolioFixture,
      projects: [{ ...b, summary: "", demo_url: "", added_at: "2026-10-13T10:00", link_ok: true }],
    });
  }),
  http.post("/portfolio/:id/reprove", () =>
    HttpResponse.json({
      seed: null,
      reproduced: false,
      passed: 1,
      tested: 1,
      proofs: {
        products_list: {
          payload: { slug: "learner-abc", task_id: "products_list", answer_sha256: "ab", seeds: [5, 6, 7], passed: true, fresh: true, datasets: 3, at: "2026-10-22T16:05:00" },
          sig: "f".repeat(64),
          runs: [],
        },
      },
    }),
  ),
  http.post("/what-fits", () =>
    HttpResponse.json({
      confidence: 0.9,
      capacity_hours: 20,
      chosen: [{ concept_id: "quadratics", concept: "Quadratic equations", value: 1 }],
      dropped: [{ concept_id: "window_functions", concept: "Window functions", value: 1 }],
      p_finish: 0.93,
      expected_hours: 12,
      p90_hours: 17,
      value_share: 0.5,
      hours_per_week_for_all: 8,
      by_expected_time: { goals: ["Quadratic equations", "Window functions"], p_finish: 0.55 },
    }),
  ),
  http.post("/reschedule", async ({ request }) => {
    const b = (await request.json()) as { log: { done_minutes: number; planned_minutes: number }[] };
    const missed = b.log.some((e) => e.done_minutes < e.planned_minutes);
    return HttpResponse.json({
      adherence: missed ? 0.65 : 1,
      logged_days: b.log.length,
      done_minutes: 0,
      planned_minutes_so_far: missed ? 40 : 0,
      effective_hours_per_week: 4,
      busy_events: 0,
      past_days: [{ day: "2026-01-05", planned_minutes: 40 }],
      remaining_minutes: missed ? 300 : 200,
      feasible: true,
      finish: "2026-01-20",
      deadline: "2026-01-26",
      hours_per_week_needed: 0,
      reasons: missed ? ["You've been studying about 65% of planned time, so the remaining work is planned as 300 minutes instead of 200."] : [],
      blocks: [
        { day: "2099-01-06", start: "19:00", end: "19:45", minutes: 45, concept_id: "integers", concept: "Integers & number line", title: "Integers", kind: "teach", part: 1, parts: 2 },
      ],
      days: [{ day: "2099-01-06", busy_minutes: 0, fatigue: 0, cap_minutes: 90, max_block: 60, study_minutes: 45 }],
      busy_spans: {},
      forecast: { p50: "2026-01-21", p80: "2026-01-24", p95: "2026-01-29", p_on_time: 0.83, trust: 0.4, checks: 5, hits: 3 },
      study_times: [
        { slot: "weekend morning", multiplier: 1.3, answers: 14 },
        { slot: "weekday night", multiplier: 0.8, answers: 9 },
      ],
      focus: { half_life_min: 30, block_min: 25, answers: 40 },
      practice_answers: 60,
      memory: {
        recalls: 6,
        topics: [
          { concept_id: "null_logic", concept: "NULL & three-valued logic", half_life_days: 2.4, recalls: 4, source: "measured" },
          { concept_id: "where", concept: "WHERE & comparison operators", half_life_days: 9, recalls: 0, source: "from prerequisites" },
        ],
      },
      reviews: [
        { concept_id: "null_logic", concept: "NULL & three-valued logic", day: "2099-01-05", start: "20:00", end: "20:10", due: "2099-01-05", recall_at_due: 0.62, before: "LEFT / RIGHT / FULL JOIN", priority: 3, late: false },
      ],
      slowdowns: [
        {
          concept_id: "outer_join",
          concept: "LEFT / RIGHT / FULL JOIN",
          ratio: 0.3,
          suspects: [{ concept_id: "null_logic", concept: "NULL & three-valued logic", kind: "missing_prerequisite", mastery: 0.2 }],
        },
      ],
      velocity: {
        aware: true,
        measured_topics: 1,
        topics: [
          { concept_id: "quadratics", concept: "Quadratic equations", ratio: 1.6, velocity: 0.6, hours_to_master: 1.2, source: "predicted" },
          { concept_id: "integers", concept: "Integers & number line", ratio: 0.5, velocity: 2.1, hours_to_master: 0.3, source: "measured" },
        ],
      },
      naive: { finish: "2026-01-28", feasible: false, notes: ["3 block(s) clash with events in your calendar."] },
    });
  }),
  http.get("/library/stats", () =>
    HttpResponse.json({ harvested: "2026-10-13", problems: 600, videos: 195, leetcode: 230, hackerrank: 252, open_sites: 68, domains: ["sql"] }),
  ),
  http.get("/certifications", () =>
    HttpResponse.json({
      certifications: [
        { id: "hr_sql", name: "HackerRank SQL (Basic)", provider: "HackerRank", url: "https://www.hackerrank.com/skills-verification/sql_basic", level: "entry", free: true, price_note: "", hours: 2, blurb: "A free skills badge." },
        { id: "pl300", name: "Microsoft PL-300", provider: "Microsoft", url: "https://learn.microsoft.com/", level: "associate", free: false, price_note: "Paid exam", hours: 60, blurb: "Power BI Data Analyst." },
      ],
    }),
  ),
];

const video = (id: string, concept: string | null, kind: string, level = "") => ({
  video_id: id,
  title: `Video ${id}`,
  channel: "freeCodeCamp.org",
  minutes: 12,
  views: 1000,
  url: `https://www.youtube.com/watch?v=${id}`,
  domain: "algebra",
  concept,
  level,
  kind,
});
const problem = (title: string, difficulty: string, platform = "LeetCode") => ({
  platform,
  set: platform === "LeetCode" ? "SQL 50" : "SQL track",
  section: "",
  title,
  url: `https://example.com/${title.replaceAll(" ", "-")}`,
  difficulty,
  domain: "algebra",
  concept: "integers",
  free: true,
});
export const libraryFixture = {
  pace: "steady",
  pace_text: "You learn at a steady pace.",
  pace_source: "your speed setting",
  harvested: "2026-10-13",
  totals: { problems: 2, videos: 2, stretch: 1, review: 0, mixed: 0, weeks: 1, leetcode: 1, hackerrank: 1 },
  courses: [video("course00001", null, "course", "Beginner")],
  steps: [
    {
      concept_id: "integers",
      domain: "algebra",
      concept: "Integers & number line",
      mastery: 0.2,
      video: video("lesson00001", "integers", "lesson"),
      problems: [problem("Big Countries", "Easy"), problem("Revising the Select Query", "Easy", "HackerRank")],
    },
  ],
  weeks: [
    {
      week: 1,
      minutes: 50,
      items: [
        { type: "video", concept_id: "integers", concept: "Integers & number line", minutes: 12, title: "Video lesson00001", url: "u", video_id: "lesson00001", channel: "c" },
        { type: "problem", ...problem("Big Countries", "Easy"), concept_id: "integers", concept: "Integers & number line", minutes: 12 },
      ],
    },
  ],
  stretch: [{ ...problem("Hard One", "Hard"), concept_id: "integers" }],
  review: [],
  mixed: [],
};

export const practiceTasksFixture = {
  start: "orders_per_customer",
  path: ["null_logic", "outer_join"],
  mastery: { null_logic: 0.9, outer_join: 0.09 },
  p_correct: { null_logic: 0.83, outer_join: 0.26 },
  schema: {
    customers: {
      rows: 6,
      columns: [
        { name: "id", type: "INTEGER", pk: true, nulls: 0 },
        { name: "city", type: "TEXT", pk: false, nulls: 1 },
      ],
    },
  },
  tasks: [
    {
      id: "unknown_city",
      concept_id: "null_logic",
      concept: "NULL & three-valued logic",
      prompt: "Names of the customers whose city is unknown.",
      ordered: false,
      minutes: 6,
      hints: ["NULL means unknown: test it with IS NULL.", "SELECT … FROM … WHERE … IS NULL"],
    },
    {
      id: "orders_per_customer",
      concept_id: "outer_join",
      concept: "LEFT / RIGHT / FULL JOIN",
      prompt: "Every customer's name with their number of orders - customers with none show 0.",
      ordered: false,
      minutes: 12,
      hints: ["LEFT JOIN keeps every row of the left table.", "SELECT …, COUNT(…) FROM … LEFT JOIN … ON … = … GROUP BY …"],
    },
  ],
};

export const practiceFailFixture = {
  task_id: "orders_per_customer",
  correct: false,
  result: {
    columns: ["name", "COUNT(*)"],
    rows: [["Asha", 2], ["Eshan", 1]],
    error: "",
    truncated: false,
    ms: 0.4,
    row_status: ["ok", "extra"],
    missing_rows: 1,
    expected_rows: 2,
  },
  checks: [
    { id: "runs", label: "Query runs", passed: true, detail: "Ran in 0.4 ms." },
    { id: "values", label: "Same rows and values", passed: false, detail: "1 expected row(s) not matched." },
  ],
  p_correct_before: 0.26,
  diagnoses: [
    {
      code: "count_star_outer",
      concept_id: "null_logic",
      weight: 0.9,
      message: "COUNT(*) counts the NULL-padded row an outer join adds for 'no match'.",
    },
  ],
  mastery: {
    outer_join: { name: "LEFT / RIGHT / FULL JOIN", before: 0.09, after: 0.21 },
    null_logic: { name: "NULL & three-valued logic", before: 0.9, after: 0.65 },
  },
  edge_evidence: [{ from: "null_logic", to: "outer_join", confidence: 0.37 }],
  plan: {
    feasible: true,
    note: "",
    total_minutes: 30,
    objective: { neg_gain: -1, seconds: 1800, load: 0.5, diff_jump: 0, neg_review: 0 },
    steps: [
      { resource_id: "null_logic:practice", concept_id: "null_logic", reason: "", repair: true },
      { resource_id: "outer_join:practice", concept_id: "outer_join", reason: "" },
    ],
    sessions: [],
  },
  next_task: "unknown_city",
  replan_ms: 0.6,
  fix_clip: {
    code: "count_star_outer",
    concept_id: "null_logic",
    concept: "NULL & three-valued logic",
    moments: [
      { video_id: "nullclip001", title: "SQL NULL Functions", channel: "Data With Baraa", start: 1092, end: 1463, chapter: "Handle NULL - Mathematical Operators", score: 0.7, kind: "chapter", why: "" },
      { video_id: "nullclip002", title: "SQL Course for Beginners", channel: "Programming with Mosh", start: 4311, end: 4458, chapter: "The IS NULL Operator", score: 0.6, kind: "chapter", why: "" },
    ],
  },
};

export const portfolioFixture = {
  name: "A Syntropix learner",
  headline: "",
  github: "",
  linkedin: "",
  slug: "learner-abc",
  public: false,
  skills: {
    sql: [
      {
        task_id: "products_list",
        concept: "select_from",
        concept_name: "SELECT ... FROM",
        domain: "sql",
        kind: "sql",
        prompt: "List every product's name and price.",
        answer: "SELECT name, price FROM products",
        checks: ["Runs without errors", "Same rows and values"],
        result_preview: [["Pen", 1.5]],
        columns: ["name", "price"],
        solved_at: "2026-10-13T09:00",
        attempts: 2,
        rechecked: true,
      },
    ],
  },
  projects: [],
  solved: 1,
  rechecked_ok: 1,
  fresh_ok: 0,
  fresh_testable: 1,
  mastery: {},
  built: "today",
  share_path: "/p/learner-abc",
};
