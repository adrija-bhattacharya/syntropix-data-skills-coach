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
    };
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
    };
    return HttpResponse.json({
      roadmap: {
        goal: "quadratics",
        domain: "algebra",
        role: null,
        pace: "steady",
        weekly_hours: b.weekly_hours ?? 5,
        band: b.band ?? "intermediate",
        starting_readiness: 0.1,
        target_readiness: 1,
        already_have: [],
        you_are_here: {},
        total_hours: 40,
        total_weeks: 8,
        finish_estimate: "2026-05-01",
        deadline: null,
        on_track: null,
        notes: ["Pace: steady - estimates assume an average learning speed."],
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
];
