/** Small styled primitives shared across the app. */
import type { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

export function Button({
  variant = "default",
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "ghost" }) {
  const cls = variant === "default" ? "btn" : `btn ${variant}`;
  return <button className={`${cls} ${className}`.trim()} {...rest} />;
}

export function Field({
  label,
  value,
  hint,
  htmlFor,
  children,
}: {
  label: ReactNode;
  value?: ReactNode;
  hint?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>
        <span>{label}</span>
        {value != null && <span className="val">{value}</span>}
      </label>
      {children}
      {hint != null && <p className="hint">{hint}</p>}
    </div>
  );
}

export function Select<T extends string>({
  options,
  className = "",
  ...rest
}: Omit<SelectHTMLAttributes<HTMLSelectElement>, "value" | "onChange"> & {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  const { value, onChange, ...native } = rest;
  return (
    <select
      className={`select ${className}`.trim()}
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      {...native}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function Badge({
  children,
  tone = "neutral",
  mono = false,
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn";
  mono?: boolean;
}) {
  const cls = ["badge", tone === "neutral" ? "" : tone, mono ? "mono" : ""].filter(Boolean).join(" ");
  return <span className={cls}>{children}</span>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span role="status">
      <span className="spinner" aria-hidden /> {label}
    </span>
  );
}

export function Callout({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warn" }) {
  return <div className={tone === "warn" ? "callout warn" : "callout"} role={tone === "warn" ? "alert" : undefined}>{children}</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
