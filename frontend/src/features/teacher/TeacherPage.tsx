import { useMemo, useReducer, useState, type Dispatch } from "react";

import { ParetoChart } from "../../components/ParetoChart";
import { Caption, ErrorBox, HciRibbon, Loading, Ms, Pill } from "../../components/stitch";
import type { Catalogue, Path, RecommendInput } from "../../lib/api";
import { OBJECTIVE_KEYS, OBJECTIVE_META, num } from "../../lib/format";
import { useRecommend } from "../../lib/queries";
import { constraintReducer, initialConstraints, toRecommendInput, type ConstraintAction, type ConstraintState } from "./constraintReducer";

/** For teachers: hard constraints in, Pareto front of plans out. */
export function TeacherPage({ catalogue }: { catalogue: Catalogue }) {
  const [state, dispatch] = useReducer(constraintReducer, initialConstraints, (init) => ({
    ...init,
    goals: catalogue.goals.slice(0, 1),
  }));
  const [submitted, setSubmitted] = useState(false);
  const [selected, setSelected] = useState(0);
  const input = useMemo<RecommendInput>(() => toRecommendInput(state), [state]);
  const query = useRecommend(input, submitted);
  const paths = query.data?.paths ?? [];
  const active = paths[Math.min(selected, Math.max(0, paths.length - 1))];

  return (
    <div className="flex flex-col w-full gap-space-lg">
      <div className="flex flex-col gap-space-xs bg-surface-container-low p-space-lg rounded-xl shadow-md">
        <Caption>For teachers</Caption>
        <h1 className="font-headline-lg text-headline-lg">Shape a class plan</h1>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Ban or lock resources and force an order; the solver re-plans under these hard constraints
          and returns the plans no other plan beats on every objective.
        </p>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg items-start">
        <div className="xl:col-span-4">
          <Builder catalogue={catalogue} state={state} dispatch={dispatch} busy={query.isFetching} onSolve={() => { setSubmitted(true); setSelected(0); }} />
        </div>
        <section className="xl:col-span-8 bg-surface-container-low rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md">
          <div className="flex items-center justify-between gap-space-sm flex-wrap">
            <h2 className="font-headline-md text-headline-md">Best plans to choose from</h2>
            {paths.length > 0 && <Pill tone="primary">{paths.length} non-dominated</Pill>}
          </div>
          {!submitted && <p className="font-body-sm text-body-sm text-on-surface-variant">Set your rules and press the button to see the best plans: each one is a different balance of time, learning and effort.</p>}
          {query.isFetching && <Loading label="Finding plans…" />}
          {query.isError && <ErrorBox>{query.error.message}</ErrorBox>}
          {submitted && !query.isError && !query.isFetching && paths.length === 0 && (
            <ErrorBox>{String(query.data?.meta.infeasible_reason ?? "No plan can follow all of these rules. Try relaxing one.")}</ErrorBox>
          )}
          {paths.length > 0 && active && (
            <>
              <ParetoChart paths={paths} selected={selected} onSelect={setSelected} />
              <p className="font-label-annotation text-label-annotation text-outline">Click a dot to see that plan. Bigger dot = heavier workload.</p>
              <PathDetail path={active} />
            </>
          )}
        </section>
      </div>
      <HciRibbon
        title="Design notes: teacher rules"
        cards={[
          { tag: "H-03", title: "User Control", body: "You set the rules; the planner follows them or explains why it can't." },
          { tag: "H-05", title: "Error Prevention", tone: "secondary", body: "An order that would go round in a circle is rejected straight away." },
          { tag: "H-10", title: "Explain Trade-offs", body: "You see every plan that no other plan beats on time, learning and workload all at once (the Pareto front)." },
          { tag: "Algorithm", title: "Multi-goal planning", tone: "tertiary", body: "Plans come from a dynamic program that balances several goals over the prerequisite map." },
        ]}
      />
    </div>
  );
}

function ChipGroup({ label, options, selected, onChange }: { label: string; options: { value: string; label: string }[]; selected: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="flex flex-col gap-1">
      <Caption>{label}</Caption>
      <div role="group" aria-label={label} className="flex flex-wrap gap-1 max-h-40 overflow-auto">
        {options.map((o) => {
          const on = selected.includes(o.value);
          return (
            <button
              key={o.value}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(on ? selected.filter((x) => x !== o.value) : [...selected, o.value])}
              className={`px-2 py-0.5 rounded font-label-badge text-label-badge ${on ? "bg-primary text-on-primary" : "bg-surface-container text-on-surface-variant hover:text-on-surface"}`}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Builder({ catalogue, state, dispatch, onSolve, busy }: { catalogue: Catalogue; state: ConstraintState; dispatch: Dispatch<ConstraintAction>; onSolve: () => void; busy: boolean }) {
  const concepts = catalogue.concepts.map((c) => ({ value: c.id, label: c.name }));
  const resources = catalogue.resources.map((r) => ({ value: r.id, label: r.id }));
  const sel = "px-space-sm py-1.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm flex-1";
  return (
    <form
      className="bg-surface-container rounded-xl p-space-lg shadow-md flex flex-col gap-space-md"
      onSubmit={(e) => {
        e.preventDefault();
        onSolve();
      }}
    >
      <h2 className="font-headline-sm text-headline-sm">Rules <span className="font-body-sm text-body-sm text-outline">— the plan must follow them</span></h2>
      <ChipGroup label="Goal topics" options={concepts} selected={state.goals} onChange={(goals) => dispatch({ type: "setGoals", goals })} />
      <label className="flex flex-col gap-1">
        <span className="flex justify-between"><Caption>Time budget</Caption><span className="font-code-sm text-code-sm text-secondary">{state.budgetMin} min</span></span>
        <input type="range" min={20} max={420} step={5} value={state.budgetMin} onChange={(e) => dispatch({ type: "setBudget", minutes: Number(e.target.value) })} className="accent-primary" />
      </label>
      <ChipGroup label="Never use these lessons" options={resources} selected={state.ban} onChange={(ban) => dispatch({ type: "setBan", ban })} />
      <ChipGroup label="Always include these lessons" options={resources} selected={state.lock} onChange={(lock) => dispatch({ type: "setLock", lock })} />
      <div className="flex flex-col gap-1">
        <Caption>Teach this before that</Caption>
        <div className="flex items-center gap-space-xs">
          <select aria-label="before" value={state.before} onChange={(e) => dispatch({ type: "setForce", before: e.target.value })} className={sel}>
            <option value="">—</option>
            {concepts.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
          <span className="font-label-badge text-label-badge text-outline">before</span>
          <select aria-label="after" value={state.after} onChange={(e) => dispatch({ type: "setForce", after: e.target.value })} className={sel}>
            <option value="">—</option>
            {concepts.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>
        <span className="font-label-annotation text-label-annotation text-outline">Adds a “learn this first” link; refused if it would make a loop.</span>
      </div>
      <label className="flex flex-col gap-1">
        <span className="flex justify-between"><Caption>How many plans to show</Caption><span className="font-code-sm text-code-sm text-secondary">{state.nPaths}</span></span>
        <input type="range" min={2} max={20} value={state.nPaths} onChange={(e) => dispatch({ type: "setNPaths", n: Number(e.target.value) })} className="accent-primary" />
      </label>
      <div className="flex gap-space-sm">
        <button type="submit" disabled={busy || state.goals.length === 0} className="flex-1 py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm disabled:opacity-40 flex items-center justify-center gap-1">
          <Ms name="tune" size={16} /> {busy ? "Finding plans…" : "Find the best plans"}
        </button>
        <button type="button" onClick={() => dispatch({ type: "reset" })} className="px-space-md py-2 rounded-lg bg-surface-container-high font-body-sm text-body-sm">
          Reset
        </button>
      </div>
    </form>
  );
}

function PathDetail({ path }: { path: Path }) {
  return (
    <div className="flex flex-col gap-space-sm">
      <div className="flex items-center gap-space-sm flex-wrap">
        <span className="font-headline-sm text-headline-sm">{path.steps.length} steps</span>
        <Pill tone="neutral">~{Math.round(path.total_minutes)} min</Pill>
        <Pill tone="tertiary">right order</Pill>
      </div>
      <ol className="flex flex-col gap-1">
        {path.steps.map((s, i) => (
          <li key={`${s.resource_id}-${i}`} className="flex items-center gap-space-sm p-space-sm rounded bg-surface-container-lowest font-body-sm text-body-sm">
            <span className="font-code-sm text-code-sm text-outline w-6">{i + 1}</span>
            <span className="font-code-sm text-code-sm text-on-surface">{s.resource_id}</span>
            {s.review && <Pill tone="tertiary">review</Pill>}
          </li>
        ))}
      </ol>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-space-xs">
        {OBJECTIVE_KEYS.map((k) => {
          const m = OBJECTIVE_META[k];
          return (
            <div key={k} className="p-space-sm rounded bg-surface-container-lowest flex flex-col">
              <Caption>{m.label} {m.better === "higher" ? "↑" : "↓"}</Caption>
              <span className="font-code-sm text-code-sm">{num(m.transform(path.objective[k]))}{m.unit ? ` ${m.unit}` : ""}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
