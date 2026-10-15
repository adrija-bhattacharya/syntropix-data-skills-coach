import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";

import { useLearner } from "../context/LearnerContext";
import { modelCertainty, useTrack } from "../context/TrackContext";
import { api, latencyStore } from "../lib/api";
import { useResolve } from "../lib/queries";
import { IntroSplash } from "./IntroSplash";
import { Kbd, Ms } from "./stitch";
import { SyntropixLogo } from "./SyntropixLogo";

export const NAV: { to: string; icon: string; label: string; match: string[] }[] = [
  { to: "/today", icon: "today", label: "Today", match: ["/today"] },
  { to: "/roadmap", icon: "route", label: "Roadmap", match: ["/roadmap", "/plan", "/session"] },
  { to: "/map", icon: "hub", label: "Skill Map", match: ["/map"] },
  { to: "/learn", icon: "smart_display", label: "Learn (Videos)", match: ["/learn"] },
  { to: "/practice", icon: "code", label: "Practice", match: ["/practice"] },
  { to: "/projects", icon: "folder_special", label: "Projects", match: ["/projects"] },
  { to: "/portfolio", icon: "badge", label: "Portfolio", match: ["/portfolio"] },
  { to: "/interview", icon: "record_voice_over", label: "Interview Prep", match: ["/interview"] },
  { to: "/certifications", icon: "workspace_premium", label: "Certifications", match: ["/certifications"] },
  { to: "/progress", icon: "trending_up", label: "Progress", match: ["/progress"] },
  { to: "/calendar", icon: "calendar_month", label: "Calendar", match: ["/calendar"] },
];
const MORE: { to: string; icon: string; label: string }[] = [
  { to: "/assess", icon: "quiz", label: "Skill check" },
  { to: "/teacher", icon: "school", label: "For teachers" },
];

function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000, retry: 0 });
}

export function Shell({ children }: { children: ReactNode }) {
  const [palette, setPalette] = useState(false);
  const [explain, setExplain] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((v) => !v);
      } else if (e.key === "Escape") {
        setPalette(false);
        setExplain(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="min-h-screen bg-surface-container-lowest text-on-surface">
      <IntroSplash />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:z-[60] focus:top-2 focus:left-2 focus:px-3 focus:py-2 focus:rounded focus:bg-primary focus:text-on-primary"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="lg:pl-64">
        <TopBar onSearch={() => setPalette(true)} />
        <main id="main" className="relative pt-24 lg:pt-20 pb-24 lg:pb-14 min-h-screen w-full px-space-md lg:px-space-lg">
          {children}
        </main>
        <Footer onExplain={() => setExplain(true)} />
      </div>
      {palette && <Palette onClose={() => setPalette(false)} />}
      {explain && <ExplainNumbers onClose={() => setExplain(false)} />}
    </div>
  );
}

function Sidebar() {
  const { track } = useTrack();
  const { pathname } = useLocation();
  const health = useHealth();
  const cert = modelCertainty(track);
  const active = (m: string[]) => m.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const item = (on: boolean) =>
    `flex flex-col lg:flex-row items-center gap-1 lg:gap-space-sm px-space-sm lg:px-space-md py-space-sm rounded-lg transition-all font-body-sm text-[11px] lg:text-body-sm min-h-[44px] shrink-0 ${
      on ? "bg-surface-container-high text-primary font-bold lg:border-l-2 lg:border-primary" : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
    }`;

  return (
    <aside className="fixed z-50 bg-surface-container-low border-outline-variant/30 flex lg:flex-col lg:left-0 lg:top-0 lg:h-full lg:w-64 lg:border-r lg:pt-4 lg:pb-4 inset-x-0 bottom-0 border-t lg:border-t-0 lg:inset-x-auto lg:bottom-auto">
      <Link to="/" aria-label="Syntropix home" className="hidden lg:flex px-space-lg mb-space-lg items-center gap-space-sm">
        <SyntropixLogo size={36} animated={false} />
        <span className="flex-1 font-headline-sm text-headline-sm text-on-surface tracking-wide">
          SYNTRO<span className="text-primary">PIX</span>
        </span>
        {health.data && (
          <span className="font-label-annotation text-label-annotation px-1.5 py-0.5 rounded bg-surface-container-highest text-on-surface-variant">
            v{health.data.version}
          </span>
        )}
      </Link>
      <nav aria-label="Main" className="flex-1 flex lg:flex-col justify-start overflow-x-auto lg:overflow-visible px-space-xs lg:px-space-sm gap-0.5">
        {NAV.map((n) => {
          const on = active(n.match);
          return (
            <NavLink key={n.to} to={n.to} aria-current={on ? "page" : undefined} className={item(on)}>
              <Ms name={n.icon} />
              <span className="text-center lg:text-left whitespace-nowrap">{n.label}</span>
            </NavLink>
          );
        })}
        <div className="hidden lg:block mt-space-md mb-space-xs px-space-md">
          <span className="font-label-annotation text-label-annotation text-outline uppercase tracking-wider">More</span>
        </div>
        {MORE.map((n) => {
          const on = active([n.to]);
          return (
            <NavLink key={n.to} to={n.to} aria-current={on ? "page" : undefined} className={item(on)}>
              <Ms name={n.icon} />
              <span className="text-center lg:text-left whitespace-nowrap">{n.label}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="hidden lg:flex px-space-md pt-space-md border-t border-outline-variant/20 flex-col gap-space-xs">
        <div className="flex items-center justify-between text-on-surface-variant font-label-badge text-label-badge">
          <span>How sure we are of your level</span>
          <span className="text-tertiary">{cert == null ? "—" : `${Math.round(cert * 100)}%`}</span>
        </div>
        <div className="w-full bg-surface-container-highest h-1 rounded-full overflow-hidden">
          <div className="bg-tertiary h-full" style={{ width: `${Math.round((cert ?? 0) * 100)}%` }} />
        </div>
        {cert == null && (
          <Link to="/assess" className="font-label-annotation text-label-annotation text-outline hover:text-primary">
            Take the skill check to find out →
          </Link>
        )}
      </div>
    </aside>
  );
}

function TopBar({ onSearch }: { onSearch: () => void }) {
  const { track, update } = useTrack();
  const health = useHealth();
  const resolved = useResolve(track.goal);
  const online = health.isSuccess;

  return (
    <header className="fixed top-0 left-0 lg:left-64 right-0 z-40 bg-surface-container-low/95 backdrop-blur-md border-b border-outline-variant/30">
      <div className="h-6 px-space-lg bg-surface-container-lowest/80 border-b border-outline-variant/20 flex items-center justify-between font-label-annotation text-label-annotation text-on-surface-variant">
        <span className="truncate">
          Syntropix {health.data ? `v${health.data.version}` : ""} · your data-skills coach
          {resolved.data ? ` · ${resolved.data.concepts.length} topics on your map` : ""}
        </span>
        <span className={`flex items-center gap-space-xs ${online ? "text-tertiary" : "text-error"}`}>
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${online ? "bg-tertiary animate-pulse" : "bg-error"}`} />
          {online ? "Connected" : health.isPending ? "Connecting…" : "Offline: start the server"}
        </span>
      </div>
      <div className="h-14 px-space-md lg:px-space-lg flex items-center justify-between gap-space-md">
        <button
          type="button"
          onClick={onSearch}
          aria-label="Search pages and commands (Ctrl K)"
          className="relative flex-1 max-w-xl flex items-center pl-8 pr-14 py-1.5 bg-surface-container-lowest border border-outline-variant/40 rounded text-outline font-body-sm text-body-sm hover:border-primary text-left"
        >
          <Ms name="search" className="absolute left-space-sm top-1/2 -translate-y-1/2 text-outline" />
          Search pages… (Ctrl K)
          <span className="absolute right-space-sm top-1/2 -translate-y-1/2 font-label-badge text-label-badge px-1.5 py-0.5 rounded bg-surface-container-highest text-on-surface-variant border border-outline-variant/40">
            ⌘K
          </span>
        </button>
        <div className="flex items-center gap-space-md shrink-0">
          {resolved.data && (
            <Link
              to="/map"
              aria-label="Your goal: open the Skill Map"
              className="hidden md:flex items-center gap-space-xs px-space-sm py-1 rounded bg-secondary-container/10 border border-secondary-container/30 text-secondary font-label-badge text-label-badge"
            >
              <Ms name="flag" size={14} />
              <span>
                Goal: {trackName(resolved.data.domain)}
              </span>
            </Link>
          )}
          <button
            type="button"
            aria-pressed={track.hci}
            onClick={() => update({ hci: !track.hci })}
            className="hidden sm:flex items-center gap-space-xs px-space-sm py-1 rounded bg-surface-container-high border border-outline-variant/30 text-on-surface-variant font-label-annotation text-label-annotation hover:text-on-surface"
          >
            <Ms name={track.hci ? "toggle_on" : "toggle_off"} size={14} className={track.hci ? "text-tertiary" : ""} />
            <span>Design notes: {track.hci ? "on" : "off"}</span>
          </button>
          <LearnerMenu />
        </div>
      </div>
    </header>
  );
}

export function trackName(domain: string): string {
  const names: Record<string, string> = {
    sql: "SQL Analytics",
    python: "Python",
    python_data: "pandas & NumPy",
    stats: "Statistics",
    dataviz: "Data Visualisation",
    dsa_python: "DSA in Python",
    spreadsheets: "Spreadsheets",
    git: "Git",
    powerbi: "Power BI",
    tableau: "Tableau",
    data_eng: "Data Engineering",
    foundations: "Foundations",
    algebra: "Algebra",
  };
  return names[domain] ?? domain.replace(/\b\w/g, (c) => c.toUpperCase());
}

function LearnerMenu() {
  const { learnerId, setLearnerId } = useLearner();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(learnerId);
  return (
    <div className="relative">
      <button
        type="button"
        aria-label={`Learner: ${learnerId}`}
        aria-expanded={open}
        onClick={() => {
          setDraft(learnerId);
          setOpen((v) => !v);
        }}
        className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-on-primary"
      >
        <Ms name="person" />
      </button>
      {open && (
        <form
          className="absolute right-0 top-10 w-64 p-space-md rounded-xl bg-surface-container-high shadow-xl flex flex-col gap-space-sm"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) setLearnerId(draft.trim());
            setOpen(false);
          }}
        >
          <label className="font-label-annotation text-label-annotation text-on-surface-variant uppercase" htmlFor="learner-id">
            Your name or ID
          </label>
          <input
            id="learner-id"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="px-space-sm py-1.5 rounded bg-surface-container-lowest border border-outline-variant/40 font-code-sm text-code-sm focus:outline-none focus:border-primary"
          />
          <p className="font-label-annotation text-label-annotation text-outline">
            Each name keeps its own progress and plan, so a family can share one computer.
          </p>
          <button type="submit" className="py-1.5 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm">
            Switch
          </button>
        </form>
      )}
    </div>
  );
}

function Footer({ onExplain }: { onExplain: () => void }) {
  const latency = useSyncExternalStore(latencyStore.subscribe, latencyStore.get);
  const health = useHealth();
  return (
    <footer className="hidden lg:flex fixed bottom-0 left-64 right-0 h-8 bg-surface-container-low/95 backdrop-blur-md border-t border-outline-variant/30 px-space-lg z-40 items-center justify-between font-label-badge text-label-badge text-on-surface-variant">
      <div className="flex items-center gap-space-lg">
        <span className="flex items-center gap-space-xs">
          <Ms name="sync" size={14} className={health.isSuccess ? "text-tertiary" : "text-error"} />
          {health.isSuccess ? "Saved and up to date" : "Offline"}
        </span>
        <span className="flex items-center gap-space-xs">
          <Ms name="speed" size={14} className="text-primary" />
          Response time: {latency == null ? "—" : `${latency} ms`}
        </span>
        <button type="button" onClick={onExplain} className="hover:text-primary cursor-help underline decoration-dotted">
          What do these numbers mean?
        </button>
      </div>
      <div className="flex items-center gap-space-md text-outline font-label-annotation text-label-annotation">
        <span>Keyboard:</span>
        <span>
          <Kbd>⌘K</Kbd> Search
        </span>
        <span>
          <Kbd>Ctrl+↵</Kbd> Run
        </span>
        <span>
          <Kbd>1-4</Kbd> Answer
        </span>
      </div>
    </footer>
  );
}

const COMMANDS: { label: string; hint: string; to: string }[] = [
  { label: "Home", hint: "the opening page", to: "/" },
  { label: "Today", hint: "what to do now", to: "/today" },
  { label: "Roadmap", hint: "your path, phase by phase", to: "/roadmap" },
  { label: "Study plan", hint: "sessions and steps", to: "/plan" },
  { label: "Skill Map", hint: "set a goal, see how topics connect", to: "/map" },
  { label: "Learn (Videos)", hint: "videos in the right order", to: "/learn" },
  { label: "Practice", hint: "built-in practice that checks your answer", to: "/practice" },
  { label: "Problem sets", hint: "LeetCode, HackerRank and more", to: "/practice?tab=sets" },
  { label: "Projects", hint: "portfolio projects on real data", to: "/projects" },
  { label: "Portfolio", hint: "your verified work, ready for recruiters", to: "/portfolio" },
  { label: "Interview Prep", hint: "mock interview and questions", to: "/interview" },
  { label: "Certifications", hint: "badges and exams", to: "/certifications" },
  { label: "Progress", hint: "what you know so far", to: "/progress" },
  { label: "Calendar", hint: "sessions on your calendar", to: "/calendar" },
  { label: "Skill check", hint: "10-minute quiz", to: "/assess" },
  { label: "For teachers", hint: "shape a class plan", to: "/teacher" },
];

function Palette({ onClose }: { onClose: () => void }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => input.current?.focus(), []);
  const list = COMMANDS.filter((c) => `${c.label} ${c.hint}`.toLowerCase().includes(q.toLowerCase()));
  const go = (to: string) => {
    nav(to);
    onClose();
  };
  return (
    <div className="fixed inset-0 z-[70] bg-black/60 flex items-start justify-center pt-[12vh]" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-label="Command palette"
        className="w-[min(560px,92vw)] rounded-xl bg-surface-container-high shadow-2xl overflow-hidden"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-space-sm px-space-md border-b border-outline-variant/30">
          <Ms name="search" className="text-outline" />
          <input
            ref={input}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setSel(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") setSel((s) => Math.min(s + 1, list.length - 1));
              else if (e.key === "ArrowUp") setSel((s) => Math.max(s - 1, 0));
              else if (e.key === "Enter" && list[sel]) go(list[sel].to);
            }}
            placeholder="Jump to…"
            aria-label="Search pages"
            className="flex-1 bg-transparent py-3 font-body-md text-body-md focus:outline-none"
          />
          <Kbd>Esc</Kbd>
        </div>
        <ul className="max-h-80 overflow-auto p-space-xs">
          {list.map((c, i) => (
            <li key={c.to}>
              <button
                type="button"
                onMouseEnter={() => setSel(i)}
                onClick={() => go(c.to)}
                className={`w-full flex items-center justify-between px-space-md py-2 rounded-lg text-left font-body-sm text-body-sm ${
                  i === sel ? "bg-primary/15 text-on-surface" : "text-on-surface-variant"
                }`}
              >
                <span>{c.label}</span>
                <span className="font-label-annotation text-label-annotation text-outline">{c.hint}</span>
              </button>
            </li>
          ))}
          {list.length === 0 && <li className="px-space-md py-2 text-outline font-body-sm text-body-sm">No matches</li>}
        </ul>
      </div>
    </div>
  );
}

const NUMBERS: [string, string][] = [
  ["How sure we are of your level", "After the skill check, how much the app's uncertainty about each skill has shrunk. 0% = no idea yet, 100% = certain."],
  ["You know X% (mastery)", "The app's estimate that you know a topic. It goes up when you answer correctly, down when you don't, and slowly fades if you don't practise (it models forgetting)."],
  ["Chance you'll get it right", "From your mastery: if you mostly know it you'll usually be right, with a little room for slips and lucky guesses."],
  ["Your pace", "How fast your mastery grows per hour of practice. It decides how many warm-up problems you get and how much fits in a week."],
  ["Time to goal / time saved", "Minutes of the lessons your plan picked, compared with taking the longest lesson for every topic."],
  ["Spare days", "How many days of slack your calendar has before the deadline, after fitting your sessions into your weekly hours."],
  ["How sure a link is", "How confident the app is that topic A really needs to come before topic B. It learns this from everyone's answers."],
  ["Response time", "How long the last request to the Syntropix server took."],
];

function ExplainNumbers({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[70] bg-black/60 flex items-center justify-center p-space-md" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-label="Where the numbers come from"
        className="w-[min(640px,94vw)] max-h-[80vh] overflow-auto rounded-xl bg-surface-container-high shadow-2xl p-space-lg flex flex-col gap-space-md"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="font-headline-sm text-headline-sm">What do these numbers mean?</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 rounded hover:bg-surface-container-highest">
            <Ms name="close" />
          </button>
        </div>
        <dl className="flex flex-col gap-space-sm">
          {NUMBERS.map(([k, v]) => (
            <div key={k} className="p-space-sm rounded-lg bg-surface-container-low">
              <dt className="font-label-badge text-label-badge text-primary uppercase">{k}</dt>
              <dd className="font-body-sm text-body-sm text-on-surface-variant mt-1">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
