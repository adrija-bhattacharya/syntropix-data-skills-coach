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
};

function planFor(speed: string) {
  const kind = speed === "fast" ? "lesson" : "practice";
  return {
    feasible: true,
    note: "",
    total_minutes: speed === "fast" ? 30 : 18,
    objective: {
      neg_gain: -2.1,
      seconds: speed === "fast" ? 1800 : 1080,
      load: 1.2,
      diff_jump: 3,
      neg_review: 0,
    },
    steps: [
      {
        resource_id: `integers:${kind}`,
        concept_id: "integers",
        reason: "Builds **Integers & number line**; no prerequisites; difficulty 1.",
      },
      {
        resource_id: "quadratics:lesson",
        concept_id: "quadratics",
        reason: "Builds **Quadratic equations**; prerequisites covered by earlier steps.",
      },
    ],
  };
}

export const handlers = [
  http.get("/catalogue", () => HttpResponse.json(catalogueFixture)),

  http.post("/recommend", async ({ request }) => {
    const body = (await request.json()) as { mode?: string; speed?: string; goals: string[] };
    if (body.goals.includes("__boom__")) {
      return HttpResponse.json({ detail: "unknown concepts: ['__boom__']" }, { status: 422 });
    }
    if (body.mode === "pareto") {
      return HttpResponse.json({
        paths: [planFor("fast"), planFor("slow")],
        meta: { mode: "pareto", returned: 2 },
      });
    }
    return HttpResponse.json({
      paths: [planFor(body.speed ?? "normal")],
      meta: { mode: body.mode ?? "optimal", returned: 1, speed: body.speed ?? "normal" },
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
    return HttpResponse.json({ resource_id: b.resource_id, reason: `Why ${b.resource_id}: grounded in the graph.` });
  }),
];
