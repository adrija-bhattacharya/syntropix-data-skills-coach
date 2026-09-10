/**
 * Typed VELPO API client.  Every response is validated at runtime with zod, so
 * a shape change on the Python side fails loudly in one place instead of
 * surfacing as `undefined` deep in a component.
 */
import { z } from "zod";

export const Concept = z.object({ id: z.string(), name: z.string() });
export const Resource = z.object({
  id: z.string(),
  concepts: z.array(z.string()),
  difficulty: z.number(),
  minutes: z.number(),
  kind: z.string(),
});
export const Catalogue = z.object({
  concepts: z.array(Concept),
  resources: z.array(Resource),
  goals: z.array(z.string()),
  discovered: z.boolean().default(false),
});

export const Step = z.object({
  resource_id: z.string(),
  concept_id: z.string(),
  reason: z.string(),
  review: z.boolean().default(false),
  check: z.boolean().default(false),
  title: z.string().default(""),
  url: z.string().default(""),
  source: z.string().default(""),
  kind: z.string().default("lesson"),
  difficulty: z.number().default(0),
});
export const Session = z.object({ start: z.number(), end: z.number() });
export const Objective = z.object({
  neg_gain: z.number(),
  seconds: z.number(),
  load: z.number(),
  diff_jump: z.number(),
  neg_review: z.number(),
});
export const Path = z.object({
  feasible: z.boolean(),
  note: z.string(),
  total_minutes: z.number(),
  objective: Objective,
  steps: z.array(Step),
  sessions: z.array(Session).default([]),
  confidence: z.record(z.number()).optional(),
  min_confidence: z.number().optional(),
});
export const RecommendResponse = z.object({
  paths: z.array(Path),
  meta: z.record(z.unknown()),
});

export const CalendarStep = z.object({
  day: z.string(),
  weekday: z.number(),
  slot_index: z.number(),
  concept_id: z.string(),
  concept: z.string(),
  resource_id: z.string(),
  title: z.string().default(""),
  url: z.string().default(""),
  source: z.string().default(""),
  kind: z.enum(["teach", "review", "check", "retention"]),
  minutes: z.number(),
});
export const CalendarPlan = z.object({
  feasible: z.boolean(),
  note: z.string().default(""),
  start: z.string(),
  deadline: z.string(),
  finish: z.string().nullable(),
  slack_days: z.number(),
  weeks: z.number(),
  hours_per_week: z.number(),
  hours_per_week_needed: z.number(),
  n_retention: z.number(),
  goal_mastery: z.record(z.number()).default({}),
  reasons: z.array(z.string()).default([]),
  steps: z.array(CalendarStep).default([]),
});
export const ScheduleResponse = z.object({
  calendar: CalendarPlan,
  meta: z.record(z.unknown()),
});

export const Certification = z.object({
  id: z.string(),
  name: z.string(),
  provider: z.string(),
  url: z.string(),
  level: z.enum(["entry", "associate", "professional"]),
  free: z.boolean(),
  price_note: z.string(),
  hours: z.number(),
  blurb: z.string(),
});
export const LearnResource = z.object({
  id: z.string(),
  title: z.string(),
  channel: z.string(),
  url: z.string(),
  kind: z.string(),
  minutes: z.number().default(0),
  level: z.number().default(3),
  note: z.string().default(""),
  free: z.boolean().default(true),
  embed_url: z.string().default(""),
  thumbnail: z.string().default(""),
});
export const RoadmapPhase = z.object({
  index: z.number(),
  title: z.string(),
  domain: z.string().default(""),
  concept_ids: z.array(z.string()).default([]),
  concept_names: z.array(z.string()).default([]),
  new_skills: z.number(),
  est_hours: z.number(),
  est_weeks: z.number(),
  start_week: z.number(),
  focus: z.string().default(""),
  checkpoint: z.string().default(""),
  resources: z.array(z.record(z.unknown())).default([]),
  videos: z.array(LearnResource).default([]),
  certifications: z.array(Certification).default([]),
});
export const Roadmap = z.object({
  goal: z.string(),
  domain: z.string(),
  role: z.string().nullable(),
  pace: z.enum(["deliberate", "steady", "fast"]),
  weekly_hours: z.number(),
  starting_readiness: z.number(),
  target_readiness: z.number(),
  already_have: z.array(z.string()).default([]),
  you_are_here: z.record(z.number()).default({}),
  total_hours: z.number(),
  total_weeks: z.number(),
  finish_estimate: z.string().nullable(),
  band: z.string().default("intermediate"),
  deadline: z.string().nullable(),
  on_track: z.boolean().nullable(),
  notes: z.array(z.string()).default([]),
  recommended: z.array(LearnResource).default([]),
  phases: z.array(RoadmapPhase).default([]),
  certifications: z.array(Certification).default([]),
});
export const RoadmapResponse = z.object({ roadmap: Roadmap });

export const GraphEdgeChange = z.object({
  a: z.string(),
  b: z.string(),
  a_name: z.string(),
  b_name: z.string(),
  action: z.enum(["prune", "suggest", "add", "strengthen", "weaken"]),
  mean: z.number(),
  prior_mean: z.number(),
  support: z.number(),
  summary: z.string(),
});
export const GraphHealth = z.object({
  domain: z.string(),
  source: z.string(),
  observations: z.number(),
  watched: z.number(),
  clean: z.boolean(),
  pruned: z.array(GraphEdgeChange).default([]),
  added: z.array(GraphEdgeChange).default([]),
  suggested: z.array(GraphEdgeChange).default([]),
  reweighted: z.array(GraphEdgeChange).default([]),
  recovery: z
    .object({
      recall: z.number(),
      precision_drop: z.number(),
      hidden: z.array(z.array(z.string())),
      injected: z.array(z.array(z.string())),
    })
    .nullable()
    .default(null),
});

/** Role-gap meta on a /recommend response when the goal was a job role. */
export interface RoleMeta {
  role: true;
  domain: string;
  method: string;
  readiness: number;
  readiness_before: number;
  readiness_curve: [number, number][];
}
export function roleMeta(meta: Record<string, unknown>): RoleMeta | null {
  return meta.role === true ? (meta as unknown as RoleMeta) : null;
}
export const ObserveResponse = z.object({
  n_interactions: z.number(),
  time_budget_min: z.number(),
  mean_velocity: z.number(),
  mastery: z.record(z.number()),
});
export const ExplainResponse = z.object({ resource_id: z.string(), reason: z.string() });

export const ResolveResponse = z.object({
  goal: z.string(),
  domain: z.string(),
  source: z.enum(["seed", "role", "dynamic"]),
  assessable: z.boolean().default(true),
  goals: z.array(z.string()),
  concepts: z.array(Concept),
  prerequisites: z.array(z.tuple([z.string(), z.string()])),
});

export const AssessQuestion = z.object({
  item_id: z.string(),
  skill: z.string(),
  kind: z.enum(["mcq", "task"]),
  stem: z.string(),
  choices: z.array(z.string()),
});
export const SkillEstimate = z.object({
  skill: z.string(),
  theta: z.number(),
  se: z.number(),
  mastery: z.number(),
  n_items: z.number(),
  confident: z.boolean(),
});
export const AssessState = z.object({
  done: z.boolean(),
  band: z.string().default("intermediate"),
  answered: z.number(),
  progress: z.number(),
  style: z
    .object({ hands_on: z.number(), recall: z.number(), note: z.string() })
    .nullable()
    .default(null),
  question: AssessQuestion.nullable(),
  estimates: z.array(SkillEstimate),
});

export type Band = "beginner" | "intermediate" | "advanced";

export const DiscoverResource = z.object({
  title: z.string(),
  url: z.string(),
  source: z.string(),
  kind: z.string(),
  difficulty: z.number(),
  minutes: z.number(),
});
export const DiscoverResponse = z.object({
  concept: z.string(),
  resources: z.array(DiscoverResource),
});

export type Concept = z.infer<typeof Concept>;
export type Resource = z.infer<typeof Resource>;
export type Catalogue = z.infer<typeof Catalogue>;
export type Step = z.infer<typeof Step>;
export type Objective = z.infer<typeof Objective>;
export type Path = z.infer<typeof Path>;
export type RecommendResponse = z.infer<typeof RecommendResponse>;
export type CalendarStep = z.infer<typeof CalendarStep>;
export type CalendarPlan = z.infer<typeof CalendarPlan>;
export type Certification = z.infer<typeof Certification>;
export type LearnResource = z.infer<typeof LearnResource>;
export type RoadmapPhase = z.infer<typeof RoadmapPhase>;
export type Roadmap = z.infer<typeof Roadmap>;
export type GraphHealth = z.infer<typeof GraphHealth>;
export type GraphEdgeChange = z.infer<typeof GraphEdgeChange>;
export type ObserveResponse = z.infer<typeof ObserveResponse>;

export type Session = z.infer<typeof Session>;
export type ResolveResponse = z.infer<typeof ResolveResponse>;
export type AssessQuestion = z.infer<typeof AssessQuestion>;
export type SkillEstimate = z.infer<typeof SkillEstimate>;
export type AssessState = z.infer<typeof AssessState>;
export type DiscoverResource = z.infer<typeof DiscoverResource>;
export type Speed = "slow" | "normal" | "fast";
export type SolverMode = "sequence" | "optimal" | "interactive" | "pareto";

export interface RecommendInput {
  learner_id: string;
  goals: string[];
  time_budget_min: number;
  mode?: SolverMode;
  n_paths?: number;
  speed?: Speed;
  ban?: string[];
  lock?: string[];
  force_order?: [string, string][];
  goal?: string; // free-text goal -> resolved to a knowledge graph server-side
}

export interface ScheduleInput {
  learner_id: string;
  goals: string[];
  goal?: string;
  deadline: string; // YYYY-MM-DD
  weekly_minutes?: number;
  speed?: Speed;
}

export interface RoadmapInput {
  learner_id: string;
  goal: string;
  weekly_hours?: number;
  deadline?: string; // YYYY-MM-DD
  band?: Band;
}

export interface ObserveInput {
  learner_id: string;
  resource_id: string;
  correct: boolean;
  minutes: number;
  hints?: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  schema: z.ZodType<T, z.ZodTypeDef, unknown>,
  path: string,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError("Cannot reach the VELPO API. Is it running? (python velpo.py api)", 0);
  }
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : `HTTP ${res.status}`;
    throw new ApiError(detail, res.status);
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiError(`Unexpected response from ${path}: ${parsed.error.message}`, res.status);
  }
  return parsed.data;
}

export const api = {
  catalogue: () => request(Catalogue, "/catalogue"),

  recommend: (input: RecommendInput) =>
    request(RecommendResponse, "/recommend", { method: "POST", body: JSON.stringify(input) }),

  observe: (input: ObserveInput) =>
    request(ObserveResponse, "/observe", { method: "POST", body: JSON.stringify(input) }),

  explain: (learner_id: string, resource_id: string) =>
    request(ExplainResponse, "/explain", {
      method: "POST",
      body: JSON.stringify({ learner_id, resource_id }),
    }),

  resolve: (goal: string) =>
    request(ResolveResponse, "/resolve", { method: "POST", body: JSON.stringify({ goal }) }),

  assessStart: (learner_id: string, goals: string[], band: Band = "intermediate", goal?: string) =>
    request(AssessState, "/assess/start", {
      method: "POST",
      body: JSON.stringify({ learner_id, goals, band, goal }),
    }),

  assessAnswer: (learner_id: string, item_id: string, response: string) =>
    request(AssessState, "/assess/answer", {
      method: "POST",
      body: JSON.stringify({ learner_id, item_id, response }),
    }),

  discover: (concept_id: string) =>
    request(DiscoverResponse, `/discover/${encodeURIComponent(concept_id)}`),

  schedule: (input: ScheduleInput) =>
    request(ScheduleResponse, "/schedule", { method: "POST", body: JSON.stringify(input) }),

  roadmap: (input: RoadmapInput) =>
    request(RoadmapResponse, "/roadmap", { method: "POST", body: JSON.stringify(input) }),

  graphHealth: (goal: string, learners = 6000) =>
    request(GraphHealth, "/graph/health", {
      method: "POST",
      body: JSON.stringify({ goal, learners }),
    }),
};
