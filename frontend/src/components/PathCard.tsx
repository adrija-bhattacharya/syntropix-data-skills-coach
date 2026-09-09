import type { Catalogue, Path } from "../api";
import { OBJ_LABELS } from "../api";

export function PathCard({ path, catalogue }: { path: Path; catalogue: Catalogue }) {
  if (!path.feasible) {
    return (
      <div className="card warn">
        <strong>No feasible plan.</strong> {path.note}
      </div>
    );
  }
  if (path.steps.length === 0) return <div className="card">Goal already satisfied.</div>;
  const res = new Map(catalogue.resources.map((r) => [r.id, r]));

  return (
    <div className="card">
      <div className="path-head">
        {path.steps.length} steps &middot; ~{Math.round(path.total_minutes)} min
      </div>
      <ol className="steps">
        {path.steps.map((s, i) => {
          const r = res.get(s.resource_id);
          return (
            <li key={i}>
              <div className="step-title">
                <span className="mono">{s.resource_id}</span>
                {r && (
                  <span className="tag">
                    {r.kind} &middot; difficulty {r.difficulty}
                  </span>
                )}
              </div>
              <div className="reason">{s.reason}</div>
            </li>
          );
        })}
      </ol>
      <div className="obj">
        {Object.entries(path.objective).map(([k, v]) => (
          <span key={k} className="obj-chip">
            {OBJ_LABELS[k] ?? k}: {v >= 0 ? "+" : ""}
            {v.toFixed(2)}
          </span>
        ))}
      </div>
    </div>
  );
}
