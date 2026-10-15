import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { SyntropixLogo } from "../../components/SyntropixLogo";
import { Ms } from "../../components/stitch";
import { modelCertainty, useTrack } from "../../context/TrackContext";
import { api } from "../../lib/api";

const QUICK_GOALS = [
  { goal: "data analyst", label: "Data Analyst", icon: "query_stats" },
  { goal: "bi analyst", label: "BI Analyst", icon: "dashboard" },
  { goal: "analytics engineer", label: "Analytics Engineer", icon: "account_tree" },
  { goal: "data engineer", label: "Data Engineer", icon: "storage" },
  { goal: "sql", label: "SQL", icon: "database" },
  { goal: "excel", label: "Excel", icon: "grid_on" },
  { goal: "python", label: "Python", icon: "code" },
  { goal: "pandas", label: "pandas", icon: "table_view" },
  { goal: "statistics", label: "Statistics", icon: "functions" },
  { goal: "power bi", label: "Power BI", icon: "bar_chart" },
  { goal: "tableau", label: "Tableau", icon: "insert_chart" },
  { goal: "git", label: "Git", icon: "commit" },
];

interface Stage {
  title: string;
  detail: string;
  state: "waiting" | "running" | "done" | "todo";
  ms?: number;
}
interface LogLine {
  t: number;
  tag: string;
  text: string;
}

/** The opening page: the Syntropix mark, then a live start-up of your space. */
export function WelcomePage() {
  const { track, update } = useTrack();
  const nav = useNavigate();
  const t0 = useRef(performance.now());
  const [log, setLog] = useState<LogLine[]>([]);
  const [stages, setStages] = useState<Stage[]>([
    { title: "Load the skills", detail: "Reading every topic Syntropix can teach.", state: "running" },
    { title: "Connect topics in learning order", detail: "Working out what you need to learn before what.", state: "waiting" },
    { title: "Gather videos and practice", detail: "YouTube lessons, LeetCode and HackerRank problems.", state: "waiting" },
    { title: "Check your level", detail: "A short quiz so your plan skips what you already know.", state: "waiting" },
  ]);
  const [goalText, setGoalText] = useState(track.goal);
  const cert = modelCertainty(track);

  useEffect(() => {
    let alive = true;
    const say = (tag: string, text: string) =>
      alive && setLog((l) => [...l, { t: (performance.now() - t0.current) / 1000, tag, text }]);
    const set = (i: number, patch: Partial<Stage>) =>
      alive && setStages((s) => s.map((x, j) => (j === i ? { ...x, ...patch } : x)));
    const time = async <T,>(f: () => Promise<T>) => {
      const a = performance.now();
      const v = await f();
      return [v, performance.now() - a] as const;
    };
    (async () => {
      say("START", "Starting Syntropix…");
      try {
        const [h, ms] = await time(api.health);
        set(0, { state: "done", ms, detail: `${h.concepts} topics and ${h.resources} lessons ready.` });
        say("SKILLS", `Loaded ${h.concepts} topics (${ms.toFixed(0)} ms).`);
      } catch {
        set(0, { state: "todo", detail: "Can't reach the server. Is it running?" });
        say("ERROR", "Server not reachable.");
        return;
      }
      if (track.goal) {
        set(1, { state: "running" });
        try {
          const [r, ms] = await time(() => api.resolve(track.goal));
          set(1, { state: "done", ms, detail: `${r.concepts.length} topics for "${track.goal}", joined by ${r.prerequisites.length} "learn this first" links.` });
          say("MAP", `Built your skill map: ${r.concepts.length} topics, ${r.prerequisites.length} links (${ms.toFixed(0)} ms).`);
        } catch {
          set(1, { state: "todo", detail: "Couldn't build a map for that goal. Try another one below." });
        }
      } else {
        set(1, { state: "todo", detail: "Pick a goal below and your map is built for it." });
        say("MAP", "Waiting for your goal.");
      }
      set(2, { state: "running" });
      try {
        const [s, ms] = await time(api.libraryStats);
        set(2, {
          state: "done",
          ms,
          detail: `${s.videos} videos, ${s.leetcode} LeetCode + ${s.hackerrank} HackerRank problems and ${s.open_sites} open practice sets${s.harvested ? ` (collected ${s.harvested})` : ""}.`,
        });
        say("LIBRARY", `${s.videos} videos and ${s.problems} practice items across ${s.domains.length} skills (${ms.toFixed(0)} ms).`);
      } catch {
        set(2, { state: "todo", detail: "The video and problem library isn't available." });
      }
      set(3, cert == null ? { state: "todo", detail: "Not measured yet: take the 10-minute skill check." } : { state: "done", detail: `Measured: the app is ${Math.round(cert * 100)}% sure of your level.` });
      say("READY", track.goal ? "Your space is ready." : "Ready: choose a goal to begin.");
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [track.goal]);

  const choose = (goal: string) => {
    update({ goal });
    nav("/today");
  };
  const doneCount = stages.filter((s) => s.state === "done").length;

  return (
    <div className="flex flex-col gap-space-lg max-w-6xl mx-auto">
      <section className="relative overflow-hidden rounded-2xl bg-surface-container-low border border-outline-variant/30 px-space-lg py-space-xl flex flex-col items-center text-center gap-space-md">
        <div aria-hidden className="absolute inset-0 opacity-30" style={{ backgroundImage: "radial-gradient(circle at 50% 40%, rgba(148,125,255,.25), transparent 55%), linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px)", backgroundSize: "auto, 28px 28px, 28px 28px" }} />
        <span className="relative px-space-sm py-1 rounded-full bg-surface-container-high border border-outline-variant/40 font-label-badge text-label-badge text-tertiary uppercase tracking-wider">
          {cert == null ? "Your level: not measured yet" : `Your level: ${Math.round(cert * 100)}% measured`}
        </span>
        <SyntropixLogo size={260} className="relative drop-shadow-[0_0_30px_rgba(148,125,255,0.35)]" />
        <span className="relative px-space-sm py-1 rounded-full bg-tertiary/10 border border-tertiary/30 font-label-badge text-label-badge text-tertiary uppercase tracking-wider flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-tertiary animate-pulse" />
          {doneCount < stages.length ? `Getting your space ready · ${doneCount}/${stages.length}` : "Ready"}
        </span>
        <h1 className="relative font-headline-xl text-[3.25rem] leading-none tracking-[0.12em] font-bold">
          SYNTRO<span className="bg-gradient-to-r from-[#a78bfa] to-[#e879f9] bg-clip-text text-transparent">PIX</span>
        </h1>
        <p className="relative font-label-badge text-label-badge text-on-surface-variant uppercase tracking-[0.25em]">Your personal data-skills coach</p>
        <p className="relative max-w-2xl font-body-md text-body-md text-on-surface-variant">
          Learn SQL, Excel, Python, statistics, Power BI, Tableau and data engineering step by step. Syntropix builds your
          plan, plays the right videos, gives you practice that checks your answers instantly, and adjusts to how fast you learn.
        </p>
        <div className="relative flex flex-wrap justify-center gap-space-sm">
          <Link to={track.goal ? "/today" : "#goal"} className="px-space-lg py-2.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-md flex items-center gap-1.5 shadow-lg">
            {track.goal ? "Continue learning" : "Get started"} <Ms name="arrow_forward" />
          </Link>
          <Link to="/assess" className="px-space-lg py-2.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest font-body-strong text-body-md flex items-center gap-1.5">
            <Ms name="quiz" /> Take the skill check
          </Link>
        </div>
      </section>

      <section id="goal" className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
        <h2 className="font-headline-sm text-headline-sm">What do you want to become or learn?</h2>
        <div className="flex flex-wrap gap-space-xs">
          {QUICK_GOALS.map((g) => (
            <button
              key={g.goal}
              type="button"
              onClick={() => choose(g.goal)}
              aria-pressed={track.goal === g.goal}
              className={`px-space-md py-2 rounded-lg flex items-center gap-1.5 font-body-sm text-body-sm border ${track.goal === g.goal ? "bg-primary/20 border-primary text-primary" : "bg-surface-container border-outline-variant/30 hover:border-primary"}`}
            >
              <Ms name={g.icon} size={18} /> {g.label}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (goalText.trim().length > 1) choose(goalText.trim());
          }}
          className="flex gap-space-xs"
        >
          <label htmlFor="goal-text" className="sr-only">Or type your own goal</label>
          <input id="goal-text" value={goalText} onChange={(e) => setGoalText(e.target.value)} placeholder="…or type your own, e.g. “window functions” or “dbt”" className="flex-1 px-space-md py-2 rounded-lg bg-surface-container-lowest border border-outline-variant/40 font-body-sm text-body-sm focus:border-primary outline-none" />
          <button type="submit" className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm">Go</button>
        </form>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-space-lg">
        <section className="lg:col-span-3 p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Ms name="auto_awesome" className="text-primary" /> Setting up your space</h2>
            <span className="font-label-badge text-label-badge text-outline">{doneCount} of {stages.length} done</span>
          </div>
          {stages.map((s, i) => (
            <div key={s.title} className={`flex items-start gap-space-sm p-space-sm rounded-lg ${s.state === "running" ? "bg-primary/10 border-l-2 border-primary" : "bg-surface-container"}`}>
              <Ms
                name={s.state === "done" ? "check_circle" : s.state === "running" ? "progress_activity" : s.state === "todo" ? "pending" : "radio_button_unchecked"}
                className={`${s.state === "done" ? "text-tertiary" : s.state === "running" ? "text-primary animate-spin" : s.state === "todo" ? "text-secondary" : "text-outline"} mt-0.5`}
              />
              <div className="flex-1 flex flex-col">
                <span className="font-body-strong text-body-sm">Step {i + 1}: {s.title}</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">{s.detail}</span>
              </div>
              {s.ms != null && <span className="font-code-sm text-code-sm text-outline">{(s.ms / 1000).toFixed(2)}s</span>}
              {i === 3 && s.state === "todo" && (
                <Link to="/assess" className="px-space-sm py-1 rounded bg-primary text-on-primary font-label-badge text-label-badge">Start</Link>
              )}
            </div>
          ))}
        </section>

        <section className="lg:col-span-2 rounded-xl bg-[#07080c] border border-outline-variant/30 flex flex-col overflow-hidden" aria-label="Start-up log">
          <div className="flex items-center gap-space-xs px-space-md py-2 border-b border-outline-variant/20">
            <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
            <span className="ml-space-sm font-code-sm text-code-sm text-on-surface-variant">syntropix-startup.log</span>
          </div>
          <div className="p-space-md font-code-sm text-code-sm flex flex-col gap-1.5 min-h-[14rem]" aria-live="polite">
            {log.map((l, i) => (
              <div key={i} className="flex gap-space-sm">
                <span className="text-outline shrink-0">{l.t.toFixed(3)}s</span>
                <span className={`shrink-0 ${l.tag === "ERROR" ? "text-error" : l.tag === "READY" ? "text-tertiary" : "text-primary"}`}>[{l.tag}]</span>
                <span className="text-on-surface-variant">{l.text}</span>
              </div>
            ))}
            <span className="text-tertiary animate-pulse">▍</span>
          </div>
        </section>
      </div>
    </div>
  );
}
