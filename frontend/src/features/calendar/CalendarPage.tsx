import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Caption, ErrorBox, Hci, HciRibbon, Loading, Ms, Pill, addDays, dayLabel, isoToday } from "../../components/stitch";
import { trackName } from "../../components/Shell";
import { useLearner } from "../../context/LearnerContext";
import { useTrack } from "../../context/TrackContext";
import type { CalendarPlan, CalendarStep, ScheduleInput } from "../../lib/api";
import { downloadIcs } from "../../lib/ics";
import { useResolve, useSchedule } from "../../lib/queries";
import { NeedGoal } from "../plan/NeedGoal";
import { FeedbackLoop } from "./FeedbackLoop";

const KIND: Record<CalendarStep["kind"], { label: string; dot: string; text: string }> = {
  teach: { label: "Study session", dot: "bg-primary", text: "text-primary" },
  review: { label: "Review", dot: "bg-tertiary", text: "text-tertiary" },
  retention: { label: "Refresher", dot: "bg-tertiary", text: "text-tertiary" },
  check: { label: "Quick check", dot: "bg-secondary", text: "text-secondary" },
};
const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Calendar - the Stitch deadline-calendar screen. */
export function CalendarPage() {
  const { track, update } = useTrack();
  const { learnerId } = useLearner();
  const resolved = useResolve(track.goal);
  const nav = useNavigate();
  const [missed, setMissed] = useState(0);
  const goals = resolved.data?.goals ?? [];
  const base = useMemo<ScheduleInput>(
    () => ({ learner_id: learnerId, goal: track.goal, goals, deadline: track.deadline, weekly_minutes: Math.round(track.hoursPerWeek * 60), speed: track.speed }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [learnerId, track.goal, goals.join(","), track.deadline, track.hoursPerWeek, track.speed],
  );
  const sim = useMemo<ScheduleInput>(() => ({ ...base, start: addDays(isoToday(), missed) }), [base, missed]);
  const q = useSchedule(base, resolved.isSuccess && Boolean(track.deadline));
  const qs = useSchedule(sim, resolved.isSuccess && Boolean(track.deadline) && missed > 0);

  if (!track.goal) return <NeedGoal />;
  const domain = resolved.data?.domain ?? "";

  return (
    <div className="flex flex-col w-full gap-space-lg text-on-surface">
      <div className="flex flex-col gap-space-sm bg-surface-container-low p-space-lg rounded-xl shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-space-md">
          <nav aria-label="Breadcrumb" className="flex items-center gap-space-xs font-label-badge text-label-badge text-outline">
            <span>{trackName(domain)}</span>
            <Ms name="chevron_right" size={12} />
            <span className="text-primary font-bold">Calendar</span>
            {missed > 0 && (
              <>
                <Ms name="chevron_right" size={12} />
                <span className="text-secondary font-bold">If you miss {missed} day{missed > 1 ? "s" : ""}</span>
              </>
            )}
          </nav>
          <Hci>
            <span className="text-secondary">[H-03 Forgiving]</span> • Missed days are re-planned, not punished
          </Hci>
        </div>
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-md pt-space-xs">
          <div>
            <h1 className="font-headline-lg text-headline-lg tracking-tight">Calendar{missed > 0 ? ` · what if you miss ${missed} day${missed > 1 ? "s" : ""}?` : ""}</h1>
            <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">
              Your plan on real days, with refreshers spaced out so you don't forget before your date. Tell it how your week went and it re-plans.
            </p>
          </div>
          <div className="flex items-center gap-1.5 p-1 bg-surface-container-lowest rounded-lg self-start lg:self-auto flex-wrap">
            <button type="button" onClick={() => nav("/roadmap")} className="px-space-md py-1.5 font-label-badge text-label-badge text-on-surface-variant hover:text-on-surface rounded">Timeline Roadmap</button>
            <button type="button" onClick={() => nav("/plan")} className="px-space-md py-1.5 font-label-badge text-label-badge text-on-surface-variant hover:text-on-surface rounded">Study Plan</button>
            <span className="px-space-md py-1.5 font-label-badge text-label-badge bg-primary text-on-primary font-bold rounded shadow-sm" aria-current="page">Calendar</span>
            <button
              type="button"
              disabled={!q.data?.calendar.steps.length}
              onClick={() => q.data && exportCal(q.data.calendar, track.goal)}
              className="px-space-md py-1.5 font-label-badge text-label-badge text-on-surface-variant hover:text-on-surface rounded flex items-center gap-1 disabled:opacity-40"
            >
              Export &amp; Sync <Ms name="sync" size={14} />
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-space-md pt-space-sm">
          <label className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
            Target date
            <input type="date" value={track.deadline} onChange={(e) => update({ deadline: e.target.value })} className="px-space-sm py-1 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm text-on-surface" />
          </label>
          <label className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
            Hours / week
            <input type="number" min={1} max={60} step={0.5} value={track.hoursPerWeek} onChange={(e) => update({ hoursPerWeek: Math.max(1, Number(e.target.value) || 1) })} className="w-24 px-space-sm py-1 rounded bg-surface-container-lowest border border-outline-variant/40 font-code-sm text-code-sm text-on-surface" />
          </label>
          <div className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
            Simulate a missed session
            <div className="flex gap-1" role="group" aria-label="Days missed">
              {[0, 1, 2, 3].map((d) => (
                <button
                  key={d}
                  type="button"
                  aria-pressed={missed === d}
                  disabled={!track.deadline}
                  onClick={() => setMissed(d)}
                  className={`px-space-sm py-1 rounded font-label-badge text-label-badge disabled:opacity-40 ${missed === d ? "bg-secondary text-on-secondary" : "bg-surface-container hover:bg-surface-container-high text-on-surface-variant"}`}
                >
                  {d === 0 ? "None" : `+${d}d`}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {track.deadline && resolved.isSuccess && goals.length > 0 && (
        <FeedbackLoop learnerId={learnerId} goal={track.goal} goals={goals} deadline={track.deadline} hoursPerWeek={track.hoursPerWeek} speed={track.speed} domain={resolved.data!.source === "seed" ? resolved.data!.domain : resolved.data!.source} />
      )}

      {!track.deadline ? (
        <div className="p-space-lg rounded-xl bg-surface-container shadow-md flex items-start gap-space-md">
          <Ms name="event" size={24} className="text-primary" />
          <p className="font-body-md text-body-md text-on-surface-variant">
            Pick a target date, such as an exam or an interview. Every step and spaced refresher then
            goes on a real day, with a check that each goal skill is at least 75% on that date.
          </p>
        </div>
      ) : resolved.isPending || q.isPending ? (
        <Loading label="Fitting your plan to the calendar…" />
      ) : q.isError ? (
        <ErrorBox>{q.error.message}</ErrorBox>
      ) : resolved.isError ? (
        <ErrorBox>{resolved.error.message}</ErrorBox>
      ) : (
        <CalendarBody cal={q.data.calendar} sim={missed > 0 ? qs.data?.calendar : undefined} simLoading={missed > 0 && qs.isPending} missed={missed} onUseHours={(h) => update({ hoursPerWeek: h })} goal={track.goal} />
      )}

      <HciRibbon
        title="Design notes: calendar"
        cards={[
          { tag: "H-01", title: "System Status Visibility", body: "Spare days, hours needed and the predicted mastery on your date are shown before you commit." },
          { tag: "H-03", title: "User Freedom & Fallback", tone: "tertiary", body: "Simulate missed days with one click and see whether the deadline still holds, with no punitive reset." },
          { tag: "H-07", title: "Flexibility & Efficiency", tone: "secondary", body: "If a date is out of reach, one click applies the hours per week that would make it." },
          { tag: "Memory", title: "Spacing & forgetting", body: "Refreshers are placed so you don't forget a topic before your date." },
        ]}
      />
    </div>
  );
}

function exportCal(cal: CalendarPlan, goal: string) {
  downloadIcs(
    "velpo-calendar.ics",
    `Syntropix · ${goal}`,
    [
      ...cal.steps.map((s) => ({ day: s.day, title: `${KIND[s.kind].label}: ${s.concept}`, description: `${Math.round(s.minutes)} min${s.url ? ` · ${s.url}` : ""}` })),
      { day: cal.deadline, title: `Target: ${goal}` },
    ],
  );
}

/** Hours per week the plan really uses: the backend reports "needed" only for
 *  an unreachable date, so for a feasible plan derive it from the schedule. */
function hoursNeeded(cal: CalendarPlan): number {
  if (cal.hours_per_week_needed > 0) return cal.hours_per_week_needed;
  const weeks = Math.max(1 / 7, (Date.parse(cal.deadline) - Date.parse(cal.start)) / (7 * 864e5));
  return cal.steps.reduce((t, s) => t + s.minutes, 0) / 60 / weeks;
}

/** Spare days that can absorb a missed session: deadline minus the day the
 *  last *plan* step lands. Reinforcements are left out on purpose - the
 *  scheduler parks them as late as it can, so they say nothing about slack. */
function buffer(cal: CalendarPlan): number {
  const days = cal.steps.filter((s) => s.kind !== "retention").map((s) => s.day);
  if (!days.length) return cal.slack_days;
  const last = days.reduce((a, b) => (a > b ? a : b));
  return Math.round((Date.parse(cal.deadline) - Date.parse(last)) / 864e5);
}

function minGoal(cal: CalendarPlan): number | null {
  const v = Object.values(cal.goal_mastery);
  return v.length ? Math.min(...v) : null;
}

function CalendarBody({
  cal,
  sim,
  simLoading,
  missed,
  onUseHours,
  goal,
}: {
  cal: CalendarPlan;
  sim?: CalendarPlan;
  simLoading: boolean;
  missed: number;
  onUseHours: (h: number) => void;
  goal: string;
}) {
  const needed = Math.ceil(cal.hours_per_week_needed * 2) / 2;
  const studyDays = new Set(cal.steps.map((s) => s.day)).size || 1;
  const perDay = cal.steps.reduce((t, s) => t + s.minutes, 0) / studyDays;
  const retention = minGoal(cal);
  const spare = buffer(cal);
  const absorbed = sim ? Math.max(0, spare - buffer(sim)) : 0;

  return (
    <>
      {missed > 0 && (
        <div className={`flex flex-col lg:flex-row lg:items-center justify-between gap-space-md p-space-md rounded-xl shadow-md ${sim?.feasible === false ? "bg-error-container/20" : "bg-tertiary-container/10"}`}>
          <div className="flex items-center gap-space-md">
            <div className="w-10 h-10 rounded-lg bg-secondary/20 flex items-center justify-center text-secondary shrink-0">
              <Ms name="warning" size={24} />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-space-sm flex-wrap">
                <Pill tone="secondary">WHAT IF YOU MISS DAYS?</Pill>
                <span className="font-headline-sm text-headline-sm">Missed {missed} day{missed > 1 ? "s" : ""} · start moves to {dayLabel(addDays(isoToday(), missed))}</span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">
                {simLoading || !sim
                  ? "Re-planning from the later start…"
                  : sim.feasible
                    ? `No problem: your spare days go from ${spare} to ${buffer(sim)}. You still finish by ${dayLabel(cal.deadline)} with no extra hours.`
                    : `That's too much to absorb: ${sim.note} You'd need about ${sim.hours_per_week_needed.toFixed(1)} hours a week.`}
              </p>
            </div>
          </div>
          {sim && (
            <Pill tone={sim.feasible ? "tertiary" : "error"} icon={sim.feasible ? "verified" : "error"}>
              {sim.feasible ? "STILL ON TIME, NO CRAMMING" : "DEADLINE AT RISK"}
            </Pill>
          )}
        </div>
      )}

      {!cal.feasible && (
        <div role="alert" className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-md p-space-md rounded-xl bg-error-container/20">
          <div className="flex items-start gap-space-sm">
            <Ms name="error" className="text-error" />
            <div>
              <strong className="text-error">Not on track for {dayLabel(cal.deadline)}.</strong>{" "}
              <span className="text-on-surface-variant">{cal.note}</span>
              {cal.hours_per_week_needed > cal.hours_per_week && (
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  You have {cal.hours_per_week.toFixed(1)} h/week; this date needs about <b className="text-on-surface">{needed} h/week</b>, or a later date.
                </p>
              )}
            </div>
          </div>
          {cal.hours_per_week_needed > cal.hours_per_week && (
            <button type="button" onClick={() => onUseHours(needed)} className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm shrink-0">
              Use {needed} h/week
            </button>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-md">
        <Metric label="Hours you need" icon="insights" value={hoursNeeded(cal).toFixed(1)} unit="hours a week" sub={`You have ${cal.hours_per_week.toFixed(1)} h`} fill={Math.min(1, hoursNeeded(cal) / Math.max(cal.hours_per_week, 0.1))} tone="tertiary" />
        <Metric label="Study per day" icon="timer" value={perDay.toFixed(1)} unit="minutes a study day" sub={`${studyDays} study days`} fill={Math.min(1, perDay / 120)} tone="secondary" />
        <Metric label="Spare days" icon="shield_with_heart" value={`+${spare}`} unit="days to spare" sub={sim ? `${absorbed} used by the missed days` : "after your last new topic"} fill={Math.min(1, spare / 7)} tone="primary" />
        <Metric label="Remembered on the day" icon="verified" value={retention == null ? "—" : `${Math.round(retention * 100)}%`} unit="your weakest goal topic" sub="allowing for forgetting" fill={retention ?? 0} tone="tertiary" />
      </div>

      {sim && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-space-md">
          <Compare title={`IF YOU MISS ${missed} DAY${missed > 1 ? "S" : ""}`} icon="sync_problem" tone={sim.feasible ? "secondary" : "error"} cal={sim} />
          <Compare title="YOUR PLAN" icon="security_update_good" tone="tertiary" cal={cal} />
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg items-start">
        <div className="xl:col-span-8">
          <Grid cal={cal} missed={missed} />
        </div>
        <div className="xl:col-span-4 flex flex-col gap-space-md">
          <section className="bg-surface-container-low rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md">
            <div className="flex items-center justify-between pb-space-xs">
              <h3 className="font-headline-sm text-headline-sm">Missed-day check</h3>
              <Pill tone={cal.feasible ? "tertiary" : "error"}>{cal.feasible ? "ON TRACK" : "AT RISK"}</Pill>
            </div>
            <div className="bg-surface-container-lowest p-space-md rounded-lg flex flex-col gap-2">
              <div className="flex items-center justify-between font-label-badge text-label-badge">
                <span className="text-outline">Spare days left</span>
                <span className="text-primary font-bold">{sim ? buffer(sim) : spare} of {spare} days</span>
              </div>
              <div className="w-full bg-surface-container-highest h-2.5 rounded-full overflow-hidden flex">
                <div className="bg-secondary h-full" style={{ width: `${spare ? (absorbed / spare) * 100 : 0}%` }} />
                <div className="bg-primary h-full" style={{ width: `${spare ? ((spare - absorbed) / spare) * 100 : 0}%` }} />
              </div>
            </div>
            <div className="space-y-2 font-label-badge text-label-badge">
              <Audit k="Days missed (simulated)" v={missed ? `+${missed}` : "0"} />
              <Audit k="Spare days" v={sim ? `${spare} → ${buffer(sim)}` : `${spare}`} />
              <Audit k="Deadline moves by" v={sim && !sim.feasible ? "Date at risk" : `0 days (${dayLabel(cal.deadline)})`} good={!sim || sim.feasible} />
              <Audit k="Extra hours needed" v={sim ? `${Math.max(0, sim.hours_per_week_needed - cal.hours_per_week).toFixed(1)} h a week` : "none"} good={!sim || sim.hours_per_week_needed <= cal.hours_per_week} />
              <Audit k="Refreshers" v={`${cal.n_retention}`} />
            </div>
            {Object.keys(cal.goal_mastery).length > 0 && (
              <div className="bg-surface-container-lowest p-space-md rounded-lg flex flex-col gap-2">
                <Caption>Predicted on {dayLabel(cal.deadline)}</Caption>
                {Object.entries(cal.goal_mastery).map(([n, m]) => (
                  <div key={n} className="flex flex-col gap-1">
                    <div className="flex justify-between font-body-sm text-body-sm">
                      <span className="text-on-surface-variant">{n}</span>
                      <span className={m >= 0.75 ? "text-tertiary" : "text-error"}>{Math.round(m * 100)}%</span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
                      <div className={`h-full ${m >= 0.75 ? "bg-tertiary" : "bg-error"}`} style={{ width: `${m * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
            <button
              type="button"
              disabled={!cal.steps.length}
              onClick={() => exportCal(cal, goal)}
              className="w-full py-2 rounded-lg bg-surface-container-high hover:bg-surface-bright font-body-strong text-body-sm flex items-center justify-center gap-1.5 disabled:opacity-40"
            >
              <Ms name="calendar_month" size={18} /> Sync Sessions to GCal / iCal (.ics)
            </button>
          </section>
          <section className="bg-surface-container-low rounded-xl p-space-md shadow-sm flex flex-col gap-2">
            <Caption>Good to know</Caption>
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              {cal.reasons[0] ?? "Spare days before your deadline soak up real life, so a missed day doesn't turn into cramming."}
            </p>
          </section>
        </div>
      </div>
    </>
  );
}

function Metric({ label, icon, value, unit, sub, fill, tone }: { label: string; icon: string; value: string; unit: string; sub: string; fill: number; tone: "primary" | "secondary" | "tertiary" }) {
  const t = { primary: ["text-primary", "bg-primary"], secondary: ["text-secondary", "bg-secondary"], tertiary: ["text-tertiary", "bg-tertiary"] }[tone];
  return (
    <div className="bg-surface-container-low p-space-md rounded-xl flex flex-col justify-between shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="font-label-badge text-label-badge text-on-surface-variant uppercase">{label}</span>
        <Ms name={icon} className={t[0]} />
      </div>
      <div className="flex items-baseline gap-2">
        <span className={`font-headline-lg text-headline-lg font-bold ${t[0]}`}>{value}</span>
        <span className="font-body-sm text-body-sm text-outline">{unit}</span>
      </div>
      <span className="mt-2 font-label-badge text-label-badge text-outline">{sub}</span>
      <div className="w-full bg-surface-container-highest h-1.5 rounded-full mt-3 overflow-hidden">
        <div className={`${t[1]} h-full rounded-full`} style={{ width: `${Math.round(Math.max(0, Math.min(1, fill)) * 100)}%` }} />
      </div>
    </div>
  );
}

function Compare({ title, icon, tone, cal }: { title: string; icon: string; tone: "secondary" | "tertiary" | "error"; cal: CalendarPlan }) {
  const color = { secondary: "text-secondary", tertiary: "text-tertiary", error: "text-error" }[tone];
  const days = new Set(cal.steps.map((s) => s.day)).size || 1;
  return (
    <div className="p-space-md bg-surface-container-lowest rounded-xl shadow-sm">
      <span className={`font-label-badge text-label-badge flex items-center gap-1.5 font-bold ${color}`}>
        <Ms name={icon} size={16} /> {title}
      </span>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-label-badge text-label-badge mt-2">
        {[
          ["NEEDED", `${hoursNeeded(cal).toFixed(1)} h/wk`],
          ["PER DAY", `${(cal.steps.reduce((t, s) => t + s.minutes, 0) / days).toFixed(0)} min`],
          ["SPARE DAYS", `${buffer(cal)}`],
          ["ON THE DATE", cal.feasible ? "Ready" : "At risk"],
        ].map(([k, v]) => (
          <div key={k} className="bg-surface-container-high p-2 rounded">
            <span className="block text-outline text-[10px]">{k}</span>
            <span className={`font-bold ${color}`}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Audit({ k, v, good = true }: { k: string; v: string; good?: boolean }) {
  return (
    <div className="flex items-center justify-between p-2 rounded bg-surface-container-lowest">
      <span className="text-outline">{k}</span>
      <span className={good ? "text-tertiary font-bold" : "text-error font-bold"}>{v}</span>
    </div>
  );
}

function Grid({ cal, missed }: { cal: CalendarPlan; missed: number }) {
  const byDay = new Map<string, CalendarStep[]>();
  for (const s of cal.steps) byDay.set(s.day, [...(byDay.get(s.day) ?? []), s]);
  const today = isoToday();
  const startMs = Date.parse(`${cal.start}T00:00:00Z`);
  const first = startMs - ((new Date(startMs).getUTCDay() + 6) % 7) * 864e5;
  const endMs = Date.parse(`${cal.deadline}T00:00:00Z`);
  const last = endMs + (6 - ((new Date(endMs).getUTCDay() + 6) % 7)) * 864e5;
  const days: string[] = [];
  for (let t = first; t <= last; t += 864e5) days.push(new Date(t).toISOString().slice(0, 10));
  const missedDays = new Set(Array.from({ length: missed }, (_, i) => addDays(today, i)));

  return (
    <section className="bg-surface-container-low rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm pb-space-xs">
        <div>
          <h2 className="font-headline-md text-headline-md">Schedule Manifest: {dayLabel(cal.start)} – {dayLabel(cal.deadline)}, {cal.deadline.slice(0, 4)}</h2>
          <Caption>Reviews are spaced out · rest days stay free</Caption>
        </div>
        <div className="flex items-center gap-space-sm flex-wrap font-label-badge text-label-badge">
          <span className="flex items-center gap-1.5 text-on-surface"><span className="w-2.5 h-2.5 rounded-full bg-primary" /> Study session</span>
          <span className="flex items-center gap-1.5 text-tertiary"><span className="w-2.5 h-2.5 rounded-full bg-tertiary" /> Review / rest</span>
          <span className="flex items-center gap-1.5 text-secondary"><span className="w-2.5 h-2.5 rounded-full bg-secondary" /> Check / deadline</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[640px]" role="grid" aria-label="Study calendar">
          <div className="grid grid-cols-7 gap-2 text-center font-label-badge text-label-badge text-outline uppercase py-1" role="row">
            {DOW.map((d) => (
              <div key={d} role="columnheader">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-2">
            {days.map((d) => {
              const items = byDay.get(d) ?? [];
              const before = d < cal.start;
              const after = d > cal.deadline;
              const target = d === cal.deadline;
              const rest = !before && !after && !target && items.length === 0;
              const mins = items.reduce((t, s) => t + s.minutes, 0);
              const cls = before || after
                ? "bg-surface-container-lowest/40 opacity-40"
                : target
                  ? "bg-secondary-container/15 ring-1 ring-secondary"
                  : missedDays.has(d)
                    ? "bg-secondary/10 border border-secondary/40"
                    : rest
                      ? "bg-tertiary-container/10"
                      : d === today
                        ? "bg-surface-container-lowest border border-primary/30"
                        : "bg-surface-container-lowest";
              return (
                <div key={d} role="gridcell" aria-label={`${dayLabel(d)}: ${items.length} item${items.length === 1 ? "" : "s"}`} className={`min-h-[96px] p-2 rounded-lg flex flex-col justify-between gap-1 ${cls}`}>
                  <div className="flex items-center justify-between">
                    <span className={`font-label-badge text-label-badge ${target ? "text-secondary font-bold" : rest ? "text-tertiary" : d === today ? "text-primary font-bold" : "text-on-surface"}`}>{dayLabel(d)}</span>
                    {target ? (
                      <Ms name="verified" size={16} className="text-secondary" />
                    ) : missedDays.has(d) ? (
                      <span className="font-label-annotation text-label-annotation px-1 bg-secondary/20 text-secondary rounded font-bold">MISSED</span>
                    ) : rest ? (
                      <span className="font-label-annotation text-label-annotation text-tertiary font-bold">REST</span>
                    ) : null}
                  </div>
                  <div className="flex flex-col gap-0.5 min-w-0">
                    {target ? (
                      <span className="font-label-badge text-label-badge text-secondary font-bold">DEADLINE</span>
                    ) : before ? (
                      <span className="font-body-sm text-body-sm text-outline">Passed</span>
                    ) : after ? (
                      <span className="font-body-sm text-body-sm text-outline">—</span>
                    ) : rest ? (
                      <span className="font-label-annotation text-label-annotation text-tertiary">Refresher</span>
                    ) : (
                      items.slice(0, 3).map((s, i) => (
                        <span key={`${s.concept_id}-${i}`} className={`font-label-badge text-label-badge truncate ${KIND[s.kind].text === "text-primary" ? "text-on-surface" : KIND[s.kind].text}`} title={`${KIND[s.kind].label}: ${s.concept} · ${Math.round(s.minutes)} min`}>
                          {s.url ? <a href={s.url} target="_blank" rel="noreferrer" className="hover:underline">{s.concept}</a> : s.concept}
                        </span>
                      ))
                    )}
                    {items.length > 3 && <span className="font-label-annotation text-label-annotation text-outline">+{items.length - 3} more</span>}
                  </div>
                  {!before && !after && !target && items.length > 0 && (
                    <span className="font-label-annotation text-label-annotation text-outline">{Math.round(mins)} min</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
