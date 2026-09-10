import { useMemo } from "react";

import { Badge, Callout, Spinner } from "../../components/ui";
import { useLearner } from "../../context/LearnerContext";
import type { Certification, RoadmapInput, RoadmapPhase } from "../../lib/api";
import { useRoadmap } from "../../lib/queries";

const PACE_BLURB: Record<string, string> = {
  deliberate: "measured — you get extra time per topic",
  steady: "steady — an average learning speed",
  fast: "fast — your velocity shortens the estimates",
};

export function RoadmapView({
  goalText,
  weeklyHours,
  deadline,
}: {
  goalText: string;
  weeklyHours: number;
  deadline?: string;
}) {
  const { learnerId } = useLearner();
  const input = useMemo<RoadmapInput>(
    () => ({
      learner_id: learnerId,
      goal: goalText,
      weekly_hours: weeklyHours,
      deadline: deadline || undefined,
    }),
    [learnerId, goalText, weeklyHours, deadline],
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

      <ol className="rm-timeline">
        {rm.phases.map((p) => (
          <PhaseRow key={p.index} p={p} />
        ))}
      </ol>

      <div className="rm-certs">
        <h4 style={{ margin: "4px 0 8px" }}>Certifications for this track</h4>
        <div className="chips" style={{ marginBottom: 8 }}>
          <Badge tone="good">
            {rm.certifications.filter((c) => c.free).length} free to earn
          </Badge>
          <Badge>{rm.certifications.length} total</Badge>
        </div>
        {rm.certifications.map((c) => (
          <CertRow key={c.id} c={c} />
        ))}
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
