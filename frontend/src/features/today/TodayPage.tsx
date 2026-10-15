import { Link } from "react-router-dom";

import { trackName } from "../../components/Shell";
import { ErrorBox, Loading, Ms, Pill, dayLabel, hm, isoToday } from "../../components/stitch";
import { modelCertainty } from "../../context/TrackContext";
import { useFeedback } from "../../lib/feedback";
import { DIFF_TONE, PACE_LABEL, useTrackLibrary } from "../../lib/library";
import { buildSessions, practiceTarget, usePlan } from "../../lib/plan";
import { streak, toggle, useDone } from "../../lib/progress";
import { NeedGoal } from "../plan/NeedGoal";

const TYPE_WORD = { teach: "Learn", review: "Review", check: "Quick check", repair: "Fix a gap", milestone: "Checkpoint" } as const;

/** Today: what to do right now - one session, one video, a few problems. */
export function TodayPage() {
  const p = usePlan();
  const { q } = useTrackLibrary();
  const done = useDone();
  const { track } = p;

  if (!track.goal) return <NeedGoal />;
  if (p.resolved.isPending || p.rec.isPending) return <Loading label="Getting today ready…" />;
  if (p.resolved.isError) return <ErrorBox>{p.resolved.error.message}</ErrorBox>;
  if (p.rec.isError) return <ErrorBox>{p.rec.error.message}</ErrorBox>;

  const domain = p.resolved.data.source === "seed" ? p.resolved.data.domain : p.resolved.data.source;
  const sessions = p.plan ? buildSessions(p.plan, p.goals, track.hoursPerWeek) : [];
  const session = sessions.find((s) => s.status === "current") ?? sessions.find((s) => s.status !== "done");
  const finished = sessions.filter((s) => s.status === "done").length;
  const nextVideo =
    q.data &&
    [...q.data.courses, ...q.data.steps.flatMap((s) => (s.video ? [s.video] : []))].find((v) => !done.videos[v.video_id]);
  const nextProblems = q.data ? q.data.steps.flatMap((s) => s.problems.map((pr) => ({ ...pr, concept: s.concept }))).filter((pr) => !done.problems[pr.url]).slice(0, 3) : [];
  const days = track.deadline ? Math.ceil((Date.parse(track.deadline) - Date.parse(isoToday())) / 864e5) : null;
  const cert = modelCertainty(track);
  const hour = new Date().getHours();
  const hello = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="flex flex-col gap-space-lg">
      <header className="flex flex-col gap-space-xs">
        <span className="font-label-annotation text-label-annotation text-outline uppercase tracking-wider">{new Date().toDateString()}</span>
        <h1 className="font-headline-md text-headline-md">{hello}! Here's today.</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">
          Your goal: <b className="text-on-surface">{track.goal}</b> ({trackName(p.resolved.data.domain)}).{" "}
          <Link to="/map" className="underline hover:text-primary">Change goal</Link>
        </p>
      </header>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-space-sm">
        <Tile icon="local_fire_department" tone="text-secondary" label="Day streak" value={`${streak(done)} day${streak(done) === 1 ? "" : "s"}`} />
        <Tile icon="event_available" tone="text-tertiary" label="Sessions finished" value={`${finished} / ${sessions.length}`} />
        <Tile icon="flag" tone="text-primary" label="Days to your deadline" value={days == null ? "No deadline" : days >= 0 ? String(days) : "Passed"} />
        <Tile icon="speed" tone="text-secondary" label="Your pace" value={q.data ? PACE_LABEL[q.data.pace] ?? q.data.pace : "…"} />
      </div>

      {cert == null && (
        <Link to="/assess" className="p-space-md rounded-xl bg-primary/10 border border-primary/30 flex items-center gap-space-sm hover:bg-primary/15">
          <Ms name="quiz" className="text-primary" />
          <span className="flex-1 font-body-sm text-body-sm">
            <b>New here?</b> Take the 10-minute skill check so your plan skips what you already know.
          </span>
          <Ms name="arrow_forward" />
        </Link>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-space-lg items-start">
        <section className="xl:col-span-2 p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs">
              <Ms name="today" className="text-primary" /> {session ? `Session ${session.number}` : "All sessions done"}
            </h2>
            {session && <Pill tone="neutral">about {hm(session.minutes)}</Pill>}
          </div>
          {session ? (
            <>
              <ol className="flex flex-col gap-space-xs">
                {session.steps.map((ps) => {
                  const lab = practiceTarget(ps.step.concept_id, domain);
                  return (
                    <li key={ps.index} className={`flex items-center gap-space-sm p-space-sm rounded-lg ${ps.done ? "bg-surface-container/50 text-outline" : "bg-surface-container"}`}>
                      <Ms name={ps.done ? "check_circle" : "radio_button_unchecked"} className={ps.done ? "text-tertiary" : "text-outline"} />
                      <span className="flex-1 min-w-0">
                        <span className="font-label-annotation text-label-annotation text-primary uppercase">{TYPE_WORD[ps.type]}</span>
                        <span className="block font-body-sm text-body-sm truncate">{ps.step.concept || ps.step.concept_id}{ps.step.title ? ` · ${ps.step.title}` : ""}</span>
                      </span>
                      <span className="font-label-annotation text-label-annotation text-outline">{hm(ps.step.minutes)}</span>
                      {lab && !ps.done && (
                        <Link to={`/practice?target=${encodeURIComponent(lab)}`} className="px-space-sm py-1 rounded bg-primary text-on-primary font-label-badge text-label-badge">
                          Practise
                        </Link>
                      )}
                    </li>
                  );
                })}
              </ol>
              <Link to={`/session/${session.number}`} className="w-fit px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center gap-1.5">
                Open this session <Ms name="arrow_forward" size={16} />
              </Link>
            </>
          ) : (
            <p className="font-body-sm text-body-sm text-on-surface-variant">You've finished every session on this plan. 🎉 Try a project or interview practice next.</p>
          )}
        </section>

        <div className="flex flex-col gap-space-lg">
          {track.deadline > isoToday() ? (
            <TodayLoop learnerId={p.learnerId} goal={track.goal} goals={p.goals} deadline={track.deadline} hoursPerWeek={track.hoursPerWeek} speed={track.speed} />
          ) : (
            <Link to="/calendar" className="p-space-md rounded-xl bg-surface-container-low flex items-center gap-space-sm hover:bg-surface-container font-body-sm text-body-sm">
              <Ms name="event" className="text-primary" /> Set a deadline and Syntropix fits your sessions around your real week.
            </Link>
          )}
          <section className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-sm">
            <h2 className="font-body-strong text-body-md flex items-center gap-space-xs">
              <Ms name="smart_display" className="text-error" /> Next video
            </h2>
            {nextVideo ? (
              <Link to="/learn" className="flex flex-col gap-1 group">
                <img src={`https://i.ytimg.com/vi/${nextVideo.video_id}/mqdefault.jpg`} alt="" className="w-full aspect-video object-cover rounded-lg bg-surface-container" />
                <span className="font-body-sm text-body-sm group-hover:text-primary line-clamp-2">{nextVideo.title}</span>
                <span className="font-label-annotation text-label-annotation text-outline">{nextVideo.channel} · {hm(nextVideo.minutes)}</span>
              </Link>
            ) : (
              <span className="font-body-sm text-body-sm text-outline">{q.isPending ? "Loading…" : "All videos watched!"}</span>
            )}
          </section>

          <section className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs">
            <h2 className="font-body-strong text-body-md flex items-center gap-space-xs">
              <Ms name="code" className="text-tertiary" /> Solve next
            </h2>
            {nextProblems.map((pr) => (
              <div key={pr.url} className="flex items-center gap-space-xs font-body-sm text-body-sm">
                <input type="checkbox" checked={false} onChange={() => toggle("problems", pr.url)} aria-label={`Mark "${pr.title}" as solved`} className="w-4 h-4 accent-[#4de082]" />
                <a href={pr.url} target="_blank" rel="noreferrer" className="flex-1 truncate hover:text-primary hover:underline">{pr.title}</a>
                <Pill tone={DIFF_TONE[pr.difficulty] ?? "neutral"}>{pr.platform}</Pill>
              </div>
            ))}
            <Link to="/practice?tab=sets" className="font-label-badge text-label-badge text-primary hover:underline">See all problems →</Link>
          </section>
        </div>
      </div>
    </div>
  );
}

function Tile({ icon, label, value, tone }: { icon: string; label: string; value: string; tone: string }) {
  return (
    <div className="p-space-md rounded-xl bg-surface-container-low flex items-center gap-space-sm">
      <Ms name={icon} size={26} className={tone} />
      <span className="flex flex-col">
        <span className="font-label-annotation text-label-annotation text-outline uppercase">{label}</span>
        <span className="font-headline-sm text-headline-sm">{value}</span>
      </span>
    </div>
  );
}

/** Feed the calendar loop every day: how did the last session go, and what's on today. */
function TodayLoop(props: { learnerId: string; goal: string; goals: string[]; deadline: string; hoursPerWeek: number; speed: string }) {
  const { q, log, mark } = useFeedback(props);
  if (q.isPending) return <Loading label="Fitting today into your week…" />;
  if (q.isError) return <ErrorBox>{q.error.message}</ErrorBox>;
  const r = q.data;
  const last = r.past_days.filter((d) => !log[d.day]).at(-1);
  const today = r.blocks.filter((b) => b.day === isoToday());
  return (
    <section className="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-sm" aria-label="Today's study blocks">
      {last && (
        <div className="flex flex-col gap-space-xs p-space-sm rounded-lg bg-primary/10">
          <span className="font-body-strong text-body-sm">How did {dayLabel(last.day)} go? ({hm(last.planned_minutes)} planned)</span>
          <div className="flex gap-space-xs" role="group" aria-label={`How ${dayLabel(last.day)} went`}>
            {(
              [
                ["Done", last.planned_minutes],
                ["Half", Math.round(last.planned_minutes / 2)],
                ["Missed", 0],
              ] as const
            ).map(([label, done]) => (
              <button key={label} type="button" onClick={() => mark(last.day, last.planned_minutes, done)} className="px-space-sm py-1 rounded bg-surface-container-high hover:bg-surface-container-highest font-label-badge text-label-badge">
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
      <h2 className="font-body-strong text-body-md flex items-center gap-space-xs">
        <Ms name="schedule" className="text-primary" /> Your blocks today
      </h2>
      {today.length ? (
        <ul className="flex flex-col gap-1">
          {today.map((b, i) => (
            <li key={i} className="flex items-center gap-space-sm font-body-sm text-body-sm">
              <span className="font-code-sm text-code-sm text-primary w-24 shrink-0">{b.start}–{b.end}</span>
              <span className="truncate">{b.concept}{b.parts > 1 ? ` (part ${b.part} of ${b.parts})` : ""}</span>
            </li>
          ))}
        </ul>
      ) : (
        <span className="font-body-sm text-body-sm text-on-surface-variant">
          Nothing fits today{r.blocks[0] ? `. Next: ${dayLabel(r.blocks[0].day)} at ${r.blocks[0].start}` : ""}.
        </span>
      )}
      <span className="font-label-annotation text-label-annotation text-outline">
        {r.logged_days ? `You manage about ${Math.round(r.adherence * 100)}% of planned time · ` : ""}
        {r.forecast?.p50
          ? `likely done ${dayLabel(r.forecast.p50)} (80% by ${r.forecast.p80 ? dayLabel(r.forecast.p80) : "—"})`
          : `finish ${r.finish ? dayLabel(r.finish) : "—"}`}{" "}
        · <Link to="/calendar" className="underline hover:text-primary">re-plan your week</Link>
      </span>
    </section>
  );
}
