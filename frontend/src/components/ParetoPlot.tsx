import type { Path } from "../api";

// dependency-free SVG scatter: x = time, y = mastery gain, colour = load
export function ParetoPlot({
  paths,
  selected,
  onSelect,
}: {
  paths: Path[];
  selected: number;
  onSelect: (i: number) => void;
}) {
  if (paths.length === 0) return null;
  const W = 440;
  const H = 260;
  const pad = 40;

  const pts = paths.map((p, i) => ({
    i,
    x: p.objective.seconds ?? 0,
    y: -(p.objective.neg_gain ?? 0),
    load: p.objective.load ?? 0,
  }));
  const xr = extent(pts.map((p) => p.x));
  const yr = extent(pts.map((p) => p.y));
  const lmax = Math.max(...pts.map((p) => p.load), 1e-9);
  const sx = (x: number) => pad + ((x - xr[0]) / (xr[1] - xr[0] || 1)) * (W - 2 * pad);
  const sy = (y: number) => H - pad - ((y - yr[0]) / (yr[1] - yr[0] || 1)) * (H - 2 * pad);
  const colour = (l: number) => `hsl(${220 - (l / lmax) * 200}, 70%, 48%)`;

  return (
    <svg className="pareto" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Pareto front">
      <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} className="axis" />
      <line x1={pad} y1={pad} x2={pad} y2={H - pad} className="axis" />
      <text x={W / 2} y={H - 8} className="axlabel">
        total time (s) &rarr;
      </text>
      <text x={12} y={H / 2} className="axlabel" transform={`rotate(-90 14 ${H / 2})`}>
        mastery gain &rarr;
      </text>
      {pts.map((p) => (
        <circle
          key={p.i}
          cx={sx(p.x)}
          cy={sy(p.y)}
          r={p.i === selected ? 8 : 5}
          fill={colour(p.load)}
          stroke={p.i === selected ? "#111" : "none"}
          strokeWidth={2}
          style={{ cursor: "pointer" }}
          onClick={() => onSelect(p.i)}
        >
          <title>{`path ${p.i}: ${Math.round(p.x)} s, mastery +${p.y.toFixed(2)}, load ${p.load.toFixed(2)}`}</title>
        </circle>
      ))}
    </svg>
  );
}

function extent(xs: number[]): [number, number] {
  return [Math.min(...xs), Math.max(...xs)];
}
