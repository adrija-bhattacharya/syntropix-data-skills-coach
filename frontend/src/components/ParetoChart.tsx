import { memo } from "react";
import {
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import type { Path } from "../lib/api";
import { paretoPoint } from "../lib/format";

/** Non-dominated plans: x = minutes, y = mastery gain, bubble size = cognitive load. */
export const ParetoChart = memo(function ParetoChart({
  paths,
  selected,
  onSelect,
}: {
  paths: Path[];
  selected: number;
  onSelect: (i: number) => void;
}) {
  const data = paths.map(paretoPoint);

  return (
    <div className="chart-wrap">
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 10, right: 16, bottom: 24, left: 4 }}>
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="minutes"
            name="time"
            unit=" min"
            tick={{ fontSize: 11 }}
            stroke="var(--muted)"
            label={{ value: "study time", position: "insideBottom", offset: -12, fontSize: 11, fill: "var(--muted)" }}
          />
          <YAxis
            type="number"
            dataKey="gain"
            name="mastery gain"
            tick={{ fontSize: 11 }}
            stroke="var(--muted)"
            label={{ value: "mastery gain", angle: -90, position: "insideLeft", fontSize: 11, fill: "var(--muted)" }}
          />
          <ZAxis type="number" dataKey="load" range={[60, 320]} name="load" />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", fontSize: 12 }}
            formatter={(v: number, n: string) => [n === "load" ? v.toFixed(2) : v, n]}
          />
          <Scatter data={data} onClick={(d) => onSelect((d as { index: number }).index)}>
            {data.map((p) => (
              <Cell
                key={p.index}
                fill={p.index === selected ? "var(--accent)" : "var(--accent-soft)"}
                stroke="var(--accent)"
                strokeWidth={p.index === selected ? 2 : 1}
                cursor="pointer"
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
});
