// Typed client for the VELPO FastAPI service.

export interface Concept {
  id: string;
  name: string;
}
export interface Resource {
  id: string;
  concepts: string[];
  difficulty: number;
  minutes: number;
  kind: string;
}
export interface Catalogue {
  concepts: Concept[];
  resources: Resource[];
  goals: string[];
}
export interface Step {
  resource_id: string;
  concept_id: string;
  reason: string;
}
export interface Path {
  feasible: boolean;
  note: string;
  total_minutes: number;
  objective: Record<string, number>;
  steps: Step[];
}
export interface RecommendResponse {
  paths: Path[];
  meta: Record<string, string | number>;
}
export interface LearnerState {
  n_interactions: number;
  time_budget_min: number;
  mean_velocity: number;
  mastery: Record<string, number>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.detail ? JSON.stringify(d.detail) : `HTTP ${r.status}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  catalogue: (): Promise<Catalogue> => fetch("/catalogue").then((r) => r.json()),

  recommend: (b: {
    learner_id: string;
    goals: string[];
    time_budget_min: number;
    mode?: "optimal" | "interactive" | "pareto";
    n_paths?: number;
    ban?: string[];
    lock?: string[];
    force_order?: [string, string][];
  }): Promise<RecommendResponse> => post("/recommend", b),

  observe: (b: {
    learner_id: string;
    resource_id: string;
    correct: boolean;
    minutes: number;
    hints?: number;
  }): Promise<LearnerState> => post("/observe", b),
};

export const OBJ_LABELS: Record<string, string> = {
  neg_gain: "mastery gain",
  seconds: "time (s)",
  load: "cognitive load",
  diff_jump: "difficulty jump",
  neg_review: "review gain",
};
