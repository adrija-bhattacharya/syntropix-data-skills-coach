import { Link } from "react-router-dom";

import { ErrorBox, Loading, Ms } from "../../components/stitch";
import { usePlan } from "../../lib/plan";

/** Shared guard: every planning screen needs a goal (set on the opening page or Skill Map). */
export function NeedGoal() {
  return (
    <div className="max-w-xl mx-auto mt-space-xl p-space-lg rounded-xl bg-surface-container shadow-md flex flex-col gap-space-md items-start">
      <span className="w-10 h-10 rounded-lg bg-primary/15 text-primary flex items-center justify-center">
        <Ms name="flag" />
      </span>
      <h1 className="font-headline-md text-headline-md">Set a goal first</h1>
      <p className="font-body-md text-body-md text-on-surface-variant">
        Tell Syntropix what you want to learn or become (for example “data analyst” or “SQL”).
        Your plan, videos and practice are all built from that goal.
      </p>
      <Link
        to="/"
        className="px-space-md py-2 rounded-lg bg-primary text-on-primary font-body-strong text-body-sm flex items-center gap-1.5"
      >
        Choose a goal <Ms name="arrow_forward" size={16} />
      </Link>
    </div>
  );
}

/** Loading / error / no-goal states for screens built on `usePlan()`. */
export function planGate(p: ReturnType<typeof usePlan>) {
  if (!p.track.goal) return <NeedGoal />;
  if (p.resolved.isPending) return <Loading label={`Resolving "${p.track.goal}"…`} />;
  if (p.resolved.isError) return <ErrorBox>Couldn't resolve "{p.track.goal}": {p.resolved.error.message}</ErrorBox>;
  if (p.rec.isPending) return <Loading label="Sequencing your plan…" />;
  if (p.rec.isError) return <ErrorBox>{p.rec.error.message}</ErrorBox>;
  if (!p.plan) return <ErrorBox>No plan returned.</ErrorBox>;
  if (!p.plan.feasible)
    return (
      <ErrorBox>
        No plan fits the time budget: {p.plan.note || "it is too tight"}. Raise the budget on the
        Skill Map page.
      </ErrorBox>
    );
  return null;
}
