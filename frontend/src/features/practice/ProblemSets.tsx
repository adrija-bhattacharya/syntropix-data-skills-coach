import { useState } from "react";
import { Link } from "react-router-dom";

import { ErrorBox, Loading, Ms, Pill, hm } from "../../components/stitch";
import type { Problem } from "../../lib/api";
import { DIFF_TONE, SKILL_NAME, useTrackLibrary } from "../../lib/library";
import { practiceTarget } from "../../lib/plan";
import { toggle, useDone } from "../../lib/progress";
import { PaceBar } from "../learn/PaceBar";
import { NeedGoal } from "../plan/NeedGoal";

type View = "weeks" | "topics" | "stretch" | "review" | "more";
const VIEWS: { id: View; label: string; icon: string }[] = [
  { id: "weeks", label: "Week by week", icon: "calendar_view_week" },
  { id: "topics", label: "Topic by topic", icon: "format_list_numbered" },
  { id: "stretch", label: "Stretch (harder)", icon: "trending_up" },
  { id: "review", label: "Review (you know these)", icon: "replay" },
  { id: "more", label: "More practice", icon: "library_add" },
];

/** LeetCode, HackerRank and open-site problems, in the order your path needs them. */
export function ProblemSets() {
  const { q, pace, setPace, track } = useTrackLibrary();
  const done = useDone();
  const [view, setView] = useState<View>("weeks");
  const [platform, setPlatform] = useState<string>("all");

  if (!track.goal) return <NeedGoal />;
  if (q.isPending) return <Loading label="Collecting practice problems…" />;
  if (q.isError) return <ErrorBox>{q.error.message}</ErrorBox>;
  const d = q.data;
  const all = d.steps.flatMap((s) => s.problems);
  const platforms = [...new Set([...all, ...d.mixed].map((p) => p.platform))].sort();
  const keep = (p: Problem) => platform === "all" || p.platform === platform;
  const solved = all.filter((p) => done.problems[p.url]).length;

  return (
    <div className="flex flex-col gap-space-md">
      <PaceBar data={d} pace={pace} setPace={setPace} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-space-sm">
        <Stat icon="task_alt" label="Solved" value={`${solved} / ${all.length}`} />
        <Stat icon="code" label="LeetCode on your path" value={String(d.totals.leetcode ?? 0)} />
        <Stat icon="terminal" label="HackerRank on your path" value={String(d.totals.hackerrank ?? 0)} />
        <Stat icon="calendar_month" label="Weeks at your pace" value={String(d.totals.weeks ?? 0)} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <div className="flex flex-wrap gap-space-xs" role="tablist" aria-label="How to list problems">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              role="tab"
              aria-selected={view === v.id}
              onClick={() => setView(v.id)}
              className={`px-space-sm py-1.5 rounded-lg font-body-sm text-body-sm flex items-center gap-1 ${view === v.id ? "bg-primary/20 text-primary font-bold" : "bg-surface-container-low hover:bg-surface-container text-on-surface-variant"}`}
            >
              <Ms name={v.icon} size={16} /> {v.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
          Site
          <select value={platform} onChange={(e) => setPlatform(e.target.value)} className="px-space-sm py-1 rounded bg-surface-container-low border border-outline-variant/40">
            <option value="all">All sites</option>
            {platforms.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </label>
      </div>

      {view === "weeks" &&
        d.weeks.map((w) => {
          const items = w.items.filter((it) => it.type === "video" || keep(it as unknown as Problem));
          if (!items.length) return null;
          return (
            <section key={w.week} className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs">
              <div className="flex items-center justify-between">
                <h2 className="font-headline-sm text-headline-sm">Week {w.week}</h2>
                <span className="font-label-annotation text-label-annotation text-outline">about {hm(w.minutes)}</span>
              </div>
              {items.map((it, i) =>
                it.type === "video" ? (
                  <Link key={i} to="/learn" className="flex items-center gap-space-sm p-space-xs rounded hover:bg-surface-container font-body-sm text-body-sm">
                    <Ms name={done.videos[it.video_id ?? ""] ? "check_circle" : "smart_display"} size={18} className={done.videos[it.video_id ?? ""] ? "text-tertiary" : "text-error"} />
                    <span className="text-primary font-label-annotation text-label-annotation w-40 truncate shrink-0">{it.concept}</span>
                    <span className="flex-1 truncate">Watch: {it.title}</span>
                    <span className="text-outline font-label-annotation text-label-annotation">{hm(it.minutes)}</span>
                  </Link>
                ) : (
                  <Row key={i} p={it as unknown as Problem} concept={it.concept} minutes={it.minutes} />
                ),
              )}
            </section>
          );
        })}

      {view === "topics" &&
        d.steps.map((s, i) => {
          const ps = s.problems.filter(keep);
          const lab = practiceTarget(s.concept_id, s.domain);
          return (
            <section key={s.concept_id} className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs">
              <div className="flex flex-wrap items-center justify-between gap-space-xs">
                <h2 className="font-body-strong text-body-md">
                  {i + 1}. {s.concept} <span className="font-label-annotation text-label-annotation text-outline">· {SKILL_NAME[s.domain] ?? s.domain}</span>
                </h2>
                <span className="flex items-center gap-space-xs">
                  <Pill tone={s.mastery >= 0.75 ? "tertiary" : "neutral"}>you know {Math.round(s.mastery * 100)}%</Pill>
                  {lab && (
                    <Link to={`/practice?target=${encodeURIComponent(lab)}`} className="font-label-badge text-label-badge px-space-sm py-1 rounded bg-primary/15 text-primary hover:bg-primary/25">
                      Try it here first
                    </Link>
                  )}
                </span>
              </div>
              {ps.length ? ps.map((p) => <Row key={p.url} p={p} />) : <span className="font-body-sm text-body-sm text-outline">Use the built-in practice for this topic.</span>}
            </section>
          );
        })}

      {view === "stretch" && <List items={d.stretch.filter(keep)} empty="Nothing parked here: at your pace every problem is already in your weeks." />}
      {view === "review" &&
        (d.review.length ? (
          d.review.map((s) => (
            <section key={s.concept_id} className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs">
              <h2 className="font-body-strong text-body-md">{s.concept}</h2>
              {s.problems.filter(keep).map((p) => <Row key={p.url} p={p} />)}
            </section>
          ))
        ) : (
          <ErrorBox>No topics mastered yet: practise or take the skill check and they'll show up here.</ErrorBox>
        ))}
      {view === "more" && <List items={[...d.extra, ...d.mixed].filter(keep)} empty="No extra problems for this goal." />}

      <p className="font-label-annotation text-label-annotation text-outline">
        Problem lists come straight from LeetCode's and HackerRank's sites and from open sites like SQLZoo and Kaggle Learn
        {d.harvested ? ` (collected on ${d.harvested})` : ""}. Solve them on that site, then tick them off here.
      </p>
    </div>
  );
}

function Stat({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-1">
      <span className="font-label-annotation text-label-annotation text-outline uppercase flex items-center gap-1">
        <Ms name={icon} size={14} /> {label}
      </span>
      <span className="font-headline-sm text-headline-sm">{value}</span>
    </div>
  );
}

function List({ items, empty }: { items: Problem[]; empty: string }) {
  if (!items.length) return <ErrorBox>{empty}</ErrorBox>;
  return (
    <section className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs">
      {items.map((p) => (
        <Row key={p.url} p={p} concept={p.concept_id ? (p as { concept?: string }).concept ?? undefined : undefined} />
      ))}
    </section>
  );
}

const PLATFORM_ICON: Record<string, string> = { LeetCode: "code", HackerRank: "terminal" };

function Row({ p, concept, minutes }: { p: Problem; concept?: string; minutes?: number }) {
  const done = useDone();
  const solved = !!done.problems[p.url];
  return (
    <div className="flex items-center gap-space-sm p-space-xs rounded hover:bg-surface-container font-body-sm text-body-sm">
      <input
        type="checkbox"
        checked={solved}
        onChange={() => toggle("problems", p.url)}
        aria-label={`Mark "${p.title}" as solved`}
        className="w-4 h-4 accent-[#4de082] shrink-0"
      />
      <Ms name={PLATFORM_ICON[p.platform] ?? "public"} size={16} className="text-outline shrink-0" />
      {concept && <span className="text-primary font-label-annotation text-label-annotation w-40 truncate shrink-0">{concept}</span>}
      <a href={p.url} target="_blank" rel="noreferrer" className={`flex-1 min-w-0 truncate hover:text-primary hover:underline ${solved ? "line-through text-outline" : ""}`}>
        {p.title}
      </a>
      <span className="hidden sm:inline font-label-annotation text-label-annotation text-outline truncate max-w-[10rem]">{!p.set || p.platform === p.set ? p.platform : `${p.platform} · ${p.set}`}</span>
      <Pill tone={DIFF_TONE[p.difficulty] ?? "neutral"}>{p.difficulty}</Pill>
      {minutes != null && <span className="hidden md:inline w-12 text-right font-label-annotation text-label-annotation text-outline">{hm(minutes)}</span>}
    </div>
  );
}
