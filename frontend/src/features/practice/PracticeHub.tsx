import { useSearchParams } from "react-router-dom";

import { Ms } from "../../components/stitch";
import { PracticePage } from "./PracticePage";
import { ProblemSets } from "./ProblemSets";

/** Practice: built-in tasks checked instantly, and real problem sets elsewhere. */
export function PracticeHub() {
  const [params, setParams] = useSearchParams();
  const sets = params.get("tab") === "sets";
  const tab = (on: boolean) =>
    `px-space-md py-2 rounded-lg flex items-center gap-1.5 font-body-strong text-body-sm ${on ? "bg-primary text-on-primary" : "bg-surface-container-low hover:bg-surface-container text-on-surface-variant"}`;
  return (
    <div className="flex flex-col gap-space-md">
      <header className="flex flex-wrap items-end justify-between gap-space-sm">
        <div className="flex flex-col gap-space-xs">
          <h1 className="font-headline-md text-headline-md">Practice</h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
            {sets
              ? "Real problems from LeetCode, HackerRank and free sites, in the order your plan needs them and paced to how fast you learn."
              : "Answer right here and get it checked instantly. If you get it wrong, you'll see what went wrong and what to fix first."}
          </p>
        </div>
        <div role="tablist" aria-label="Practice type" className="flex gap-space-xs">
          <button type="button" role="tab" aria-selected={!sets} onClick={() => setParams({})} className={tab(!sets)}>
            <Ms name="bolt" size={18} /> Practise here
          </button>
          <button type="button" role="tab" aria-selected={sets} onClick={() => setParams({ tab: "sets" })} className={tab(sets)}>
            <Ms name="code" size={18} /> LeetCode, HackerRank &amp; more
          </button>
        </div>
      </header>
      {sets ? <ProblemSets /> : <PracticePage />}
    </div>
  );
}
