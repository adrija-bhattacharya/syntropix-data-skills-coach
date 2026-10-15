import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { Band, SkillEstimate, Speed } from "../lib/api";

/**
 * The learner's current track - the goal they set on the Skill Map page and
 * the settings every other screen plans with.  Persisted, so a reload or a new
 * tab lands on the same plan.
 */
export interface Track {
  goal: string;
  band: Band;
  hoursPerWeek: number;
  /** Time budget the study-plan solver may spend, in minutes. */
  budgetMinutes: number;
  speed: Speed;
  deadline: string; // YYYY-MM-DD or ""
  /** Show the HCI-principle annotations (the "[H-01]" ribbons) - a top-bar toggle. */
  hci: boolean;
  /** Last finished skill check: per-skill estimate + the prior SD it started from. */
  assessment: { estimates: SkillEstimate[]; priorSd: number } | null;
}

const DEFAULTS: Track = {
  goal: "",
  band: "intermediate",
  hoursPerWeek: 6,
  budgetMinutes: 600,
  speed: "normal",
  deadline: "",
  hci: false,
  assessment: null,
};

interface Ctx {
  track: Track;
  update: (patch: Partial<Track>) => void;
}

const TrackCtx = createContext<Ctx | null>(null);
const KEY = "syntropix-track";
const OLD_KEY = "velpo-track"; // before the rename: keep the goal, reset the design notes

function load(): Track {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Track>) };
    const old = localStorage.getItem(OLD_KEY);
    return old ? { ...DEFAULTS, ...(JSON.parse(old) as Partial<Track>), hci: false } : DEFAULTS;
  } catch {
    return DEFAULTS;
  }
}

export function TrackProvider({ children, initial }: { children: ReactNode; initial?: Partial<Track> }) {
  const [track, setTrack] = useState<Track>(() => ({ ...load(), ...initial }));
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(track));
    } catch {
      /* private mode etc. - the app still works for this tab */
    }
  }, [track]);
  const value = useMemo<Ctx>(
    () => ({ track, update: (patch) => setTrack((t) => ({ ...t, ...patch })) }),
    [track],
  );
  return <TrackCtx.Provider value={value}>{children}</TrackCtx.Provider>;
}

export function useTrack(): Ctx {
  const c = useContext(TrackCtx);
  if (!c) throw new Error("useTrack must be used inside <TrackProvider>");
  return c;
}

/** Certainty of one estimate, 0..1: how far its SD has shrunk from the prior's. */
export function certainty(se: number, priorSd: number): number {
  return Math.max(0, Math.min(1, 1 - se / priorSd));
}

/** Mean certainty over the skills the check actually asked about. */
export function modelCertainty(track: Track): number | null {
  const a = track.assessment;
  if (!a) return null;
  const asked = a.estimates.filter((e) => e.n_items > 0);
  if (!asked.length) return null;
  return asked.reduce((t, e) => t + certainty(e.se, a.priorSd), 0) / asked.length;
}
