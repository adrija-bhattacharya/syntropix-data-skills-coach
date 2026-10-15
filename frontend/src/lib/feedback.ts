import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { isoToday } from "../components/stitch";
import { api, type RescheduleInput } from "./api";

/** The calendar feedback loop's state, shared by the Calendar and Today pages:
 * when the plan started, how each past session went, and the imported calendar.
 * Kept in this browser. */
export type SessionLog = Record<string, { planned: number; done: number }>;

export function useStored<T>(key: string, initial: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(v));
    } catch {
      /* private mode or full: keep it for this tab only */
    }
  }, [key, v]);
  return [v, setV];
}

export function useFeedback(p: { learnerId: string; goal: string; goals: string[]; deadline: string; hoursPerWeek: number; speed: string }) {
  const scope = `${p.learnerId}|${p.goal}`;
  const [planStart, setPlanStart] = useStored<string>(`syntropix-plan-start:${scope}`, isoToday());
  const [log, setLog] = useStored<SessionLog>(`syntropix-log:${scope}`, {});
  const [ics, setIcs] = useStored<{ name: string; text: string } | null>(`syntropix-ics:${p.learnerId}`, null);

  const input = useMemo<RescheduleInput>(() => {
    const now = new Date();
    return {
      learner_id: p.learnerId,
      goal: p.goal,
      goals: p.goals,
      deadline: p.deadline,
      hours_per_week: p.hoursPerWeek,
      speed: p.speed,
      plan_start: planStart,
      log: Object.entries(log).map(([day, v]) => ({ day, planned_minutes: v.planned, done_minutes: v.done })),
      busy_ics: ics?.text,
      now_minute: now.getHours() * 60 + now.getMinutes(),
    };
    // now_minute is read once per input change, on purpose
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.learnerId, p.goal, p.goals.join(","), p.deadline, p.hoursPerWeek, p.speed, planStart, log, ics]);

  const q = useQuery({
    queryKey: ["reschedule", { ...input, now_minute: undefined, busy_ics: ics?.name }] as const,
    queryFn: () => api.reschedule(input),
    enabled: p.goals.length > 0 && p.deadline > isoToday(),
    placeholderData: (prev) => prev,
  });

  const mark = (day: string, planned: number, done: number) => setLog({ ...log, [day]: { planned, done } });
  const unmark = (day: string) => {
    const next = { ...log };
    delete next[day];
    setLog(next);
  };
  return { q, log, mark, unmark, planStart, setPlanStart, ics, setIcs };
}
