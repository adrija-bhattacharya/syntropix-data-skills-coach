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
});

export const Step = z.object({
  resource_id: z.string(),
  concept_id: z.string(),
  reason: z.string(),
  review: z.boolean().default(false),
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
});
export const RecommendResponse = z.object({
  paths: z.array(Path),
  meta: z.record(z.union([z.string(), z.number()])),
});
export const ObserveResponse = z.object({
  n_interactions: z.number(),
  time_budget_min: z.number(),
  mean_velocity: z.number(),
  mastery: z.record(z.number()),
});
export const ExplainResponse = z.object({ resource_id: z.string(), reason: z.string() });

export type Concept = z.infer<typeof Concept>;
export type Resource = z.infer<typeof Resource>;
export type Catalogue = z.infer<typeof Catalogue>;
export type Step = z.infer<typeof Step>;
export type Objective = z.infer<typeof Objective>;
export type Path = z.infer<typeof Path>;
export type RecommendResponse = z.infer<typeof RecommendResponse>;
export type ObserveResponse = z.infer<typeof ObserveResponse>;

export type Session = z.infer<typeof Session>;
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
};
