import { useMemo } from "react";

import { ResourceCard } from "../../components/ResourceCard";
import { Badge, Callout, Spinner } from "../../components/ui";
import { useLearner } from "../../context/LearnerContext";
import type { Path, RecommendInput, RoleMeta } from "../../lib/api";
import { roleMeta } from "../../lib/api";
import { OBJECTIVE_KEYS, OBJECTIVE_META, num } from "../../lib/format";
import { useRecommend } from "../../lib/queries";

export function PlanView({
  goalText,
  goals,
  minutes,
  speed,
}: {
  goalText: string;
  goals: string[];
  minutes: number;
  speed: "slow" | "normal" | "fast";
}) {
  const { learnerId } = useLearner();
  const input = useMemo<RecommendInput>(
    () => ({
      learner_id: learnerId,
      goal: goalText,
      goals,
      time_budget_min: minutes,
      mode: "sequence",
      speed,
    }),
    [learnerId, goalText, goals, minutes, speed],
  );
  const q = useRecommend(input, true);
  const plan = q.data?.paths[0];

  if (q.isPending) return <Spinner label="Sequencing your plan…" />;
  if (q.isError) return <Callout tone="warn">{q.error.message}</Callout>;
  if (!plan) return <Callout tone="warn">No plan returned.</Callout>;
  if (!plan.feasible)
    return <Callout tone="warn">No feasible plan: {plan.note || "the budget is too tight."}</Callout>;

  const role = q.data ? roleMeta(q.data.meta) : null;

  return (
    <div>
      {role && <RoleReadiness role={role} />}
      <PlanBody plan={plan} learnerId={learnerId} />
    </div>
  );
}

function RoleReadiness({ role }: { role: RoleMeta }) {
  const before = Math.round(role.readiness_before * 100);
  const after = Math.round(role.readiness * 100);
  const curve = role.readiness_curve;
  const maxMin = curve.at(-1)?.[0] || 1;
  return (
    <div className="quiz-card" style={{ marginBottom: 18 }}>
      <span className="skill">{role.domain} · hiring readiness</span>
      <div className="stem" style={{ fontSize: 18, margin: "8px 0 14px" }}>
        {before}% → <span style={{ color: "var(--accent-2)" }}>{after}%</span>{" "}
        <span className="sub" style={{ fontSize: 13 }}>after this plan</span>
      </div>
      <div className="meter" style={{ gridTemplateColumns: "1fr" }}>
        <div className="track" style={{ height: 10 }}>
          <div className="fill" style={{ width: `${after}%` }} />
        </div>
      </div>
      <svg viewBox="0 0 300 44" style={{ width: "100%", marginTop: 12, opacity: 0.9 }} aria-hidden>
        <polyline
          fill="none"
          stroke="var(--accent)"
          strokeWidth="2"
          points={curve.map(([m, r]) => `${(m / maxMin) * 300},${44 - r * 40}`).join(" ")}
        />
      </svg>
      <p className="hint">
        Readiness climbs as you cover the skills this role weights most — stop any time and you
        still know where you stand. ({role.method === "greedy" ? "value-density fill" : "exact"})
      </p>
    </div>
  );
}

function PlanBody({ plan, learnerId }: { plan: Path; learnerId: string }) {
  const sessionStart = new Map(plan.sessions.map((s, i) => [s.start, i + 1]));
  const nReviews = plan.steps.filter((s) => s.review).length;

  return (
    <div>
      <div className="plan-head">
        <span className="n">{plan.steps.length} steps</span>
        <Badge mono>~{Math.round(plan.total_minutes)} min</Badge>
        <Badge tone="good">prerequisite-valid</Badge>
        {plan.sessions.length > 1 && <Badge>{plan.sessions.length} sessions</Badge>}
        {nReviews > 0 && <Badge tone="good">{nReviews} spaced reviews</Badge>}
      </div>

      {plan.steps.map((s, i) => (
        <div key={`${s.resource_id}-${i}`}>
          {sessionStart.has(i) && (
            <div className="session-label">session {sessionStart.get(i)}</div>
          )}
          <ResourceCard step={s} learnerId={learnerId} />
        </div>
      ))}

      <div className="objgrid">
        {OBJECTIVE_KEYS.map((k) => {
          const m = OBJECTIVE_META[k];
          return (
            <div className="cell" key={k}>
              <div className="k">
                {m.label} {m.better === "higher" ? "↑" : "↓"}
              </div>
              <div className="v">
                {num(m.transform(plan.objective[k]))}
                {m.unit ? ` ${m.unit}` : ""}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
