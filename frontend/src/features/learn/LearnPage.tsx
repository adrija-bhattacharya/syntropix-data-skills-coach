import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ErrorBox, Loading, Ms, Pill, hm } from "../../components/stitch";
import type { Video } from "../../lib/api";
import { PACE_LABEL, SKILL_NAME, checkLine, clock, embed, useTrackLibrary, type Pace } from "../../lib/library";
import { toggle, useDone } from "../../lib/progress";
import { NeedGoal } from "../plan/NeedGoal";
import { PaceBar } from "./PaceBar";

/** Learn (Videos): every video to watch, in order, playing inside the app. */
export function LearnPage() {
  const { q, pace, setPace, track } = useTrackLibrary();
  const done = useDone();
  const [playing, setPlaying] = useState<Video | null>(null);

  const playlist = useMemo<{ v: Video; section: string; concept?: string; mastery?: number }[]>(() => {
    if (!q.data) return [];
    const courses = q.data.courses.map((v) => ({ v, section: `${SKILL_NAME[v.domain] ?? v.domain} · full course · ${v.level}` }));
    const lessons = q.data.steps
      .filter((s) => s.video)
      .map((s) => ({ v: s.video!, section: "Topic by topic", concept: s.concept, mastery: s.mastery }));
    return [...courses, ...lessons];
  }, [q.data]);

  if (!track.goal) return <NeedGoal />;
  if (q.isPending) return <Loading label="Finding the right videos…" />;
  if (q.isError) return <ErrorBox>{q.error.message}</ErrorBox>;

  const current = playing ?? playlist.find((p) => !done.videos[p.v.video_id])?.v ?? playlist[0]?.v ?? null;
  const idx = current ? playlist.findIndex((p) => p.v.video_id === current.video_id) : -1;
  const watched = playlist.filter((p) => done.videos[p.v.video_id]).length;
  const next = playlist.slice(idx + 1).find((p) => !done.videos[p.v.video_id])?.v;
  const sections = [...new Set(playlist.map((p) => p.section))];

  return (
    <div className="flex flex-col gap-space-lg">
      <header className="flex flex-col gap-space-xs">
        <h1 className="font-headline-md text-headline-md">Learn with videos</h1>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
          Start with a full beginner course, then watch one short lesson for each topic, in the order your
          plan needs them. Videos play right here. Tick each one off when you've watched it.
        </p>
      </header>

      <PaceBar data={q.data} pace={pace} setPace={(p: Pace) => setPace(p)} />

      {!current ? (
        <ErrorBox>No videos yet for this goal.</ErrorBox>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg items-start">
          <section className="xl:col-span-8 flex flex-col gap-space-sm">
            <div className="relative w-full overflow-hidden rounded-xl bg-black shadow-lg" style={{ aspectRatio: "16 / 9" }}>
              <iframe
                key={current.video_id}
                src={embed(current.video_id, current.check?.start ?? 0)}
                title={current.title}
                className="absolute inset-0 w-full h-full"
                allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
                allowFullScreen
                loading="lazy"
                referrerPolicy="strict-origin-when-cross-origin"
              />
            </div>
            <div className="flex flex-wrap items-start justify-between gap-space-sm">
              <div className="flex flex-col gap-1 min-w-0">
                <h2 className="font-headline-sm text-headline-sm">{current.title}</h2>
                <span className="font-body-sm text-body-sm text-on-surface-variant">
                  {current.channel} · {hm(current.minutes)}
                  {current.views ? ` · ${current.views.toLocaleString()} views` : ""} ·{" "}
                  <a href={current.url} target="_blank" rel="noreferrer" className="underline hover:text-primary">
                    open on YouTube
                  </a>
                </span>
                {checkLine(current.check) && (
                  <span className="font-label-annotation text-label-annotation text-tertiary flex items-center gap-1" title={current.check?.reason}>
                    <Ms name="fact_check" size={14} /> {checkLine(current.check)}
                    {current.check && current.check.start > 0 && ` Starts at ${clock(current.check.start)}${current.check.chapter ? `: “${current.check.chapter}”` : ""}.`}
                  </span>
                )}
              </div>
              <div className="flex gap-space-xs">
                <button
                  type="button"
                  aria-pressed={!!done.videos[current.video_id]}
                  onClick={() => toggle("videos", current.video_id)}
                  className={`px-space-md py-2 rounded-lg font-body-strong text-body-sm flex items-center gap-1.5 ${
                    done.videos[current.video_id] ? "bg-tertiary/20 text-tertiary" : "bg-surface-container-high hover:bg-surface-container-highest"
                  }`}
                >
                  <Ms name={done.videos[current.video_id] ? "check_circle" : "radio_button_unchecked"} size={18} />
                  {done.videos[current.video_id] ? "Watched" : "Mark as watched"}
                </button>
                {next && (
                  <button type="button" onClick={() => setPlaying(next)} className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center gap-1.5">
                    Next video <Ms name="skip_next" size={18} />
                  </button>
                )}
              </div>
            </div>
          </section>

          <aside className="xl:col-span-4 flex flex-col gap-space-sm p-space-md rounded-xl bg-surface-container-low max-h-[80vh] overflow-y-auto" aria-label="Playlist">
            <div className="flex items-center justify-between">
              <span className="font-body-strong text-body-sm">Your playlist</span>
              <Pill tone="tertiary">{watched} / {playlist.length} watched</Pill>
            </div>
            {sections.map((sec) => (
              <div key={sec} className="flex flex-col gap-1">
                <span className="font-label-annotation text-label-annotation text-outline uppercase tracking-wider pt-space-xs">{sec}</span>
                {playlist
                  .filter((p) => p.section === sec)
                  .map((p) => {
                    const on = p.v.video_id === current.video_id;
                    const seen = !!done.videos[p.v.video_id];
                    return (
                      <button
                        key={p.v.video_id}
                        type="button"
                        onClick={() => setPlaying(p.v)}
                        aria-current={on ? "true" : undefined}
                        className={`text-left flex gap-space-sm p-space-xs rounded-lg ${on ? "bg-primary/15 ring-1 ring-primary/50" : "hover:bg-surface-container"}`}
                      >
                        <img src={`https://i.ytimg.com/vi/${p.v.video_id}/mqdefault.jpg`} alt="" loading="lazy" className="w-28 aspect-video object-cover rounded shrink-0 bg-surface-container" />
                        <span className="flex flex-col min-w-0 gap-0.5">
                          {p.concept && <span className="font-label-annotation text-label-annotation text-primary truncate">{p.concept}</span>}
                          <span className="font-body-sm text-body-sm text-on-surface line-clamp-2">{p.v.title}</span>
                          <span className="font-label-annotation text-label-annotation text-outline flex items-center gap-1">
                            {seen && <Ms name="check_circle" size={13} className="text-tertiary" />}
                            {p.v.check?.level === "verified" && <Ms name="fact_check" size={13} className="text-tertiary" label="checked: teaches this topic" />}
                            {p.v.channel} · {hm(p.v.minutes)}
                            {p.mastery != null && p.mastery >= 0.75 && " · you know this"}
                          </span>
                        </span>
                      </button>
                    );
                  })}
              </div>
            ))}
          </aside>
        </div>
      )}

      <p className="font-label-annotation text-label-annotation text-outline">
        Videos are from YouTube teachers like freeCodeCamp, Alex The Analyst, StatQuest, Kevin Stratvert and Guy in a Cube
        {q.data.harvested ? `, collected on ${q.data.harvested}` : ""}. Want to practise what you just watched?{" "}
        <Link to="/practice" className="underline hover:text-primary">Go to Practice</Link>.
      </p>
    </div>
  );
}

export { PACE_LABEL };
