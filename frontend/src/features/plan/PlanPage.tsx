import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Caption, Hci, HciRibbon, Kbd, Ms, Pill, Tabs, dayLabel, isoToday } from "../../components/stitch";
import { useLearner } from "../../context/LearnerContext";
import { useTrack } from "../../context/TrackContext";
import type { Path, Step } from "../../lib/api";
import { downloadIcs } from "../../lib/ics";
import {
  MASTERED,
  buildSessions,
  dependants,
  planDelta,
  practiceTarget,
  usePlan,
  type PlanSession,
  type PlanStep,
  type StepType,
} from "../../lib/plan";
import { useExplain } from "../../lib/queries";
import { planGate } from "./NeedGoal";

type Filter = "all" | "upcoming" | "repairs";

const TYPE: Record<
  StepType,
  { label: string; badgeIcon: string; icon: string; box: string; badge: string; hci: string }
> = {
  review: {
    label: "Review",
    badgeIcon: "cached",
    icon: "sync",
    box: "bg-tertiary/10 text-tertiary",
    badge: "bg-tertiary-container/20 text-tertiary",
    hci: "[H-01 Status Visibility] Scheduled before predicted decay",
  },
  repair: {
    label: "Fix a gap",
    badgeIcon: "build",
    icon: "build_circle",
    box: "bg-error-container/40 text-error",
    badge: "bg-error-container/40 text-error",
    hci: "[H-09 Error Recovery] Inserted by a practice diagnosis",
  },
  teach: {
    label: "Learn",
    badgeIcon: "school",
    icon: "menu_book",
    box: "bg-primary/10 text-primary",
    badge: "bg-primary/20 text-primary",
    hci: "[H-04 Consistency] Prerequisites before dependants",
  },
  check: {
    label: "Quick check",
    badgeIcon: "crisis_alert",
    icon: "speed",
    box: "bg-secondary-container/20 text-secondary-fixed-dim",
    badge: "bg-secondary-container/20 text-secondary-fixed-dim",
    hci: "[H-05 Error Prevention] An uncertain prerequisite is checked first",
  },
  milestone: {
    label: "Goal checkpoint",
    badgeIcon: "flag",
    icon: "military_tech",
    box: "bg-secondary/10 text-secondary",
    badge: "bg-secondary-container/20 text-secondary",
    hci: "Your goal topic",
  },
};

export function PlanTabs({ current }: { current: "roadmap" | "plan" }) {
  const nav = useNavigate();
  return (
    <Tabs
      label="Plan views"
      value={current}
      onChange={(v) => nav(v === "plan" ? "/plan" : "/roadmap")}
      options={[
        { value: "roadmap", label: "Roadmap (timeline)", icon: current === "roadmap" ? undefined : "timeline" },
        { value: "plan", label: "Study plan (sessions)", icon: current === "plan" ? undefined : "list" },
      ]}
    />
  );
}

export function PlanPage() {
  const p = usePlan();
  const gate = planGate(p);
  if (gate) return gate;
  return <StudyPlan plan={p.plan!} goals={p.goals} domain={p.resolved.data!.source === "seed" ? p.resolved.data!.domain : p.resolved.data!.source} />;
}

function StudyPlan({ plan, goals, domain }: { plan: Path; goals: string[]; domain: string }) {
  const { track, update } = useTrack();
  const { learnerId } = useLearner();
  const sessions = useMemo(() => buildSessions(plan, goals, track.hoursPerWeek), [plan, goals, track.hoursPerWeek]);
  const delta = useMemo(() => planDelta(learnerId, track.goal, plan), [learnerId, track.goal, plan]);
  const [filter, setFilter] = useState<Filter>("all");
  const [openWhy, setOpenWhy] = useState<Set<number>>(new Set());
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const listRef = useRef<HTMLDivElement>(null);
  const nav = useNavigate();

  const all = sessions.flatMap((s) => s.steps);
  const current = sessions.find((s) => s.status === "current");
  const next = current?.steps.find((s) => !s.done) ?? all.find((s) => !s.done);
  const remaining = sessions.filter((s) => s.status !== "done").reduce((t, s) => t + s.minutes, 0);
  const saved = Math.max(0, plan.baseline_minutes - plan.total_minutes);
  const last = [...sessions].reverse().find((s) => s.status !== "done");
  const finish = track.deadline || last?.date || isoToday();
  const repairs = all.filter((s) => s.type === "repair").length;
  const checks = all.filter((s) => s.type === "check").length;
  const show = (s: PlanStep) =>
    filter === "all" ? true : filter === "upcoming" ? !s.done : s.type === "repair" || s.type === "check";
  const toggleWhy = (i: number) =>
    setOpenWhy((o) => {
      const n = new Set(o);
      if (n.has(i)) n.delete(i);
      else n.add(i);
      return n;
    });

  // J / K move between steps, Space toggles "Why this now?", Enter launches
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      const cards = [...(listRef.current?.querySelectorAll<HTMLElement>("[data-step]") ?? [])];
      const at = cards.indexOf(document.activeElement as HTMLElement);
      if (e.key === "j" || e.key === "k") {
        e.preventDefault();
        const n = e.key === "j" ? Math.min(at + 1, cards.length - 1) : Math.max(at - 1, 0);
        cards[at < 0 ? 0 : n]?.focus();
      } else if (e.key === " " && at >= 0) {
        e.preventDefault();
        toggleWhy(Number(cards[at]!.dataset.step));
      } else if (e.key === "Enter" && at >= 0) {
        cards[at]!.querySelector<HTMLElement>("[data-launch]")?.click();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex flex-col w-full">
      <section className="flex flex-col gap-space-lg mb-space-xl">
        <div className="flex flex-wrap items-center justify-between gap-space-md">
          <PlanTabs current="plan" />
          <div className="flex items-center gap-space-sm flex-wrap">
            {current && next && (
              <span className="flex items-center gap-space-xs px-space-md py-1 rounded-full bg-surface-container-high text-primary font-label-badge text-label-badge shadow-sm">
                <Ms name="play_circle" size={14} />
                Current: Session {String(current.number).padStart(2, "0")} · {next.step.concept}
              </span>
            )}
            <span className="hidden xl:flex items-center gap-space-xs px-space-sm py-1 rounded-full bg-tertiary-container/20 text-tertiary font-label-badge text-label-badge">
              <Ms name="verified" size={13} />
              Plan up to date
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-space-md p-space-lg rounded-xl bg-surface-container shadow-md">
          <div className="flex flex-col gap-space-xs">
            <Caption>Time left</Caption>
            <div className="flex items-baseline gap-space-xs">
              <span className="font-headline-lg text-headline-lg text-on-surface">{(remaining / 60).toFixed(1)}</span>
              <span className="font-label-badge text-label-badge text-on-surface-variant">hours</span>
              <span className="font-body-sm text-body-sm text-outline ml-space-xs">
                (in {sessions.filter((s) => s.status !== "done").length} sessions)
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-space-xs">
            <Caption>Time saved</Caption>
            <div className="flex items-baseline gap-space-xs">
              <span className="font-headline-lg text-headline-lg text-secondary">+{(saved / 60).toFixed(1)}</span>
              <span className="font-label-badge text-label-badge text-secondary">hours saved</span>
            </div>
            <span className="font-label-badge text-label-badge text-on-surface-variant">
              compared with taking every full lesson ({(plan.baseline_minutes / 60).toFixed(1)}h)
            </span>
          </div>
          <div className="flex flex-col gap-space-xs">
            <Caption>You'll finish around</Caption>
            <div className="flex items-baseline gap-space-xs">
              <span className="font-headline-lg text-headline-lg text-on-surface">{dayLabel(finish)}</span>
              <span className="font-label-badge text-label-badge text-on-surface-variant">{finish.slice(0, 4)}</span>
            </div>
            <span className="font-label-badge text-label-badge text-tertiary">
              {plan.min_confidence != null
                ? `${Math.round(plan.min_confidence * 100)}% sure you're ready for each step`
                : track.deadline
                  ? "Your deadline"
                  : `At ${track.hoursPerWeek} h/week`}
            </span>
          </div>
          <div className="flex flex-col gap-space-xs">
            <Caption>Changes made for you</Caption>
            <div className="flex items-center gap-space-xs mt-1 flex-wrap">
              <Pill tone="error" icon="build">
                {repairs} fix-up step{repairs === 1 ? "" : "s"}
              </Pill>
              <Pill tone="secondary" icon="speed">
                {checks} quick check{checks === 1 ? "" : "s"}
              </Pill>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-space-md pt-space-xs">
          <div className="flex flex-wrap items-center gap-space-xs" role="group" aria-label="Filter steps">
            {(
              [
                ["all", `All Steps (${all.length})`],
                ["upcoming", `Upcoming Only (${all.filter((s) => !s.done).length})`],
                ["repairs", `Repairs & Checks (${repairs + checks})`],
              ] as const
            ).map(([f, text]) => (
              <button
                key={f}
                type="button"
                aria-pressed={filter === f}
                onClick={() => setFilter(f)}
                className={`px-space-md py-1 rounded font-body-sm text-body-sm flex items-center gap-1 ${
                  filter === f
                    ? "bg-surface-container-high text-on-surface font-body-strong shadow-sm"
                    : f === "repairs"
                      ? "bg-surface-container text-error hover:bg-surface-container-high"
                      : "bg-surface-container text-on-surface-variant hover:text-on-surface"
                }`}
              >
                {f === "repairs" && <Ms name="warning" size={14} />}
                {text}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-space-sm">
            <span className="flex items-center gap-space-xs px-space-sm py-1 rounded bg-surface-container-low text-on-surface-variant font-label-annotation text-label-annotation">
              <Ms name="sort" size={14} />
              Order: Topological Sort (Prerequisite-Aware)
            </span>
            <span className="px-space-sm py-1 rounded bg-surface-container text-on-surface-variant font-label-badge text-label-badge">
              ⚙ {Math.round(plan.session_minutes)}m / session
            </span>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg mb-space-xl">
        <div ref={listRef} className="lg:col-span-8 flex flex-col gap-space-xl">
          {sessions.map((s) => {
            const visible = s.steps.filter(show);
            if (!visible.length) return null;
            const hero = s.status === "current";
            const open =
              filter !== "all" ||
              expanded.has(s.index) ||
              hero ||
              (s.status === "scheduled" && s.index === (current?.index ?? -1) + 1);
            return (
              <SessionBlock
                key={s.index}
                session={s}
                open={open}
                onToggle={() =>
                  setExpanded((e) => {
                    const n = new Set(e);
                    if (n.has(s.index)) n.delete(s.index);
                    else n.add(s.index);
                    return n;
                  })
                }
              >
                {visible.map((ps) => (
                  <StepCard
                    key={ps.index}
                    ps={ps}
                    plan={plan}
                    session={s}
                    domain={domain}
                    learnerId={learnerId}
                    why={openWhy.has(ps.index)}
                    onWhy={() => toggleWhy(ps.index)}
                    active={ps === next}
                  />
                ))}
              </SessionBlock>
            );
          })}
        </div>

        <div className="lg:col-span-4 flex flex-col gap-space-lg">
          {next && <Directive ps={next} domain={domain} />}
          {current && <CognitiveLoad session={current} />}
          <DeltaCard delta={delta} />
          <section className="p-space-lg rounded-xl bg-surface-container shadow-md flex flex-col gap-space-md">
            <span className="font-headline-sm text-headline-sm text-on-surface">Plan tools</span>
            <div className="flex flex-col gap-space-xs">
              <button
                type="button"
                onClick={() => nav("/session/" + (current?.number ?? 1))}
                className="w-full py-2 px-space-md rounded-lg bg-surface-container-high hover:bg-surface-bright text-on-surface font-body-sm text-body-sm flex items-center justify-between"
              >
                <span className="flex items-center gap-space-xs">
                  <Ms name="preview" size={16} /> Open current session
                </span>
                <span className="font-label-annotation text-label-annotation text-outline">Open</span>
              </button>
              <button
                type="button"
                onClick={() =>
                  downloadIcs(
                    "velpo-study-plan.ics",
                    `Syntropix · ${track.goal}`,
                    sessions
                      .filter((s) => s.status !== "done")
                      .map((s) => ({
                        day: s.date,
                        title: `Syntropix session ${s.number}: ${s.focus.slice(0, 3).join(", ")}`,
                        description: `${Math.round(s.minutes)} min · ${s.steps.length} steps`,
                      })),
                  )
                }
                className="w-full py-2 px-space-md rounded-lg bg-surface-container-high hover:bg-surface-bright text-on-surface font-body-sm text-body-sm flex items-center justify-between"
              >
                <span className="flex items-center gap-space-xs">
                  <Ms name="calendar_month" size={16} /> Export to Calendar (iCal/GCal)
                </span>
                <span className="font-label-annotation text-label-annotation text-outline">.ics</span>
              </button>
              <label className="w-full py-2 px-space-md rounded-lg bg-surface-container-high text-on-surface font-body-sm text-body-sm flex items-center justify-between gap-space-sm">
                <span className="flex items-center gap-space-xs">
                  <Ms name="tune" size={16} /> Weekly Cadence
                </span>
                <span className="flex items-center gap-1">
                  <input
                    type="number"
                    min={1}
                    max={60}
                    step={0.5}
                    value={track.hoursPerWeek}
                    onChange={(e) => update({ hoursPerWeek: Math.max(1, Number(e.target.value) || 1) })}
                    aria-label="Hours per week"
                    className="w-16 px-1 py-0.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-code-sm text-code-sm text-right"
                  />
                  <span className="font-label-annotation text-label-annotation text-outline">h/wk</span>
                </span>
              </label>
            </div>
          </section>
          <div className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex items-start gap-space-sm">
            <Ms name="help_center" className="text-outline shrink-0 mt-0.5" />
            <div className="flex flex-col gap-1">
              <span className="font-label-badge text-label-badge text-on-surface">Why this order?</span>
              <p className="font-label-annotation text-label-annotation text-on-surface-variant">
                You always learn a topic after the topics it builds on. Among the orders that respect
                that, Syntropix picks the one that teaches the most in your time.
              </p>
            </div>
          </div>
        </div>
      </div>

      <HciRibbon
        title="Design notes: study plan"
        cards={[
          { tag: "H-01", title: "Visibility of System Status", body: "Minutes, session status and re-plan latency are shown for every step, so time spent is never a guess." },
          { tag: "H-04", title: "Consistency & Standards", tone: "secondary", body: "Each step type has its colour, its icon and a text badge: colour is never the only cue." },
          { tag: "H-10", title: "Explain Any Decision", body: "“Why this now?” shows the planner's own reason for every step, in plain language." },
          { tag: "Pedagogy", title: "Spaced Retrieval", tone: "tertiary", body: "Reviews are re-inserted when the forgetting model predicts a concept will fade before the goal." },
        ]}
        keys={
          <>
            <span>
              Move: <Kbd>J</Kbd> next step / <Kbd>K</Kbd> previous step
            </span>
            <span>
              Explain: <Kbd>Space</Kbd> “Why this now?”
            </span>
            <span>
              Start: <Kbd>Enter</Kbd>
            </span>
          </>
        }
      />
    </div>
  );
}

function SessionBlock({
  session: s,
  open,
  onToggle,
  children,
}: {
  session: PlanSession;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  const doneSteps = s.steps.filter((x) => x.done).length;
  const when =
    s.status === "done"
      ? "Completed"
      : s.status === "current"
        ? `Today, ${dayLabel(s.date)}`
        : `${new Date(`${s.date}T00:00:00Z`).toLocaleDateString(undefined, { weekday: "long", timeZone: "UTC" })}, ${dayLabel(s.date)}`;
  if (!open) {
    return (
      <section className={`flex flex-col gap-space-sm transition-opacity hover:opacity-100 ${s.status === "done" ? "opacity-70" : "opacity-80"}`}>
        <div className="flex items-center justify-between p-space-md rounded-xl bg-surface-container-low shadow-sm">
          <div className="flex items-center gap-space-md">
            <Ms
              name={s.status === "done" ? "check_circle" : "event_repeat"}
              size={20}
              className={s.status === "done" ? "text-tertiary" : "text-outline"}
            />
            <div className="flex flex-col">
              <span className="font-headline-sm text-headline-sm text-on-surface">
                Session {String(s.number).padStart(2, "0")} · {when}
                {s.status === "scheduled" && " (Planned)"}
              </span>
              <span className="font-label-annotation text-label-annotation text-on-surface-variant">
                {s.steps.length} steps · {Math.round(s.minutes)} min · {s.focus.slice(0, 3).join(", ")}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-space-sm">
            {s.status === "done" && <Pill tone="tertiary">{doneSteps} of {s.steps.length} verified</Pill>}
            <Link
              to={`/session/${s.number}`}
              className="px-space-sm py-1 rounded bg-surface-container text-on-surface-variant font-label-badge text-label-badge hover:bg-surface-container-high"
            >
              Preview
            </Link>
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={false}
              aria-label={`Show the steps of session ${s.number}`}
              className="px-space-sm py-1 rounded bg-surface-container text-on-surface-variant font-label-badge text-label-badge hover:bg-surface-container-high"
            >
              View Steps ({s.steps.length})
            </button>
          </div>
        </div>
      </section>
    );
  }
  const hero = s.status === "current";
  return (
    <section className="flex flex-col gap-space-md">
      <div
        className={`flex flex-wrap items-center justify-between gap-space-sm p-space-md rounded-xl ${
          hero ? "bg-surface-container-high shadow-md" : "bg-surface-container-low shadow-sm"
        }`}
      >
        <div className="flex items-center gap-space-md">
          {hero ? (
            <div className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse" />
          ) : (
            <Ms name={s.status === "done" ? "check_circle" : "calendar_today"} size={20} className={s.status === "done" ? "text-tertiary" : "text-outline"} />
          )}
          <div className="flex flex-col">
            <div className="flex items-center gap-space-sm flex-wrap">
              <h2 className="font-headline-md text-headline-md text-on-surface">
                Session {String(s.number).padStart(2, "0")} · {when}
              </h2>
              <Pill tone={hero ? "primary" : s.status === "done" ? "tertiary" : "neutral"}>
                {hero ? "In Progress" : s.status === "done" ? "Completed" : "Scheduled"}
              </Pill>
            </div>
            <span className="font-label-annotation text-label-annotation text-on-surface-variant">
              Estimated: {Math.round(s.minutes)} min · Target: {s.focus.slice(0, 3).join(", ")}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-space-md">
          {hero ? (
            <>
              <div className="flex flex-col text-right">
                <span className="font-label-badge text-label-badge text-on-surface">
                  Step {Math.min(doneSteps + 1, s.steps.length)} of {s.steps.length}
                </span>
                <span className="font-label-annotation text-label-annotation text-tertiary">
                  {Math.round(s.steps.filter((x) => !x.done).reduce((t, x) => t + x.step.minutes, 0))}m remaining
                </span>
              </div>
              <div className="w-16 h-2 rounded-full bg-surface-container-lowest overflow-hidden">
                <div className="h-full bg-primary rounded-full" style={{ width: `${(doneSteps / s.steps.length) * 100}%` }} />
              </div>
            </>
          ) : (
            <span className="font-label-badge text-label-badge text-outline">
              {doneSteps} of {s.steps.length} complete
            </span>
          )}
          <Link to={`/session/${s.number}`} className="font-label-badge text-label-badge text-on-surface-variant hover:text-primary flex items-center gap-1">
            Preview <Ms name="open_in_new" size={14} />
          </Link>
        </div>
      </div>
      <div className="flex flex-col gap-space-md">{children}</div>
    </section>
  );
}

function launchOf(ps: PlanStep, domain: string): { label: string; to?: string; href?: string } | null {
  const target = practiceTarget(ps.step.concept_id, domain);
  const label = {
    review: "Start review",
    repair: "Start fix-up",
    check: "Start check",
    milestone: "Start checkpoint",
    teach: ps.step.kind === "video" || ps.step.source === "youtube" ? "Watch video" : "Open lesson",
  }[ps.type];
  if (target && (ps.type !== "teach" || !ps.step.url))
    return { label: ps.type === "teach" ? "Practise it" : label, to: `/practice?target=${encodeURIComponent(target)}` };
  if (ps.step.url) return { label, href: ps.step.url };
  if (target) return { label, to: `/practice?target=${encodeURIComponent(target)}` };
  return null;
}

function StepCard({
  ps,
  plan,
  session,
  domain,
  learnerId,
  why,
  onWhy,
  active,
}: {
  ps: PlanStep;
  plan: Path;
  session: PlanSession;
  domain: string;
  learnerId: string;
  why: boolean;
  onWhy: () => void;
  active: boolean;
}) {
  const t = TYPE[ps.type];
  const s = ps.step;
  const explain = useExplain();
  // locked when a prerequisite of this step is taught earlier in the same session and isn't done
  const blocker = session.steps.find(
    (o) => o.index < ps.index && !o.done && (plan.prerequisites[s.concept_id] ?? []).includes(o.step.concept_id),
  );
  const launch = launchOf(ps, domain);
  const unlocks = dependants(plan, s.concept_id).map((c) => plan.names[c] ?? c);
  const unmet = (plan.prerequisites[s.concept_id] ?? []).filter((c) => (plan.mastery[c] ?? 0) < MASTERED);
  const toggle = () => {
    onWhy();
    if (!why && !explain.data) explain.mutate({ learnerId, resourceId: s.resource_id });
  };
  const meta = metaLine(ps);

  return (
    <div
      data-step={ps.index}
      tabIndex={0}
      className={`p-space-lg rounded-xl flex flex-col gap-space-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
        why || active ? "bg-surface-container-high shadow-xl" : "bg-surface-container shadow-md hover:bg-surface-container-high"
      } ${ps.done ? "opacity-70" : ""}`}
    >
      <div className="flex items-start justify-between gap-space-md">
        <div className="flex items-start gap-space-md min-w-0">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${t.box}`}>
            <Ms name={ps.done ? "check" : t.icon} />
          </div>
          <div className="flex flex-col gap-0.5 min-w-0">
            <div className="flex flex-wrap items-center gap-space-xs">
              <span className={`font-label-badge text-label-badge ${active ? "text-primary" : "text-on-surface-variant"}`}>
                Step {ps.label}
                {active && " (Active Focus)"}
              </span>
              <span className={`px-2 py-0.5 rounded font-label-badge text-label-badge flex items-center gap-1 ${t.badge}`}>
                <Ms name={t.badgeIcon} size={12} /> {t.label}
              </span>
              {meta && (
                <span className={`font-label-annotation text-label-annotation ${ps.type === "repair" ? "text-error" : ps.type === "milestone" ? "text-secondary" : "text-outline"}`}>
                  · {meta}
                </span>
              )}
            </div>
            <h3 className="font-headline-sm text-headline-sm text-on-surface">{s.title || s.concept}</h3>
            <div className="flex flex-wrap items-center gap-space-sm font-label-annotation text-label-annotation text-on-surface-variant mt-1">
              <span className={`flex items-center gap-1 ${ps.type === "repair" ? "text-primary" : ""}`}>
                <Ms name={kindIcon(s)} size={14} /> {kindText(s, domain)}
              </span>
              <span>·</span>
              <span className="flex items-center gap-1">
                <Ms name="schedule" size={14} /> {Math.round(s.minutes)} min
              </span>
              {s.difficulty > 0 && (
                <>
                  <span>·</span>
                  <span>Difficulty {s.difficulty.toFixed(1)} / 5</span>
                </>
              )}
              {ps.type === "repair" && (
                <>
                  <span>·</span>
                  <span className="text-error font-bold">Priority: fix first</span>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-space-sm shrink-0">
          {ps.done ? (
            <Pill tone="tertiary" icon="check">
              Mastered
            </Pill>
          ) : blocker ? (
            <span className="px-space-md py-1.5 rounded-lg bg-surface-container-highest text-on-surface-variant font-body-strong text-body-sm">
              Locked (Unlocks after {blocker.label})
            </span>
          ) : launch ? (
            launch.to ? (
              <Link
                data-launch
                to={launch.to}
                className={
                  active || ps.type === "repair"
                    ? "px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm shadow-md hover:bg-primary-fixed flex items-center gap-1.5"
                    : "px-space-md py-1.5 rounded-lg bg-surface-container-highest hover:bg-surface-bright text-on-surface font-body-strong text-body-sm"
                }
              >
                {(active || ps.type === "repair") && <Ms name="play_arrow" size={16} />}
                {launch.label}
              </Link>
            ) : (
              <a
                data-launch
                href={launch.href}
                target="_blank"
                rel="noreferrer"
                className={
                  active
                    ? "px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm shadow-md hover:bg-primary-fixed flex items-center gap-1.5"
                    : "px-space-md py-1.5 rounded-lg bg-surface-container-highest hover:bg-surface-bright text-on-surface font-body-strong text-body-sm flex items-center gap-1"
                }
              >
                {launch.label} <Ms name="open_in_new" size={14} />
              </a>
            )
          ) : null}
        </div>
      </div>

      {why ? (
        <>
          <div className="p-space-md rounded-lg bg-surface-container-lowest shadow-sm flex flex-col gap-space-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-space-xs text-secondary font-label-badge text-label-badge">
                <Ms name="psychology_alt" size={16} />
                <span>WHY THIS NOW?</span>
              </div>
              <Hci>[H-10 Explain Decision]</Hci>
            </div>
            {s.reason && <p className="font-body-md text-body-md text-on-surface-variant">{plain(s.reason)}</p>}
            {explain.isPending && <p className="font-body-sm text-body-sm text-outline">Loading the reason…</p>}
            {explain.data && <p className="font-body-md text-body-md text-on-surface-variant">{plain(explain.data.reason)}</p>}
            {explain.isError && <p className="font-body-sm text-body-sm text-outline">Couldn't load more detail.</p>}
            <div className="flex flex-wrap items-center gap-space-md pt-space-xs font-label-annotation text-label-annotation text-outline">
              <span>
                Concept: <strong className="text-on-surface font-code-sm text-code-sm">{s.concept_id}</strong>
              </span>
              <span>
                Now: <strong className="text-secondary font-code-sm text-code-sm">p(know) = {(ps.mastery ?? 0).toFixed(2)}</strong>
              </span>
              {unlocks.length > 0 && (
                <span>
                  Unlocks: <strong className="text-on-surface font-code-sm text-code-sm">{unlocks.slice(0, 3).join(", ")}</strong>
                </span>
              )}
              {unmet.length > 0 && (
                <span>
                  Needs first: <strong className="text-on-surface font-code-sm text-code-sm">{unmet.map((c) => plan.names[c] ?? c).join(", ")}</strong>
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between pt-space-xs text-on-surface-variant font-label-badge text-label-badge">
            <button type="button" onClick={toggle} aria-expanded className="hover:text-primary flex items-center gap-1">
              Hide rationale <Ms name="expand_less" size={14} />
            </button>
            <Hci>Cognitive effort: {s.difficulty >= 3.5 ? "High" : s.difficulty >= 2 ? "Medium" : "Low"}</Hci>
          </div>
        </>
      ) : (
        <div className="pt-space-xs flex items-center justify-between gap-space-sm">
          <button
            type="button"
            onClick={toggle}
            aria-expanded={false}
            className="text-on-surface-variant hover:text-primary font-label-badge text-label-badge flex items-center gap-1 transition-colors"
          >
            Why this now? <Ms name="expand_more" size={14} />
          </button>
          <Hci className="text-right">{t.hci}</Hci>
        </div>
      )}
    </div>
  );
}

function metaLine(ps: PlanStep): string {
  const m = ps.mastery;
  if (ps.type === "review") return `Retains ${ps.step.concept} mastery (p=${(m ?? 0).toFixed(2)})`;
  if (ps.type === "repair") return "Added because a practice mistake came from this topic";
  if (ps.type === "check") return "Makes sure you know an earlier topic before building on it";
  if (ps.type === "milestone") return "This is your goal topic";
  return m != null && m > 0 ? `You already know ${Math.round(m * 100)}%` : "New topic";
}

function kindIcon(s: Step): string {
  if (s.kind === "video" || s.source === "youtube") return "play_circle";
  if (s.kind === "practice") return "terminal";
  if (s.kind === "article" || s.kind === "docs") return "article";
  if (s.kind === "book") return "menu_book";
  if (s.kind === "course") return "school";
  return "psychology";
}

function kindText(s: Step, domain: string): string {
  const src = s.source ? ` (${s.source.replace("_", " ")})` : "";
  if (s.kind === "practice") return practiceTarget(s.concept_id, domain) ? "Practice (checked instantly)" : "Practice";
  if (s.kind === "video") return `Curated Video${src}`;
  if (s.kind === "lesson") return "Lesson";
  return `${s.kind[0]!.toUpperCase()}${s.kind.slice(1)}${src}`;
}

function plain(s: string): string {
  return s.replace(/\*\*(.+?)\*\*/g, "$1");
}

function Directive({ ps, domain }: { ps: PlanStep; domain: string }) {
  const launch = launchOf(ps, domain);
  const cls =
    "w-full py-2.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-md shadow-md hover:bg-primary-fixed transition-all flex items-center justify-center gap-space-sm";
  return (
    <section className="p-space-lg rounded-xl bg-surface-container shadow-xl flex flex-col gap-space-md">
      <div className="flex items-center justify-between">
        <Caption>Do this next</Caption>
        <Pill tone="primary">Step {ps.label}</Pill>
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="font-headline-sm text-headline-sm text-on-surface">{ps.step.title || ps.step.concept}</h3>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          {TYPE[ps.type].label}. About {Math.round(ps.step.minutes)} minutes.
        </p>
      </div>
      {launch?.to ? (
        <Link to={launch.to} className={cls}>
          Start Next Step ({Math.round(ps.step.minutes)}m) <Ms name="arrow_forward" />
        </Link>
      ) : launch?.href ? (
        <a href={launch.href} target="_blank" rel="noreferrer" className={cls}>
          Start Next Step ({Math.round(ps.step.minutes)}m) <Ms name="arrow_forward" />
        </a>
      ) : null}
      <div className="flex items-center justify-between pt-space-xs font-label-annotation text-label-annotation text-outline">
        <span>
          Tip: select a step and press <Kbd>Enter</Kbd> to start
        </span>
        <span className="text-tertiary">Progress saved</span>
      </div>
    </section>
  );
}

function CognitiveLoad({ session }: { session: PlanSession }) {
  const steps = session.steps;
  const total = steps.reduce((t, s) => t + s.step.minutes, 0) || 1;
  const activeMin = steps
    .filter((s) => s.step.kind === "practice" || s.type === "check" || s.type === "repair" || s.type === "review")
    .reduce((t, s) => t + s.step.minutes, 0);
  const active = Math.round((activeMin / total) * 100);
  const diff = steps.reduce((t, s) => t + s.step.difficulty * s.step.minutes, 0) / total;
  const load = Math.round((diff / 5) * 100);
  const safe = load <= 75;
  return (
    <section className="p-space-lg rounded-xl bg-surface-container shadow-md flex flex-col gap-space-md">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-space-xs">
          <Ms name="psychology" className="text-secondary" />
          <span className="font-headline-sm text-headline-sm text-on-surface">How heavy is this session?</span>
        </div>
        <Pill tone="secondary">{load} / 100</Pill>
      </div>
      <div className="flex flex-col gap-space-xs">
        <div className="flex justify-between font-label-badge text-label-badge text-on-surface-variant">
          <span>Difficulty</span>
          <span className={safe ? "text-tertiary" : "text-error"}>{safe ? "Comfortable" : "Heavy: take breaks"}</span>
        </div>
        <div className="w-full h-2 rounded-full bg-surface-container-lowest overflow-hidden flex">
          <div className="h-full bg-tertiary" style={{ width: `${Math.min(load, 45)}%` }} />
          <div className="h-full bg-secondary" style={{ width: `${Math.max(0, Math.min(load, 75) - 45)}%` }} />
          <div className="h-full bg-error" style={{ width: `${Math.max(0, load - 75)}%` }} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-space-sm pt-space-xs">
        <div className="p-space-sm rounded-lg bg-surface-container-low flex flex-col gap-1">
          <span className="font-label-annotation text-label-annotation text-on-surface-variant">Doing (practice)</span>
          <span className="font-headline-sm text-headline-sm text-on-surface">{active}%</span>
          <span className="font-label-badge text-label-badge text-tertiary">of session time</span>
        </div>
        <div className="p-space-sm rounded-lg bg-surface-container-low flex flex-col gap-1">
          <span className="font-label-annotation text-label-annotation text-on-surface-variant">Watching and reading</span>
          <span className="font-headline-sm text-headline-sm text-on-surface">{100 - active}%</span>
          <span className="font-label-badge text-label-badge text-outline">lessons and videos</span>
        </div>
      </div>
      <Hci>[Cognitive load] Each session's time and difficulty are capped.</Hci>
    </section>
  );
}

function DeltaCard({ delta }: { delta: ReturnType<typeof planDelta> }) {
  const rows: { icon: string; tone: string; bg: string; title: string; sub: string }[] = [];
  if (delta) {
    if (delta.repairs.length)
      rows.push({ icon: "add_circle", tone: "text-error", bg: "bg-error-container/20", title: `+${delta.repairs.length} fix-up step${delta.repairs.length > 1 ? "s" : ""} added`, sub: delta.repairs.slice(0, 3).join(", ") });
    const plain = delta.added.filter((a) => !delta.repairs.includes(a));
    if (plain.length) rows.push({ icon: "add_circle", tone: "text-primary", bg: "bg-surface-container-low", title: `+${plain.length} step${plain.length > 1 ? "s" : ""} added`, sub: plain.slice(0, 3).join(", ") });
    if (delta.removed.length) rows.push({ icon: "remove_circle", tone: "text-secondary", bg: "bg-surface-container-low", title: `-${delta.removed.length} step${delta.removed.length > 1 ? "s" : ""} no longer needed`, sub: delta.removed.slice(0, 3).join(", ") });
    if (delta.moved.length) rows.push({ icon: "swap_vert", tone: "text-primary", bg: "bg-surface-container-low", title: "Order changed", sub: `Moved: ${delta.moved.slice(0, 3).join(", ")}` });
  }
  return (
    <section className="p-space-lg rounded-xl bg-surface-container shadow-md flex flex-col gap-space-md">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-space-xs">
          <Ms name="history_toggle_off" className="text-primary" />
          <span className="font-headline-sm text-headline-sm text-on-surface">What changed in your plan</span>
        </div>
        <span className="font-label-badge text-label-badge text-tertiary">since last time</span>
      </div>
      <div className="flex flex-col gap-space-sm font-label-badge text-label-badge">
        {rows.length === 0 ? (
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            {delta ? "No change since the previous plan." : "This is the first plan for this goal. Changes after practice or a skill check appear here."}
          </p>
        ) : (
          rows.map((r) => (
            <div key={r.title} className={`p-space-sm rounded-lg ${r.bg} text-on-surface flex items-start gap-space-sm`}>
              <Ms name={r.icon} size={16} className={`${r.tone} shrink-0 mt-0.5`} />
              <div className="flex flex-col gap-0.5">
                <span className={`${r.tone} font-bold`}>{r.title}</span>
                <span className="font-label-annotation text-label-annotation text-on-surface-variant">{r.sub}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export type { Step };
