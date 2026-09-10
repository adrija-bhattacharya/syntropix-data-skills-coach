import type { Objective, Path } from "./api";

/** Human labels for the 5-D objective vector.  All components are "lower is better"
 *  on the wire; the two negated ones are shown flipped so the UI reads naturally. */
export const OBJECTIVE_META: Record<
  keyof Objective,
  { label: string; better: "higher" | "lower"; transform: (v: number) => number; unit?: string }
> = {
  neg_gain: { label: "Mastery gain", better: "higher", transform: (v) => -v },
  seconds: { label: "Study time", better: "lower", transform: (v) => v / 60, unit: "min" },
  load: { label: "Cognitive load", better: "lower", transform: (v) => v },
  diff_jump: { label: "Difficulty jumps", better: "lower", transform: (v) => v },
  neg_review: { label: "Review gain", better: "higher", transform: (v) => -v },
};

export const OBJECTIVE_KEYS = Object.keys(OBJECTIVE_META) as (keyof Objective)[];

export function num(v: number, digits = 2): string {
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

/** (x = minutes, y = mastery gain, load) for a Pareto scatter. */
export function paretoPoint(p: Path, index: number): { index: number; minutes: number; gain: number; load: number } {
  return {
    index,
    minutes: Math.round(p.total_minutes),
    gain: Number((-p.objective.neg_gain).toFixed(3)),
    load: Number(p.objective.load.toFixed(3)),
  };
}
