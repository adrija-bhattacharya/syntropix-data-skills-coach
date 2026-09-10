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

function assessState(answered: number) {
  const done = answered >= 2;
  return {
    done,
    answered,
    progress: Math.min(1, answered / 2),
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

  http.post("/assess/start", () => HttpResponse.json(assessState(0))),
  http.post("/assess/answer", () => HttpResponse.json(assessState(2))),

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
