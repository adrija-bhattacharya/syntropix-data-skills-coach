import { useMemo, useState } from "react";

import { Badge, Callout, Spinner } from "../../components/ui";
import { useLearner } from "../../context/LearnerContext";
import type {
  Band,
  Certification,
  LearnResource,
  RoadmapInput,
  RoadmapPhase,
} from "../../lib/api";
import { useRoadmap } from "../../lib/queries";

const KIND_ICON: Record<string, string> = {
  video: "▶",
  playlist: "☰",
  channel: "▶",
  course: "\u{1F393}",
  docs: "\u{1F4DA}",
  practice: "✎",
};

const PACE_BLURB: Record<string, string> = {
  deliberate: "measured — you get extra time per topic",
  steady: "steady — an average learning speed",
  fast: "fast — your velocity shortens the estimates",
};

export function RoadmapView({
  goalText,
  weeklyHours,
  deadline,
  band,
}: {
  goalText: string;
  weeklyHours: number;
  deadline?: string;
  band?: Band;
}) {
  const { learnerId } = useLearner();
  const input = useMemo<RoadmapInput>(
    () => ({
      learner_id: learnerId,
      goal: goalText,
      weekly_hours: weeklyHours,
      deadline: deadline || undefined,
      band,
    }),
    [learnerId, goalText, weeklyHours, deadline, band],
  );
  const q = useRoadmap(input, true);

  if (q.isPending) return <Spinner label="Assembling your roadmap…" />;
  if (q.isError) return <Callout tone="warn">{q.error.message}</Callout>;
  const rm = q.data?.roadmap;
  if (!rm) return null;

  return (
    <div className="roadmap">
      <div className="rm-head">
        <div>
          <h3 style={{ margin: 0 }}>
            {rm.role ? `Roadmap to ${rm.role}` : `Roadmap — ${rm.domain}`}
          </h3>
          <p className="hint" style={{ margin: "2px 0 0" }}>
            {rm.phases.length} phases · {Math.round(rm.total_hours)} h · ~{Math.round(rm.total_weeks)}{" "}
            weeks at {rm.weekly_hours} h/week
            {rm.finish_estimate && ` · finish ~${rm.finish_estimate}`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <Badge tone="neutral">level: {rm.band}</Badge>
          <Badge tone="neutral">pace: {rm.pace}</Badge>
          {rm.on_track === true && <Badge tone="good">on track for {rm.deadline}</Badge>}
          {rm.on_track === false && <Badge tone="warn">tight for {rm.deadline}</Badge>}
        </div>
      </div>

      {rm.already_have.length > 0 && (
        <p className="hint" style={{ marginTop: 8 }}>
          <strong>You already have:</strong> {rm.already_have.slice(0, 8).join(", ")}
          {rm.already_have.length > 8 && ` +${rm.already_have.length - 8} more`} — skipped in the
          estimate.
        </p>
      )}

      {rm.recommended.length > 0 && (
        <div className="rm-starthere">
          <h4 style={{ margin: "10px 0 6px" }}>
            Start here — matched to your profile ({rm.band})
          </h4>
          {rm.recommended.map((v) => (
            <ResourceRow key={v.id} v={v} />
          ))}
        </div>
      )}

      <ol className="rm-timeline">
        {rm.phases.map((p) => (
          <PhaseRow key={p.index} p={p} />
        ))}
      </ol>

      <div className="rm-certs">
        <h4 style={{ margin: "4px 0 8px" }}>Certifications for this track</h4>
        {(() => {
          const free = rm.certifications.filter((c) => c.free);
          const paid = rm.certifications.filter((c) => !c.free);
          return (
            <>
              <div className="chips" style={{ marginBottom: 8 }}>
                <Badge tone="good">{free.length} free to earn</Badge>
                <Badge>{paid.length} paid</Badge>
              </div>
              {free.map((c) => (
                <CertRow key={c.id} c={c} />
              ))}
              {paid.length > 0 && (
                <details className="rm-certs-more">
                  <summary>Show {paid.length} paid certifications</summary>
                  {paid.map((c) => (
                    <CertRow key={c.id} c={c} />
                  ))}
                </details>
              )}
            </>
          );
        })()}
        <p className="hint" style={{ marginTop: 8 }}>
          External recommendations — verify current pricing and availability before enrolling.
        </p>
      </div>

      {rm.notes.map((n, i) => (
        <p key={i} className="hint">
          {n}
        </p>
      ))}
      <p className="hint">Pace read: {PACE_BLURB[rm.pace]}.</p>
    </div>
  );
}

function PhaseRow({ p }: { p: RoadmapPhase }) {
  return (
    <li className="rm-phase">
      <div className="rm-phase-mark">{p.index}</div>
      <div className="rm-phase-body">
        <div className="rm-phase-title">
          {p.title}
          <span className="rm-phase-meta">
            {p.new_skills} skills · ~{Math.round(p.est_hours)} h · week {Math.round(p.start_week)}+
          </span>
        </div>
        <p className="rm-phase-focus">{p.focus}</p>
        <div className="chips">
          {p.concept_names.slice(0, 10).map((n) => (
            <span key={n} className="chip" style={{ cursor: "default" }}>
              {n}
            </span>
          ))}
          {p.concept_names.length > 10 && (
            <span className="chip" style={{ cursor: "default" }}>
              +{p.concept_names.length - 10}
            </span>
          )}
        </div>
        {p.videos.length > 0 && (
          <div className="rm-phase-videos">
            {p.videos.map((v) => (
              <ResourceRow key={v.id} v={v} />
            ))}
          </div>
        )}
        {p.certifications.map((c) => (
          <div key={c.id} className="rm-cert-inline">
            🎓 <strong>Ready to sit:</strong>{" "}
            <a href={c.url} target="_blank" rel="noreferrer">
              {c.name}
            </a>{" "}
            <span className="hint">
              — {c.provider}, {c.free ? "free" : c.price_note}
            </span>
          </div>
        ))}
      </div>
    </li>
  );
}

function ResourceRow({ v }: { v: LearnResource }) {
  const [playing, setPlaying] = useState(false);
  const canPlay = v.embed_url.length > 0;

  return (
    <div className="rm-res">
      <span className="rm-res-icon">{KIND_ICON[v.kind] ?? "•"}</span>
      <div style={{ minWidth: 0 }}>
        <span className="rm-res-title">
          {canPlay ? (
            <button
              type="button"
              className="linklike"
              onClick={() => setPlaying((p) => !p)}
              aria-expanded={playing}
            >
              {v.title}
            </button>
          ) : (
            <a href={v.url} target="_blank" rel="noreferrer">
              {v.title}
            </a>
          )}{" "}
          <span className="hint">
            — {v.channel}
            {v.minutes ? ` · ${Math.round(v.minutes / 60) || 1}h` : ""}
          </span>
        </span>
        {v.note && !playing && (
          <p className="hint" style={{ margin: "1px 0 0" }}>
            {v.note}
          </p>
        )}
        {canPlay && !playing && (
          <button type="button" className="rm-play" onClick={() => setPlaying(true)}>
            ▶ Watch here
          </button>
        )}
        {playing && (
          <div className="rm-embed">
            <iframe
              src={`${v.embed_url}${v.embed_url.includes("?") ? "&" : "?"}autoplay=1&rel=0`}
              title={v.title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              loading="lazy"
            />
            <button type="button" className="linklike rm-embed-close" onClick={() => setPlaying(false)}>
              close
            </button>{" "}
            <a href={v.url} target="_blank" rel="noreferrer" className="hint">
              open on YouTube ↗
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

function CertRow({ c }: { c: Certification }) {
  return (
    <div className="rm-cert">
      <div className="rm-cert-top">
        <a href={c.url} target="_blank" rel="noreferrer">
          {c.name}
        </a>
        <Badge tone={c.free ? "good" : "neutral"} mono>
          {c.free ? "free" : "paid"}
        </Badge>
        <Badge mono>{c.level}</Badge>
      </div>
      <p className="hint" style={{ margin: "2px 0" }}>
        {c.provider} · {c.blurb}
      </p>
      <p className="hint" style={{ margin: 0 }}>
        {c.price_note} · ~{Math.round(c.hours)} h
      </p>
    </div>
  );
}
