import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Caption, ErrorBox, Hci, HciRibbon, Loading, Ms, Pill } from "../../components/stitch";
import { trackName } from "../../components/Shell";
import { useTrack } from "../../context/TrackContext";
import type { Band, GraphEdgeChange, ResolveResponse } from "../../lib/api";
import { MASTERED, practiceTarget, usePlan } from "../../lib/plan";
import { useGraphHealth } from "../../lib/queries";

const EXAMPLES = [
  "become a data analyst",
  "learn sql",
  "sql window functions",
  "pandas groupby",
  "A/B testing",
  "excel pivot tables",
  "I'm a complete beginner",
];

const BANDS: { value: Band; title: string; blurb: string; icon: string }[] = [
  { value: "beginner", title: "Beginner", blurb: "New to this. A few checks; the plan starts from the basics.", icon: "spa" },
  { value: "intermediate", title: "Intermediate", blurb: "You know some of it. The skill check finds out exactly what.", icon: "trending_up" },
  { value: "advanced", title: "Advanced", blurb: "Strong already. The check starts with harder questions to find any gaps.", icon: "rocket_launch" },
];

/** Skill Map: set the goal and see the prerequisite graph it resolves to. */
export function MapPage() {
  const { track, update } = useTrack();
  const [draft, setDraft] = useState(track.goal);
  const p = usePlan();
  const r = p.resolved;
  const nav = useNavigate();

  return (
    <div className="flex flex-col w-full gap-space-lg">
      <section className="flex flex-col gap-space-md bg-surface-container-low p-space-lg rounded-xl shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-space-md">
          <nav aria-label="Breadcrumb" className="flex items-center gap-space-xs font-label-badge text-label-badge text-outline">
            <span>Skill Map</span>
            <Ms name="chevron_right" size={12} />
            <span className="text-primary font-bold">{r.data ? trackName(r.data.domain) : "Choose a goal"}</span>
          </nav>
          <Hci>[H-06 Recognition over Recall] Examples and the graph are always in view</Hci>
        </div>
        <div>
          <h1 className="font-headline-lg text-headline-lg tracking-tight text-on-surface">Skill Map</h1>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">
            Say what you want to learn. Syntropix turns it into a map of topics, checks what you already
            know, and puts every step in an order where nothing comes before what it needs.
          </p>
        </div>
        <form
          className="flex flex-col sm:flex-row gap-space-sm"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) update({ goal: draft.trim(), assessment: null });
          }}
        >
          <label htmlFor="goal" className="sr-only">
            What do you want to learn?
          </label>
          <div className="relative flex-1">
            <Ms name="flag" className="absolute left-space-sm top-1/2 -translate-y-1/2 text-outline" />
            <input
              id="goal"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="What do you want to learn? e.g. become a data analyst"
              className="w-full pl-9 pr-space-md py-2.5 bg-surface-container-lowest border border-outline-variant/40 rounded-lg font-body-md text-body-md placeholder:text-outline focus:outline-none focus:border-primary"
            />
          </div>
          <button type="submit" disabled={!draft.trim()} className="px-space-lg py-2.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-strong disabled:opacity-40 flex items-center justify-center gap-1.5">
            Resolve Goal <Ms name="arrow_forward" size={16} />
          </button>
        </form>
        <div className="flex flex-wrap gap-space-xs">
          {EXAMPLES.map((x) => (
            <button
              key={x}
              type="button"
              onClick={() => {
                setDraft(x);
                update({ goal: x, assessment: null });
              }}
              className={`px-space-sm py-1 rounded-full font-label-badge text-label-badge ${
                track.goal === x ? "bg-primary text-on-primary" : "bg-surface-container text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
              }`}
            >
              {x}
            </button>
          ))}
        </div>
      </section>

      {!track.goal ? null : r.isPending ? (
        <Loading label={`Resolving "${track.goal}"…`} />
      ) : r.isError ? (
        <ErrorBox>Couldn't resolve "{track.goal}": {r.error.message}</ErrorBox>
      ) : r.data ? (
        <>
          <Calibrate resolved={r.data} onStart={() => nav(r.data.assessable ? "/assess" : "/plan")} />
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg items-start">
            <div className="xl:col-span-8">
              <DagView resolved={r.data} mastery={p.plan?.mastery ?? {}} />
            </div>
            <div className="xl:col-span-4 flex flex-col gap-space-md">
              <GraphStats resolved={r.data} />
              <GraphHealthCard goal={track.goal} />
            </div>
          </div>
        </>
      ) : null}

      <HciRibbon
        title="Design notes: skill map"
        cards={[
          { tag: "H-02", title: "Match the Real World", body: "Type your goal in your own words: it becomes a ready-made skill map, a job role, or a map built from Wikipedia." },
          { tag: "H-06", title: "Recognition over Recall", tone: "secondary", body: "Example goals and the whole prerequisite graph stay visible while you decide." },
          { tag: "H-10", title: "Explain Any Decision", body: "Every arrow means “learn this first”; how sure the app is about each arrow is updated from real learners' mistakes." },
          { tag: "Self-fixing", title: "The map fixes itself", tone: "tertiary", body: "Arrows that learners' results don't support are removed; missing ones are suggested." },
        ]}
      />
    </div>
  );
}

function Calibrate({ resolved, onStart }: { resolved: ResolveResponse; onStart: () => void }) {
  const { track, update } = useTrack();
  return (
    <section className="grid grid-cols-1 lg:grid-cols-12 gap-space-md p-space-lg rounded-xl bg-surface-container shadow-md">
      <div className="lg:col-span-7 flex flex-col gap-space-sm">
        <Caption>Step 2 · How much do you know already?</Caption>
        <fieldset className="grid grid-cols-1 sm:grid-cols-3 gap-space-sm">
          <legend className="sr-only">How much do you already know?</legend>
          {BANDS.map((b) => {
            const on = track.band === b.value;
            return (
              <label
                key={b.value}
                className={`flex flex-col gap-1 p-space-md rounded-xl cursor-pointer transition-all ${
                  on ? "bg-surface-container-high ring-1 ring-primary/50 shadow-md" : "bg-surface-container-low hover:bg-surface-container-high"
                }`}
              >
                <input type="radio" name="band" value={b.value} checked={on} onChange={() => update({ band: b.value })} className="sr-only" />
                <span className="flex items-center gap-1.5 font-body-strong text-body-strong">
                  <Ms name={b.icon} size={16} className={on ? "text-primary" : "text-outline"} /> {b.title}
                </span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">{b.blurb}</span>
              </label>
            );
          })}
        </fieldset>
      </div>
      <div className="lg:col-span-5 flex flex-col gap-space-sm">
        <Caption>Your time</Caption>
        <div className="grid grid-cols-2 gap-space-sm">
          <Num label="Hours a week" value={track.hoursPerWeek} min={1} max={60} step={0.5} onChange={(v) => update({ hoursPerWeek: v })} />
          <Num label="Total plan length (minutes)" value={track.budgetMinutes} min={30} max={6000} step={30} onChange={(v) => update({ budgetMinutes: v })} />
          <label className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
            Learning speed
            <select
              value={track.speed}
              onChange={(e) => update({ speed: e.target.value as typeof track.speed })}
              className="px-space-sm py-1.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm normal-case text-on-surface"
            >
              <option value="slow">Take it slow</option>
              <option value="normal">Normal</option>
              <option value="fast">Move fast</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
            Target date
            <input
              type="date"
              value={track.deadline}
              onChange={(e) => update({ deadline: e.target.value })}
              className="px-space-sm py-1 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm text-on-surface"
            />
          </label>
        </div>
        <button type="button" onClick={onStart} className="mt-space-xs w-full py-2.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-md shadow-md hover:bg-primary-fixed flex items-center justify-center gap-space-sm">
          {resolved.assessable ? "Take the skill check" : "Build my plan"} <Ms name="arrow_forward" />
        </button>
        {resolved.assessable ? (
          <Link to="/plan" className="text-center font-label-badge text-label-badge text-outline hover:text-primary">
            Skip the check and plan from your level →
          </Link>
        ) : (
          <p className="font-label-annotation text-label-annotation text-outline">
            No calibrated skill check for this graph yet: the plan starts from your level and adapts as you practise.
          </p>
        )}
      </div>
    </section>
  );
}

function Num({ label, value, min, max, step, onChange }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <label className="flex flex-col gap-1 font-label-annotation text-label-annotation text-on-surface-variant uppercase">
      {label}
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Math.min(max, Math.max(min, Number(e.target.value) || min)))}
        className="px-space-sm py-1 rounded bg-surface-container-lowest border border-outline-variant/40 font-code-sm text-code-sm text-on-surface"
      />
    </label>
  );
}

// ---------------------------------------------------------------- DAG view
function layers(resolved: ResolveResponse): Map<string, number> {
  const depth = new Map<string, number>(resolved.concepts.map((c) => [c.id, 0]));
  // longest path from the roots (the graph is small; repeat relaxation to a fixpoint)
  for (let i = 0; i < resolved.concepts.length; i++) {
    let changed = false;
    for (const [a, b] of resolved.prerequisites) {
      const d = (depth.get(a) ?? 0) + 1;
      if (d > (depth.get(b) ?? 0)) {
        depth.set(b, d);
        changed = true;
      }
    }
    if (!changed) break;
  }
  return depth;
}

function DagView({ resolved, mastery }: { resolved: ResolveResponse; mastery: Record<string, number> }) {
  const [sel, setSel] = useState<string | null>(null);
  const layout = useMemo(() => {
    const depth = layers(resolved);
    const cols = new Map<number, string[]>();
    for (const c of resolved.concepts) {
      const d = depth.get(c.id) ?? 0;
      cols.set(d, [...(cols.get(d) ?? []), c.id]);
    }
    const W = 172, H = 46, GX = 48, GY = 14;
    const pos = new Map<string, { x: number; y: number }>();
    let maxRows = 0;
    [...cols.entries()].forEach(([d, ids]) => {
      maxRows = Math.max(maxRows, ids.length);
      ids.forEach((id, i) => pos.set(id, { x: 16 + d * (W + GX), y: 16 + i * (H + GY) }));
    });
    return { pos, W, H, width: 32 + cols.size * (W + GX) - GX, height: 32 + maxRows * (H + GY) - GY };
  }, [resolved]);
  const name = new Map(resolved.concepts.map((c) => [c.id, c.name] as const));
  const goals = new Set(resolved.goals);
  const selPre = sel ? resolved.prerequisites.filter(([, b]) => b === sel).map(([a]) => a) : [];
  const selPost = sel ? resolved.prerequisites.filter(([a]) => a === sel).map(([, b]) => b) : [];
  const practice = sel ? practiceTarget(sel, resolved.source === "seed" ? resolved.domain : resolved.source) : null;

  return (
    <section className="bg-surface-container-low rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm">
        <div>
          <h2 className="font-headline-md text-headline-md text-on-surface">How the topics connect</h2>
          <Caption>{resolved.concepts.length} topics · {resolved.prerequisites.length} links · an arrow means “learn this first”</Caption>
        </div>
        <div className="flex items-center gap-space-sm flex-wrap font-label-badge text-label-badge">
          <span className="flex items-center gap-1.5 text-secondary"><span className="w-2.5 h-2.5 rounded-full bg-secondary" /> Goal</span>
          <span className="flex items-center gap-1.5 text-tertiary"><span className="w-2.5 h-2.5 rounded-full bg-tertiary" /> Known</span>
          <span className="flex items-center gap-1.5 text-primary"><span className="w-2.5 h-2.5 rounded-full bg-primary" /> In progress</span>
        </div>
      </div>
      <div className="overflow-auto rounded-lg bg-surface-container-lowest max-h-[560px]">
        <svg width={layout.width} height={layout.height} role="img" aria-label={`Prerequisite graph with ${resolved.concepts.length} concepts`}>
          <defs>
            <marker id="dag-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0 0L10 5L0 10z" fill="#484555" />
            </marker>
          </defs>
          {resolved.prerequisites.map(([a, b]) => {
            const p = layout.pos.get(a), q = layout.pos.get(b);
            if (!p || !q) return null;
            const x1 = p.x + layout.W, y1 = p.y + layout.H / 2, x2 = q.x, y2 = q.y + layout.H / 2;
            const hot = sel === a || sel === b;
            return (
              <path
                key={`${a}-${b}`}
                d={`M${x1} ${y1} C${x1 + 30} ${y1}, ${x2 - 30} ${y2}, ${x2 - 2} ${y2}`}
                fill="none"
                stroke={hot ? "#cabeff" : "#484555"}
                strokeWidth={hot ? 1.75 : 1}
                markerEnd="url(#dag-arrow)"
              />
            );
          })}
          {resolved.concepts.map((c) => {
            const p = layout.pos.get(c.id)!;
            const m = mastery[c.id] ?? 0;
            const goal = goals.has(c.id);
            const done = m >= MASTERED;
            const stroke = sel === c.id ? "#cabeff" : goal ? "#aef432" : done ? "#4de082" : "#484555";
            const label = c.name.length > 22 ? `${c.name.slice(0, 21)}…` : c.name;
            return (
              <g
                key={c.id}
                role="button"
                tabIndex={0}
                aria-label={`${c.name}, mastery ${Math.round(m * 100)}%${goal ? ", goal" : ""}`}
                onClick={() => setSel(c.id === sel ? null : c.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSel(c.id === sel ? null : c.id);
                  }
                }}
                className="cursor-pointer focus:outline-none"
              >
                <rect x={p.x} y={p.y} width={layout.W} height={layout.H} rx={6} fill="#1d1f26" stroke={stroke} strokeWidth={goal || sel === c.id ? 2 : 1} />
                <rect x={p.x} y={p.y + layout.H - 4} width={layout.W * m} height={4} rx={2} fill={done ? "#4de082" : "#cabeff"} />
                <text x={p.x + 10} y={p.y + 19} fill="#e2e2eb" fontSize={12} fontFamily="Inter">{label}</text>
                <text x={p.x + 10} y={p.y + 34} fill="#938ea1" fontSize={10} fontFamily="JetBrains Mono">
                  {goal ? "GOAL · " : ""}p={m.toFixed(2)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      {sel && (
        <div className="p-space-md rounded-lg bg-surface-container flex flex-col gap-space-xs">
          <div className="flex items-center justify-between gap-space-sm flex-wrap">
            <span className="font-headline-sm text-headline-sm">{name.get(sel)}</span>
            <span className="flex items-center gap-space-xs">
              <Pill tone={(mastery[sel] ?? 0) >= MASTERED ? "tertiary" : "primary"}>p(know) = {(mastery[sel] ?? 0).toFixed(2)}</Pill>
              {practice && (
                <Link to={`/practice?target=${encodeURIComponent(practice)}`} className="px-space-sm py-1 rounded bg-primary text-on-primary font-label-badge text-label-badge flex items-center gap-1">
                  <Ms name="terminal" size={14} /> Practise
                </Link>
              )}
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Needs first: {selPre.length ? selPre.map((c) => name.get(c)).join(", ") : "nothing — a root concept"}.
          </p>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Unlocks: {selPost.length ? selPost.map((c) => name.get(c)).join(", ") : "nothing — an end topic"}.
          </p>
        </div>
      )}
    </section>
  );
}

function GraphStats({ resolved }: { resolved: ResolveResponse }) {
  const depth = layers(resolved);
  const deepest = Math.max(0, ...depth.values()) + 1;
  const source = { seed: "Ready-made skill map", role: "Job-role map (several skills together)", dynamic: "Built from Wikipedia" }[resolved.source];
  return (
    <section className="bg-surface-container-low rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md">
      <div className="flex items-center justify-between">
        <h3 className="font-headline-sm text-headline-sm">Map summary</h3>
        <Pill tone="tertiary" icon="verified">No loops</Pill>
      </div>
      <div className="grid grid-cols-2 gap-space-sm">
        {[
          ["Topics", resolved.concepts.length],
          ["Links", resolved.prerequisites.length],
          ["Levels", deepest],
          ["Goals", resolved.goals.length],
        ].map(([k, v]) => (
          <div key={k} className="p-space-sm rounded-lg bg-surface-container-lowest flex flex-col">
            <Caption>{k}</Caption>
            <span className="font-headline-md text-headline-md">{v}</span>
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-1 font-body-sm text-body-sm text-on-surface-variant">
        <span>
          Source: <strong className="text-on-surface">{source}</strong>
        </span>
        <span>
          Goal: <strong className="text-secondary">{resolved.goals.map((g) => resolved.concepts.find((c) => c.id === g)?.name ?? g).join(", ")}</strong>
        </span>
      </div>
    </section>
  );
}

function GraphHealthCard({ goal }: { goal: string }) {
  const [run, setRun] = useState(false);
  const live = useGraphHealth(goal, true, 0);
  const exp = useGraphHealth(goal, run, 6000);
  const changes = (g: { pruned: GraphEdgeChange[]; added: GraphEdgeChange[]; suggested: GraphEdgeChange[] }) => [
    ...g.pruned.map((c) => ["remove_circle", "text-error", c.summary] as const),
    ...g.added.map((c) => ["add_circle", "text-tertiary", c.summary] as const),
    ...g.suggested.map((c) => ["help", "text-secondary", c.summary] as const),
  ];
  return (
    <section className="bg-surface-container-low rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-space-xs">
          <Ms name="healing" className="text-tertiary" />
          <h3 className="font-headline-sm text-headline-sm">Is the map right?</h3>
        </div>
        <Pill tone="tertiary">Fixes itself</Pill>
      </div>
      {live.data && (
        <div className="p-space-sm rounded-lg bg-surface-container-lowest flex flex-col gap-1 font-label-badge text-label-badge">
          <div className="flex justify-between">
            <span className="text-outline">From real practice</span>
            <span className="text-on-surface">{live.data.observations} answers · {live.data.watched} links watched</span>
          </div>
          {changes(live.data).length === 0 ? (
            <span className="text-tertiary">Nothing contradicts the map yet.</span>
          ) : (
            changes(live.data).map(([i, c, s]) => (
              <span key={s} className="flex items-start gap-1 text-on-surface-variant">
                <Ms name={i} size={14} className={c} /> {s}
              </span>
            ))
          )}
        </div>
      )}
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        Try it: we hide two real links, add two fake ones, simulate 6,000 learners, and see if the app spots both.
      </p>
      {!run ? (
        <button type="button" onClick={() => setRun(true)} className="py-2 rounded-lg bg-surface-container-high hover:bg-surface-bright font-body-strong text-body-sm flex items-center justify-center gap-1.5">
          <Ms name="science" size={16} /> Run the experiment
        </button>
      ) : exp.isPending ? (
        <Loading label="Simulating learners…" />
      ) : exp.isError ? (
        <ErrorBox>{exp.error.message}</ErrorBox>
      ) : exp.data?.recovery ? (
        <div className="flex flex-col gap-space-xs font-label-badge text-label-badge">
          <div className="grid grid-cols-2 gap-space-xs">
            <div className="p-space-sm rounded bg-surface-container-lowest">
              <Caption>Hidden links found</Caption>
              <div className="font-headline-sm text-headline-sm text-tertiary">{Math.round(exp.data.recovery.recall * 100)}%</div>
            </div>
            <div className="p-space-sm rounded bg-surface-container-lowest">
              <Caption>Fake links removed</Caption>
              <div className="font-headline-sm text-headline-sm text-tertiary">{Math.round(exp.data.recovery.precision_drop * 100)}%</div>
            </div>
          </div>
          {changes(exp.data).map(([i, c, s]) => (
            <span key={s} className="flex items-start gap-1 text-on-surface-variant">
              <Ms name={i} size={14} className={c} /> {s}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}
