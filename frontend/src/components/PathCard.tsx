import { memo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Catalogue, Path } from "../lib/api";
import { OBJECTIVE_KEYS, OBJECTIVE_META, num } from "../lib/format";
import { useExplain } from "../lib/queries";
import { Badge, Button, Callout } from "./ui";

export const PathCard = memo(function PathCard({
  path,
  catalogue,
  learnerId,
}: {
  path: Path;
  catalogue: Catalogue;
  learnerId: string;
}) {
  if (!path.feasible) {
    return (
      <Callout tone="warn">
        <strong>No feasible plan.</strong> {path.note || "The time budget cannot fit the prerequisite closure."}
      </Callout>
    );
  }
  if (path.steps.length === 0) return <Callout>Goal already satisfied — nothing to study.</Callout>;

  const byId = new Map(catalogue.resources.map((r) => [r.id, r]));
  const curve = path.steps.map((s, i) => ({
    i: i + 1,
    difficulty: byId.get(s.resource_id)?.difficulty ?? 0,
  }));

  const reviews = path.steps.filter((s) => s.review).length;
  const sessionAt = new Map(path.sessions.map((s, k) => [s.start, k + 1]));

  return (
    <div>
      <div className="plan-head">
        <span className="title">{path.steps.length} steps</span>
        <Badge mono>~{Math.round(path.total_minutes)} min</Badge>
        {path.sessions.length > 0 && <Badge>{path.sessions.length} sessions</Badge>}
        {reviews > 0 && <Badge tone="good">{reviews} spaced review{reviews === 1 ? "" : "s"}</Badge>}
        <Badge tone="good">prerequisite-valid</Badge>
      </div>
      {path.note && <p className="hint">{path.note}</p>}

      <div className="chart-wrap" style={{ height: 96 }} aria-hidden>
        <ResponsiveContainer>
          <LineChart data={curve} margin={{ top: 6, right: 8, bottom: 0, left: -24 }}>
            <XAxis dataKey="i" tick={{ fontSize: 10 }} stroke="var(--muted)" />
            <YAxis width={30} tick={{ fontSize: 10 }} stroke="var(--muted)" domain={[0, "dataMax + 1"]} />
            <Tooltip
              contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", fontSize: 12 }}
              formatter={(v: number) => [v, "difficulty"]}
              labelFormatter={(l) => `step ${l}`}
            />
            <Line
              type="monotone"
              dataKey="difficulty"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={{ r: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="hint">
        Difficulty across the plan — the sequencing DP balances smooth jumps against
        keeping prerequisites fresh.
      </p>

      <ol className="steps">
        {path.steps.map((s, i) => (
          <Step
            key={`${s.resource_id}-${i}`}
            step={s}
            index={i + 1}
            resource={byId.get(s.resource_id)}
            learnerId={learnerId}
            session={sessionAt.get(i)}
          />
        ))}
      </ol>

      <div className="objgrid">
        {OBJECTIVE_KEYS.map((k) => {
          const meta = OBJECTIVE_META[k];
          return (
            <div className="cell" key={k}>
              <div className="k">
                {meta.label} {meta.better === "higher" ? "↑" : "↓"}
              </div>
              <div className="v">
                {num(meta.transform(path.objective[k]))}
                {meta.unit ? ` ${meta.unit}` : ""}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});

function Step({
  step,
  index,
  resource,
  learnerId,
  session,
}: {
  step: Path["steps"][number];
  index: number;
  resource: Catalogue["resources"][number] | undefined;
  learnerId: string;
  session: number | undefined;
}) {
  const explain = useExplain();
  const [open, setOpen] = useState(false);

  return (
    <>
      {session != null && (
        <li className="session-divider" aria-hidden>
          Session {session}
        </li>
      )}
      <li className={step.review ? "is-review" : undefined} data-step={index}>
        <div className="step-title">
          <span className="mono">{step.resource_id}</span>
          {step.review && <Badge tone="good">review</Badge>}
          {resource && !step.review && (
            <Badge>
              {resource.kind} · difficulty {resource.difficulty}
            </Badge>
          )}
          <Button
            variant="ghost"
            style={{ marginLeft: "auto", padding: "2px 8px", fontSize: 12 }}
            aria-expanded={open}
            onClick={() => {
              setOpen((v) => !v);
              if (!open && !explain.data)
                explain.mutate({ learnerId, resourceId: step.resource_id });
            }}
          >
            why?
          </Button>
        </div>
        <div className="step-reason" dangerouslySetInnerHTML={{ __html: mdBold(step.reason) }} />
        {open && (
          <div className="step-reason" style={{ marginTop: 6, fontStyle: "italic" }}>
            {explain.isPending && "…"}
            {explain.error && (
              <span style={{ color: "var(--warn)" }}>could not load explanation</span>
            )}
            {explain.data && (
              <span dangerouslySetInnerHTML={{ __html: mdBold(explain.data.reason) }} />
            )}
          </div>
        )}
      </li>
    </>
  );
}

/** the API returns `**bold**` markers in reason strings - render just those. */
function mdBold(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}
