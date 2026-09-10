import { useMemo, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { Button, Callout, Select, Spinner } from "../../components/ui";
import { useResolve } from "../../lib/queries";
import { AssessQuiz } from "./AssessQuiz";
import { PlanView } from "./PlanView";

type Step = "resolve" | "assess" | "plan";

export function LearnPage() {
  const [params] = useSearchParams();
  const goal = (params.get("goal") ?? "").trim();
  const resolved = useResolve(goal);
  const [step, setStep] = useState<Step>("resolve");
  const [minutes, setMinutes] = useState(150);
  const [speed, setSpeed] = useState<"slow" | "normal" | "fast">("normal");

  const skillNames = useMemo(() => {
    const m: Record<string, string> = {};
    for (const c of resolved.data?.concepts ?? []) m[c.id] = c.name;
    return m;
  }, [resolved.data]);

  if (!goal) return <Navigate to="/" replace />;
  if (resolved.isPending) return <Spinner label={`Resolving "${goal}"…`} />;
  if (resolved.isError)
    return (
      <Callout tone="warn">
        Couldn’t resolve “{goal}”. {resolved.error.message}
      </Callout>
    );

  const r = resolved.data;
  const active: Step = step === "assess" && !r.assessable ? "plan" : step;

  return (
    <div>
      <div className="steps-nav">
        <span className={active !== "resolve" ? "done" : "b"}>1 · Goal</span> ›{" "}
        {r.assessable && (
          <>
            <span className={active === "plan" ? "done" : active === "assess" ? "b" : ""}>
              2 · Assess
            </span>{" "}
            ›{" "}
          </>
        )}
        <span className={active === "plan" ? "b" : ""}>{r.assessable ? "3" : "2"} · Plan</span>
      </div>

      {active === "resolve" && (
        <div className="panel" style={{ maxWidth: 640, margin: "0 auto" }}>
          <h2>
            {r.goals.map((g) => skillNames[g] ?? g).join(", ")}{" "}
            <span className="sub">
              — {r.source === "seed" ? `curated ${r.domain}` : "built from Wikipedia"} graph,{" "}
              {r.concepts.length} concepts
            </span>
          </h2>
          <div className="chips" style={{ marginBottom: 18 }}>
            {r.concepts.slice(0, 18).map((c) => (
              <span key={c.id} className="chip" style={{ cursor: "default" }}>
                {c.name}
              </span>
            ))}
          </div>

          <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
            <label style={{ fontSize: 12, color: "var(--ink-2)" }}>
              Time budget
              <input
                type="range"
                min={30}
                max={480}
                step={10}
                value={minutes}
                onChange={(e) => setMinutes(Number(e.target.value))}
                style={{ display: "block", width: 180 }}
              />
              <span style={{ fontFamily: "var(--mono)" }}>{minutes} min</span>
            </label>
            <label style={{ fontSize: 12, color: "var(--ink-2)" }}>
              Learning speed
              <Select
                value={speed}
                onChange={setSpeed}
                options={[
                  { value: "slow", label: "take it slow" },
                  { value: "normal", label: "normal" },
                  { value: "fast", label: "move fast" },
                ]}
                style={{ display: "block", marginTop: 4 }}
              />
            </label>
          </div>

          <Button
            variant="primary"
            className="big"
            style={{ marginTop: 20 }}
            onClick={() => setStep(r.assessable ? "assess" : "plan")}
          >
            {r.assessable ? "Take the 2-minute assessment →" : "Build my plan →"}
          </Button>
          {!r.assessable && (
            <p className="hint">
              No calibrated diagnostic for this domain yet — the plan starts from Bayesian
              cold-start priors and adapts as you log attempts.
            </p>
          )}
        </div>
      )}

      {active === "assess" && (
        <AssessQuiz goals={r.goals} skillNames={skillNames} onDone={() => setStep("plan")} />
      )}

      {active === "plan" && (
        <div className="panel">
          <PlanView goalText={goal} goals={r.goals} minutes={minutes} speed={speed} />
        </div>
      )}
    </div>
  );
}
