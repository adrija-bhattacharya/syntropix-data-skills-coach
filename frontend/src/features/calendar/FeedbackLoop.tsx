import { useState } from "react";

import { ErrorBox, Loading, Ms, Pill, dayLabel, hm, isoToday } from "../../components/stitch";
import type { RescheduleBlock, RescheduleResponse } from "../../lib/api";
import { useFeedback } from "../../lib/feedback";
import { ForecastCheck, Memory, Slowdowns, StudyContext, WhatFitsCard } from "./SmartPanels";
import { downloadIcs } from "../../lib/ics";

/**
 * The calendar feedback loop: tell the app how your sessions really went (and,
 * optionally, give it your calendar), and the rest of the plan is split into
 * blocks that fit around your real week.
 */
const toMin = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
};
const DAY0 = 7 * 60; // the day bars run 07:00 .. 23:00
const DAY1 = 23 * 60;
const pct = (m: number) => `${((Math.min(DAY1, Math.max(DAY0, m)) - DAY0) / (DAY1 - DAY0)) * 100}%`;

export function FeedbackLoop({
  learnerId,
  goal,
  goals,
  deadline,
  hoursPerWeek,
  speed,
  domain,
}: {
  learnerId: string;
  goal: string;
  goals: string[];
  deadline: string;
  hoursPerWeek: number;
  speed: string;
  domain: string;
}) {
  const { q, log, mark, unmark, planStart, setPlanStart, ics, setIcs } = useFeedback({ learnerId, goal, goals, deadline, hoursPerWeek, speed });
  const [icsError, setIcsError] = useState<string | null>(null);
  const readIcs = async (file: File) => {
    setIcsError(null);
    const text = await file.text();
    if (!text.includes("BEGIN:VCALENDAR")) {
      setIcsError("That doesn't look like a calendar file (.ics).");
      return;
    }
    setIcs({ name: file.name, text: text.slice(0, 2_900_000) });
  };

  return (
    <section className="p-space-lg rounded-xl bg-surface-container-low shadow-md flex flex-col gap-space-md" aria-labelledby="loop-title">
      <div className="flex flex-wrap items-start justify-between gap-space-sm">
        <div className="flex flex-col gap-1 max-w-3xl">
          <h2 id="loop-title" className="font-headline-md text-headline-md flex items-center gap-space-xs">
            <Ms name="sync_alt" className="text-primary" /> Your week, re-planned
          </h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Tell Syntropix how your sessions really went, and (optionally) add your calendar. It works out how much you
            actually manage, splits what's left into short blocks, and fits them around your meetings, without going over
            your {hoursPerWeek} hours a week.
          </p>
        </div>
        <label className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
          I started this plan on
          <input
            type="date"
            value={planStart}
            max={isoToday()}
            onChange={(e) => e.target.value && setPlanStart(e.target.value)}
            className="px-space-sm py-1 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm text-on-surface"
          />
        </label>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-space-md">
        <div className="flex flex-col gap-space-xs p-space-md rounded-lg bg-surface-container">
          <span className="font-body-strong text-body-sm">1. How did your sessions go?</span>
          {q.data && q.data.past_days.length === 0 && (
            <span className="font-body-sm text-body-sm text-outline">
              No past sessions yet. Set the start date above if you began earlier.
            </span>
          )}
          <div className="flex flex-col gap-1 max-h-64 overflow-y-auto pr-1">
            {q.data?.past_days
              .slice()
              .reverse()
              .map((d) => {
                const entry = log[d.day];
                const state = !entry ? "unset" : entry.done >= entry.planned ? "done" : entry.done <= 0 ? "missed" : "partly";
                return (
                  <div key={d.day} className="flex flex-wrap items-center gap-space-xs font-body-sm text-body-sm">
                    <span className="w-28 shrink-0">{dayLabel(d.day)}</span>
                    <span className="w-20 shrink-0 text-outline">{hm(d.planned_minutes)} planned</span>
                    <div className="flex gap-1" role="group" aria-label={`How ${dayLabel(d.day)} went`}>
                      {(
                        [
                          ["done", "Done", d.planned_minutes],
                          ["partly", "Half", Math.round(d.planned_minutes / 2)],
                          ["missed", "Missed", 0],
                        ] as const
                      ).map(([k, label, done]) => (
                        <button
                          key={k}
                          type="button"
                          aria-pressed={state === k}
                          onClick={() => (state === k ? unmark(d.day) : mark(d.day, d.planned_minutes, done))}
                          className={`px-space-sm py-0.5 rounded font-label-badge text-label-badge ${
                            state === k
                              ? k === "done"
                                ? "bg-tertiary text-on-tertiary"
                                : k === "missed"
                                  ? "bg-error-container text-on-error-container"
                                  : "bg-secondary text-on-secondary"
                              : "bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <label className="flex items-center gap-1 text-outline">
                      <span className="sr-only">Minutes studied on {dayLabel(d.day)}</span>
                      <input
                        type="number"
                        min={0}
                        max={600}
                        value={entry ? entry.done : ""}
                        placeholder="min"
                        onChange={(e) => mark(d.day, d.planned_minutes, Math.max(0, Number(e.target.value) || 0))}
                        className="w-16 px-1 py-0.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-code-sm text-code-sm"
                      />
                    </label>
                  </div>
                );
              })}
          </div>
        </div>

        <div className="flex flex-col gap-space-xs p-space-md rounded-lg bg-surface-container">
          <span className="font-body-strong text-body-sm">2. Add your calendar (optional)</span>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Export it as an <b>.ics</b> file (Google Calendar: Settings → Import &amp; export → Export; Outlook: Save
            calendar). It stays in this browser and is only used to find your free time.
          </p>
          <div className="flex flex-wrap items-center gap-space-xs">
            <label className="px-space-md py-1.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm cursor-pointer flex items-center gap-1.5">
              <Ms name="upload_file" size={16} /> {ics ? "Replace calendar" : "Choose .ics file"}
              <input type="file" accept=".ics,text/calendar" className="sr-only" onChange={(e) => e.target.files?.[0] && void readIcs(e.target.files[0])} />
            </label>
            {ics && (
              <>
                <Pill tone="tertiary" icon="event_available">
                  {ics.name}: {q.data ? `${q.data.busy_events} events ahead` : "reading…"}
                </Pill>
                <button type="button" onClick={() => setIcs(null)} className="font-label-badge text-label-badge text-outline hover:text-error">
                  Remove
                </button>
              </>
            )}
          </div>
          {icsError && <ErrorBox>{icsError}</ErrorBox>}
        </div>
      </div>

      {q.isPending ? (
        <Loading label="Re-planning around your week…" />
      ) : q.isError ? (
        <ErrorBox>{q.error.message}</ErrorBox>
      ) : (
        <>
          <Result r={q.data} goal={goal} domain={domain} />
          <WhatFitsCard
            learnerId={learnerId}
            goal={goal}
            goals={goals}
            deadline={deadline}
            hoursPerWeek={hoursPerWeek}
            log={Object.entries(log).map(([day, v]) => ({ day, planned_minutes: v.planned, done_minutes: v.done }))}
          />
        </>
      )}
    </section>
  );
}

function Result({ r, goal, domain }: { r: RescheduleResponse; goal: string; domain: string }) {
  const byDay = new Map<string, RescheduleBlock[]>();
  r.blocks.forEach((b) => byDay.set(b.day, [...(byDay.get(b.day) ?? []), b]));
  const days = r.days.slice(0, 14);
  const late = r.finish && r.finish > r.deadline;
  return (
    <div className="flex flex-col gap-space-md">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-space-sm">
        <Tile
          icon="speed"
          label="You manage"
          value={r.logged_days ? `${Math.round(r.adherence * 100)}% of planned time` : "Not measured yet"}
          sub={r.logged_days ? `${hm(r.done_minutes)} of ${hm(r.planned_minutes_so_far)} over ${r.logged_days} day(s)` : "Mark a few sessions above"}
        />
        <Tile icon="hourglass_top" label="Still to do" value={hm(r.remaining_minutes)} sub="including a realistic buffer" />
        {r.forecast ? (
          <Tile
            icon="flag"
            label="Likely finish"
            value={r.forecast.p50 ? dayLabel(r.forecast.p50) : "after the horizon"}
            sub={`80% sure by ${r.forecast.p80 ? dayLabel(r.forecast.p80) : "—"} · ${Math.round(r.forecast.p_on_time * 100)}% chance by the deadline`}
            tone={r.forecast.p_on_time >= 0.8 ? "text-tertiary" : r.forecast.p_on_time >= 0.5 ? "text-secondary" : "text-error"}
          />
        ) : (
          <Tile
            icon="flag"
            label="You'll finish"
            value={r.finish ? dayLabel(r.finish) : "—"}
            sub={r.feasible ? `deadline ${dayLabel(r.deadline)}` : `needs about ${r.hours_per_week_needed} h a week`}
            tone={r.feasible && !late ? "text-tertiary" : "text-error"}
          />
        )}
        <Tile
          icon="compare_arrows"
          label="A fixed calendar would"
          value={r.naive.finish ? `finish ${dayLabel(r.naive.finish)}` : "not finish"}
          sub={r.naive.notes[0] ?? "ignore your calendar"}
        />
      </div>

      <ForecastCheck r={r} />
      <Slowdowns r={r} domain={domain} />
      <StudyContext r={r} />
      <Memory r={r} domain={domain} />
      {r.velocity?.aware && r.velocity.topics.length > 0 && <Speed v={r.velocity} />}

      {r.reasons.length > 0 && (
        <ul className="flex flex-col gap-1 p-space-md rounded-lg bg-surface-container-lowest">
          {r.reasons.map((x) => (
            <li key={x} className="flex items-start gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
              <Ms name="info" size={16} className="text-secondary mt-0.5" /> {x}
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center justify-between">
        <span className="font-body-strong text-body-sm">Next two weeks</span>
        <div className="flex items-center gap-space-md font-label-annotation text-label-annotation text-outline">
          <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-outline-variant" /> busy</span>
          <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-primary" /> study block</span>
          <button
            type="button"
            disabled={!r.blocks.length}
            onClick={() =>
              downloadIcs(
                "syntropix-study-blocks.ics",
                `Syntropix · ${goal}`,
                r.blocks.map((b) => ({
                  day: b.day,
                  start: b.start,
                  end: b.end,
                  title: `Study: ${b.concept}${b.parts > 1 ? ` (${b.part}/${b.parts})` : ""}`,
                  description: b.title,
                })),
              )
            }
            className="px-space-sm py-1 rounded bg-surface-container-high hover:bg-surface-container-highest text-on-surface flex items-center gap-1 disabled:opacity-40"
          >
            <Ms name="download" size={14} /> Add blocks to my calendar
          </button>
        </div>
      </div>
      <div className="flex flex-col gap-1" role="list" aria-label="Study blocks for the next two weeks">
        <div className="flex gap-space-sm font-label-annotation text-label-annotation text-outline" aria-hidden>
          <span className="w-28 shrink-0" />
          <div className="relative flex-1 h-3">
            {[8, 12, 16, 20].map((h) => (
              <span key={h} className="absolute -translate-x-1/2" style={{ left: pct(h * 60) }}>{h}:00</span>
            ))}
          </div>
          <span className="w-56 shrink-0" />
        </div>
        {days.map((d) => {
          const blocks = byDay.get(d.day) ?? [];
          const busy = r.busy_spans[d.day] ?? [];
          return (
            <div key={d.day} role="listitem" className="flex items-center gap-space-sm">
              <span className="w-28 shrink-0 font-body-sm text-body-sm flex items-center gap-1">
                {dayLabel(d.day)}
                {d.fatigue >= 0.25 && (
                  <span title={`Busier than your usual day: blocks up to ${d.max_block} min`} className="text-secondary">
                    <Ms name="battery_3_bar" size={14} label="busy day" />
                  </span>
                )}
              </span>
              <div className="relative flex-1 h-7 rounded bg-surface-container-lowest overflow-hidden">
                {busy.map(([a, b], i) => (
                  <span key={`b${i}`} className="absolute top-0 bottom-0 bg-outline-variant/70" style={{ left: pct(toMin(a)), width: `calc(${pct(toMin(b))} - ${pct(toMin(a))})` }} title={`Busy ${a}–${b}`} />
                ))}
                {blocks.map((b, i) => (
                  <span
                    key={`s${i}`}
                    className={`absolute top-1 bottom-1 rounded-sm ${b.kind === "retention" || b.kind === "review" ? "bg-tertiary" : "bg-primary"}`}
                    style={{ left: pct(toMin(b.start)), width: `calc(${pct(toMin(b.end))} - ${pct(toMin(b.start))})` }}
                    title={`${b.start}–${b.end} ${b.concept}${b.parts > 1 ? ` (part ${b.part} of ${b.parts})` : ""}`}
                  />
                ))}
              </div>
              <span className="w-56 shrink-0 font-label-annotation text-label-annotation text-on-surface-variant truncate">
                {blocks.length ? blocks.map((b) => `${b.start} ${b.concept.split(" ")[0]}${b.parts > 1 ? ` ${b.part}/${b.parts}` : ""}`).join(" · ") : "rest"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Tile({ icon, label, value, sub, tone = "text-on-surface" }: { icon: string; label: string; value: string; sub: string; tone?: string }) {
  return (
    <div className="p-space-md rounded-lg bg-surface-container flex flex-col gap-0.5">
      <span className="font-label-annotation text-label-annotation text-outline uppercase flex items-center gap-1">
        <Ms name={icon} size={14} /> {label}
      </span>
      <span className={`font-headline-sm text-headline-sm ${tone}`}>{value}</span>
      <span className="font-label-annotation text-label-annotation text-on-surface-variant">{sub}</span>
    </div>
  );
}

/** Your speed per topic: where the plan gives you more or less time than the lessons. */
function Speed({ v }: { v: NonNullable<RescheduleResponse["velocity"]> }) {
  const [all, setAll] = useState(false);
  const shown = all ? v.topics : [...v.topics.slice(0, 3), ...v.topics.slice(-2)].filter((t, i, a) => a.findIndex((x) => x.concept_id === t.concept_id) === i);
  return (
    <details className="p-space-md rounded-lg bg-surface-container-lowest" open>
      <summary className="cursor-pointer font-body-strong text-body-sm">
        Planned at your speed{" "}
        <span className="font-label-annotation text-label-annotation text-outline">
          ({v.measured_topics ? `${v.measured_topics} topic(s) measured from your practice, the rest predicted from what they build on` : "predicted until you practise: it sharpens with every answer"})
        </span>
      </summary>
      <div className="flex flex-col gap-1 pt-space-xs">
        {shown.map((t) => (
          <div key={t.concept_id} className="flex items-center gap-space-sm font-body-sm text-body-sm">
            <span className="flex-1 truncate">{t.concept}</span>
            <span className={`w-36 text-right font-label-annotation text-label-annotation ${t.ratio > 1.15 ? "text-secondary" : t.ratio < 0.85 ? "text-tertiary" : "text-outline"}`}>
              {t.ratio > 1.15 ? `${t.ratio.toFixed(1)}× the lesson time` : t.ratio < 0.85 ? `${Math.round(t.ratio * 100)}% of the lesson time` : "about the lesson time"}
            </span>
            <Pill tone="neutral">{t.source}</Pill>
          </div>
        ))}
        {v.topics.length > 5 && (
          <button type="button" onClick={() => setAll((a) => !a)} className="w-fit font-label-badge text-label-badge text-primary hover:underline">
            {all ? "Show fewer" : `Show all ${v.topics.length} topics`}
          </button>
        )}
      </div>
    </details>
  );
}
