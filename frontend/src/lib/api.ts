/**
 * Typed Syntropix API client.  Every response is validated at runtime with zod, so
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
  minutes: z.number().default(0),
  concept: z.string().default(""),
  repair: z.boolean().default(false),
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
  mastery: z.record(z.number()).default({}),
  prerequisites: z.record(z.array(z.string())).default({}),
  names: z.record(z.string()).default({}),
  p_correct: z.record(z.number()).default({}),
  baseline_minutes: z.number().default(0),
  session_minutes: z.number().default(35),
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
  a: z.number().default(1),
  b: z.number().default(0),
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
  /** expected questions left, including the current one */
  remaining: z.number().nullable().default(null),
  prior_sd: z.number().default(1.5),
  prior_mean: z.number().default(0),
  se_target: z.number().default(0.55),
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

// --- execution-verified practice (claim E) ---
export const PracticeTask = z.object({
  id: z.string(),
  concept_id: z.string(),
  concept: z.string(),
  /** sql | python | excel | value - decides the workspace */
  kind: z.string().default("sql"),
  domain: z.string().default("sql"),
  prompt: z.string(),
  ordered: z.boolean(),
  minutes: z.number().default(5),
  hints: z.array(z.string()).default([]),
  cell: z.string().default(""),
  fill_down: z.boolean().default(false),
  options: z.array(z.string()).default([]),
  context: z.array(z.array(z.string())).default([]),
  context_note: z.string().default(""),
  env: z.record(z.string()).default({}),
});
export const SchemaColumn = z.object({
  name: z.string(),
  type: z.string(),
  pk: z.boolean(),
  nulls: z.number(),
});
export const PracticeTasks = z.object({
  start: z.string().nullable().default(null),
  path: z.array(z.string()).default([]),
  mastery: z.record(z.number()).default({}),
  p_correct: z.record(z.number()).default({}),
  schema: z.record(z.object({ rows: z.number(), columns: z.array(SchemaColumn) })),
  /** the Excel practice sheet, A..I x rows 1..11, as displayed values */
  sheet: z.array(z.array(z.string())).default([]),
  tasks: z.array(PracticeTask),
});
export const PracticeDiagnosis = z.object({
  code: z.string(),
  concept_id: z.string(),
  weight: z.number(),
  message: z.string(),
});
export const FixMoment = z.object({
  video_id: z.string(),
  title: z.string(),
  channel: z.string().default(""),
  start: z.number(),
  end: z.number(),
  chapter: z.string().default(""),
  score: z.number().default(0),
  kind: z.enum(["chapter", "topic"]),
  why: z.string().default(""),
});
/** Claim H1: the video moment that explains the mistake in a wrong answer. */
export const FixClip = z.object({
  code: z.string(),
  concept_id: z.string(),
  concept: z.string(),
  moments: z.array(FixMoment),
});
export const PracticeResult = z.object({
  task_id: z.string(),
  correct: z.boolean(),
  result: z.object({
    columns: z.array(z.string()),
    rows: z.array(z.array(z.union([z.string(), z.number(), z.null()]))),
    error: z.string(),
    truncated: z.boolean(),
    ms: z.number().default(0),
    row_status: z.array(z.enum(["ok", "extra"])).default([]),
    missing_rows: z.number().default(0),
    expected_rows: z.number().default(0),
  }),
  checks: z
    .array(z.object({ id: z.string(), label: z.string(), passed: z.boolean(), detail: z.string() }))
    .default([]),
  p_correct_before: z.number().default(0),
  diagnoses: z.array(PracticeDiagnosis),
  mastery: z.record(z.object({ name: z.string(), before: z.number(), after: z.number() })),
  edge_evidence: z.array(z.object({ from: z.string(), to: z.string(), confidence: z.number() })),
  plan: Path,
  next_task: z.string().nullable(),
  replan_ms: z.number(),
  in_portfolio: z.boolean().default(false),
  fix_clip: FixClip.nullable().default(null),
});

export type Concept = z.infer<typeof Concept>;
export type FixClip = z.infer<typeof FixClip>;
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
export type PracticeTask = z.infer<typeof PracticeTask>;
export type SchemaColumn = z.infer<typeof SchemaColumn>;
// --- skill library: real videos + practice problems, ordered by velocity ---
export const Video = z.object({
  video_id: z.string(),
  title: z.string(),
  channel: z.string(),
  minutes: z.number(),
  views: z.number().default(0),
  url: z.string(),
  domain: z.string(),
  concept: z.string().nullable(),
  level: z.string().default(""),
  kind: z.string(),
  /** semantic check: does it teach the topic, from what evidence, where */
  check: z
    .object({
      level: z.string(),
      source: z.string(),
      judge: z.string(),
      start: z.number(),
      chapter: z.string(),
      reason: z.string(),
      score: z.number(),
      coverage: z.array(z.string()),
    })
    .nullable()
    .default(null),
});
export const Problem = z.object({
  platform: z.string(),
  set: z.string(),
  section: z.string().default(""),
  title: z.string(),
  url: z.string(),
  difficulty: z.string(),
  domain: z.string().nullable(),
  concept: z.string().nullable(),
  free: z.boolean().default(true),
  minutes: z.number().optional(),
  concept_id: z.string().optional(),
});
export const LibraryStep = z.object({
  concept_id: z.string(),
  domain: z.string(),
  concept: z.string(),
  mastery: z.number(),
  video: Video.nullable(),
  problems: z.array(Problem),
});
export const WeekItem = z.object({
  type: z.enum(["video", "problem"]),
  concept_id: z.string(),
  concept: z.string(),
  minutes: z.number(),
  title: z.string(),
  url: z.string(),
  platform: z.string().optional(),
  set: z.string().optional(),
  difficulty: z.string().optional(),
  video_id: z.string().optional(),
  channel: z.string().optional(),
});
export const Library = z.object({
  pace: z.string(),
  pace_text: z.string(),
  pace_source: z.string(),
  harvested: z.string().nullable(),
  totals: z.record(z.number()),
  courses: z.array(Video),
  steps: z.array(LibraryStep),
  weeks: z.array(z.object({ week: z.number(), minutes: z.number(), items: z.array(WeekItem) })),
  stretch: z.array(Problem),
  extra: z.array(Problem).default([]),
  review: z.array(LibraryStep),
  mixed: z.array(Problem),
});
export const LibraryStats = z.object({
  harvested: z.string().nullable(),
  problems: z.number(),
  videos: z.number(),
  leetcode: z.number(),
  hackerrank: z.number(),
  open_sites: z.number(),
  domains: z.array(z.string()),
});
export type Video = z.infer<typeof Video>;
export type Problem = z.infer<typeof Problem>;
export type LibraryStep = z.infer<typeof LibraryStep>;
export type Library = z.infer<typeof Library>;
export type WeekItem = z.infer<typeof WeekItem>;

// --- calendar feedback loop (claim F) ---
export const RescheduleBlock = z.object({
  day: z.string(),
  start: z.string(),
  end: z.string(),
  minutes: z.number(),
  concept_id: z.string(),
  concept: z.string(),
  title: z.string(),
  kind: z.string(),
  part: z.number(),
  parts: z.number(),
});
export const RescheduleResponse = z.object({
  adherence: z.number(),
  logged_days: z.number(),
  done_minutes: z.number(),
  planned_minutes_so_far: z.number(),
  effective_hours_per_week: z.number(),
  busy_events: z.number(),
  past_days: z.array(z.object({ day: z.string(), planned_minutes: z.number() })),
  remaining_minutes: z.number(),
  feasible: z.boolean(),
  finish: z.string().nullable(),
  deadline: z.string(),
  hours_per_week_needed: z.number(),
  reasons: z.array(z.string()),
  blocks: z.array(RescheduleBlock),
  days: z.array(
    z.object({
      day: z.string(),
      busy_minutes: z.number(),
      fatigue: z.number(),
      cap_minutes: z.number(),
      max_block: z.number(),
      study_minutes: z.number(),
    }),
  ),
  busy_spans: z.record(z.array(z.tuple([z.string(), z.string()]))).default({}),
  forecast: z
    .object({
      p50: z.string().nullable(),
      p80: z.string().nullable(),
      p95: z.string().nullable(),
      p_on_time: z.number(),
      trust: z.number().default(1),
      checks: z.number().default(0),
      hits: z.number().default(0),
    })
    .nullable()
    .default(null),
  study_times: z.array(z.object({ slot: z.string(), multiplier: z.number(), answers: z.number() })).default([]),
  focus: z.object({ half_life_min: z.number(), block_min: z.number(), answers: z.number() }).nullable().default(null),
  practice_answers: z.number().default(0),
  /** H3: how long you keep each topic, measured from your own answers after a pause */
  memory: z
    .object({
      recalls: z.number(),
      topics: z.array(z.object({ concept_id: z.string(), concept: z.string(), half_life_days: z.number(), recalls: z.number(), source: z.string() })),
    })
    .default({ recalls: 0, topics: [] }),
  /** H3: 10-minute reviews placed in free time, just before a topic is needed or fades */
  reviews: z
    .array(
      z.object({
        concept_id: z.string(),
        concept: z.string(),
        day: z.string(),
        start: z.string(),
        end: z.string(),
        due: z.string(),
        recall_at_due: z.number(),
        before: z.string().nullable(),
        priority: z.number(),
        late: z.boolean(),
      }),
    )
    .default([]),
  slowdowns: z
    .array(
      z.object({
        concept_id: z.string(),
        concept: z.string(),
        ratio: z.number(),
        suspects: z.array(z.object({ concept_id: z.string(), concept: z.string(), kind: z.string(), mastery: z.number() })),
      }),
    )
    .default([]),
  velocity: z
    .object({
      aware: z.boolean(),
      measured_topics: z.number(),
      topics: z.array(
        z.object({
          concept_id: z.string(),
          concept: z.string(),
          ratio: z.number(),
          velocity: z.number(),
          hours_to_master: z.number(),
          source: z.string(),
        }),
      ),
    })
    .nullable()
    .default(null),
  naive: z.object({ finish: z.string().nullable(), feasible: z.boolean(), notes: z.array(z.string()) }),
});
export type RescheduleBlock = z.infer<typeof RescheduleBlock>;
export type RescheduleResponse = z.infer<typeof RescheduleResponse>;
export interface RescheduleInput {
  learner_id: string;
  goal: string;
  goals: string[];
  deadline: string;
  hours_per_week: number;
  speed: string;
  plan_start?: string;
  log: { day: string; planned_minutes: number; done_minutes: number }[];
  busy_ics?: string;
  now_minute?: number;
}

// --- proof-of-skill portfolio ---
/** Claim H2: a signed re-test of one answer on newly generated practice data. */
export const FreshProof = z.object({
  payload: z.object({
    slug: z.string(),
    task_id: z.string(),
    answer_sha256: z.string(),
    seeds: z.array(z.number()),
    passed: z.boolean(),
    fresh: z.boolean(),
    datasets: z.number(),
    at: z.string(),
  }),
  sig: z.string(),
  runs: z.array(z.object({ seed: z.number(), passed: z.boolean(), changed: z.boolean(), rows: z.number() })).default([]),
});
export const ReproveResult = z.object({
  seed: z.number().nullable(),
  reproduced: z.boolean(),
  proofs: z.record(FreshProof),
  passed: z.number(),
  tested: z.number(),
});
export const PortfolioSolve = z.object({
  task_id: z.string(),
  concept: z.string(),
  concept_name: z.string(),
  domain: z.string(),
  kind: z.string(),
  prompt: z.string(),
  answer: z.string(),
  checks: z.array(z.string()),
  result_preview: z.array(z.array(z.unknown())),
  columns: z.array(z.string()),
  solved_at: z.string(),
  attempts: z.number(),
  rechecked: z.boolean(),
  proof: FreshProof.nullable().default(null),
});
export const PortfolioProject = z.object({
  project_id: z.string(),
  title: z.string(),
  summary: z.string(),
  skills: z.array(z.string()),
  repo_url: z.string(),
  demo_url: z.string(),
  added_at: z.string(),
  link_ok: z.boolean().nullable(),
});
export const PortfolioView = z.object({
  name: z.string(),
  headline: z.string(),
  github: z.string(),
  linkedin: z.string(),
  slug: z.string(),
  public: z.boolean(),
  skills: z.record(z.array(PortfolioSolve)),
  projects: z.array(PortfolioProject),
  solved: z.number(),
  rechecked_ok: z.number(),
  fresh_ok: z.number().default(0),
  fresh_testable: z.number().default(0),
  mastery: z.record(z.number()),
  built: z.string(),
  share_path: z.string(),
  /** issued once, the first time the portfolio is opened - kept in this browser */
  edit_key: z.string().optional(),
});
export type PortfolioView = z.infer<typeof PortfolioView>;
export type PortfolioSolve = z.infer<typeof PortfolioSolve>;
export interface ProfileInput {
  name: string;
  headline: string;
  github: string;
  linkedin: string;
  public: boolean;
}
export interface ProjectInput {
  project_id: string;
  title: string;
  summary: string;
  skills: string[];
  repo_url: string;
  demo_url: string;
}

export const WhatFits = z.object({
  confidence: z.number(),
  capacity_hours: z.number(),
  chosen: z.array(z.object({ concept_id: z.string(), concept: z.string(), value: z.number() })),
  dropped: z.array(z.object({ concept_id: z.string(), concept: z.string(), value: z.number() })),
  p_finish: z.number(),
  expected_hours: z.number(),
  p90_hours: z.number(),
  value_share: z.number(),
  hours_per_week_for_all: z.number().nullable(),
  by_expected_time: z.object({ goals: z.array(z.string()), p_finish: z.number() }),
});
export type WhatFits = z.infer<typeof WhatFits>;

export const Health = z.object({
  status: z.string(),
  version: z.string(),
  concepts: z.number(),
  resources: z.number(),
});
export type Health = z.infer<typeof Health>;
export type PracticeTasks = z.infer<typeof PracticeTasks>;
export type PracticeDiagnosis = z.infer<typeof PracticeDiagnosis>;
export type PracticeResult = z.infer<typeof PracticeResult>;
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
  start?: string; // YYYY-MM-DD; a later start simulates missed days
}

export interface RoadmapInput {
  learner_id: string;
  goal: string;
  weekly_hours?: number;
  deadline?: string; // YYYY-MM-DD
  band?: Band;
  speed?: Speed;
}

export interface ObserveInput {
  learner_id: string;
  resource_id: string;
  correct: boolean;
  minutes: number;
  hints?: number;
}

export interface PracticeInput {
  learner_id: string;
  task_id: string;
  query: string;
  goals?: string[];
  /** the track's free-text goal - picks the same graph the plan uses */
  goal?: string;
}

// ---- last request latency, for the status bar (a tiny external store)
let lastLatency: number | null = null;
const listeners = new Set<() => void>();
function recordLatency(ms: number): void {
  lastLatency = Math.round(ms);
  listeners.forEach((l) => l());
}
export const latencyStore = {
  subscribe(l: () => void) {
    listeners.add(l);
    return () => listeners.delete(l);
  },
  get: () => lastLatency,
};

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
  const t0 = performance.now();
  try {
    res = await fetch(path, {
      ...init,
      headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...(init?.headers as Record<string, string> | undefined) },
    });
  } catch {
    throw new ApiError("Can't reach the Syntropix server. Is it running? (python velpo.py serve)", 0);
  }
  recordLatency(performance.now() - t0);
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

/** The portfolio's edit key lives in this browser only. */
export function portfolioKey(learnerId: string): string | null {
  try {
    return localStorage.getItem(`syntropix-portfolio-key:${learnerId}`);
  } catch {
    return null;
  }
}

async function owned(learnerId: string, path: string, init: RequestInit = {}) {
  const key = portfolioKey(learnerId);
  const out = await request(PortfolioView, path, { ...init, headers: key ? { "X-Portfolio-Key": key } : {} });
  if (out.edit_key) {
    try {
      localStorage.setItem(`syntropix-portfolio-key:${learnerId}`, out.edit_key);
    } catch {
      /* private mode: the key lasts for this tab only */
    }
  }
  return out;
}

export const api = {
  health: () => request(Health, "/health"),

  library: (q: { goal: string; learner_id: string; speed: string; pace: string; hours_per_week: number }) =>
    request(Library, `/library?${new URLSearchParams({ ...q, hours_per_week: String(q.hours_per_week) })}`),

  libraryStats: () => request(LibraryStats, "/library/stats"),

  portfolio: (learnerId: string) => owned(learnerId, `/portfolio/${encodeURIComponent(learnerId)}`),
  portfolioProfile: (learnerId: string, input: ProfileInput) =>
    owned(learnerId, `/portfolio/${encodeURIComponent(learnerId)}/profile`, { method: "PUT", body: JSON.stringify(input) }),
  portfolioProject: (learnerId: string, input: ProjectInput) =>
    owned(learnerId, `/portfolio/${encodeURIComponent(learnerId)}/projects`, { method: "POST", body: JSON.stringify(input) }),
  portfolioRemove: (learnerId: string, what: "solves" | "projects", id: string) =>
    owned(learnerId, `/portfolio/${encodeURIComponent(learnerId)}/${what}/${encodeURIComponent(id)}`, { method: "DELETE" }),
  portfolioReprove: (learnerId: string) => {
    const key = portfolioKey(learnerId);
    return request(ReproveResult, `/portfolio/${encodeURIComponent(learnerId)}/reprove`, {
      method: "POST",
      body: JSON.stringify({}),
      headers: key ? { "X-Portfolio-Key": key } : {},
    });
  },
  portfolioExportUrl: (learnerId: string) => {
    const key = portfolioKey(learnerId);
    return `/portfolio/${encodeURIComponent(learnerId)}/export.html${key ? `?key=${encodeURIComponent(key)}` : ""}`;
  },

  whatFits: (input: { learner_id: string; goal: string; goals: string[]; deadline: string; hours_per_week: number; confidence: number; log: RescheduleInput["log"] }) =>
    request(WhatFits, "/what-fits", { method: "POST", body: JSON.stringify(input) }),

  reschedule: (input: RescheduleInput) =>
    request(RescheduleResponse, "/reschedule", { method: "POST", body: JSON.stringify(input) }),

  certifications: (goal: string) =>
    request(z.object({ certifications: z.array(Certification) }), `/certifications?goal=${encodeURIComponent(goal)}`),
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

  practiceTasks: (learner_id: string, target: string, goal?: string) =>
    request(
      PracticeTasks,
      `/practice/tasks?learner_id=${encodeURIComponent(learner_id)}&target=${encodeURIComponent(target)}` +
        (goal ? `&goal=${encodeURIComponent(goal)}` : ""),
    ),

  practiceSubmit: (input: PracticeInput) =>
    request(PracticeResult, "/practice/submit", { method: "POST", body: JSON.stringify(input) }),

  graphHealth: (goal: string, learners = 6000) =>
    request(GraphHealth, "/graph/health", {
      method: "POST",
      body: JSON.stringify({ goal, learners }),
    }),
};
