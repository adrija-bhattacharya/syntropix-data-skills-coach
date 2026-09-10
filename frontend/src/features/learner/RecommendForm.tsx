import { useMemo } from "react";

import { ChipSelect } from "../../components/ChipSelect";
import { Button, Field, Select, Spinner } from "../../components/ui";
import { useLearner } from "../../context/LearnerContext";
import type { Catalogue, SolverMode, Speed } from "../../lib/api";

export interface RecommendFormState {
  goals: string[];
  budgetMin: number;
  mode: Exclude<SolverMode, "pareto">;
  speed: Speed;
}

export function RecommendForm({
  catalogue,
  state,
  onChange,
  onSubmit,
  busy,
}: {
  catalogue: Catalogue;
  state: RecommendFormState;
  onChange: (patch: Partial<RecommendFormState>) => void;
  onSubmit: () => void;
  busy: boolean;
}) {
  const { learnerId, setLearnerId } = useLearner();
  const conceptOptions = useMemo(
    () => catalogue.concepts.map((c) => ({ value: c.id, label: c.name })),
    [catalogue],
  );

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <h2>Get a path</h2>

      <Field label="Learner id" htmlFor="learner-id">
        <input
          id="learner-id"
          value={learnerId}
          onChange={(e) => setLearnerId(e.target.value || "demo")}
        />
      </Field>

      <ChipSelect
        label="Goal concepts"
        options={conceptOptions}
        selected={state.goals}
        onChange={(goals) => onChange({ goals })}
      />

      <Field label="Time budget" value={`${state.budgetMin} min`} htmlFor="budget">
        <input
          id="budget"
          type="range"
          min={20}
          max={360}
          step={5}
          value={state.budgetMin}
          onChange={(e) => onChange({ budgetMin: Number(e.target.value) })}
        />
      </Field>

      <Field label="Solver" htmlFor="mode">
        <Select
          id="mode"
          value={state.mode}
          onChange={(mode) => onChange({ mode })}
          options={[
            { value: "sequence", label: "sequence — order-ideal DP (+ review + sessions)" },
            { value: "optimal", label: "selection — multiple-choice knapsack" },
            { value: "interactive", label: "interactive — anytime A*" },
          ]}
        />
      </Field>

      <Field
        label="Learning speed (N2)"
        hint="Scales the learner's per-concept velocity — a fast learner gets a fuller, lesson-heavy plan."
        htmlFor="speed"
      >
        <Select
          id="speed"
          value={state.speed}
          onChange={(speed) => onChange({ speed })}
          options={[
            { value: "slow", label: "slow learner" },
            { value: "normal", label: "normal" },
            { value: "fast", label: "fast learner" },
          ]}
        />
      </Field>

      <Button type="submit" variant="primary" disabled={busy || state.goals.length === 0}>
        {busy ? <Spinner label="solving…" /> : "Recommend"}
      </Button>
    </form>
  );
}
