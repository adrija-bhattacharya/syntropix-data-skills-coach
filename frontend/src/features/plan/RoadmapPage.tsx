import { useMemo, useState } from "react";

import { Caption, ErrorBox, Hci, HciRibbon, Loading, Ms, Pill, dayLabel } from "../../components/stitch";
import { useLearner } from "../../context/LearnerContext";
import { useTrack } from "../../context/TrackContext";
import type { Certification, LearnResource, RoadmapInput, RoadmapPhase } from "../../lib/api";
import { useRoadmap } from "../../lib/queries";
import { NeedGoal } from "./NeedGoal";
import { PlanTabs } from "./PlanPage";

/** Roadmap - the "Roadmap (Timeline)" tab of the Stitch plan header. */
export function RoadmapPage() {
  const { learnerId } = useLearner();
  const { track } = useTrack();
  const input = useMemo<RoadmapInput>(
    () => ({
      learner_id: learnerId,
      goal: track.goal,
      weekly_hours: track.hoursPerWeek,
      deadline: track.deadline || undefined,
      band: track.band,
      speed: track.speed,
    }),
    [learnerId, track.goal, track.hoursPerWeek, track.deadline, track.band, track.speed],
  );
  const q = useRoadmap(input, Boolean(track.goal));
  const [playing, setPlaying] = useState<LearnResource | null>(null);

  if (!track.goal) return <NeedGoal />;
  if (q.isPending) return <Loading label="Building your roadmap…" />;
  if (q.isError) return <ErrorBox>{q.error.message}</ErrorBox>;
  const rm = q.data.roadmap;
  const totalWeeks = Math.max(1, rm.total_weeks, ...rm.phases.map((p) => p.start_week + p.est_weeks));
  const here = rm.phases.find((p) => p.new_skills > 0) ?? rm.phases[0];

  return (
    <div className="flex flex-col w-full gap-space-lg">
      <div className="flex flex-wrap items-center justify-between gap-space-md">
        <PlanTabs current="roadmap" />
        <Pill tone="neutral" icon="speed" className="capitalize">
          Pace: {rm.pace} · {rm.weekly_hours} h/week
        </Pill>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-space-md p-space-lg rounded-xl bg-surface-container shadow-md">
        <div className="flex flex-col gap-space-xs">
          <Caption>Total time</Caption>
          <div className="flex items-baseline gap-space-xs">
            <span className="font-headline-lg text-headline-lg">{rm.total_hours.toFixed(1)}</span>
            <span className="font-label-badge text-label-badge text-on-surface-variant">hours</span>
          </div>
          <span className="font-label-badge text-label-badge text-outline">at your pace</span>
        </div>
        <div className="flex flex-col gap-space-xs">
          <Caption>Phases</Caption>
          <div className="flex items-baseline gap-space-xs">
            <span className="font-headline-lg text-headline-lg">{rm.phases.length}</span>
            <span className="font-label-badge text-label-badge text-on-surface-variant">over {rm.total_weeks.toFixed(1)} weeks</span>
          </div>
        </div>
        <div className="flex flex-col gap-space-xs">
          <Caption>You'll finish around</Caption>
          <div className="flex items-baseline gap-space-xs">
            <span className="font-headline-lg text-headline-lg">{rm.finish_estimate ? dayLabel(rm.finish_estimate) : "—"}</span>
            <span className="font-label-badge text-label-badge text-on-surface-variant">{rm.finish_estimate?.slice(0, 4)}</span>
          </div>
          {rm.deadline && (
            <span className={`font-label-badge text-label-badge ${rm.on_track ? "text-tertiary" : "text-error"}`}>
              {rm.on_track ? "On track for" : "Behind for"} {dayLabel(rm.deadline)}
            </span>
          )}
        </div>
        <div className="flex flex-col gap-space-xs">
          <Caption>Ready now</Caption>
          <div className="flex items-baseline gap-space-xs">
            <span className="font-headline-lg text-headline-lg text-secondary">
              {Math.round(rm.starting_readiness * 100)}% → {Math.round(rm.target_readiness * 100)}%
            </span>
          </div>
          <span className="font-label-badge text-label-badge text-outline">of the goal's skills</span>
        </div>
      </div>

      <section className="bg-surface-container-low rounded-xl p-space-lg shadow-sm flex flex-col gap-space-md">
        <div className="flex items-center justify-between flex-wrap gap-space-sm">
          <h2 className="font-headline-md text-headline-md">Your path, phase by phase</h2>
          <Hci>[H-01 Status Visibility] Bars are drawn to scale in weeks</Hci>
        </div>
        <div className="flex flex-col gap-space-sm" role="list" aria-label="Phases by week">
          {rm.phases.map((p) => (
            <div key={p.index} role="listitem" className="grid grid-cols-[minmax(120px,220px)_1fr] items-center gap-space-md">
              <span className="font-body-sm text-body-sm text-on-surface truncate">
                {p.index}. {p.title}
              </span>
              <div className="relative h-7 rounded bg-surface-container-lowest">
                <div
                  className={`absolute top-1 bottom-1 rounded ${p === here ? "bg-primary/40 ring-1 ring-primary" : p.new_skills === 0 ? "bg-tertiary/25" : "bg-surface-container-highest"}`}
                  style={{ left: `${(p.start_week / totalWeeks) * 100}%`, width: `${Math.max(2, (p.est_weeks / totalWeeks) * 100)}%` }}
                />
                <span
                  className="absolute top-1/2 -translate-y-1/2 font-label-annotation text-label-annotation text-on-surface-variant whitespace-nowrap px-1"
                  style={{ left: `${Math.min(80, ((p.start_week + p.est_weeks) / totalWeeks) * 100)}%` }}
                >
                  {p.est_hours.toFixed(1)}h · {p.est_weeks.toFixed(1)} wk
                </span>
                {p === here && (
                  <span className="absolute -top-2 font-label-annotation text-label-annotation text-primary font-bold" style={{ left: `${(p.start_week / totalWeeks) * 100}%` }}>
                    ▼ YOU ARE HERE
                  </span>
                )}
              </div>
            </div>
          ))}
          <div className="grid grid-cols-[minmax(120px,220px)_1fr] gap-space-md">
            <span />
            <div className="flex justify-between font-label-annotation text-label-annotation text-outline">
              <span>Week 0</span>
              <span>Week {(totalWeeks / 2).toFixed(1)}</span>
              <span>Week {totalWeeks.toFixed(1)}</span>
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg items-start">
        <div className="xl:col-span-8 flex flex-col gap-space-md">
          {rm.phases.map((p) => (
            <PhaseCard key={p.index} p={p} here={p === here} onPlay={setPlaying} />
          ))}
        </div>
        <div className="xl:col-span-4 flex flex-col gap-space-md">
          {playing && (
            <section className="bg-surface-container rounded-xl p-space-md shadow-xl flex flex-col gap-space-sm">
              <div className="flex items-center justify-between">
                <span className="font-body-strong text-body-sm truncate">{playing.title}</span>
                <button type="button" onClick={() => setPlaying(null)} aria-label="Close video" className="p-1 rounded hover:bg-surface-container-high">
                  <Ms name="close" />
                </button>
              </div>
              <div className="aspect-video rounded-lg overflow-hidden bg-black">
                <iframe title={playing.title} src={playing.embed_url} className="w-full h-full" allow="encrypted-media; picture-in-picture" allowFullScreen />
              </div>
            </section>
          )}
          {rm.recommended.length > 0 && (
            <section className="bg-surface-container-low rounded-xl p-space-lg shadow-sm flex flex-col gap-space-sm">
              <h3 className="font-headline-sm text-headline-sm">Start here: picked for your level</h3>
              {rm.recommended.map((r) => (
                <ResourceRow key={r.id} r={r} onPlay={setPlaying} />
              ))}
            </section>
          )}
          <section className="bg-surface-container-low rounded-xl p-space-lg shadow-sm flex flex-col gap-space-sm">
            <h3 className="font-headline-sm text-headline-sm">Certificates you can aim for</h3>
            {rm.certifications.map((c) => (
              <CertRow key={c.id} c={c} />
            ))}
          </section>
          {rm.notes.length > 0 && (
            <section className="bg-surface-container-low rounded-xl p-space-md shadow-sm flex flex-col gap-1">
              <Caption>Notes</Caption>
              {rm.notes.map((n) => (
                <p key={n} className="font-body-sm text-body-sm text-on-surface-variant">{n}</p>
              ))}
            </section>
          )}
        </div>
      </div>

      <HciRibbon
        title="Design notes: roadmap"
        cards={[
          { tag: "H-01", title: "Visibility of System Status", body: "Every phase shows hours and weeks at your pace, drawn to scale on one timeline." },
          { tag: "H-02", title: "Match the Real World", tone: "secondary", body: "Phases are named after the skills a job asks for; certifications sit where you'll be ready for them." },
          { tag: "H-07", title: "Flexibility", body: "Change your pace or hours on the Skill Map page and every date here moves with it." },
          { tag: "Pedagogy", title: "Curated Resources", tone: "tertiary", body: "Videos and docs are picked per phase and level from a verified library, not a search." },
        ]}
      />
    </div>
  );
}

function PhaseCard({ p, here, onPlay }: { p: RoadmapPhase; here: boolean; onPlay: (r: LearnResource) => void }) {
  return (
    <section className={`p-space-lg rounded-xl flex flex-col gap-space-md ${here ? "bg-surface-container-high shadow-xl" : "bg-surface-container shadow-md"}`}>
      <div className="flex items-start justify-between gap-space-md flex-wrap">
        <div className="flex items-start gap-space-md">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${p.new_skills === 0 ? "bg-tertiary/10 text-tertiary" : "bg-primary/10 text-primary"}`}>
            <Ms name={p.new_skills === 0 ? "check" : "flag"} />
          </div>
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-space-xs flex-wrap">
              <span className="font-label-badge text-label-badge text-on-surface-variant">Phase {p.index}</span>
              {here && <Pill tone="primary">You are here</Pill>}
              {p.new_skills === 0 && <Pill tone="tertiary">You know this</Pill>}
            </div>
            <h3 className="font-headline-sm text-headline-sm">{p.title}</h3>
            <span className="font-label-annotation text-label-annotation text-on-surface-variant">
              {p.new_skills} new skill{p.new_skills === 1 ? "" : "s"} · {p.est_hours.toFixed(1)} h · starts week {p.start_week.toFixed(1)}
            </span>
          </div>
        </div>
      </div>
      {p.focus && <p className="font-body-md text-body-md text-on-surface-variant">{p.focus}</p>}
      {p.concept_names.length > 0 && (
        <div className="flex flex-wrap gap-space-xs">
          {p.concept_names.map((n) => (
            <span key={n} className="px-2 py-0.5 rounded bg-surface-container-lowest font-label-badge text-label-badge text-on-surface-variant">
              {n}
            </span>
          ))}
        </div>
      )}
      {p.videos.length > 0 && (
        <div className="flex flex-col gap-space-xs">
          <Caption>Picked for this phase</Caption>
          {p.videos.map((r) => (
            <ResourceRow key={r.id} r={r} onPlay={onPlay} />
          ))}
        </div>
      )}
      {p.certifications.length > 0 && (
        <div className="flex flex-wrap gap-space-xs items-center">
          <Caption>Ready to take:</Caption>
          {p.certifications.map((c) => (
            <a key={c.id} href={c.url} target="_blank" rel="noreferrer" className="px-2 py-0.5 rounded bg-secondary-container/20 text-secondary font-label-badge text-label-badge hover:underline">
              {c.name}
            </a>
          ))}
        </div>
      )}
      {p.checkpoint && (
        <div className="p-space-sm rounded bg-surface-container-lowest border-l-2 border-secondary font-body-sm text-body-sm text-on-surface-variant">
          {p.checkpoint}
        </div>
      )}
    </section>
  );
}

function ResourceRow({ r, onPlay }: { r: LearnResource; onPlay: (r: LearnResource) => void }) {
  return (
    <div className="flex items-start justify-between gap-space-sm p-space-sm rounded-lg bg-surface-container-lowest">
      <div className="flex items-start gap-space-sm min-w-0">
        <Ms name={r.embed_url ? "play_circle" : r.kind === "practice" ? "terminal" : "article"} className="text-primary shrink-0 mt-0.5" />
        <div className="flex flex-col min-w-0">
          <a href={r.url} target="_blank" rel="noreferrer" className="font-body-strong text-body-sm text-on-surface hover:text-primary truncate">
            {r.title}
          </a>
          <span className="font-label-annotation text-label-annotation text-outline">
            {r.channel} · {r.kind}
            {r.minutes ? ` · ${Math.round(r.minutes / 60) >= 1 ? `${(r.minutes / 60).toFixed(1)} h` : `${r.minutes} min`}` : ""}
          </span>
          {r.note && <span className="font-body-sm text-body-sm text-on-surface-variant">{r.note}</span>}
        </div>
      </div>
      {r.embed_url && (
        <button type="button" onClick={() => onPlay(r)} className="px-space-sm py-1 rounded bg-surface-container-highest hover:bg-surface-bright font-label-badge text-label-badge shrink-0">
          Queue Video
        </button>
      )}
    </div>
  );
}

function CertRow({ c }: { c: Certification }) {
  return (
    <a href={c.url} target="_blank" rel="noreferrer" className="p-space-sm rounded-lg bg-surface-container-lowest hover:bg-surface-container flex flex-col gap-0.5">
      <span className="flex items-center justify-between gap-space-sm">
        <span className="font-body-strong text-body-sm text-on-surface">{c.name}</span>
        <Pill tone={c.free ? "tertiary" : "neutral"}>{c.free ? "Free" : c.level}</Pill>
      </span>
      <span className="font-label-annotation text-label-annotation text-outline">
        {c.provider} · ~{c.hours} h · {c.price_note}
      </span>
    </a>
  );
}
