import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Caption, Hci, HciRibbon, Ms, Pill, dayLabel, hm, isoToday } from "../../components/stitch";
import { trackName } from "../../components/Shell";
import { useLearner } from "../../context/LearnerContext";
import { useTrack } from "../../context/TrackContext";
import type { Path, ScheduleInput } from "../../lib/api";
import { downloadIcs } from "../../lib/ics";
import { MASTERED, buildSessions, practiceTarget, usePlan, type PlanSession, type PlanStep } from "../../lib/plan";
import { useExplain, useSchedule } from "../../lib/queries";
import { planGate } from "./NeedGoal";

/** Session preview / cleared - the Stitch "Session NN Preview" screens. */
export function SessionPage() {
  const p = usePlan();
  const gate = planGate(p);
  if (gate) return gate;
  return <SessionView plan={p.plan!} goals={p.goals} domain={p.resolved.data!.source === "seed" ? p.resolved.data!.domain : p.resolved.data!.source} trackDomain={p.resolved.data!.domain} />;
}

function SessionView({ plan, goals, domain, trackDomain }: { plan: Path; goals: string[]; domain: string; trackDomain: string }) {
  const { n } = useParams();
  const { learnerId } = useLearner();
  const { track } = useTrack();
  const sessions = useMemo(() => buildSessions(plan, goals, track.hoursPerWeek), [plan, goals, track.hoursPerWeek]);
  const idx = Math.min(sessions.length, Math.max(1, Number(n) || 1)) - 1;
  const s = sessions[idx]!;
  const prev = sessions[idx - 1];
  const next = sessions[idx + 1];
  const cleared = s.status === "done";
  const concepts = [...new Set(s.steps.map((x) => x.step.concept_id))];
  const avg = (f: (c: string) => number) => concepts.reduce((t, c) => t + f(c), 0) / Math.max(1, concepts.length);
  const meanMastery = avg((c) => plan.mastery[c] ?? 0);
  const passProb = avg((c) => plan.p_correct[c] ?? 0);
  const milestone = s.steps.find((x) => x.type === "milestone");
  const first = s.steps.find((x) => !x.done) ?? s.steps[0];

  const schedInput = useMemo<ScheduleInput>(
    () => ({ learner_id: learnerId, goal: track.goal, goals, deadline: track.deadline, weekly_minutes: track.hoursPerWeek * 60, speed: track.speed }),
    [learnerId, track.goal, goals, track.deadline, track.hoursPerWeek, track.speed],
  );
  const cal = useSchedule(schedInput, Boolean(track.deadline)).data?.calendar;
  const when = s.date === isoToday() ? "TODAY" : dayLabel(s.date).toUpperCase();

  return (
    <div className="flex flex-col w-full gap-space-lg">
      <header className="flex flex-col gap-space-sm">
        <div className="flex flex-wrap items-center justify-between gap-space-sm font-code-sm text-code-sm text-on-surface-variant">
          <div className="flex items-center gap-space-xs">
            <Link to="/map" className="hover:text-primary">Skill map</Link>
            <span className="text-outline">/</span>
            <Link to="/plan" className="hover:text-primary uppercase">{trackName(trackDomain)}</Link>
            <span className="text-outline">/</span>
            <span className="text-primary font-body-strong">SESSION {String(s.number).padStart(2, "0")} {cleared ? "CLEARED" : "PREVIEW"}</span>
          </div>
          <div className="flex items-center gap-space-xs">
            <Hci className="px-space-xs py-0.5 rounded bg-surface-container-high">[H-10 CAUSAL DAG TRANSPARENCY]</Hci>
            {sessions.length > 1 && (
              <span className="flex items-center gap-1">
                <Link aria-label="Previous session" to={`/session/${Math.max(1, s.number - 1)}`} className="p-1 rounded hover:bg-surface-container-high"><Ms name="chevron_left" /></Link>
                <span className="font-label-badge text-label-badge">{s.number} / {sessions.length}</span>
                <Link aria-label="Next session" to={`/session/${Math.min(sessions.length, s.number + 1)}`} className="p-1 rounded hover:bg-surface-container-high"><Ms name="chevron_right" /></Link>
              </span>
            )}
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-space-xs p-space-sm rounded-lg bg-surface-container-low">
          <Telemetry icon="schedule" label="When" value={cleared ? "Done" : when} tone="text-on-surface" />
          <Telemetry icon="analytics" label="You know these" value={`${Math.round(meanMastery * 100)}% ${meanMastery >= MASTERED ? "(known)" : "on average"}`} tone="text-tertiary" />
          <Telemetry icon="flag" label="Deadline" value={track.deadline ? dayLabel(track.deadline) : "None set"} tone="text-on-surface" />
          <Telemetry icon="hourglass_top" label="Spare days" value={cal ? (cal.feasible ? `${cal.slack_days} days spare` : "Behind schedule") : "Set a deadline"} tone={cal && !cal.feasible ? "text-error" : "text-secondary"} />
          <Telemetry icon="verified" label="Chance you pass" value={`${Math.round(passProb * 100)}%`} tone="text-primary" />
        </div>
        {(prev || milestone) && (
          <div className="flex flex-wrap items-center justify-between gap-space-sm p-space-sm rounded-lg bg-surface-container-low">
            {milestone ? (
              <div className="flex items-center gap-space-sm">
                <Pill tone="secondary" icon="stars">MILESTONE</Pill>
                <span className="font-body-sm text-body-sm text-on-surface font-semibold">{milestone.step.concept} — a goal of this track</span>
              </div>
            ) : <span />}
            {prev && (
              <div className="flex items-center gap-space-xs text-on-surface-variant font-code-sm text-code-sm">
                <Ms name={prev.status === "done" ? "check_circle" : "pending"} size={16} className={prev.status === "done" ? "text-tertiary" : "text-outline"} />
                <span>SESSION {String(prev.number).padStart(2, "0")} {prev.status === "done" ? "FINISHED" : "IN PROGRESS"}</span>
                <span className="text-outline">·</span>
                <span className="text-tertiary">{Math.round((prev.steps.filter((x) => x.done).length / prev.steps.length) * 100)}% MASTERY</span>
                <span className="text-outline">·</span>
                <span>{hm(prev.minutes)}</span>
              </div>
            )}
          </div>
        )}
      </header>

      <section className="relative overflow-hidden p-space-lg rounded-xl bg-surface-container shadow-xl">
        <div className="absolute -right-24 -top-24 w-96 h-96 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-space-lg">
          <div className="flex flex-col gap-space-xs max-w-4xl">
            <div className="flex items-center gap-space-xs flex-wrap">
              <Pill tone="primary">Session Unit {String(s.number).padStart(2, "0")}</Pill>
              <span className="font-code-sm text-code-sm text-outline">EST. RUNTIME: {hm(s.minutes)}</span>
              {cleared && <Pill tone="tertiary" icon="verified">FINISHED</Pill>}
            </div>
            <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">{s.focus.join(" & ")}</h1>
            <p className="font-body-md text-body-md text-on-surface-variant">
              {s.steps.length} step{s.steps.length === 1 ? "" : "s"}:{" "}
              {s.steps.map((x) => `${x.step.concept} (${x.type === "teach" ? "learn" : x.type})`).join(", ")}.
            </p>
          </div>
          <div className="flex flex-wrap lg:flex-col gap-space-xs shrink-0 min-w-[240px]">
            {first && <LaunchButton ps={first} domain={domain} primary label={`Launch Step ${first.label} →`} />}
            <Link to="/plan" className="px-space-md py-2 rounded-lg bg-surface-container-high hover:bg-surface-bright font-body-sm text-body-sm flex items-center gap-1.5">
              <Ms name="list" size={16} /> Back to Study Plan
            </Link>
            <button
              type="button"
              onClick={() => downloadIcs(`velpo-session-${s.number}.ics`, `VELPO session ${s.number}`, [{ day: s.date, title: `VELPO session ${s.number}: ${s.focus.join(", ")}`, description: `${Math.round(s.minutes)} min` }])}
              className="px-space-md py-2 rounded-lg bg-surface-container-high hover:bg-surface-bright font-body-sm text-body-sm flex items-center gap-1.5"
            >
              <Ms name="event" size={16} /> Sync Calendar (.ICS)
            </button>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg">
        <div className="lg:col-span-3 flex flex-col gap-space-md">
          <Lineage plan={plan} prev={prev} s={s} next={next} />
          <Metacog plan={plan} concept={first?.step.concept_id ?? concepts[0]!} name={first?.step.concept ?? ""} />
        </div>
        <div className="lg:col-span-6 flex flex-col gap-space-md">
          {s.steps.map((ps) => (
            <StepBlock key={ps.index} ps={ps} plan={plan} session={s} domain={domain} learnerId={learnerId} />
          ))}
          {cleared && next && (
            <div className="p-space-md rounded-xl bg-tertiary-container/10 border border-tertiary/30 flex items-center justify-between gap-space-sm flex-wrap">
              <span className="flex items-center gap-space-sm font-body-strong text-body-sm text-tertiary">
                <Ms name="lock_open" /> Session {String(next.number).padStart(2, "0")} unlocked: {next.focus.slice(0, 2).join(", ")}
              </span>
              <Link to={`/session/${next.number}`} className="px-space-md py-1.5 rounded-lg bg-tertiary text-on-tertiary font-body-strong text-body-sm">
                Open Session {String(next.number).padStart(2, "0")}
              </Link>
            </div>
          )}
        </div>
        <div className="lg:col-span-3 flex flex-col gap-space-md">
          <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-sm">
            <div className="flex items-center justify-between border-b border-outline-variant/20 pb-space-xs">
              <span className="flex items-center gap-space-xs font-headline-sm text-headline-sm"><Ms name="speed" className="text-tertiary" /> Time</span>
              {cal && <Pill tone={cal.feasible ? "tertiary" : "error"}>{cal.feasible ? "ON TRACK" : "AT RISK"}</Pill>}
            </div>
            <Row k="Session length" v={hm(s.minutes)} />
            <Row k="Longest session" v={`${Math.round(plan.session_minutes)} min`} />
            <Row k="Your study time" v={`${track.hoursPerWeek} hours a week`} />
            <Row k="Spare days" v={cal ? `${cal.slack_days} days` : "—"} />
            <Row k="Deadline" v={track.deadline ? dayLabel(track.deadline) : "none set"} />
          </section>
          <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-sm">
            <span className="flex items-center gap-space-xs font-headline-sm text-headline-sm"><Ms name="workspace_premium" className="text-secondary" /> How well you know these</span>
            {concepts.map((c) => {
              const m = plan.mastery[c] ?? 0;
              return (
                <div key={c} className="flex flex-col gap-1">
                  <div className="flex justify-between font-body-sm text-body-sm">
                    <span className="text-on-surface-variant truncate">{plan.names[c] ?? c}</span>
                    <span className={m >= MASTERED ? "text-tertiary" : "text-secondary"}>{Math.round(m * 100)}%</span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
                    <div className={`h-full ${m >= MASTERED ? "bg-tertiary" : "bg-secondary"}`} style={{ width: `${m * 100}%` }} />
                  </div>
                </div>
              );
            })}
            <Hci>Counts as known at {Math.round(MASTERED * 100)}% or more</Hci>
          </section>
          <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-xs">
            <span className="flex items-center gap-space-xs font-headline-sm text-headline-sm"><Ms name="healing" className="text-primary" /> If you get stuck</span>
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              If you get a practice question wrong, the app works out which earlier topic caused it and
              adds a short fix-up step before you try again.
            </p>
            {plan.steps.some((x) => x.repair) && (
              <Pill tone="error" icon="build" className="w-fit">
                Fix-up steps waiting: {[...new Set(plan.steps.filter((x) => x.repair).map((x) => x.concept))].join(", ")}
              </Pill>
            )}
          </section>
        </div>
      </div>

      <HciRibbon
        title="Design notes: sessions"
        cards={[
          { tag: "H-10", title: "Show the why", body: "Before and after shows what this session builds on and what it unlocks." },
          { tag: "H-01", title: "Visibility of Status", tone: "secondary", body: "Runtime, slack and predicted pass rate come straight from the planner and the knowledge-tracing model." },
          { tag: "H-09", title: "Error Recovery", body: "A failed drill becomes a targeted repair, not a repeat of the same task." },
          { tag: "Self-check", title: "Know what you know", tone: "tertiary", body: "Guess how you'll do and compare it with the app's estimate." },
        ]}
      />
    </div>
  );
}

function Telemetry({ icon, label, value, tone }: { icon: string; label: string; value: string; tone: string }) {
  return (
    <div className="flex items-center gap-space-xs px-space-sm py-1 rounded bg-surface-container-lowest">
      <Ms name={icon} size={16} className="text-primary" />
      <div className="flex flex-col">
        <span className="font-label-annotation text-label-annotation text-outline uppercase">{label}</span>
        <span className={`font-code-sm text-code-sm ${tone}`}>{value}</span>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between font-body-sm text-body-sm">
      <span className="text-on-surface-variant">{k}</span>
      <span className="text-on-surface font-code-sm text-code-sm">{v}</span>
    </div>
  );
}

function Lineage({ plan, prev, s, next }: { plan: Path; prev?: PlanSession; s: PlanSession; next?: PlanSession }) {
  const node = (cid: string, state: "cleared" | "active" | "locked") => {
    const m = plan.mastery[cid] ?? 0;
    const name = plan.names[cid] ?? cid;
    if (state === "active")
      return (
        <div key={`a-${cid}`} className="flex items-start gap-space-xs p-space-xs rounded bg-primary/10 border border-primary/50 shadow-sm">
          <Ms name="radio_button_checked" size={18} className="text-primary mt-0.5" />
          <div className="flex flex-col min-w-0">
            <span className="font-body-strong text-body-sm text-primary truncate">{name}</span>
            <span className="font-code-sm text-code-sm text-on-surface-variant">NOW · you know {Math.round(m * 100)}%</span>
          </div>
        </div>
      );
    return (
      <div key={`${state}-${cid}`} className={`flex items-start gap-space-xs p-space-xs rounded ${state === "locked" ? "bg-surface-container-low opacity-60" : "bg-surface-container-lowest"}`}>
        <Ms name={state === "locked" ? "lock" : m >= MASTERED ? "check_circle" : "pending"} size={18} className={state === "locked" ? "text-outline mt-0.5" : m >= MASTERED ? "text-tertiary mt-0.5" : "text-secondary mt-0.5"} />
        <div className="flex flex-col min-w-0">
          <span className={`font-body-sm text-body-sm truncate ${state === "locked" ? "text-outline" : "text-on-surface"}`}>{name}</span>
          <span className={`font-code-sm text-code-sm ${state === "locked" ? "text-outline" : m >= MASTERED ? "text-tertiary" : "text-secondary"}`}>
            {state === "locked" ? `AFTER SESSION ${s.number}` : `${m >= MASTERED ? "KNOWN" : "STILL LEARNING"} · ${Math.round(m * 100)}%`}
          </span>
        </div>
      </div>
    );
  };
  const uniq = (x?: PlanSession) => (x ? [...new Set(x.steps.map((y) => y.step.concept_id))] : []);
  return (
    <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-sm">
      <div className="flex items-center justify-between border-b border-outline-variant/20 pb-space-xs">
        <span className="flex items-center gap-space-xs font-headline-sm text-headline-sm"><Ms name="hub" className="text-primary" /> Before and after</span>
      </div>
      <div className="flex flex-col gap-space-xs">
        {uniq(prev).slice(-3).map((c) => node(c, "cleared"))}
        {uniq(s).map((c) => node(c, "active"))}
        {uniq(next).slice(0, 2).map((c) => node(c, "locked"))}
      </div>
    </section>
  );
}

function Metacog({ plan, concept, name }: { plan: Path; concept: string; name: string }) {
  const [rating, setRating] = useState<number | null>(null);
  const model = plan.p_correct[concept] ?? 0;
  return (
    <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-sm">
      <span className="font-label-annotation text-label-annotation text-primary font-bold tracking-wider uppercase">Quick self-check</span>
      <p className="font-body-sm text-body-sm text-on-surface leading-tight">How likely are you to get a {name} question right right now?</p>
      <div className="grid grid-cols-3 gap-1">
        {[
          ["Unlikely", 0.3],
          ["Maybe", 0.6],
          ["Likely", 0.88],
        ].map(([k, v]) => (
          <button
            key={k as string}
            type="button"
            aria-pressed={rating === v}
            onClick={() => setRating(v as number)}
            className={`py-1 px-2 rounded font-label-badge text-label-badge ${rating === v ? "bg-primary/20 text-primary font-bold" : "bg-surface-container hover:bg-surface-container-high text-on-surface-variant"}`}
          >
            {k}
          </button>
        ))}
      </div>
      {rating != null && (
        <p className="font-label-annotation text-label-annotation text-on-surface-variant">
          The app thinks {Math.round(model * 100)}%. {Math.abs(rating - model) < 0.15 ? "Your guess matches your results." : rating > model ? "You may be a bit over-confident: a quick review could help." : "You know more than you think!"}
        </p>
      )}
    </section>
  );
}

function LaunchButton({ ps, domain, primary = false, label }: { ps: PlanStep; domain: string; primary?: boolean; label?: string }) {
  const target = practiceTarget(ps.step.concept_id, domain);
  const cls = primary
    ? "px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm shadow-md hover:bg-primary-fixed flex items-center gap-1.5"
    : "px-space-md py-1.5 rounded-lg bg-primary/90 text-on-primary font-body-strong text-body-sm flex items-center gap-1.5 w-fit";
  const text = label ?? (target ? `Practise step ${ps.label}` : `Open step ${ps.label}`);
  if (target)
    return (
      <Link to={`/practice?target=${encodeURIComponent(target)}`} className={cls}>
        <Ms name="bolt" size={18} /> {text}
      </Link>
    );
  if (ps.step.url)
    return (
      <a href={ps.step.url} target="_blank" rel="noreferrer" className={cls}>
        <Ms name="open_in_new" size={16} /> {text}
      </a>
    );
  return null;
}

function StepBlock({ ps, plan, session, domain, learnerId }: { ps: PlanStep; plan: Path; session: PlanSession; domain: string; learnerId: string }) {
  const explain = useExplain();
  const [open, setOpen] = useState(false);
  const blocker = session.steps.find((o) => o.index < ps.index && !o.done && (plan.prerequisites[ps.step.concept_id] ?? []).includes(o.step.concept_id));
  const state = ps.done ? "DONE" : blocker ? `AFTER STEP ${blocker.label}` : "READY";
  return (
    <section className={`p-space-lg rounded-xl flex flex-col gap-space-sm ${ps.done ? "bg-surface-container-low opacity-80" : blocker ? "bg-surface-container-low" : "bg-surface-container shadow-md ring-1 ring-primary/30"}`}>
      <div className="flex flex-wrap items-center gap-space-xs">
        <Pill tone="primary">STEP {ps.label} · {Math.round(ps.step.minutes)} MIN</Pill>
        <Pill tone={ps.done ? "tertiary" : blocker ? "neutral" : "secondary"}>{state}</Pill>
        <span className="font-label-annotation text-label-annotation text-on-surface-variant uppercase tracking-wider">{ps.type === "teach" ? "LEARN" : ps.type}</span>
      </div>
      <h2 className="font-headline-md text-headline-md text-on-surface">{ps.step.title || ps.step.concept}</h2>
      {ps.step.reason && <p className="font-body-md text-body-md text-on-surface-variant">{ps.step.reason.replace(/\*\*(.+?)\*\*/g, "$1")}</p>}
      <div className="p-space-sm rounded bg-surface-container-lowest border-l-2 border-secondary flex flex-col gap-1">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => {
            setOpen((v) => !v);
            if (!open && !explain.data) explain.mutate({ learnerId, resourceId: ps.step.resource_id });
          }}
          className="font-label-annotation text-label-annotation text-secondary uppercase font-bold tracking-wider text-left flex items-center gap-1"
        >
          Why this step here? <Ms name={open ? "expand_less" : "expand_more"} size={14} />
        </button>
        {open && (
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            {explain.isPending ? "Loading…" : explain.data ? explain.data.reason.replace(/\*\*(.+?)\*\*/g, "$1") : "Couldn't load the reason."}
          </p>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-space-sm pt-space-xs">
        <div className="flex items-center gap-space-md font-code-sm text-code-sm">
          <span className="flex items-center gap-1 text-tertiary">
            <Ms name="check" size={16} /> you know {Math.round((ps.mastery ?? 0) * 100)}%
          </span>
          <span className="flex items-center gap-1 text-on-surface-variant">
            <Ms name="speed" size={16} /> difficulty {Math.round(ps.step.difficulty)}/5
          </span>
        </div>
        {!ps.done && !blocker && <LaunchButton ps={ps} domain={domain} />}
      </div>
    </section>
  );
}

export { Caption };
