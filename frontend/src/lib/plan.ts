/**
 * The study plan as the Stitch screens show it: sessions with real dates and
 * statuses, typed steps, and the delta from the learner's previous plan.
 * Everything here is derived from the /recommend response - no invented data.
 */
import { localIso } from "./dates";
import { useMemo } from "react";

import { useLearner } from "../context/LearnerContext";
import { useTrack } from "../context/TrackContext";
import type { Path, RecommendInput, Step } from "./api";
import { roleMeta } from "./api";
import { useRecommend, useResolve } from "./queries";

export const MASTERED = 0.75;

export type StepType = "teach" | "review" | "check" | "repair" | "milestone";

export function stepType(s: Step, isMilestone: boolean): StepType {
  if (s.repair) return "repair";
  if (s.check) return "check";
  if (s.review) return "review";
  return isMilestone ? "milestone" : "teach";
}

export interface PlanStep {
  step: Step;
  index: number; // position in the whole plan
  label: string; // "4.2"
  type: StepType;
  done: boolean;
  mastery: number | undefined;
}

export interface PlanSession {
  index: number; // 0-based
  number: number; // 1-based, as shown
  steps: PlanStep[];
  minutes: number;
  status: "done" | "current" | "scheduled";
  date: string; // ISO day the session is planned for
  focus: string[]; // concept names
}

/** ISO day helpers (UTC, so dates never shift with timezone). */
const today = () => localIso();
const plusDays = (iso: string, n: number) =>
  new Date(Date.parse(`${iso}T00:00:00Z`) + n * 864e5).toISOString().slice(0, 10);

export function buildSessions(plan: Path, goals: string[], hoursPerWeek: number): PlanSession[] {
  const bounds = plan.sessions.length ? plan.sessions : [{ start: 0, end: plan.steps.length }];
  // the last step that teaches a goal concept is the milestone of the plan
  let milestone = -1;
  plan.steps.forEach((s, i) => {
    if (goals.includes(s.concept_id) && !s.review && !s.check) milestone = i;
  });
  const perDay = Math.max(1, (hoursPerWeek * 60) / 7);

  let current = -1;
  const raw = bounds.map((b, si) => {
    const steps: PlanStep[] = plan.steps.slice(b.start, b.end).map((s, k) => {
      const m = plan.mastery[s.concept_id];
      return {
        step: s,
        index: b.start + k,
        label: `${si + 1}.${k + 1}`,
        type: stepType(s, b.start + k === milestone),
        done: !s.repair && m != null && m >= MASTERED && !s.review && !s.check,
        mastery: m,
      };
    });
    const minutes = steps.reduce((t, s) => t + s.step.minutes, 0);
    const done = steps.length > 0 && steps.every((s) => s.done);
    if (!done && current < 0) current = si;
    return { si, steps, minutes, done };
  });

  // pack upcoming sessions into days by the learner's daily capacity: the
  // current session is today, each later one goes on the first day with room
  let day = 0;
  let used = 0;
  return raw.map((r) => {
    const status: PlanSession["status"] = r.done && (current < 0 || r.si < current) ? "done" : r.si === current ? "current" : "scheduled";
    let date = today();
    if (status === "current") used = r.minutes;
    if (status === "scheduled") {
      if (used > 0 && used + r.minutes > perDay) {
        day += Math.max(1, Math.floor(used / perDay));
        used = 0;
      }
      if (day === 0) day = 1;
      used += r.minutes;
      date = plusDays(today(), day);
    }
    return {
      index: r.si,
      number: r.si + 1,
      steps: r.steps,
      minutes: r.minutes,
      status,
      date,
      focus: [...new Set(r.steps.map((s) => s.step.concept || s.step.concept_id))],
    };
  });
}

/** Steps that come after `concept` and need it (direct dependants on the plan). */
export function dependants(plan: Path, concept: string): string[] {
  return Object.entries(plan.prerequisites)
    .filter(([, pre]) => pre.includes(concept))
    .map(([c]) => c);
}

// ------------------------------------------------------------ plan delta
export interface PlanDelta {
  added: string[]; // concept names
  removed: string[];
  moved: string[];
  repairs: string[];
}

const DELTA_KEY = "velpo-plan-history";

function key(s: Step) {
  return `${s.concept_id}|${s.review ? "r" : s.check ? "c" : "t"}`;
}

/** Compare with the learner's previous plan for this goal (kept in localStorage):
 *  when the plan changes, the old one becomes "previous" and the diff is shown. */
export function planDelta(learnerId: string, goal: string, plan: Path): PlanDelta | null {
  const id = `${learnerId}::${goal}`;
  const now = plan.steps.map(key);
  let store: Record<string, { current: string[]; previous: string[] | null }> = {};
  try {
    store = JSON.parse(localStorage.getItem(DELTA_KEY) ?? "{}");
  } catch {
    store = {};
  }
  const entry = store[id];
  if (!entry || entry.current.join() !== now.join()) {
    store[id] = { current: now, previous: entry ? entry.current : null };
    try {
      localStorage.setItem(DELTA_KEY, JSON.stringify(store));
    } catch {
      /* ignore */
    }
  }
  const prev = store[id]?.previous;
  if (!prev) return null;
  const name = (k: string) => {
    const cid = k.split("|")[0]!;
    return plan.names[cid] ?? plan.steps.find((s) => s.concept_id === cid)?.concept ?? cid;
  };
  const before = new Set(prev);
  const after = new Set(now);
  const common = now.filter((k) => before.has(k));
  const prevOrder = prev.filter((k) => after.has(k));
  return {
    added: now.filter((k) => !before.has(k)).map(name),
    removed: prev.filter((k) => !after.has(k)).map(name),
    moved: common.filter((k, i) => prevOrder[i] !== k).map(name),
    repairs: plan.steps.filter((s) => s.repair).map((s) => s.concept || s.concept_id),
  };
}

// --------------------------------------------------------------- hook
/** Resolve the track's goal and fetch its sequenced plan. */
export function usePlan() {
  const { learnerId } = useLearner();
  const { track } = useTrack();
  const resolved = useResolve(track.goal);
  const goals = resolved.data?.goals ?? [];
  const input = useMemo<RecommendInput>(
    () => ({
      learner_id: learnerId,
      goal: track.goal,
      goals,
      time_budget_min: track.budgetMinutes,
      mode: "sequence",
      speed: track.speed,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [learnerId, track.goal, goals.join(","), track.budgetMinutes, track.speed],
  );
  const rec = useRecommend(input, resolved.isSuccess);
  const plan = rec.data?.paths[0];
  const role = rec.data ? roleMeta(rec.data.meta) : null;
  return { resolved, rec, plan, role, goals, learnerId, track };
}

/** Domains whose every concept has graded practice tasks. */
export const PRACTICE_DOMAINS = new Set([
  "sql",
  "python",
  "python_data",
  "spreadsheets",
  "stats",
  "dataviz",
  "powerbi",
  "tableau",
  "data_eng",
  "git",
]);

/** The concept to open the practice lab on, or null when its domain has no tasks.
 * Role graphs prefix ids with their domain (`sql.outer_join`); seed graphs don't. */
export function practiceTarget(conceptId: string, domain: string): string | null {
  const dot = conceptId.indexOf(".");
  const d = dot > 0 ? conceptId.slice(0, dot) : domain;
  return PRACTICE_DOMAINS.has(d) ? conceptId : null;
}
