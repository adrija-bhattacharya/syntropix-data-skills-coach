import { Ms, Pill } from "../../components/stitch";
import type { Library } from "../../lib/api";
import { PACE_LABEL, type Pace } from "../../lib/library";

/** "How fast do you learn?" - measured from your practice, or chosen. */
export function PaceBar({ data, pace, setPace }: { data: Library; pace: Pace; setPace: (p: Pace) => void }) {
  return (
    <section className="flex flex-wrap items-center justify-between gap-space-sm p-space-md rounded-xl bg-surface-container-low">
      <div className="flex items-start gap-space-sm max-w-2xl">
        <Ms name="speed" className="text-secondary mt-0.5" />
        <div className="flex flex-col">
          <span className="font-body-strong text-body-sm">
            Your pace: {PACE_LABEL[data.pace]}{" "}
            <span className="font-label-annotation text-label-annotation text-outline">({data.pace_source === "measured" ? "measured from your practice" : data.pace_source})</span>
          </span>
          <span className="font-body-sm text-body-sm text-on-surface-variant">{data.pace_text}</span>
        </div>
      </div>
      <div className="flex items-center gap-space-xs" role="radiogroup" aria-label="Pace">
        {(["auto", "deliberate", "steady", "fast"] as const).map((p) => (
          <button
            key={p}
            type="button"
            role="radio"
            aria-checked={pace === p}
            onClick={() => setPace(p)}
            className={`px-space-sm py-1 rounded font-label-badge text-label-badge ${pace === p ? "bg-primary text-on-primary" : "bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant"}`}
          >
            {PACE_LABEL[p]}
          </button>
        ))}
        <Pill tone="neutral" className="hidden md:inline-flex">{data.totals.weeks ?? 0} weeks of practice</Pill>
      </div>
    </section>
  );
}
