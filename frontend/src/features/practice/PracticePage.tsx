import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ErrorBox, Hci, HciRibbon, Kbd, Loading, Ms, Pill, dayLabel } from "../../components/stitch";
import { useLearner } from "../../context/LearnerContext";
import { useTrack } from "../../context/TrackContext";
import type { PracticeResult, PracticeTask, PracticeTasks } from "../../lib/api";
import { trackName } from "../../components/Shell";
import { practiceTarget } from "../../lib/plan";
import { usePracticeSubmit, usePracticeTasks, useResolve } from "../../lib/queries";
import { FixClip } from "./FixClip";

const MASTERED = 0.75;

/** Short titles for the fingerprint codes the API returns. */
const CHECK_TITLES: Record<string, string> = {
  null_equality: "Comparing with = NULL",
  aggregate_in_where: "Aggregate inside WHERE",
  having_without_group: "HAVING without GROUP BY",
  join_fanout: "Join multiplied rows before the total",
  join_duplicates: "Join repeats rows",
  duplicates: "Repeated rows",
  dropped_unmatched: "Rows without a match disappeared",
  count_star_outer: "COUNT(*) on an outer join",
  collapsed_window: "GROUP BY where a window keeps rows",
  missing_partition: "Window without PARTITION BY",
  missing_group_by: "Aggregate without GROUP BY",
  wrong_grouping: "Grouped at the wrong level",
  unfiltered: "Missing filter",
  unlimited: "Too many rows",
  wrong_direction: "Sorted the wrong way",
  wrong_order: "Right rows, wrong order",
  wrong_columns: "Wrong number of columns",
  unknown_name: "Unknown table or column",
  ambiguous_column: "Ambiguous column after a join",
  case_boundary: "CASE boundaries",
  aggregate_misuse: "Aggregate used where it can't be",
  window_misuse: "Window function used where it can't be",
  forbidden: "Only read queries are allowed",
  multiple_statements: "More than one statement",
  timeout: "Query ran too long",
  syntax: "The query didn't run",
  result_differs: "Result differs from the expected one",
  // python / pandas
  nan_equality: "Comparing with == NaN",
  series_and_or: "`and`/`or` on a Series",
  unknown_key: "Unknown column or variable",
  merge_fanout: "Merge multiplied rows",
  missing_groupby: "Aggregate without groupby",
  // excel
  no_equals: "Formula without =",
  vlookup_approx: "VLOOKUP approximate match",
  excel_error: "The formula returns an error",
  missing_anchor: "Missing $ anchor",
  // value answers
  not_a_number: "Not a number",
};

const title = (code: string) => CHECK_TITLES[code] ?? code.charAt(0).toUpperCase() + code.slice(1).replaceAll("_", " ");

/** What each kind of task is checked by, and how its editor behaves. */
const KINDS: Record<string, { engine: string; ext: string; icon: string; placeholder: string; multiline: boolean }> = {
  sql: { engine: "SQLite in-memory", ext: "sql", icon: "database", placeholder: "-- Write your query, then Ctrl+Enter\nSELECT …", multiline: true },
  python: { engine: "Python sandbox", ext: "py", icon: "terminal", placeholder: "# The shop tables are DataFrames (orders, customers, …).\n# Assign your answer to `result`, then Ctrl+Enter\nresult = …", multiline: true },
  excel: { engine: "Formula evaluator", ext: "xlsx", icon: "grid_on", placeholder: "=SUM(…)", multiline: false },
  value: { engine: "Answer check", ext: "txt", icon: "quiz", placeholder: "Your answer", multiline: false },
};
const kindOf = (t: PracticeTask) => KINDS[t.kind] ?? KINDS.sql!;

const KEYWORDS = /\b(select|from|where|group by|order by|having|limit|left join|right join|inner join|join|on|as|and|or|not|is|null|in|distinct|count|sum|avg|min|max|case|when|then|else|end|with|over|partition by|union|desc|asc)\b/gi;

/** Uppercase keywords and break before the main clauses - a light formatter. */
function format(sql: string): string {
  return sql
    .replace(KEYWORDS, (k) => k.toUpperCase())
    .replace(/\s+(FROM|WHERE|GROUP BY|HAVING|ORDER BY|LIMIT|LEFT JOIN|INNER JOIN|JOIN|UNION)\b/g, "\n$1")
    .trim();
}

export function PracticePage() {
  const { learnerId } = useLearner();
  const { track } = useTrack();
  const resolved = useResolve(track.goal);
  const [params, setParams] = useSearchParams();
  const r = resolved.data;
  const graphDomain = r ? (r.source === "seed" ? r.domain : r.source) : "sql";
  const fallback = r ? r.goals.map((g) => practiceTarget(g, graphDomain)).find(Boolean) : null;
  // practise on the track's own graph when it has tasks; else the SQL graph
  const goal = fallback || params.get("target") ? track.goal : undefined;
  const target = params.get("target") || fallback || "outer_join";
  const tasks = usePracticeTasks(learnerId, target, resolved.isLoading ? undefined : goal);

  if (resolved.isLoading || tasks.isPending) return <Loading label="Getting your practice ready…" />;
  if (tasks.isError)
    return (
      <div className="flex flex-col gap-space-sm">
        <ErrorBox>{tasks.error.message}</ErrorBox>
        {params.get("target") && (
          <button type="button" onClick={() => setParams({})} className="w-fit px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm">
            Practise toward this track's goal instead
          </button>
        )}
      </div>
    );
  return (
    <Lab
      key={`${learnerId}|${target}|${goal ?? ""}`}
      data={tasks.data}
      target={target}
      goal={goal}
      domain={r?.domain ?? "sql"}
      initialTask={params.get("task")}
      onTarget={(t) => setParams({ target: t })}
    />
  );
}

function Lab({
  data,
  target,
  goal,
  domain,
  initialTask,
  onTarget,
}: {
  data: PracticeTasks;
  target: string;
  goal?: string;
  domain: string;
  initialTask: string | null;
  onTarget: (t: string) => void;
}) {
  const { learnerId } = useLearner();
  const { track } = useTrack();
  const submit = usePracticeSubmit(learnerId);
  const byId = useMemo(() => new Map(data.tasks.map((t) => [t.id, t] as const)), [data]);
  const names = useMemo(() => new Map(data.tasks.map((t) => [t.concept_id, t.concept] as const)), [data]);
  const [taskId, setTaskId] = useState<string>(
    initialTask && data.tasks.some((t) => t.id === initialTask) ? initialTask : (data.start ?? data.tasks[0]!.id),
  );
  const [query, setQuery] = useState("");
  const [mastery, setMastery] = useState<Record<string, number>>(data.mastery);
  const [attempts, setAttempts] = useState<Record<string, number>>({});
  const [hints, setHints] = useState(0);
  const [predict, setPredict] = useState<number | null>(null);
  const [calib, setCalib] = useState<{ p: number; ok: boolean }[]>([]);
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());
  const result = submit.data;
  const task = byId.get(taskId)!;
  const path = result ? [...new Set(result.plan.steps.map((s) => s.concept_id))] : data.path;
  const repairs = new Set(result?.plan.steps.filter((s) => s.repair).map((s) => s.concept_id) ?? []);
  const m = mastery[task.concept_id] ?? 0;
  const pCorrect = result?.plan.p_correct[task.concept_id] ?? data.p_correct[task.concept_id] ?? m;

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const select = (id: string) => {
    setTaskId(id);
    setQuery("");
    setHints(0);
    setPredict(null);
    setStartedAt(Date.now());
    submit.reset();
  };

  const run = () => {
    if (!query.trim() || submit.isPending) return;
    submit.mutate(
      { task_id: task.id, query, goals: [target], goal },
      {
        onSuccess: (r) => {
          setAttempts((a) => ({ ...a, [r.task_id]: (a[r.task_id] ?? 0) + 1 }));
          setMastery((mm) => ({ ...mm, ...Object.fromEntries(Object.entries(r.mastery).map(([c, v]) => [c, v.after])) }));
          if (predict != null) setCalib((c) => [...c, { p: predict, ok: r.correct }]);
          setPredict(null);
        },
      },
    );
  };

  const left = Math.max(0, task.minutes * 60 - (now - startedAt) / 1000);
  const brier = calib.length ? calib.reduce((t, c) => t + (c.p - (c.ok ? 1 : 0)) ** 2, 0) / calib.length : null;
  const state = !result ? "IN PROGRESS" : result.correct ? "SOLVED" : "NOT YET";
  const passed = result?.checks.filter((c) => c.passed).length ?? 0;
  const top = result && !result.correct ? result.diagnoses[0] : undefined;
  const isRepair = top !== undefined && top.concept_id !== task.concept_id;
  const next = result?.next_task ? byId.get(result.next_task) : undefined;
  const kind = kindOf(task);

  return (
    <div className="flex flex-col w-full text-on-surface">
      {result?.correct && (
        <div className="mb-space-md p-space-md rounded-xl bg-tertiary-container/15 border border-tertiary/40 flex flex-wrap items-center justify-between gap-space-sm">
          <span className="flex items-center gap-space-sm font-body-strong text-body-sm text-tertiary">
            <Ms name="verified" /> Correct! {passed} of {result.checks.length} checks passed · your plan was updated
            {result.in_portfolio && (
              <Link to="/portfolio" className="underline hover:text-on-surface">· saved to your portfolio</Link>
            )}
          </span>
          {next ? (
            <button type="button" onClick={() => select(next.id)} className="px-space-md py-2 rounded-lg bg-tertiary text-on-tertiary font-body-strong text-body-sm flex items-center gap-1.5">
              Next: {next.concept} <Ms name="arrow_forward" size={16} />
            </button>
          ) : (
            <Pill tone="tertiary" icon="flag">Goal reached: {names.get(target) ?? target}</Pill>
          )}
        </div>
      )}

      <header className="flex flex-col gap-space-sm mb-space-lg">
        <div className="flex flex-wrap items-center justify-between gap-space-md">
          <div className="flex flex-wrap items-center gap-space-sm">
            <Link to="/plan" className="flex items-center gap-1 px-space-sm py-1 rounded bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant">
              <Ms name="arrow_back" size={16} />
              <span className="font-label-badge text-label-badge">Return to Study Plan</span>
            </Link>
            <span className="text-outline-variant font-code-sm text-code-sm">/</span>
            <nav aria-label="Breadcrumb" className="flex items-center gap-space-xs font-code-sm text-code-sm flex-wrap">
              <span className="text-on-surface-variant">{trackName(domain)}</span>
              <span className="text-outline">/</span>
              <span className="text-on-surface-variant">Goal: {names.get(target) ?? target}</span>
              <span className="text-outline">/</span>
              <span className="text-primary font-body-strong">{task.concept}</span>
              <Pill tone={state === "SOLVED" ? "tertiary" : state === "NOT YET" ? "error" : "warn"}>{state}</Pill>
            </nav>
          </div>
          <div className="flex items-center gap-space-sm">
            <Hci className="px-space-sm py-1 rounded bg-surface-container-high">[H-09: Error Recovery Engine Active]</Hci>
            <Link to="/map" className="px-space-sm py-1.5 rounded bg-surface-container-high hover:bg-surface-container-highest font-label-badge text-label-badge flex items-center gap-1">
              <Ms name="hub" size={15} className="text-primary" /> See skill map
            </Link>
            <button type="button" onClick={run} disabled={!query.trim() || submit.isPending} className="px-space-md py-1.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center gap-1 disabled:opacity-40">
              <Ms name="play_arrow" size={17} /> Check my answer (Ctrl+↵)
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-space-xs p-space-sm rounded-lg bg-surface-container-low">
          <Tele k="Status" v={submit.isPending ? "Checking…" : result?.result.error ? "Error" : "Ready"} tone={result?.result.error ? "text-error" : "text-tertiary"} dot />
          <Tele k="Checked by" v={`${kind.engine} · ${result ? result.result.ms.toFixed(1) : "0"}ms`} />
          <Tele k="You know this" v={`${Math.round(m * 100)}%`} tone="text-secondary" />
          <Tele k="Result" v={!result ? "Not tried yet" : result.correct ? "Correct" : isRepair ? "Fix an earlier topic" : "Try again"} tone={!result ? "text-secondary-fixed-dim" : result.correct ? "text-tertiary" : "text-error"} />
          <Tele k="Goal" v={names.get(target) ?? target} />
          <Tele k="Deadline" v={track.deadline ? dayLabel(track.deadline) : "—"} />
          <Tele k="Try" v={`Attempt ${(attempts[taskId] ?? 0) + (result?.task_id === taskId ? 0 : 1)}`} />
          <Tele k="Chance you get it" v={`${Math.round(pCorrect * 100)}% (${pCorrect >= 0.7 ? "high" : pCorrect >= 0.4 ? "medium" : "low"})`} tone="text-tertiary" />
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
        {/* LEFT */}
        <div className="lg:col-span-3 flex flex-col gap-space-md">
          <section className="flex flex-col p-space-md rounded-xl bg-surface-container-low shadow-sm">
            <div className="flex items-center justify-between pb-space-sm mb-space-sm">
              <div className="flex items-center gap-1.5">
                <Ms name="route" size={16} className="text-primary" />
                <span className="font-label-annotation text-label-annotation uppercase tracking-wider text-outline">Path to Goal</span>
              </div>
              <span className="font-code-sm text-code-sm text-on-surface-variant">{path.filter((c) => (mastery[c] ?? 0) >= MASTERED).length} of {path.length} done</span>
            </div>
            <label className="sr-only" htmlFor="target">Goal concept</label>
            <select id="target" value={target} onChange={(e) => onTarget(e.target.value)} className="mb-space-sm px-space-sm py-1.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm">
              {[...names].map(([v, l]) => (
                <option key={v} value={v}>Goal: {l}</option>
              ))}
            </select>
            <div className="flex flex-col gap-space-xs">
              {path.map((c, i) => {
                const firstTask = data.tasks.find((t) => t.concept_id === c);
                const active = c === task.concept_id;
                const done = (mastery[c] ?? 0) >= MASTERED;
                const repair = repairs.has(c) && !active;
                return (
                  <button
                    key={c}
                    type="button"
                    disabled={!firstTask}
                    aria-label={`${names.get(c) ?? c}: ${active ? "now" : repair ? "fix first" : done ? "done" : "next"}, you know ${Math.round((mastery[c] ?? 0) * 100)}%`}
                    onClick={() => firstTask && select(firstTask.id)}
                    className={`text-left p-space-sm rounded-lg flex flex-col gap-0.5 ${
                      active ? "bg-surface-container border-l-2 border-primary" : repair ? "bg-error-container/20 border-l-2 border-error" : done ? "bg-surface-container-lowest/60" : "bg-surface-container-lowest/60 opacity-80"
                    } disabled:cursor-default`}
                  >
                    <span className="flex items-center justify-between">
                      <span className={`font-label-badge text-label-badge ${active ? "text-primary" : repair ? "text-error" : done ? "text-tertiary" : "text-outline"} flex items-center gap-1`}>
                        <Ms name={active ? "radio_button_checked" : repair ? "build" : done ? "check_circle" : firstTask ? "pending" : "lock"} size={14} />
                        STEP {i + 1} · {active ? "NOW" : repair ? "FIX FIRST" : done ? "DONE" : firstTask ? "NEXT" : "LESSON"}
                      </span>
                      <span className="font-code-sm text-code-sm text-on-surface-variant">{Math.round((mastery[c] ?? 0) * 100)}%</span>
                    </span>
                    <span className="font-body-strong text-body-sm text-on-surface">{names.get(c) ?? c}</span>
                  </button>
                );
              })}
            </div>
            <label className="sr-only" htmlFor="task">All tasks</label>
            <select id="task" value={taskId} onChange={(e) => select(e.target.value)} className="mt-space-sm px-space-sm py-1.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm">
              {data.tasks.map((t) => (
                <option key={t.id} value={t.id}>{t.concept} — {t.id.replaceAll("_", " ")}</option>
              ))}
            </select>
          </section>

          {(task.kind === "sql" || task.kind === "python") && <Schema schema={data.schema} python={task.kind === "python"} env={task.env} />}
          {task.kind === "excel" && <SheetGrid sheet={data.sheet} cell={task.cell} />}

          {top && (
            <section className="flex flex-col p-space-md rounded-xl bg-error-container/20 text-on-surface shadow-sm">
              <div className="flex items-center gap-1.5 mb-space-xs text-error">
                <Ms name="warning" />
                <span className="font-label-badge text-label-badge uppercase tracking-wider font-bold">What went wrong</span>
              </div>
              <div className="font-body-strong text-body-sm text-error mb-1">{title(top.code)}</div>
              <p className="font-body-sm text-body-sm text-on-surface-variant leading-relaxed">{top.message}</p>
              <p className="font-label-annotation text-label-annotation text-on-surface-variant mt-space-sm">
                This comes from <b className="text-on-surface">{names.get(top.concept_id) ?? top.concept_id}</b>
                {isRepair ? ", an earlier topic, so a short fix-up step was added before this one." : ", the topic of this task."}
              </p>
            </section>
          )}

          <section className="flex flex-col p-space-md rounded-xl bg-surface-container-low shadow-sm">
            <div className="flex items-center justify-between mb-space-xs">
              <span className="font-label-annotation text-label-annotation uppercase text-outline">Guess before you check</span>
              {brier != null && <span className="font-label-annotation text-label-annotation px-1 rounded bg-surface-container text-tertiary">Guess score {Math.round((1 - brier) * 100)}%</span>}
            </div>
            <span className="font-body-strong text-body-sm text-on-surface mb-space-sm">Will your answer be right?</span>
            <div className="grid grid-cols-3 gap-1 mb-space-sm">
              {[
                ["Unlikely", 0.3],
                ["Maybe", 0.6],
                ["Likely", 0.88],
              ].map(([k, v]) => (
                <button
                  key={k as string}
                  type="button"
                  aria-pressed={predict === v}
                  onClick={() => setPredict(v as number)}
                  className={`py-1 px-2 rounded font-label-badge text-label-badge ${predict === v ? "bg-primary/20 text-primary font-bold" : "bg-surface-container hover:bg-surface-container-high text-on-surface-variant"}`}
                >
                  {k}
                </button>
              ))}
            </div>
            <div className="flex items-center justify-between font-label-annotation text-label-annotation text-outline">
              <span>The app's guess</span>
              <span className="font-code-sm text-code-sm text-on-surface">{Math.round(pCorrect * 100)}%</span>
            </div>
            <Hci className="mt-1">Guess score: how well your guesses match your results ({calib.length} guesses so far, Brier score)</Hci>
          </section>
        </div>

        {/* CENTRE */}
        <div className="lg:col-span-6 flex flex-col gap-space-md">
          <section className="flex flex-col p-space-lg rounded-xl bg-surface-container shadow-md">
            <div className="flex flex-wrap items-center justify-between gap-space-xs mb-space-xs">
              <div className="flex items-center gap-space-xs">
                <span className="font-label-annotation text-label-annotation px-space-xs py-0.5 rounded bg-surface-container-high text-primary font-semibold uppercase">{task.concept_id.includes(".") ? task.concept_id : `${task.domain}.${task.concept_id}`}</span>
                <span className="font-label-annotation text-label-annotation text-outline uppercase tracking-wider">{task.concept}</span>
                {task.concept_id === target && <Pill tone="secondary">Goal</Pill>}
                {task.ordered && <Pill tone="neutral">Order matters</Pill>}
              </div>
              <Hci className="px-space-xs py-0.5 rounded bg-surface-container-lowest">[HCI: DIRECT MANIPULATION]</Hci>
            </div>
            <h1 className="font-headline-sm text-headline-sm text-on-surface whitespace-pre-line">{task.prompt}</h1>
            {task.context.length > 0 && <ContextTable rows={task.context} note={task.context_note} />}
          </section>

          <section className="flex flex-col rounded-xl bg-surface-container-lowest overflow-hidden shadow-lg">
            <div className="flex items-center justify-between px-space-md py-2 bg-surface-container-low">
              <div className="flex items-center gap-space-sm">
                <span className="flex items-center gap-1.5 px-space-sm py-1 rounded bg-surface-container-lowest">
                  <Ms name={kind.icon} size={15} className="text-primary" />
                  <span className="font-code-sm text-code-sm font-semibold">{task.kind === "excel" ? `Sheet1!${task.cell}${task.fill_down ? " (fill down)" : ""}` : `${task.id}.${kind.ext}`}</span>
                </span>
                {result && <span className="font-label-annotation text-label-annotation text-tertiary">Ran in {result.result.ms.toFixed(1)} ms</span>}
              </div>
              <div className="flex items-center gap-1.5">
                {task.kind === "sql" && <button type="button" onClick={() => setQuery((q) => format(q))} disabled={!query} className="px-space-sm py-1 rounded hover:bg-surface-container-high font-label-badge text-label-badge flex items-center gap-1 disabled:opacity-40">
                  <Ms name="auto_fix_normal" size={14} /> Format
                </button>}
                <button type="button" onClick={() => setQuery("")} disabled={!query} className="px-space-sm py-1 rounded hover:bg-surface-container-high font-label-badge text-label-badge flex items-center gap-1 disabled:opacity-40">
                  <Ms name="restart_alt" size={14} /> Reset
                </button>
              </div>
            </div>
            <div className="relative p-space-md">
              <Editor task={task} value={query} onChange={setQuery} onRun={run} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-space-sm p-space-md bg-surface-container-low">
              <div className="flex items-center gap-space-sm">
                <button type="button" onClick={run} disabled={!query.trim() || submit.isPending} className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center gap-1.5 disabled:opacity-40">
                  <Ms name="verified" /> {submit.isPending ? "Running…" : "Run and check"} <span className="font-label-annotation text-label-annotation">(Ctrl+↵)</span>
                </button>
                <button type="button" onClick={() => setHints((h) => Math.min(task.hints.length, h + 1))} disabled={hints >= task.hints.length} className="px-space-md py-2 rounded-lg bg-surface-container-high hover:bg-surface-container-highest font-body-sm text-body-sm flex items-center gap-1.5 disabled:opacity-40">
                  <Ms name="lightbulb" size={16} /> Show hint {hints < task.hints.length ? hints + 1 : ""}
                </button>
              </div>
              {result && !result.result.error && (task.kind === "sql" || task.kind === "python") && (
                <div className="flex items-center gap-space-md font-label-annotation text-label-annotation text-outline">
                  <span>Rows: <strong className="text-on-surface">{result.result.rows.length}{result.result.truncated ? "+" : ""}</strong></span>
                  <span>Expected: <strong className="text-on-surface">{result.result.expected_rows}</strong></span>
                  <span>Columns: <strong className="text-on-surface">{result.result.columns.length}</strong></span>
                </div>
              )}
            </div>
            {submit.isError && <div className="p-space-md"><ErrorBox>{submit.error.message}</ErrorBox></div>}
          </section>

          {result && <Checks result={result} names={names} />}
          {result && <ResultTable result={result} kind={task.kind} />}
        </div>

        {/* RIGHT */}
        <div className="lg:col-span-3 flex flex-col gap-space-md">
          <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-xs">
            <div className="flex items-center justify-between">
              <span className="font-label-annotation text-label-annotation text-outline uppercase">Why this matters</span>
              <Hci>[H-10 Explain Decision]</Hci>
            </div>
            <span className="font-headline-sm text-headline-sm">{task.concept}</span>
            <p className="font-body-sm text-body-sm text-on-surface-variant">{task.hints[0] || "Graded by its result: any answer that produces the right output passes."}</p>
            {result && Object.entries(result.mastery).map(([c, v]) => (
              <div key={c} className="flex flex-col gap-1 pt-1">
                <div className="flex justify-between font-label-badge text-label-badge">
                  <span className="text-on-surface-variant">{v.name}</span>
                  <span className={v.after >= v.before ? "text-tertiary" : "text-error"}>{Math.round(v.before * 100)}→{Math.round(v.after * 100)}%</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
                  <div className={`h-full ${v.after >= MASTERED ? "bg-tertiary" : "bg-primary"}`} style={{ width: `${v.after * 100}%` }} />
                </div>
              </div>
            ))}
            {result?.edge_evidence.map((e) => (
              <p key={`${e.from}-${e.to}`} className="font-label-annotation text-label-annotation text-on-surface-variant">
                We're now {Math.round(e.confidence * 100)}% sure {names.get(e.from) ?? e.from} should be learned before {names.get(e.to) ?? e.to}.
              </p>
            ))}
          </section>

          {top && (
            <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-xs">
              <div className="flex items-center justify-between">
                <span className="font-label-annotation text-label-annotation text-outline uppercase">How to fix it</span>
                
              </div>
              <p className="font-body-sm text-body-sm text-on-surface">{top.message}</p>
              {isRepair && next && (
                <button type="button" onClick={() => select(next.id)} className="mt-1 py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center justify-center gap-1">
                  Fix {next.concept} first <Ms name="arrow_forward" size={16} />
                </button>
              )}
            </section>
          )}

          <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-xs">
            <div className="flex items-center justify-between">
              <span className="font-label-annotation text-label-annotation text-outline uppercase">Hints</span>
              <span className="font-label-annotation text-label-annotation text-on-surface-variant">{hints} hint{hints === 1 ? "" : "s"} used</span>
            </div>
            {task.hints.map((h, i) => (
              <div key={i} className="p-space-sm rounded-lg bg-surface-container flex flex-col gap-1">
                <span className="font-body-strong text-body-sm flex items-center justify-between">
                  {i === 0 ? "Hint 1: the idea" : `Hint ${i + 1}: the shape`}
                  {i >= hints && <Ms name="lock" size={14} className="text-outline" />}
                </span>
                {i < hints ? (
                  <span className={i === 1 ? "font-code-sm text-code-sm text-primary break-words" : "font-body-sm text-body-sm text-on-surface-variant"}>{h}</span>
                ) : (
                  <button type="button" onClick={() => setHints(i + 1)} className="text-left font-label-annotation text-label-annotation text-outline hover:text-primary">
                    Reveal
                  </button>
                )}
              </div>
            ))}
          </section>

          <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-xs">
            <span className="font-label-annotation text-label-annotation text-outline uppercase">Suggested time</span>
            <div className="flex items-baseline justify-between">
              <span className="font-headline-md text-headline-md">{Math.floor(left / 60)}:{String(Math.floor(left % 60)).padStart(2, "0")}</span>
              <span className="font-label-annotation text-label-annotation text-outline">of {Math.round(task.minutes)} minutes</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
              <div className="h-full bg-tertiary" style={{ width: `${(left / (task.minutes * 60)) * 100}%` }} />
            </div>
          </section>

          {next && !result?.correct && (
            <section className="p-space-md rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-xs">
              <span className="font-label-annotation text-label-annotation text-outline uppercase">Next Step</span>
              <span className="font-body-strong text-body-sm line-clamp-3">{next.id === task.id ? "Try this task again" : `${next.concept}: ${next.prompt}`}</span>
              <button type="button" onClick={() => select(next.id)} className="py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-bright font-body-strong text-body-sm">
                {next.id === task.id ? "Try Again" : `Next: ${next.concept}`}
              </button>
            </section>
          )}
        </div>
      </div>

      <HciRibbon
        title="Design notes: practice"
        cards={[
          { tag: "H-09", title: "Error Recovery", body: "A wrong result is traced to the concept behind it; a short repair comes first when an earlier topic is the cause." },
          { tag: "H-05", title: "Error Prevention", tone: "secondary", body: "SQL and Python run in read-only, time-boxed sandboxes; formulas run in a built-in evaluator. Nothing can change data or hang." },
          { tag: "H-01", title: "Visibility of Status", body: "Each check passes or fails on its own, and every returned row is marked as matching or extra." },
          { tag: "Pedagogy", title: "Graded Hints", tone: "tertiary", body: "Hint 1 names the idea, hint 2 shows the answer's shape without giving it away." },
        ]}
        keys={
          <>
            <span>Run: <Kbd>Ctrl</Kbd> + <Kbd>↵</Kbd></span>
            <span>Search: <Kbd>⌘K</Kbd></span>
          </>
        }
      />
    </div>
  );
}

function Tele({ k, v, tone = "text-on-surface", dot = false }: { k: string; v: string; tone?: string; dot?: boolean }) {
  return (
    <div className="flex flex-col px-space-sm py-1 rounded bg-surface-container-lowest min-w-0">
      <span className="font-label-annotation text-label-annotation text-outline uppercase tracking-wider">{k}</span>
      <span className={`flex items-center gap-1 font-code-sm text-code-sm truncate ${tone}`}>
        {dot && <span className="w-1.5 h-1.5 rounded-full bg-current shrink-0" />}
        {v}
      </span>
    </div>
  );
}

/** The answer box: a code editor, an Excel formula bar, option buttons, or a value field. */
function Editor({ task, value, onChange, onRun }: { task: PracticeTask; value: string; onChange: (v: string) => void; onRun: () => void }) {
  const kind = kindOf(task);
  const key = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey || !kind.multiline)) {
      e.preventDefault();
      onRun();
    }
  };
  if (task.kind === "value" && task.options.length)
    return (
      <div role="radiogroup" aria-label="Choose an answer" className="flex flex-col gap-space-xs">
        {task.options.map((o, i) => (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={value === o}
            onClick={() => onChange(o)}
            className={`text-left p-space-sm rounded-lg border flex items-start gap-space-sm font-body-sm text-body-sm ${
              value === o ? "border-primary bg-primary/10 text-on-surface" : "border-outline-variant/30 bg-surface-container-low hover:bg-surface-container text-on-surface-variant"
            }`}
          >
            <span className="font-code-sm text-code-sm text-primary">{String.fromCharCode(65 + i)}</span>
            <span>{o}</span>
          </button>
        ))}
      </div>
    );
  if (!kind.multiline)
    return (
      <div className="flex items-center gap-space-sm rounded-lg bg-surface-container-low px-space-sm py-2">
        <span className="font-code-sm text-code-sm text-outline shrink-0">{task.kind === "excel" ? `${task.cell}  fx` : "Answer"}</span>
        <label htmlFor="answer" className="sr-only">{task.kind === "excel" ? `Formula for ${task.cell}` : "Your answer"}</label>
        <input
          id="answer"
          spellCheck={false}
          autoComplete="off"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={key}
          placeholder={kind.placeholder}
          className="flex-1 min-w-0 bg-transparent font-code-lg text-code-lg text-on-surface focus:outline-none placeholder:text-outline-variant"
        />
      </div>
    );
  return (
    <>
      <label htmlFor="sql" className="sr-only">{task.kind === "python" ? "Your Python" : "Your SQL"}</label>
      <textarea
        id="sql"
        rows={10}
        spellCheck={false}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (task.kind === "python" && e.key === "Tab") {
            e.preventDefault();
            const t = e.currentTarget;
            const at = t.selectionStart;
            onChange(value.slice(0, at) + "    " + value.slice(t.selectionEnd));
            requestAnimationFrame(() => t.setSelectionRange(at + 4, at + 4));
            return;
          }
          key(e);
        }}
        placeholder={kind.placeholder}
        className="w-full bg-transparent font-code-lg text-code-lg text-on-surface resize-y focus:outline-none placeholder:text-outline-variant"
      />
    </>
  );
}

/** The practice workbook: column letters, row numbers, the target cell marked. */
function SheetGrid({ sheet, cell }: { sheet: string[][]; cell: string }) {
  const cols = "ABCDEFGHI";
  return (
    <section className="flex flex-col p-space-md rounded-xl bg-surface-container-low shadow-sm">
      <div className="flex items-center gap-1.5 mb-space-sm">
        <Ms name="grid_on" size={16} className="text-tertiary" />
        <span className="font-label-annotation text-label-annotation uppercase tracking-wider text-outline">Sheet1</span>
      </div>
      <div className="overflow-x-auto">
        <table className="font-code-sm text-[11px] border-collapse">
          <thead>
            <tr>
              <th className="px-1 text-outline" />
              {cols.split("").map((c) => (
                <th key={c} scope="col" className="px-1.5 py-0.5 text-outline font-normal bg-surface-container">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sheet.map((row, r) => (
              <tr key={r}>
                <th scope="row" className="px-1 text-outline font-normal bg-surface-container">{r + 1}</th>
                {row.map((v, c) => {
                  const ref = `${cols[c]}${r + 1}`;
                  return (
                    <td
                      key={c}
                      title={ref}
                      className={`px-1.5 py-0.5 border border-outline-variant/20 whitespace-pre ${
                        ref === cell ? "outline outline-2 outline-primary bg-primary/10" : r === 0 ? "font-bold text-on-surface" : "text-on-surface-variant"
                      }`}
                    >
                      {v}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {cell && <Hci className="mt-space-xs">Your formula goes in {cell} (outlined).</Hci>}
    </section>
  );
}

/** A small table the question is about (value tasks). */
function ContextTable({ rows, note }: { rows: string[][]; note: string }) {
  const [head, ...body] = rows;
  return (
    <div className="mt-space-sm flex flex-col gap-1">
      <div className="overflow-x-auto rounded-lg bg-surface-container-lowest">
        <table className="w-full text-left font-code-sm text-code-sm">
          <thead className="text-outline font-label-annotation uppercase tracking-wider">
            <tr>{head?.map((h, i) => <th key={i} scope="col" className="p-2">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-surface-container/40">
            {body.map((r, i) => (
              <tr key={i}>{r.map((v, j) => <td key={j} className="p-2 text-on-surface">{v}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {note && <p className="font-label-annotation text-label-annotation text-on-surface-variant">{note}</p>}
    </div>
  );
}

function Schema({ schema, python = false, env = {} }: { schema: PracticeTasks["schema"]; python?: boolean; env?: Record<string, string> }) {
  const nullable = Object.entries(schema).flatMap(([t, d]) => d.columns.filter((c) => c.nulls > 0).map((c) => `${t}.${c.name} (${c.nulls})`));
  return (
    <section className="flex flex-col p-space-md rounded-xl bg-surface-container-low shadow-sm">
      {Object.keys(env).length > 0 && (
        <div className="mb-space-sm flex flex-col gap-1">
          <span className="font-label-annotation text-label-annotation uppercase tracking-wider text-outline">Variables in scope</span>
          {Object.entries(env).map(([k, v]) => (
            <code key={k} className="font-code-sm text-code-sm px-space-xs py-0.5 rounded bg-surface-container-lowest break-all">
              <span className="text-primary">{k}</span> = {v}
            </code>
          ))}
        </div>
      )}
      <div className="flex items-center justify-between mb-space-sm">
        <div className="flex items-center gap-1.5">
          <Ms name={python ? "table_view" : "database"} size={16} className="text-tertiary" />
          <span className="font-label-annotation text-label-annotation uppercase tracking-wider text-outline">{python ? "DataFrames you can use" : "Tables you can use"}</span>
        </div>
        <span className="font-code-sm text-code-sm text-tertiary">{Object.values(schema).reduce((t, d) => t + d.rows, 0)} rows</span>
      </div>
      <div className="flex flex-col gap-space-sm">
        {Object.entries(schema).map(([table, d]) => (
          <details key={table} className="rounded bg-surface-container-lowest" open={table === "customers"}>
            <summary className="px-space-sm py-1 font-code-sm text-code-sm text-primary font-semibold cursor-pointer flex justify-between">
              {table} <span className="text-outline font-normal">{d.rows} rows</span>
            </summary>
            <div className="flex flex-col gap-1 p-space-xs font-code-sm text-code-sm">
              {d.columns.map((c) => (
                <div key={c.name} className="flex items-center justify-between px-space-xs py-0.5 rounded bg-surface-container/50">
                  <span className="flex items-center gap-1">
                    <span className="text-on-surface">{c.name}</span>
                    {c.nulls > 0 && <span className="text-secondary-fixed-dim font-label-annotation text-[9px] uppercase">[{c.nulls} NULL]</span>}
                  </span>
                  <span className="text-outline text-label-annotation">{c.type}{c.pk ? " [PK]" : ""}</span>
                </div>
              ))}
            </div>
          </details>
        ))}
      </div>
      {nullable.length > 0 && (
        <div className="mt-space-sm p-space-sm rounded bg-secondary-container/10 text-secondary-fixed-dim font-label-annotation text-label-annotation leading-relaxed">
          <strong className="font-bold">NULL notice:</strong> {nullable.join(", ")} hold {python ? "NaN/None" : "NULLs"}. {python ? "Use .isna(), and remember .count() skips them." : "Use IS NULL, and remember COUNT(column) skips them."}
        </div>
      )}
    </section>
  );
}

function Checks({ result, names }: { result: PracticeResult; names: Map<string, string> }) {
  const passed = result.checks.filter((c) => c.passed).length;
  return (
    <section className="flex flex-col p-space-md rounded-xl bg-surface-container-low shadow-sm" aria-live="polite">
      <div className="flex items-center justify-between mb-space-sm">
        <div className="flex items-center gap-space-xs">
          <Ms name="checklist" className={result.correct ? "text-tertiary" : "text-secondary-fixed-dim"} />
          <span className="font-body-strong text-body-sm">Checks</span>
          <Pill tone={result.correct ? "tertiary" : "error"}>{result.correct ? "Correct" : "Not yet"}</Pill>
        </div>
        <span className={`font-label-badge text-label-badge px-space-xs py-0.5 rounded bg-surface-container-high ${result.correct ? "text-tertiary" : "text-secondary-fixed-dim"}`}>
          {passed} of {result.checks.length} passed
        </span>
      </div>
      <div className="flex flex-col gap-space-xs">
        {result.checks.map((c) => (
          <div key={c.id} className="flex items-start gap-space-sm p-space-sm rounded-lg bg-surface-container-lowest">
            <Ms name={c.passed ? "check_circle" : "cancel"} className={`${c.passed ? "text-tertiary" : "text-error"} mt-0.5`} />
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className={`font-code-sm text-code-sm font-semibold ${c.passed ? "text-tertiary" : "text-error"}`}>{c.label}</span>
                <span className={`font-label-annotation text-label-annotation uppercase ${c.passed ? "text-tertiary" : "text-error"}`}>{c.passed ? "PASS" : "FAIL"}</span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">{c.detail}</p>
            </div>
          </div>
        ))}
        {!result.correct &&
          result.diagnoses.map((d) => (
            <div key={d.code} className="flex items-start gap-space-sm p-space-sm rounded-lg bg-error-container/15">
              <Ms name="troubleshoot" className="text-error mt-0.5" />
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <span className="font-code-sm text-code-sm text-error font-semibold">Likely mistake: {title(d.code)}</span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">{d.message}</p>
                <p className="font-label-annotation text-label-annotation text-outline mt-0.5">
                  Topic to fix: <b className="text-on-surface">{names.get(d.concept_id) ?? d.concept_id}</b>
                </p>
              </div>
            </div>
          ))}
        {!result.correct && result.fix_clip && <FixClip clip={result.fix_clip} />}
      </div>
    </section>
  );
}

function ResultTable({ result, kind }: { result: PracticeResult; kind: string }) {
  const r = result.result;
  const rows = kind === "sql" || kind === "python";
  if (r.error) return <pre className="p-space-md rounded-xl bg-error-container/20 text-error font-code-sm text-code-sm whitespace-pre-wrap">{r.error}</pre>;
  if (!r.columns.length) return null;
  return (
    <section className="flex flex-col p-space-md rounded-xl bg-surface-container-low shadow-sm">
      <div className="flex items-center justify-between mb-space-sm">
        <div className="flex items-center gap-space-xs">
          <Ms name="table_chart" className="text-primary" />
          <span className="font-body-strong text-body-sm">Your Result</span>
        </div>
        <span className="font-label-annotation text-label-annotation text-outline uppercase tracking-wider">
          {rows ? `${r.row_status.filter((s) => s === "ok").length} matching · ${r.row_status.filter((s) => s === "extra").length} extra · ${r.missing_rows} missing` : result.correct ? "correct" : "not the expected value"}
        </span>
      </div>
      <div className="overflow-x-auto max-h-80">
        <table className="w-full text-left font-code-sm text-code-sm">
          <thead className="bg-surface-container-lowest text-outline font-label-annotation uppercase tracking-wider sticky top-0">
            <tr>
              {r.columns.map((c, i) => (
                <th key={`${c}-${i}`} scope="col" className="p-2">{c}</th>
              ))}
              <th scope="col" className="p-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-container/40">
            {r.rows.map((row, i) => (
              <tr key={i} className={r.row_status[i] === "extra" ? "bg-error-container/10" : ""}>
                {row.map((v, j) => (
                  <td key={j} className={`p-2 ${v === null ? "text-secondary-fixed-dim italic" : "text-on-surface"}`}>{v === null ? "NULL" : String(v)}</td>
                ))}
                <td className="p-2">
                  {r.row_status[i] === "ok" ? <Pill tone="tertiary">RIGHT</Pill> : <Pill tone="error">{rows ? "EXTRA" : "WRONG"}</Pill>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows && r.missing_rows > 0 && (
        <p className="mt-space-sm font-label-annotation text-label-annotation text-error">
          {r.missing_rows} expected row{r.missing_rows === 1 ? " is" : "s are"} missing from your result.
        </p>
      )}
    </section>
  );
}

export type { PracticeTask };
