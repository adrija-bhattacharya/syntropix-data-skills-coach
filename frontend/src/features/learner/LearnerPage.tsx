import { useMemo, useState } from "react";

import { PathCard } from "../../components/PathCard";
import { Callout, Empty, Spinner } from "../../components/ui";
import { useLearner } from "../../context/LearnerContext";
import type { Catalogue, RecommendInput } from "../../lib/api";
import { useRecommend } from "../../lib/queries";
import { ObservePanel } from "./ObservePanel";
import { RecommendForm, type RecommendFormState } from "./RecommendForm";

export function LearnerPage({ catalogue }: { catalogue: Catalogue }) {
  const { learnerId } = useLearner();
  const [form, setForm] = useState<RecommendFormState>(() => ({
    goals: catalogue.goals.slice(0, 1),
    budgetMin: 120,
    mode: "sequence",
    speed: "normal",
  }));
  const [submitted, setSubmitted] = useState(false);

  const input = useMemo<RecommendInput>(
    () => ({
      learner_id: learnerId,
      goals: form.goals,
      time_budget_min: form.budgetMin,
      mode: form.mode,
      speed: form.speed,
    }),
    [learnerId, form],
  );

  const query = useRecommend(input, submitted);
  const plan = query.data?.paths[0];

  return (
    <div className="grid">
      <div className="stack">
        <RecommendForm
          catalogue={catalogue}
          state={form}
          onChange={(patch) => setForm((f) => ({ ...f, ...patch }))}
          onSubmit={() => setSubmitted(true)}
          busy={query.isFetching}
        />
        <ObservePanel catalogue={catalogue} />
      </div>

      <section className="panel">
        <h2>
          Plan {query.isFetching && <Spinner />}
          {query.data?.meta.speed && <span className="sub"> · speed: {String(query.data.meta.speed)}</span>}
        </h2>
        {!submitted && <Empty>Pick goal concepts and press Recommend.</Empty>}
        {query.isError && <Callout tone="warn">{query.error.message}</Callout>}
        {submitted && !query.isError && !plan && !query.isFetching && (
          <Empty>No plan returned.</Empty>
        )}
        {plan && <PathCard path={plan} catalogue={catalogue} learnerId={learnerId} />}
      </section>
    </div>
  );
}
