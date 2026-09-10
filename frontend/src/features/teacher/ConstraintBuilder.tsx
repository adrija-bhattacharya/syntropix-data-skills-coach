import { useMemo, type Dispatch } from "react";

import { ChipSelect } from "../../components/ChipSelect";
import { Button, Field, Select, Spinner } from "../../components/ui";
import type { Catalogue } from "../../lib/api";
import type { ConstraintAction, ConstraintState } from "./constraintReducer";

export function ConstraintBuilder({
  catalogue,
  state,
  dispatch,
  onSolve,
  busy,
}: {
  catalogue: Catalogue;
  state: ConstraintState;
  dispatch: Dispatch<ConstraintAction>;
  onSolve: () => void;
  busy: boolean;
}) {
  const conceptOptions = useMemo(
    () => catalogue.concepts.map((c) => ({ value: c.id, label: c.name })),
    [catalogue],
  );
  const resourceOptions = useMemo(
    () => catalogue.resources.map((r) => ({ value: r.id, label: r.id })),
    [catalogue],
  );
  const conceptSelect = [{ value: "", label: "—" }, ...conceptOptions];

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault();
        onSolve();
      }}
    >
      <h2>
        Constraints <span className="sub">— hard, the solver re-solves</span>
      </h2>

      <ChipSelect
        label="Goal concepts"
        options={conceptOptions}
        selected={state.goals}
        onChange={(goals) => dispatch({ type: "setGoals", goals })}
      />

      <Field label="Time budget" value={`${state.budgetMin} min`} htmlFor="t-budget">
        <input
          id="t-budget"
          type="range"
          min={20}
          max={420}
          step={5}
          value={state.budgetMin}
          onChange={(e) => dispatch({ type: "setBudget", minutes: Number(e.target.value) })}
        />
      </Field>

      <ChipSelect
        label="Ban resources"
        options={resourceOptions}
        selected={state.ban}
        onChange={(ban) => dispatch({ type: "setBan", ban })}
      />
      <ChipSelect
        label="Lock resources"
        options={resourceOptions}
        selected={state.lock}
        onChange={(lock) => dispatch({ type: "setLock", lock })}
      />

      <Field label="Force order" hint="Adds a prerequisite edge; rejected if it makes a cycle.">
        <div className="row">
          <Select
            aria-label="before"
            value={state.before}
            onChange={(before) => dispatch({ type: "setForce", before })}
            options={conceptSelect}
          />
          <span className="hint" style={{ whiteSpace: "nowrap" }}>
            before
          </span>
          <Select
            aria-label="after"
            value={state.after}
            onChange={(after) => dispatch({ type: "setForce", after })}
            options={conceptSelect}
          />
        </div>
      </Field>

      <Field label="Paths to return" value={state.nPaths} htmlFor="t-npaths">
        <input
          id="t-npaths"
          type="range"
          min={2}
          max={20}
          value={state.nPaths}
          onChange={(e) => dispatch({ type: "setNPaths", n: Number(e.target.value) })}
        />
      </Field>

      <div className="row">
        <Button type="submit" variant="primary" disabled={busy || state.goals.length === 0}>
          {busy ? <Spinner label="re-solving…" /> : "Re-solve under constraints"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => dispatch({ type: "reset" })}>
          Reset
        </Button>
      </div>
    </form>
  );
}
