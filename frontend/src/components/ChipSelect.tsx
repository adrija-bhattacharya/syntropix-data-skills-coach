import { memo } from "react";

export interface Option {
  value: string;
  label: string;
}

export const ChipSelect = memo(function ChipSelect({
  label,
  options,
  selected,
  onChange,
  emptyHint,
}: {
  label: string;
  options: Option[];
  selected: string[];
  onChange: (v: string[]) => void;
  emptyHint?: string;
}) {
  const set = new Set(selected);
  const toggle = (v: string) => {
    const next = new Set(set);
    next.has(v) ? next.delete(v) : next.add(v);
    onChange(options.filter((o) => next.has(o.value)).map((o) => o.value));
  };
  return (
    <div className="field">
      <label>
        <span>{label}</span>
        {selected.length > 0 && <span className="val">{selected.length}</span>}
      </label>
      <div className="chips" role="group" aria-label={label}>
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            className="chip"
            aria-pressed={set.has(o.value)}
            onClick={() => toggle(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
      {options.length === 0 && emptyHint && <p className="hint">{emptyHint}</p>}
    </div>
  );
});
