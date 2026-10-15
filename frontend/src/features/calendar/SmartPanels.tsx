import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ErrorBox, Loading, Ms, Pill } from "../../components/stitch";
import { api, type RescheduleResponse } from "../../lib/api";
import { practiceTarget } from "../../lib/plan";

/** G2: a topic learned far slower than predicted, and the likely gap behind it. */
export function Slowdowns({ r, domain }: { r: RescheduleResponse; domain: string }) {
  if (!r.slowdowns.length) return null;
  return (
    <section className="flex flex-col gap-space-xs p-space-md rounded-lg bg-error-container/15" aria-label="Slowdown alerts">
      <span className="font-body-strong text-body-sm flex items-center gap-1.5">
        <Ms name="troubleshoot" className="text-error" /> Something may be missing
      </span>
      {r.slowdowns.map((s) => {
        const top = s.suspects[0];
        const lab = top ? practiceTarget(top.concept_id, domain) : null;
        return (
          <div key={s.concept_id} className="flex flex-wrap items-center gap-space-sm font-body-sm text-body-sm">
            <span className="flex-1 min-w-0">
              You learned <b>{s.concept}</b> at {Math.round(s.ratio * 100)}% of the speed your earlier topics predicted.
              {top
                ? top.kind === "weak_prerequisite"
                  ? ` It builds on ${top.concept}, which you don't know well yet (${Math.round(top.mastery * 100)}%).`
                  : ` A likely missing piece: ${top.concept} (${Math.round(top.mastery * 100)}%). Syntropix also told your skill map to check this link.`
                : " Try a quick review before moving on."}
            </span>
            {lab && (
              <Link to={`/practice?target=${encodeURIComponent(lab)}`} className="px-space-sm py-1 rounded bg-primary text-on-primary font-label-badge text-label-badge">
                Practise {top!.concept.split(" (")[0]}
              </Link>
            )}
          </div>
        );
      })}
    </section>
  );
}

const SLOT_WORD: Record<string, string> = {
  "weekday morning": "Weekday mornings",
  "weekday afternoon": "Weekday afternoons",
  "weekday evening": "Weekday evenings",
  "weekday night": "Weekday nights",
  "weekend morning": "Weekend mornings",
  "weekend afternoon": "Weekend afternoons",
  "weekend evening": "Weekend evenings",
  "weekend night": "Weekend nights",
};

/** G4 + G5: when you study best, and how long you stay sharp. */
export function StudyContext({ r }: { r: RescheduleResponse }) {
  const need = Math.max(0, 20 - r.practice_answers);
  return (
    <section className="grid grid-cols-1 md:grid-cols-2 gap-space-sm" aria-label="Your study patterns">
      <div className="p-space-md rounded-lg bg-surface-container-lowest flex flex-col gap-1">
        <span className="font-body-strong text-body-sm flex items-center gap-1.5">
          <Ms name="wb_twilight" className="text-secondary" /> Your best study times
        </span>
        {r.study_times.length ? (
          <>
            {r.study_times.slice(0, 4).map((t) => (
              <div key={t.slot} className="flex items-center gap-space-sm font-body-sm text-body-sm">
                <span className="flex-1">{SLOT_WORD[t.slot] ?? t.slot}</span>
                <span className="w-24 h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
                  <span className="block h-full bg-secondary" style={{ width: `${Math.min(100, (t.multiplier / 1.6) * 100)}%` }} />
                </span>
                <span className={`w-28 text-right font-label-annotation text-label-annotation ${t.multiplier >= 1.05 ? "text-tertiary" : t.multiplier <= 0.95 ? "text-error" : "text-outline"}`}>
                  {t.multiplier >= 1.05 ? `${Math.round((t.multiplier - 1) * 100)}% better` : t.multiplier <= 0.95 ? `${Math.round((1 - t.multiplier) * 100)}% worse` : "about usual"} · {t.answers}
                </span>
              </div>
            ))}
            <span className="font-label-annotation text-label-annotation text-outline">Your week is planned into your best free slots first.</span>
          </>
        ) : (
          <span className="font-body-sm text-body-sm text-on-surface-variant">
            Answer {need} more practice question{need === 1 ? "" : "s"} and Syntropix learns when you do your best work.
          </span>
        )}
      </div>
      <div className="p-space-md rounded-lg bg-surface-container-lowest flex flex-col gap-1">
        <span className="font-body-strong text-body-sm flex items-center gap-1.5">
          <Ms name="timer" className="text-primary" /> Your focus span
        </span>
        {r.focus && r.focus.answers >= 20 ? (
          <>
            <span className="font-headline-sm text-headline-sm">{r.focus.block_min}-minute blocks</span>
            <span className="font-body-sm text-body-sm text-on-surface-variant">
              Your accuracy halves after about {Math.round(r.focus.half_life_min)} minutes in a session, so blocks of {r.focus.block_min} minutes (plus a 5-minute break) teach you the most per hour.
            </span>
          </>
        ) : (
          <span className="font-body-sm text-body-sm text-on-surface-variant">
            After {need > 0 ? `${need} more` : "a few more"} practice answers (some deep into a session), blocks are sized to how long you stay sharp.
          </span>
        )}
      </div>
    </section>
  );
}

/** G1: has the forecast earned its percentages for you? */
export function ForecastCheck({ r }: { r: RescheduleResponse }) {
  const f = r.forecast;
  if (!f || f.checks === 0) return null;
  return (
    <p className="font-label-annotation text-label-annotation text-on-surface-variant flex items-center gap-1">
      <Ms name="rule" size={14} className="text-primary" />
      Self-check: the forecast's week-ahead promises held {f.hits} of {f.checks} times for you
      {f.trust < 0.95 ? ", so your dates are widened to stay honest." : ", so it keeps its normal confidence."}
    </p>
  );
}

/** G3: what can I finish by my date, with the confidence I choose? */
export function WhatFitsCard(props: { learnerId: string; goal: string; goals: string[]; deadline: string; hoursPerWeek: number; log: { day: string; planned_minutes: number; done_minutes: number }[] }) {
  const [confidence, setConfidence] = useState(0.9);
  const q = useQuery({
    queryKey: ["what-fits", { ...props, confidence }] as const,
    queryFn: () =>
      api.whatFits({
        learner_id: props.learnerId,
        goal: props.goal,
        goals: props.goals,
        deadline: props.deadline,
        hours_per_week: props.hoursPerWeek,
        confidence,
        log: props.log,
      }),
    enabled: props.goals.length > 0,
    placeholderData: (prev) => prev,
  });
  return (
    <section className="p-space-lg rounded-xl bg-surface-container-low shadow-md flex flex-col gap-space-sm" aria-labelledby="fits-title">
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <h2 id="fits-title" className="font-headline-sm text-headline-sm flex items-center gap-space-xs">
          <Ms name="checklist" className="text-tertiary" /> What can I finish by my date?
        </h2>
        <div className="flex gap-1" role="radiogroup" aria-label="How sure do you want to be?">
          {[0.8, 0.9, 0.95].map((c) => (
            <button
              key={c}
              type="button"
              role="radio"
              aria-checked={confidence === c}
              onClick={() => setConfidence(c)}
              className={`px-space-sm py-1 rounded font-label-badge text-label-badge ${confidence === c ? "bg-tertiary text-on-tertiary" : "bg-surface-container-high text-on-surface-variant"}`}
            >
              {Math.round(c * 100)}% sure
            </button>
          ))}
        </div>
      </div>
      {q.isPending ? (
        <Loading label="Trying every combination of goals…" />
      ) : q.isError ? (
        <ErrorBox>{q.error.message}</ErrorBox>
      ) : (
        <>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            With {props.hoursPerWeek} hours a week ({q.data.capacity_hours} hours of real free time before your deadline), these goals fit with at least {Math.round(q.data.confidence * 100)}% confidence, allowing for how fast you learn and how often sessions slip.
          </p>
          <div className="flex flex-wrap gap-1">
            {q.data.chosen.map((g) => (
              <Pill key={g.concept_id} tone="tertiary" icon="check">{g.concept}</Pill>
            ))}
            {q.data.dropped.map((g) => (
              <Pill key={g.concept_id} tone="neutral" icon="schedule">{g.concept} (later)</Pill>
            ))}
          </div>
          <span className="font-label-annotation text-label-annotation text-outline">
            {Math.round(q.data.p_finish * 100)}% chance to finish these · about {q.data.expected_hours} h needed (up to {q.data.p90_hours} h on a slow run)
            {q.data.dropped.length > 0 &&
              (q.data.hours_per_week_for_all
                ? ` · to fit everything at this confidence: ${q.data.hours_per_week_for_all} h a week`
                : " · everything won't fit by this date even at 60 h a week")}
          </span>
          {q.data.by_expected_time.goals.length > q.data.chosen.length && (
            <span className="font-label-annotation text-label-annotation text-outline">
              Planning by average time would promise {q.data.by_expected_time.goals.length} goals, but only finish them {Math.round(q.data.by_expected_time.p_finish * 100)}% of the time.
            </span>
          )}
        </>
      )}
    </section>
  );
}
