import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorBox, Hci, HciRibbon, Loading, Ms, Pill } from "../../components/stitch";
import { trackName } from "../../components/Shell";
import { useLearner } from "../../context/LearnerContext";
import { certainty, useTrack } from "../../context/TrackContext";
import type { AssessState, ResolveResponse, SkillEstimate } from "../../lib/api";
import { useAssessment, useResolve } from "../../lib/queries";
import { NeedGoal } from "../plan/NeedGoal";

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x));
const looksLikeCode = (s: string) => /\b(SELECT|FROM|WHERE|GROUP BY|JOIN|COUNT|SUM|AVG|df\.|import |def |=>|\(\))/.test(s);

/** Adaptive skill check - the Stitch "real-time confidence calibration" screen. */
export function AssessPage() {
  const { track } = useTrack();
  const resolved = useResolve(track.goal);
  if (!track.goal) return <NeedGoal />;
  if (resolved.isPending) return <Loading label={`Getting your skill check ready for "${track.goal}"…`} />;
  if (resolved.isError) return <ErrorBox>{resolved.error.message}</ErrorBox>;
  if (!resolved.data.assessable)
    return (
      <div className="max-w-xl mx-auto mt-space-xl p-space-lg rounded-xl bg-surface-container shadow-md flex flex-col gap-space-md">
        <h1 className="font-headline-md text-headline-md">No skill check for this goal yet</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">
          The skill check has questions for SQL, Excel, Python, pandas, statistics, data viz, Power BI, Tableau, data engineering, Git and algebra. Your plan starts from your
          chosen level and adapts as you practise.
        </p>
        <Link to="/plan" className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm w-fit">
          Go to my study plan
        </Link>
      </div>
    );
  return <Quiz resolved={resolved.data} />;
}

function Quiz({ resolved }: { resolved: ResolveResponse }) {
  const { learnerId } = useLearner();
  const { track, update } = useTrack();
  const { start, answer } = useAssessment(learnerId);
  const nav = useNavigate();
  const [state, setState] = useState<AssessState | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [flagged, setFlagged] = useState<string[]>([]);
  const names = useMemo(() => new Map(resolved.concepts.map((c) => [c.id, c.name] as const)), [resolved]);

  const key = `${learnerId}|${resolved.goals.join(",")}|${track.band}`;
  useEffect(() => {
    setState(null);
    start.mutate({ goals: resolved.goals, band: track.band, goal: track.goal }, { onSuccess: setState });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (state?.done) update({ assessment: { estimates: state.estimates, priorSd: state.prior_sd } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.done]);

  const q = state && !state.done ? state.question : null;
  const submit = useCallback(
    (response: string) => {
      if (!q || answer.isPending) return;
      setPicked(null);
      setText("");
      answer.mutate({ itemId: q.item_id, response }, { onSuccess: setState });
    },
    [q, answer],
  );

  useEffect(() => {
    if (!q) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const typing = (e.target as HTMLElement | null)?.tagName === "INPUT";
      if (e.key === "Escape") {
        e.preventDefault();
        submit("-1");
      } else if (!typing && (e.key === "f" || e.key === "F")) {
        setFlagged((f) => (f.includes(q.item_id) ? f.filter((x) => x !== q.item_id) : [...f, q.item_id]));
      } else if (!typing && q.kind === "mcq") {
        const n = Number(e.key);
        if (n >= 1 && n <= q.choices.length) {
          e.preventDefault();
          setPicked(n - 1);
        } else if (e.key === "Enter" && picked != null) {
          e.preventDefault();
          submit(String(picked));
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [q, picked, submit]);

  if (start.isError) return <ErrorBox>{start.error.message}</ErrorBox>;
  if (!state) return <Loading label="Choosing your first question…" />;

  const total = state.answered + (state.remaining ?? 0);
  const left = Math.max(0, (state.remaining ?? 0) - 1);
  const est = q ? state.estimates.find((e) => e.skill === q.skill) : undefined;
  const parent = q
    ? resolved.prerequisites.filter(([, b]) => b === q.skill).map(([a]) => a).find((a) => state.estimates.some((e) => e.skill === a))
    : undefined;
  const parentEst = parent ? state.estimates.find((e) => e.skill === parent) : undefined;

  return (
    <div className="flex flex-col w-full text-on-surface">
      <header className="w-full flex flex-col gap-space-md mb-space-lg">
        <div className="flex flex-wrap items-center justify-between gap-space-sm pb-space-xs">
          <div className="flex flex-wrap items-center gap-space-sm">
            <span className="font-label-annotation text-label-annotation tracking-wider uppercase px-2 py-0.5 rounded bg-surface-container-high text-primary font-semibold">
              Step {state.done ? 4 : 3} of 4 · {state.done ? "Building your plan" : "Answering questions"}
            </span>
            <span className="text-outline-variant font-label-badge text-label-badge">/</span>
            <div className="flex items-center gap-1.5 text-on-surface-variant font-body-sm text-body-sm">
              <span>Goal:</span>
              <span className="text-on-surface font-body-strong text-body-strong">{trackName(resolved.domain)}</span>
              <span className="font-label-badge text-label-badge text-outline capitalize">(starting at {state.band} level)</span>
            </div>
          </div>
          {!state.done && (
            <div className="flex items-center gap-space-xs px-space-md py-1 rounded-full bg-surface-container-high shadow-sm">
              <Ms name="find_replace" size={16} className="text-primary animate-pulse" />
              <span className="font-label-badge text-label-badge text-on-surface">
                Question {state.answered + 1} of ~{total}
              </span>
              <span className="text-outline text-label-badge">·</span>
              <span className="font-label-badge text-label-badge text-tertiary">
                {left === 0 ? "Last question" : `About ${left} question${left === 1 ? "" : "s"} left`}
              </span>
            </div>
          )}
        </div>
        <nav aria-label="Skill check steps" className="grid grid-cols-2 lg:grid-cols-4 gap-space-sm">
          <StepChip n="01" title="Choose a goal" state="done" />
          <StepChip n="02" title="Pick your starting level" state="done" />
          <StepChip n="03" title="Answer a few questions" state={state.done ? "done" : "active"} />
          <StepChip n="04" title="Get your plan" state={state.done ? "active" : "pending"} />
        </nav>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter items-start">
        <section className="lg:col-span-8 flex flex-col gap-space-md">
          {state.done ? (
            <article className="bg-surface-container-low rounded-xl p-space-lg shadow-md flex flex-col gap-space-md">
              <Pill tone="tertiary" icon="verified" className="w-fit">Skill check finished</Pill>
              <h1 className="font-headline-lg text-headline-lg">
                {state.band === "beginner" ? "Starting from the basics." : "Your level, measured."}
              </h1>
              <p className="font-body-md text-body-md text-on-surface-variant">
                {state.answered} question{state.answered === 1 ? "" : "s"} measured your level (you started at “{state.band}”).
                {state.style && state.style.note !== "balanced" && ` You're ${state.style.note}.`}
                {flagged.length > 0 && ` You flagged ${flagged.length} question${flagged.length === 1 ? "" : "s"} to revisit.`}
              </p>
              <button
                type="button"
                onClick={() => nav("/plan")}
                className="w-fit px-space-lg py-2.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-strong flex items-center gap-space-xs shadow-md"
              >
                See my plan <Ms name="arrow_forward" />
              </button>
            </article>
          ) : q ? (
            <article key={q.item_id} className="bg-surface-container-low rounded-xl p-space-lg shadow-md flex flex-col gap-space-md">
              <div className="flex flex-wrap items-center justify-between gap-space-xs">
                <div className="inline-flex items-center gap-space-xs px-2.5 py-1 rounded bg-primary/10 text-primary font-label-badge text-label-badge">
                  <Ms name="psychology" size={15} />
                  <span>Topic: {names.get(q.skill) ?? q.skill}</span>
                </div>
                <span className="font-label-annotation text-label-annotation text-outline uppercase tracking-wider">
                  {q.b <= -0.5 ? "Easier question" : q.b >= 0.5 ? "Harder question" : "Medium question"}
                </span>
              </div>
              <p className="font-body-lg text-body-lg text-on-surface whitespace-pre-wrap">{q.stem}</p>

              {q.kind === "mcq" ? (
                <fieldset className="flex flex-col gap-space-sm pt-2">
                  <legend className="sr-only">Select your answer for question {state.answered + 1}</legend>
                  {q.choices.map((c, i) => {
                    const on = picked === i;
                    return (
                      <label
                        key={i}
                        className={`group relative flex items-start gap-space-md p-space-md rounded-xl cursor-pointer transition-all duration-150 ${
                          on ? "bg-surface-container shadow-md ring-1 ring-primary/40 hover:bg-surface-container-high" : "bg-surface-container-low hover:bg-surface-container shadow-sm"
                        }`}
                      >
                        <input type="radio" name="answer" className="sr-only" checked={on} onChange={() => setPicked(i)} disabled={answer.isPending} />
                        <span
                          className={`flex items-center justify-center w-7 h-7 rounded-md font-code-sm text-code-sm font-bold shrink-0 transition-transform group-hover:scale-105 ${
                            on ? "bg-primary text-on-primary shadow-sm" : "bg-surface-container-highest text-on-surface-variant"
                          }`}
                        >
                          {i + 1}
                        </span>
                        <div className="flex-1 flex flex-col gap-1 min-w-0">
                          <span
                            className={`leading-relaxed ${looksLikeCode(c) ? "font-code-lg text-code-lg" : "font-body-md text-body-md"} ${
                              on ? "text-on-surface font-medium" : "text-on-surface-variant group-hover:text-on-surface"
                            }`}
                          >
                            {c}
                          </span>
                          {on && (
                            <span className="font-label-annotation text-label-annotation text-primary flex items-center gap-1">
                              <Ms name="check_circle" size={13} /> Selected · press Enter to confirm
                            </span>
                          )}
                        </div>
                        <Ms name={on ? "radio_button_checked" : "radio_button_unchecked"} size={20} className={`shrink-0 mt-0.5 ${on ? "text-primary" : "text-outline-variant group-hover:text-outline"}`} />
                      </label>
                    );
                  })}
                </fieldset>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (text.trim()) submit(text.trim());
                  }}
                >
                  <label htmlFor="answer-text" className="sr-only">
                    Your answer
                  </label>
                  <input
                    id="answer-text"
                    autoFocus
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Type your answer and press Enter"
                    className="w-full px-space-md py-3 rounded-xl bg-surface-container-lowest border border-outline-variant/40 font-code-lg text-code-lg focus:outline-none focus:border-primary"
                  />
                </form>
              )}

              <footer className="pt-space-md mt-space-sm flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-space-md">
                <div className="flex items-center gap-space-sm">
                  <button
                    type="button"
                    onClick={() => submit("-1")}
                    disabled={answer.isPending}
                    title="Record that you don't know this yet - no guessing needed"
                    className="px-space-md py-2.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant hover:text-on-surface font-body-sm text-body-sm flex items-center gap-space-xs"
                  >
                    <Ms name="visibility_off" size={16} />
                    <span>I don't know yet</span>
                    <kbd className="ml-1 px-1.5 py-0.5 rounded bg-surface-container-lowest text-outline font-label-annotation text-label-annotation">Esc</kbd>
                  </button>
                  <button
                    type="button"
                    aria-pressed={flagged.includes(q.item_id)}
                    onClick={() => setFlagged((f) => (f.includes(q.item_id) ? f.filter((x) => x !== q.item_id) : [...f, q.item_id]))}
                    className="px-space-md py-2.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant hover:text-on-surface font-body-sm text-body-sm flex items-center gap-space-xs"
                  >
                    <Ms name={flagged.includes(q.item_id) ? "bookmark" : "bookmark_border"} size={16} />
                    <span>Flag</span>
                    <kbd className="ml-1 px-1.5 py-0.5 rounded bg-surface-container-lowest text-outline font-label-annotation text-label-annotation">F</kbd>
                  </button>
                </div>
                <button
                  type="button"
                  disabled={answer.isPending || (q.kind === "mcq" ? picked == null : !text.trim())}
                  onClick={() => (q.kind === "mcq" ? picked != null && submit(String(picked)) : text.trim() && submit(text.trim()))}
                  className="px-space-lg py-2.5 rounded-lg bg-primary hover:bg-primary-fixed-dim text-on-primary font-body-strong text-body-strong flex items-center justify-center gap-space-xs shadow-md transition-all active:scale-95 disabled:opacity-40"
                >
                  <span>Next question</span>
                  <kbd className="ml-1 px-2 py-0.5 rounded bg-on-primary/20 text-on-primary font-label-annotation text-label-annotation">↵ Enter</kbd>
                </button>
              </footer>
              <div className="flex items-center justify-between pt-1 text-outline font-label-annotation text-label-annotation">
                <span>
                  Shortcuts: {q.kind === "mcq" ? "[1]–[4] select · [Enter] submit · " : "[Enter] submit · "}[Esc] I don't know yet
                </span>
                <span className="hidden sm:inline">Saying “I don't know” is fine: it's not a test</span>
              </div>
              {answer.isError && <ErrorBox>{answer.error.message}</ErrorBox>}
            </article>
          ) : null}

          {q && parent && (
            <section className="bg-surface-container-lowest/80 rounded-xl p-space-md flex items-center gap-space-md shadow-sm">
              <div className="p-2.5 rounded-lg bg-surface-container-high text-primary shrink-0">
                <Ms name="schema" size={20} />
              </div>
              <div className="flex-1 flex flex-col gap-0.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-body-strong text-body-strong text-on-surface">Comes before it: {names.get(parent) ?? parent}</span>
                  {parentEst && parentEst.n_items > 0 && (
                    <Pill tone={parentEst.confident ? "tertiary" : "neutral"}>
                      {parentEst.confident ? "Measured" : "Rough guess"}: you know {Math.round(parentEst.mastery * 100)}%
                    </Pill>
                  )}
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  {names.get(q.skill) ?? q.skill} builds on this. If this question goes badly but you know the
                  earlier topic, the gap is in {names.get(q.skill) ?? q.skill} itself.
                </p>
              </div>
            </section>
          )}
        </section>

        <aside aria-label="How sure we are" className="lg:col-span-4 flex flex-col gap-space-md">
          <div className="bg-surface-container-low rounded-xl p-space-lg shadow-md flex flex-col gap-space-md">
            <div className="flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <h2 className="font-headline-sm text-headline-sm text-on-surface tracking-tight">How sure we are about each skill</h2>
                <span className="p-1 rounded bg-surface-container-high text-primary">
                  <Ms name="show_chart" size={16} />
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-on-surface-variant font-body-sm text-body-sm">
                <span className="font-body-strong text-body-strong text-primary">How sure we are</span>
                <span className="text-outline">·</span>
                <span className="text-outline-variant font-label-annotation text-label-annotation">(Not your score)</span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant pt-1 leading-snug">
                This isn't a score. It shows how sure the app is about your level in each skill, and it
                grows with every answer, right or wrong.
              </p>
            </div>
            <div className="flex flex-col gap-space-md pt-1">
              {[...state.estimates]
                .sort((a, b) => Number(b.skill === q?.skill) - Number(a.skill === q?.skill) || b.n_items - a.n_items)
                .map((e) => (
                  <SkillMeter key={e.skill} e={e} name={names.get(e.skill) ?? e.skill} priorSd={state.prior_sd} probing={e.skill === q?.skill} done={state.done} />
                ))}
            </div>
            <div className="mt-space-xs p-space-md rounded-lg bg-surface-container-lowest flex gap-space-sm items-start">
              <Ms name="info" className="text-secondary shrink-0 mt-0.5" />
              <div className="flex flex-col gap-1">
                <span className="font-label-badge text-label-badge text-secondary uppercase font-semibold">When does it stop?</span>
                <p className="font-label-annotation text-label-annotation text-on-surface-variant leading-relaxed">
                  The app stops asking about a skill once it's sure enough about it (after at least two
                  answers) or runs out of questions for it. That's why there's no fixed number of questions.
                </p>
              </div>
            </div>
            {est && <ThetaCurve e={est} priorMean={state.prior_mean} priorSd={state.prior_sd} />}
          </div>
        </aside>
      </div>

      <HciRibbon
        title="Design notes: why the skill check works this way"
        cards={[
          { tag: "H-01", title: "Visibility of System Status", body: "Progress is the expected number of questions left, not a misleading percentage." },
          { tag: "H-07", title: "Flexibility & Efficiency", tone: "secondary", body: "Single-key shortcuts (1–4, Enter, Esc, F) let you answer without the mouse." },
          { tag: "Pedagogy", title: "Calm Confidence", tone: "tertiary", body: "Meters show how sure the model is, not a grade. Saying “I don't know yet” is better than guessing." },
          { tag: "Adaptive", title: "Most useful next question", body: "Each next question is the one that tells the app the most about your level right now." },
        ]}
      />
    </div>
  );
}

function StepChip({ n, title, state }: { n: string; title: string; state: "done" | "active" | "pending" }) {
  if (state === "active")
    return (
      <div className="relative flex items-center gap-space-sm p-space-sm rounded-lg bg-surface-container-high shadow-sm shadow-primary/20 overflow-hidden" aria-current="step">
        <div className="absolute inset-x-0 bottom-0 h-0.5 bg-primary" />
        <span className="w-6 h-6 rounded-full bg-primary text-on-primary flex items-center justify-center font-label-badge text-label-badge shrink-0 font-bold shadow-sm">{n}</span>
        <div className="min-w-0 flex flex-col">
          <span className="font-label-annotation text-label-annotation text-primary uppercase font-bold truncate">Step {n} · Now</span>
          <span className="font-body-strong text-xs text-on-surface truncate">{title}</span>
        </div>
      </div>
    );
  if (state === "done")
    return (
      <div className="flex items-center gap-space-sm p-space-sm rounded-lg bg-surface-container-low">
        <span className="w-6 h-6 rounded-full bg-tertiary/15 text-tertiary flex items-center justify-center shrink-0">
          <Ms name="check" size={14} />
        </span>
        <div className="min-w-0 flex flex-col">
          <span className="font-label-annotation text-label-annotation text-outline uppercase truncate">Step {n} · Done</span>
          <span className="font-body-strong text-xs text-on-surface truncate">{title}</span>
        </div>
      </div>
    );
  return (
    <div className="flex items-center gap-space-sm p-space-sm rounded-lg bg-surface-container-lowest/60 text-outline">
      <span className="w-6 h-6 rounded-full bg-surface-container-high text-outline flex items-center justify-center font-label-badge text-label-badge shrink-0">{n}</span>
      <div className="min-w-0 flex flex-col">
        <span className="font-label-annotation text-label-annotation text-outline uppercase truncate">Step {n} · Next</span>
        <span className="font-body-strong text-xs text-outline truncate">{title}</span>
      </div>
    </div>
  );
}

function SkillMeter({ e, name, priorSd, probing, done }: { e: SkillEstimate; name: string; priorSd: number; probing: boolean; done: boolean }) {
  const cert = Math.round(certainty(e.se, priorSd) * 100);
  const lo = sigmoid(e.theta - e.se) * 100;
  const hi = sigmoid(e.theta + e.se) * 100;
  const band = Math.round((hi - lo) / 2);
  if (probing)
    return (
      <div className="flex flex-col gap-2 p-space-sm rounded-lg bg-surface-container-high shadow-md shadow-primary/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Ms name="bolt" size={16} className="text-primary" />
            <span className="font-body-strong text-xs text-on-surface">{name}</span>
          </div>
          <span className="font-label-badge text-label-badge text-primary font-bold">{cert}% sure</span>
        </div>
        <div className="relative w-full h-2.5 rounded-full bg-surface-container-lowest overflow-hidden" aria-hidden>
          <div className="absolute left-0 top-0 bottom-0 bg-primary rounded-full transition-all duration-500" style={{ width: `${cert}%` }} />
          <div className="absolute top-0 bottom-0 bg-primary/25 rounded-full animate-pulse" style={{ left: `${lo}%`, width: `${Math.max(2, hi - lo)}%` }} />
        </div>
        <div className="flex items-center justify-between font-label-annotation text-label-annotation">
          <span className="text-primary font-semibold flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping" /> Asking about this now
          </span>
          <span className="text-on-surface-variant">You know about {Math.round(e.mastery * 100)}% (±{band}%)</span>
        </div>
      </div>
    );
  if (e.n_items === 0)
    return (
      <div className={`flex flex-col gap-1.5 p-space-sm rounded-lg bg-surface-container/30 ${done ? "opacity-50" : "opacity-80"}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Ms name={done ? "lock_outline" : "pending"} size={14} className="text-outline" />
            <span className="font-body-sm text-xs text-on-surface">{name}</span>
          </div>
          <span className="font-label-badge text-label-badge text-outline">Starting guess {Math.round(e.mastery * 100)}%</span>
        </div>
        <div className="relative w-full h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
          <div className="absolute left-0 top-0 bottom-0 bg-outline-variant/60 rounded-full" style={{ width: `${Math.round(e.mastery * 100)}%` }} />
        </div>
        <div className="flex items-center justify-between text-outline font-label-annotation text-label-annotation">
          <span>{done ? "Not asked: starting guess only" : "Coming up"}</span>
          <span>±{band}%</span>
        </div>
      </div>
    );
  return (
    <div className="flex flex-col gap-1.5 p-space-sm rounded-lg bg-surface-container/60">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Ms name={e.confident ? "verified" : "hourglass_top"} size={14} className={e.confident ? "text-tertiary" : "text-secondary"} />
          <span className="font-body-strong text-xs text-on-surface">{name}</span>
        </div>
        <span className={`font-label-badge text-label-badge ${e.confident ? "text-tertiary" : "text-secondary"}`}>{cert}% sure</span>
      </div>
      <div className="relative w-full h-2 rounded-full bg-surface-container-highest overflow-hidden">
        <div className={`absolute left-0 top-0 bottom-0 rounded-full ${e.confident ? "bg-tertiary" : "bg-secondary"}`} style={{ width: `${cert}%` }} />
      </div>
      <div className="flex items-center justify-between text-outline font-label-annotation text-label-annotation">
        <span className={e.confident ? "text-tertiary" : "text-secondary"}>{e.confident ? "Sure enough ✓" : "Still checking"}</span>
        <span>
          ±{band}% · {e.n_items} answer{e.n_items === 1 ? "" : "s"}
        </span>
      </div>
    </div>
  );
}

/** Prior (dashed) vs current posterior (filled) of θ for the skill being probed. */
function ThetaCurve({ e, priorMean, priorSd }: { e: SkillEstimate; priorMean: number; priorSd: number }) {
  const X = (t: number) => ((t + 3) / 6) * 200;
  const pdf = (t: number, m: number, s: number) => Math.exp(-0.5 * ((t - m) / s) ** 2) / s;
  const peak = Math.max(pdf(e.theta, e.theta, e.se), pdf(priorMean, priorMean, priorSd));
  const Y = (v: number) => 38 - (v / peak) * 34;
  const path = (m: number, s: number) => {
    const pts: string[] = [];
    for (let t = -3; t <= 3.0001; t += 0.1) pts.push(`${X(t).toFixed(1)},${Y(pdf(t, m, s)).toFixed(1)}`);
    return `M${pts.join(" L")}`;
  };
  return (
    <div className="p-space-sm rounded-lg bg-surface-container-lowest flex flex-col gap-1">
      <div className="flex items-center justify-between font-label-annotation text-label-annotation text-outline">
        <span>Your level: first guess (dashed) vs now</span>
        <span className="text-tertiary">{Math.round(certainty(e.se, priorSd) * 100)}% sure</span>
      </div>
      <svg aria-hidden className="w-full h-12 text-primary overflow-visible" viewBox="0 0 200 40" preserveAspectRatio="none">
        <path d={path(priorMean, priorSd)} fill="none" stroke="currentColor" strokeDasharray="3 3" strokeOpacity={0.3} strokeWidth={1.5} />
        <path d={`${path(e.theta, e.se)} L200,38 L0,38 Z`} fill="currentColor" fillOpacity={0.12} stroke="currentColor" strokeWidth={2} />
        <line x1={X(e.theta)} x2={X(e.theta)} y1={4} y2={38} stroke="#aef432" strokeOpacity={0.8} strokeWidth={1.5} />
      </svg>
      <div className="flex justify-between font-label-annotation text-label-annotation text-outline-variant px-1">
        <span>Beginner</span>
        <span className="text-secondary font-semibold">You are here</span>
        <span>Expert</span>
      </div>
      <Hci>[Method] Bayesian estimate (EAP) with a 2-parameter IRT model</Hci>
    </div>
  );
}
