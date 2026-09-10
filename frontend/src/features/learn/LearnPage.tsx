import { useMemo, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { Button, Callout, Select, Spinner } from "../../components/ui";
import type { Band } from "../../lib/api";
import { useResolve } from "../../lib/queries";
import { AssessQuiz } from "./AssessQuiz";
import { PlanView } from "./PlanView";
import { RoadmapView } from "./RoadmapView";

type Step = "resolve" | "band" | "assess" | "plan";
type PlanTab = "roadmap" | "plan";

const BANDS: { value: Band; title: string; blurb: string }[] = [
  { value: "beginner", title: "Beginner", blurb: "New to this. The plan starts from the basics — we'll mostly go by what you told us." },
  { value: "intermediate", title: "Intermediate", blurb: "You know some of it. A short adaptive test confirms and refines where you are." },
  { value: "advanced", title: "Advanced", blurb: "Strong already. The test starts high and checks for the gaps." },
];

export function LearnPage() {
  const [params] = useSearchParams();
  const goal = (params.get("goal") ?? "").trim();
  const resolved = useResolve(goal);
  const [step, setStep] = useState<Step>("resolve");
  const [band, setBand] = useState<Band>("intermediate");
  const [minutes, setMinutes] = useState(150);
  const [speed, setSpeed] = useState<"slow" | "normal" | "fast">("normal");
  const [deadline, setDeadline] = useState("");
  const [hoursPerWeek, setHoursPerWeek] = useState(5);
  const [planTab, setPlanTab] = useState<PlanTab>("roadmap");

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
  const active: Step = (step === "band" || step === "assess") && !r.assessable ? "plan" : step;
  const stepNo = (s: Step) => (r.assessable ? { resolve: 1, band: 2, assess: 2, plan: 3 }[s] : { resolve: 1, band: 2, assess: 2, plan: 2 }[s]);

  return (
    <div>
      <div className="steps-nav">
        <span className={active !== "resolve" ? "done" : "b"}>1 · Goal</span> ›{" "}
        {r.assessable && (
          <>
            <span className={active === "plan" ? "done" : active !== "resolve" ? "b" : ""}>
              2 · Assess
            </span>{" "}
            ›{" "}
          </>
        )}
        <span className={active === "plan" ? "b" : ""}>{stepNo("plan")} · Plan</span>
      </div>

      {active === "resolve" && (
        <div className="panel" style={{ maxWidth: 640, margin: "0 auto" }}>
          <h2>
            {r.goals.map((g) => skillNames[g] ?? g).join(", ")}{" "}
            <span className="sub">
              —{" "}
              {r.source === "role"
                ? `${r.domain} role`
                : r.source === "seed"
                  ? `curated ${r.domain}`
                  : "built from Wikipedia"}{" "}
              graph, {r.concepts.length} concepts
            </span>
          </h2>
          <div className="chips" style={{ marginBottom: 18 }}>
            {r.concepts.slice(0, 22).map((c) => (
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
                max={600}
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
            <label style={{ fontSize: 12, color: "var(--ink-2)" }}>
              Hours per week
              <input
                type="range"
                min={1}
                max={30}
                step={1}
                value={hoursPerWeek}
                onChange={(e) => setHoursPerWeek(Number(e.target.value))}
                style={{ display: "block", width: 160 }}
              />
              <span style={{ fontFamily: "var(--mono)" }}>{hoursPerWeek} h/week</span>
            </label>
          </div>

          <details className="deadline-box" style={{ marginTop: 16 }}>
            <summary>Have a deadline?</summary>
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 10 }}>
              <label style={{ fontSize: 12, color: "var(--ink-2)" }}>
                Target date
                <input
                  type="date"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  style={{ display: "block", marginTop: 4 }}
                />
              </label>
            </div>
            <p className="hint">
              We’ll place every step — and spaced reinforcements — on real dates so each goal skill
              is above the mastery threshold on your date, or tell you exactly what it would take.
            </p>
          </details>

          <Button
            variant="primary"
            className="big"
            style={{ marginTop: 20 }}
            onClick={() => setStep(r.assessable ? "band" : "plan")}
          >
            {r.assessable ? "Continue →" : "Build my plan →"}
          </Button>
          {!r.assessable && (
            <p className="hint">
              No calibrated diagnostic for this domain yet — the plan starts from Bayesian
              cold-start priors and adapts as you log attempts.
            </p>
          )}
        </div>
      )}

      {active === "band" && (
        <div className="quiz">
          <h2 style={{ marginBottom: 6 }}>How much do you already know?</h2>
          <p className="hint" style={{ marginBottom: 18 }}>
            Pick where you think you are. It sets where the adaptive test starts — and for a
            beginner, it does most of the work.
          </p>
          <div className="choices">
            {BANDS.map((b) => (
              <button
                key={b.value}
                className="choice"
                aria-pressed={band === b.value}
                onClick={() => {
                  setBand(b.value);
                  setStep("assess");
                }}
              >
                <strong>{b.title}</strong>
                <div className="hint" style={{ margin: "4px 0 0" }}>
                  {b.blurb}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {active === "assess" && (
        <AssessQuiz
          goalText={goal}
          goals={r.goals}
          band={band}
          skillNames={skillNames}
          onDone={() => setStep("plan")}
        />
      )}

      {active === "plan" && (
        <div className="panel">
          <div className="seg" role="tablist" style={{ marginBottom: 16 }}>
            <button
              role="tab"
              aria-selected={planTab === "roadmap"}
              className={planTab === "roadmap" ? "on" : ""}
              onClick={() => setPlanTab("roadmap")}
            >
              Full roadmap
            </button>
            <button
              role="tab"
              aria-selected={planTab === "plan"}
              className={planTab === "plan" ? "on" : ""}
              onClick={() => setPlanTab("plan")}
            >
              Study plan
            </button>
          </div>

          {planTab === "roadmap" ? (
            <RoadmapView goalText={goal} weeklyHours={hoursPerWeek} deadline={deadline} />
          ) : (
            <PlanView
              goalText={goal}
              goals={r.goals}
              minutes={minutes}
              speed={speed}
              deadline={deadline}
              hoursPerWeek={hoursPerWeek}
            />
          )}
        </div>
      )}
    </div>
  );
}
