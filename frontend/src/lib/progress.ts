import { useSyncExternalStore } from "react";

import { localIso } from "./dates";

/** What the learner ticked off outside the graded lab: videos watched and
 * external problems solved (LeetCode, HackerRank, ...).  Kept in this browser. */
export interface Done {
  videos: Record<string, string>; // video_id -> ISO date
  problems: Record<string, string>; // problem url -> ISO date
}

const KEY = "syntropix-progress";
const listeners = new Set<() => void>();
let state: Done = read();

function read(): Done {
  try {
    const raw = localStorage.getItem(KEY);
    const v = raw ? (JSON.parse(raw) as Partial<Done>) : {};
    return { videos: v.videos ?? {}, problems: v.problems ?? {} };
  } catch {
    return { videos: {}, problems: {} };
  }
}

function write(next: Done) {
  state = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* private mode - still works for this tab */
  }
  listeners.forEach((l) => l());
}

export function toggle(kind: "videos" | "problems", id: string) {
  const bucket = { ...state[kind] };
  if (bucket[id]) delete bucket[id];
  else bucket[id] = localIso();
  write({ ...state, [kind]: bucket });
}

export function useDone(): Done {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
    () => state,
  );
}

/** Days in a row (ending today or yesterday) with at least one thing done. */
export function streak(done: Done): number {
  const days = new Set([...Object.values(done.videos), ...Object.values(done.problems)]);
  let n = 0;
  const d = new Date();
  if (!days.has(localIso(d))) d.setDate(d.getDate() - 1);
  while (days.has(localIso(d))) {
    n += 1;
    d.setDate(d.getDate() - 1);
  }
  return n;
}
