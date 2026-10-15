import { Link } from "react-router-dom";

import { ErrorBox, Loading, Ms, Pill } from "../../components/stitch";
import { modelCertainty } from "../../context/TrackContext";
import { PACE_LABEL, SKILL_NAME, useTrackLibrary } from "../../lib/library";
import { streak, useDone } from "../../lib/progress";
import { NeedGoal } from "../plan/NeedGoal";

const KNOWN = 0.75;

/** How far along you are: per skill, per topic, and what you've done. */
export function ProgressPage() {
  const { q, track } = useTrackLibrary();
  const done = useDone();

  if (!track.goal) return <NeedGoal />;
  if (q.isPending) return <Loading label="Adding up your progress…" />;
  if (q.isError) return <ErrorBox>{q.error.message}</ErrorBox>;
  const d = q.data;
  const topics = [...d.review, ...d.steps];
  const bySkill = new Map<string, typeof topics>();
  topics.forEach((t) => bySkill.set(t.domain, [...(bySkill.get(t.domain) ?? []), t]));
  const known = topics.filter((t) => t.mastery >= KNOWN).length;
  const problems = [...d.steps, ...d.review].flatMap((s) => s.problems);
  const solved = problems.filter((p) => done.problems[p.url]).length;
  const videos = [...d.courses, ...topics.flatMap((t) => (t.video ? [t.video] : []))];
  const watched = videos.filter((v) => done.videos[v.video_id]).length;
  const cert = modelCertainty(track);
  const recent = [
    ...Object.entries(done.videos).map(([id, day]) => ({ day, what: `Watched: ${videos.find((v) => v.video_id === id)?.title ?? "a video"}` })),
    ...Object.entries(done.problems).map(([url, day]) => ({ day, what: `Solved: ${problems.find((p) => p.url === url)?.title ?? url}` })),
  ]
    .sort((a, b) => b.day.localeCompare(a.day))
    .slice(0, 8);

  return (
    <div className="flex flex-col gap-space-lg">
      <header className="flex flex-col gap-space-xs">
        <h1 className="font-headline-md text-headline-md">Your progress</h1>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
          A topic counts as <b>known</b> once the app is at least 75% sure you've got it, from your practice answers and skill check.
        </p>
      </header>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-space-sm">
        <Big label="Topics known" value={`${known} / ${topics.length}`} icon="school" />
        <Big label="Videos watched" value={`${watched} / ${videos.length}`} icon="smart_display" />
        <Big label="Problems solved" value={`${solved} / ${problems.length}`} icon="task_alt" />
        <Big label="Day streak" value={String(streak(done))} icon="local_fire_department" />
        <Big label="Your pace" value={PACE_LABEL[d.pace] ?? d.pace} icon="speed" />
      </div>

      <section className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-md">
        <h2 className="font-headline-sm text-headline-sm">By skill</h2>
        {[...bySkill].map(([skill, ts]) => {
          const avg = ts.reduce((s, t) => s + t.mastery, 0) / ts.length;
          return (
            <details key={skill} className="flex flex-col gap-space-xs">
              <summary className="cursor-pointer flex flex-col gap-1">
                <span className="flex justify-between font-body-sm text-body-sm">
                  <b>{SKILL_NAME[skill] ?? skill}</b>
                  <span className="text-on-surface-variant">{ts.filter((t) => t.mastery >= KNOWN).length} of {ts.length} topics known · {Math.round(avg * 100)}%</span>
                </span>
                <span className="block w-full h-2 rounded-full bg-surface-container-highest overflow-hidden">
                  <span className="block h-full bg-tertiary" style={{ width: `${avg * 100}%` }} />
                </span>
              </summary>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-x-space-lg gap-y-1 pt-space-sm">
                {ts.map((t) => (
                  <div key={t.concept_id} className="flex items-center gap-space-xs font-body-sm text-body-sm">
                    <Ms name={t.mastery >= KNOWN ? "check_circle" : "radio_button_unchecked"} size={16} className={t.mastery >= KNOWN ? "text-tertiary" : "text-outline"} />
                    <span className="flex-1 truncate">{t.concept}</span>
                    <span className="w-20 h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
                      <span className="block h-full bg-primary" style={{ width: `${t.mastery * 100}%` }} />
                    </span>
                    <span className="w-9 text-right font-label-annotation text-label-annotation text-outline">{Math.round(t.mastery * 100)}%</span>
                  </div>
                ))}
              </div>
            </details>
          );
        })}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-lg items-start">
        <section className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-xs">
          <h2 className="font-headline-sm text-headline-sm">Recent activity</h2>
          {recent.length ? (
            recent.map((r, i) => (
              <div key={i} className="flex gap-space-sm font-body-sm text-body-sm">
                <span className="text-outline w-24 shrink-0">{r.day}</span>
                <span className="truncate">{r.what}</span>
              </div>
            ))
          ) : (
            <span className="font-body-sm text-body-sm text-outline">Nothing yet. Watch a video or solve a problem and it shows up here.</span>
          )}
        </section>
        <section className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
          <h2 className="font-headline-sm text-headline-sm">Skill check</h2>
          {cert == null ? (
            <>
              <p className="font-body-sm text-body-sm text-on-surface-variant">You haven't taken the skill check yet. It takes about 10 minutes and makes your plan skip what you already know.</p>
              <Link to="/assess" className="w-fit px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm">Take the skill check</Link>
            </>
          ) : (
            <>
              <p className="font-body-sm text-body-sm text-on-surface-variant">How sure the app is about your level: <b className="text-on-surface">{Math.round(cert * 100)}%</b>.</p>
              <div className="flex flex-wrap gap-space-xs">
                {track.assessment!.estimates.slice(0, 12).map((e) => (
                  <Pill key={e.skill} tone={e.mastery >= KNOWN ? "tertiary" : "neutral"}>{e.skill.split(".").pop()!.replaceAll("_", " ")}: {Math.round(e.mastery * 100)}%</Pill>
                ))}
              </div>
              <Link to="/assess" className="w-fit font-body-sm text-body-sm text-primary hover:underline">Retake it</Link>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function Big({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-1">
      <span className="font-label-annotation text-label-annotation text-outline uppercase flex items-center gap-1"><Ms name={icon} size={14} /> {label}</span>
      <span className="font-headline-sm text-headline-sm">{value}</span>
    </div>
  );
}
