import { useMemo } from "react";

import { Badge, Callout, Spinner } from "../../components/ui";
import { useLearner } from "../../context/LearnerContext";
import type { CalendarStep, ScheduleInput, Speed } from "../../lib/api";
import { useSchedule } from "../../lib/queries";

const KIND: Record<CalendarStep["kind"], { label: string; tone: "neutral" | "good" | "warn" }> = {
  teach: { label: "learn", tone: "neutral" },
  review: { label: "review", tone: "good" },
  check: { label: "check", tone: "warn" },
  retention: { label: "reinforce", tone: "good" },
};

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function fmtDay(iso: string) {
  const d = new Date(iso + "T00:00:00");
  return `${DOW[(d.getDay() + 6) % 7]} ${d.getMonth() + 1}/${d.getDate()}`;
}

export function CalendarView({
  goalText,
  goals,
  deadline,
  weeklyMinutes,
  speed,
}: {
  goalText: string;
  goals: string[];
  deadline: string;
  weeklyMinutes: number;
  speed: Speed;
}) {
  const { learnerId } = useLearner();
  const input = useMemo<ScheduleInput>(
    () => ({
      learner_id: learnerId,
      goal: goalText,
      goals,
      deadline,
      weekly_minutes: weeklyMinutes,
      speed,
    }),
    [learnerId, goalText, goals, deadline, weeklyMinutes, speed],
  );
  const q = useSchedule(input, true);

  if (q.isPending) return <Spinner label="Fitting your plan to the calendar…" />;
  if (q.isError) return <Callout tone="warn">{q.error.message}</Callout>;
  const cal = q.data?.calendar;
  if (!cal) return null;

  if (!cal.feasible) {
    return (
      <Callout tone="warn">
        <strong>Not on track for {cal.deadline}.</strong> {cal.note}
        {cal.hours_per_week_needed > cal.hours_per_week && (
          <>
            {" "}
            You offered {cal.hours_per_week.toFixed(1)} h/week; about{" "}
            <strong>{cal.hours_per_week_needed.toFixed(1)} h/week</strong> is needed for this date —
            or move the deadline out.
          </>
        )}
      </Callout>
    );
  }

  const weeks = new Map<number, CalendarStep[]>();
  for (const s of cal.steps) {
    const wk = Math.floor((Date.parse(s.day) - Date.parse(cal.start)) / (7 * 864e5)) + 1;
    const bucket = weeks.get(wk) ?? [];
    bucket.push(s);
    weeks.set(wk, bucket);
  }

  return (
    <div className="cal">
      <div className="cal-head">
        <Badge tone="good">on track</Badge>
        <span>
          every goal skill ≥ 75% on <strong>{cal.deadline}</strong>
        </span>
        <Badge mono>{cal.slack_days} d slack</Badge>
        <Badge mono>{cal.hours_per_week} h/wk</Badge>
        {cal.n_retention > 0 && <Badge tone="good">{cal.n_retention} reinforcements</Badge>}
      </div>

      <div className="chips" style={{ margin: "10px 0 16px" }}>
        {Object.entries(cal.goal_mastery).map(([name, m]) => (
          <span key={name} className="chip" style={{ cursor: "default" }}>
            {name} · {Math.round(m * 100)}%
          </span>
        ))}
      </div>

      {[...weeks.entries()].map(([wk, steps]) => (
        <div key={wk} className="cal-week">
          <div className="cal-week-label">week {wk}</div>
          {steps.map((s, i) => (
            <div key={`${s.day}-${s.concept_id}-${i}`} className="cal-row">
              <span className="cal-date">{fmtDay(s.day)}</span>
              <Badge tone={KIND[s.kind].tone}>{KIND[s.kind].label}</Badge>
              <span className="cal-concept">
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.concept}
                  </a>
                ) : (
                  s.concept
                )}
              </span>
              <span className="cal-min">{Math.round(s.minutes)}m</span>
            </div>
          ))}
        </div>
      ))}
      <p className="hint">{cal.reasons[0]}</p>
    </div>
  );
}
