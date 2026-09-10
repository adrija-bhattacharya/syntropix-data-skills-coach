import { useMemo, useReducer, useState } from "react";

import { ParetoChart } from "../../components/ParetoChart";
import { PathCard } from "../../components/PathCard";
import { Badge, Callout, Empty, Spinner } from "../../components/ui";
import type { Catalogue, RecommendInput } from "../../lib/api";
import { useRecommend } from "../../lib/queries";
import { ConstraintBuilder } from "./ConstraintBuilder";
import { constraintReducer, initialConstraints, toRecommendInput } from "./constraintReducer";

export function TeacherPage({ catalogue }: { catalogue: Catalogue }) {
  const [state, dispatch] = useReducer(constraintReducer, initialConstraints, (init) => ({
    ...init,
    goals: catalogue.goals.slice(0, 1),
  }));
  const [submitted, setSubmitted] = useState(false);
  const [selected, setSelected] = useState(0);

  const input = useMemo<RecommendInput>(() => toRecommendInput(state), [state]);
  const query = useRecommend(input, submitted);
  const paths = query.data?.paths ?? [];
  const active = paths[Math.min(selected, Math.max(0, paths.length - 1))];

  return (
    <div className="grid">
      <ConstraintBuilder
        catalogue={catalogue}
        state={state}
        dispatch={dispatch}
        onSolve={() => {
          setSubmitted(true);
          setSelected(0);
        }}
        busy={query.isFetching}
      />

      <section className="panel">
        <h2>
          Pareto front {query.isFetching && <Spinner />}
          {paths.length > 0 && <Badge>{paths.length} non-dominated</Badge>}
        </h2>

        {!submitted && <Empty>Set constraints and re-solve to see the trade-off front.</Empty>}
        {query.isError && <Callout tone="warn">{query.error.message}</Callout>}
        {submitted && !query.isError && paths.length === 0 && !query.isFetching && (
          <Callout tone="warn">
            {String(query.data?.meta.infeasible_reason ?? "No feasible plan under these constraints.")}
          </Callout>
        )}

        {paths.length > 0 && active && (
          <>
            <ParetoChart paths={paths} selected={selected} onSelect={setSelected} />
            <p className="hint">Click a point to inspect that path. Bubble size = cognitive load.</p>
            <PathCard path={active} catalogue={catalogue} learnerId="teacher" />
          </>
        )}
      </section>
    </div>
  );
}
