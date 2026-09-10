import { useState } from "react";

import { Badge, Button, Callout, Field, Select } from "../../components/ui";
import { useLearner } from "../../context/LearnerContext";
import type { Catalogue } from "../../lib/api";
import { useObserve } from "../../lib/queries";

export function ObservePanel({ catalogue }: { catalogue: Catalogue }) {
  const { learnerId } = useLearner();
  const observe = useObserve(learnerId);
  const [resourceId, setResourceId] = useState(catalogue.resources[0]?.id ?? "");
  const [correct, setCorrect] = useState(true);
  const [minutes, setMinutes] = useState(8);

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault();
        observe.mutate({ resource_id: resourceId, correct, minutes });
      }}
    >
      <h2>
        Log an attempt <span className="sub">— updates BKT · velocity · DKT-lite</span>
      </h2>

      <Field label="Resource" htmlFor="obs-res">
        <Select
          value={resourceId}
          onChange={setResourceId}
          options={catalogue.resources.map((r) => ({ value: r.id, label: r.id }))}
        />
      </Field>

      <Field label="Minutes" value={minutes} htmlFor="obs-min">
        <input
          id="obs-min"
          type="range"
          min={1}
          max={30}
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
        />
      </Field>

      <label style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 14 }}>
        <input type="checkbox" checked={correct} onChange={(e) => setCorrect(e.target.checked)} />
        answered correctly
      </label>

      <Button type="submit" disabled={observe.isPending || !resourceId}>
        {observe.isPending ? "recording…" : "Submit attempt"}
      </Button>

      {observe.isError && <div style={{ marginTop: 10 }}><Callout tone="warn">{observe.error.message}</Callout></div>}
      {observe.data && (
        <p className="hint" style={{ marginTop: 10 }}>
          Recorded · {observe.data.n_interactions} interaction(s) ·{" "}
          <Badge mono>mean velocity {observe.data.mean_velocity.toFixed(2)}</Badge> · the plan above
          re-solved automatically.
        </p>
      )}
    </form>
  );
}
