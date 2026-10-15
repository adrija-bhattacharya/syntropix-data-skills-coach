import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ErrorBox, Loading, Ms, Pill } from "../../components/stitch";
import { useLearner } from "../../context/LearnerContext";
import { useTrack } from "../../context/TrackContext";
import { DIFF_TONE, SKILL_NAME, useTrackLibrary } from "../../lib/library";
import { practiceTarget } from "../../lib/plan";
import { toggle, useDone } from "../../lib/progress";
import { usePracticeTasks, useResolve } from "../../lib/queries";
import { NeedGoal } from "../plan/NeedGoal";

/** Questions interviewers ask, per skill - answer them out loud. */
const ASK: Record<string, string[]> = {
  sql: [
    "What is the difference between WHERE and HAVING?",
    "INNER JOIN vs LEFT JOIN: when does each lose or keep rows?",
    "What does NULL mean, and why does COUNT(*) differ from COUNT(column)?",
    "ROW_NUMBER vs RANK vs DENSE_RANK: what happens with ties?",
    "How would you find the second-highest salary?",
    "How do you remove duplicate rows but keep one of each?",
  ],
  spreadsheets: [
    "VLOOKUP vs XLOOKUP vs INDEX-MATCH: which do you use and why?",
    "What do the $ signs in $A$1 do?",
    "Walk me through building a pivot table from raw data.",
    "How would you clean a column of names with extra spaces and mixed case?",
  ],
  python: [
    "List vs tuple vs dictionary: when do you use each?",
    "What is a list comprehension? Write one.",
    "How do you handle an error without crashing the program?",
  ],
  python_data: [
    "How do you find and handle missing values in pandas?",
    "Explain groupby with an example.",
    "merge vs concat: what's the difference?",
    "Why is a vectorised operation faster than apply or a loop?",
  ],
  stats: [
    "Mean vs median: when is the median better?",
    "Explain a p-value to someone who isn't technical.",
    "What does a 95% confidence interval mean?",
    "Correlation vs causation: give an example.",
    "How would you design an A/B test for a new checkout button?",
  ],
  dataviz: [
    "How do you choose the right chart for your data?",
    "What makes a chart misleading?",
    "How would you design a dashboard for a busy manager?",
  ],
  powerbi: [
    "What is a star schema and why does Power BI like it?",
    "Calculated column vs measure: what's the difference?",
    "What does CALCULATE do to the filter context?",
    "Import vs DirectQuery: pros and cons?",
    "How does row-level security work?",
  ],
  tableau: [
    "Dimension vs measure: what's the difference?",
    "FIXED vs INCLUDE vs EXCLUDE LOD expressions: when do you use each?",
    "What is a table calculation?",
    "Extract vs live connection: which would you choose and why?",
  ],
  data_eng: [
    "ETL vs ELT: what changed with cloud warehouses?",
    "What makes a pipeline idempotent, and why does it matter?",
    "Explain a slowly changing dimension type 2.",
    "Batch vs streaming: when do you need streaming?",
    "How do you test data quality in a pipeline?",
  ],
  git: [
    "merge vs rebase: what's the difference?",
    "How do you resolve a merge conflict?",
    "How do you undo the last commit?",
    "What belongs in .gitignore?",
  ],
};

const CERT_TESTS = [
  { title: "HackerRank SQL (Basic) certificate test", url: "https://www.hackerrank.com/skills-verification/sql_basic", skill: "sql", level: "Easy" },
  { title: "HackerRank SQL (Intermediate) certificate test", url: "https://www.hackerrank.com/skills-verification/sql_intermediate", skill: "sql", level: "Medium" },
  { title: "HackerRank SQL (Advanced) certificate test", url: "https://www.hackerrank.com/skills-verification/sql_advanced", skill: "sql", level: "Hard" },
  { title: "HackerRank Python (Basic) certificate test", url: "https://www.hackerrank.com/skills-verification/python_basic", skill: "python", level: "Easy" },
];
const BANKS = [
  { title: "DataLemur: SQL interview questions from real companies", url: "https://datalemur.com/questions", skill: "sql" },
  { title: "Tech Interview Handbook: behavioural interview guide", url: "https://www.techinterviewhandbook.org/behavioral-interview/", skill: "" },
];

const MOCK_MINUTES = 30;

export function InterviewPage() {
  const { track } = useTrack();
  const { learnerId } = useLearner();
  const r = useResolve(track.goal);
  const { q } = useTrackLibrary();
  const done = useDone();
  const graphDomain = r.data ? (r.data.source === "seed" ? r.data.domain : r.data.source) : "sql";
  const target = r.data?.goals.map((g) => practiceTarget(g, graphDomain)).find(Boolean) ?? "";
  const tasks = usePracticeTasks(learnerId, target || "outer_join", target ? track.goal : undefined);
  const [seed, setSeed] = useState(0);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (startedAt == null) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [startedAt]);

  const mock = useMemo(() => {
    if (!tasks.data) return [];
    const pool = tasks.data.tasks.filter((t) => t.kind !== "value" || t.options.length === 0);
    const byDomain = new Map<string, typeof pool>();
    pool.forEach((t) => byDomain.set(t.domain, [...(byDomain.get(t.domain) ?? []), t]));
    let x = seed + 7;
    const rnd = () => ((x = (x * 9301 + 49297) % 233280) / 233280);
    const picks: typeof pool = [];
    const groups = [...byDomain.values()];
    for (let i = 0; picks.length < 5 && i < 40; i++) {
      const g = groups[i % groups.length]!;
      const t = g[Math.floor(rnd() * g.length)]!;
      if (!picks.includes(t)) picks.push(t);
    }
    return picks;
  }, [tasks.data, seed]);

  if (!track.goal) return <NeedGoal />;
  if (r.isPending) return <Loading label="Preparing interview practice…" />;
  if (r.isError) return <ErrorBox>{r.error.message}</ErrorBox>;
  const skills = r.data.source === "seed" ? [r.data.domain] : [...new Set(r.data.concepts.map((c) => c.id.split(".")[0] ?? ""))];
  const left = startedAt == null ? MOCK_MINUTES * 60 : Math.max(0, MOCK_MINUTES * 60 - (now - startedAt) / 1000);
  const top = q.data ? q.data.steps.flatMap((s) => s.problems).filter((p) => p.set === "SQL 50" || p.set === "30 Days of Pandas" || p.set === "10 Days of Statistics") : [];
  const interviewVideos = q.data ? q.data.courses.filter((v) => /interview/i.test(v.title)) : [];

  return (
    <div className="flex flex-col gap-space-lg">
      <header className="flex flex-col gap-space-xs">
        <h1 className="font-headline-md text-headline-md">Interview prep</h1>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
          Practise the way interviews work: a timed set of problems, the questions interviewers ask, and the problem lists
          most candidates use.
        </p>
      </header>

      <section className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
        <div className="flex flex-wrap items-center justify-between gap-space-sm">
          <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Ms name="timer" className="text-secondary" /> Mock interview: 5 problems, {MOCK_MINUTES} minutes</h2>
          <div className="flex items-center gap-space-sm">
            <span className={`font-headline-sm text-headline-sm font-code-lg ${left < 300 ? "text-error" : ""}`} aria-live="polite">
              {Math.floor(left / 60)}:{String(Math.floor(left % 60)).padStart(2, "0")}
            </span>
            <button type="button" onClick={() => setStartedAt(Date.now())} className="px-space-md py-1.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm">
              {startedAt == null ? "Start timer" : "Restart"}
            </button>
            <button type="button" onClick={() => { setSeed((s) => s + 1); setStartedAt(null); }} className="px-space-md py-1.5 rounded-lg bg-surface-container-high font-body-sm text-body-sm">
              New set
            </button>
          </div>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant">Each problem opens in the built-in practice, where your answer is run and checked instantly.</p>
        {tasks.isPending ? (
          <Loading label="Picking problems…" />
        ) : tasks.isError ? (
          <ErrorBox>{tasks.error.message}</ErrorBox>
        ) : (
          <ol className="flex flex-col gap-space-xs">
            {mock.map((t, i) => (
              <li key={t.id} className="flex items-center gap-space-sm p-space-sm rounded-lg bg-surface-container">
                <span className="font-code-sm text-code-sm text-primary w-5">{i + 1}</span>
                <span className="flex-1 min-w-0">
                  <span className="font-label-annotation text-label-annotation text-outline uppercase">{SKILL_NAME[t.domain] ?? t.domain} · {t.concept}</span>
                  <span className="block font-body-sm text-body-sm line-clamp-2">{t.prompt}</span>
                </span>
                <Link to={`/practice?target=${encodeURIComponent(target || t.concept_id)}&task=${encodeURIComponent(t.id)}`} className="px-space-sm py-1 rounded bg-primary text-on-primary font-label-badge text-label-badge shrink-0">
                  Solve
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-space-lg items-start">
        <section className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
          <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Ms name="record_voice_over" className="text-primary" /> Questions you'll be asked</h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">Answer each one out loud in under two minutes, as if to a friend.</p>
          {skills.filter((s) => ASK[s]).map((s) => (
            <details key={s} className="rounded-lg bg-surface-container" open={s === skills[0]}>
              <summary className="px-space-sm py-2 cursor-pointer font-body-strong text-body-sm">{SKILL_NAME[s] ?? s} ({ASK[s]!.length})</summary>
              <ul className="list-disc pl-8 pr-space-sm pb-space-sm font-body-sm text-body-sm flex flex-col gap-1">
                {ASK[s]!.map((a) => <li key={a}>{a}</li>)}
              </ul>
            </details>
          ))}
          <a href={BANKS[1]!.url} target="_blank" rel="noreferrer" className="font-body-sm text-body-sm text-primary hover:underline">
            Plus behaviour questions ("tell me about a time…"): how to answer with the STAR method →
          </a>
        </section>

        <section className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
          <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Ms name="workspace_premium" className="text-tertiary" /> Prove it: free certificate tests</h2>
          {CERT_TESTS.filter((c) => skills.includes(c.skill) || (c.skill === "python" && skills.includes("python_data"))).map((c) => (
            <a key={c.url} href={c.url} target="_blank" rel="noreferrer" className="flex items-center gap-space-sm p-space-sm rounded-lg bg-surface-container hover:bg-surface-container-high font-body-sm text-body-sm">
              <Ms name="verified" className="text-tertiary" /> <span className="flex-1">{c.title}</span> <Pill tone={DIFF_TONE[c.level] ?? "neutral"}>{c.level}</Pill>
            </a>
          ))}
          {BANKS.slice(0, 1).filter((b) => skills.includes(b.skill) || skills.includes("python_data")).map((b) => (
            <a key={b.url} href={b.url} target="_blank" rel="noreferrer" className="flex items-center gap-space-sm p-space-sm rounded-lg bg-surface-container hover:bg-surface-container-high font-body-sm text-body-sm">
              <Ms name="quiz" className="text-primary" /> <span className="flex-1">{b.title}</span>
            </a>
          ))}
          {interviewVideos.map((v) => (
            <Link key={v.video_id} to="/learn" className="flex items-center gap-space-sm p-space-sm rounded-lg bg-surface-container hover:bg-surface-container-high font-body-sm text-body-sm">
              <Ms name="smart_display" className="text-error" /> <span className="flex-1">Watch: {v.title}</span>
            </Link>
          ))}
        </section>
      </div>

      {top.length > 0 && (
        <section className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-xs">
          <h2 className="font-headline-sm text-headline-sm">The classic interview lists</h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">LeetCode's SQL 50 and 30 Days of Pandas, and HackerRank's 10 Days of Statistics, in the order of your plan.</p>
          {top.map((p) => (
            <div key={p.url} className="flex items-center gap-space-sm p-space-xs rounded hover:bg-surface-container font-body-sm text-body-sm">
              <input type="checkbox" checked={!!done.problems[p.url]} onChange={() => toggle("problems", p.url)} aria-label={`Mark "${p.title}" as solved`} className="w-4 h-4 accent-[#4de082]" />
              <a href={p.url} target="_blank" rel="noreferrer" className={`flex-1 truncate hover:text-primary hover:underline ${done.problems[p.url] ? "line-through text-outline" : ""}`}>{p.title}</a>
              <span className="hidden sm:inline font-label-annotation text-label-annotation text-outline">{p.set}</span>
              <Pill tone={DIFF_TONE[p.difficulty] ?? "neutral"}>{p.difficulty}</Pill>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
