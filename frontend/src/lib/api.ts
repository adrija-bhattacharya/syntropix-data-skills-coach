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
};
