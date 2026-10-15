/** Small building blocks shared by every Stitch screen. */
import type { ReactNode } from "react";

import { useTrack } from "../context/TrackContext";
import { localIso } from "../lib/dates";

/** A Material Symbols Outlined icon (decorative unless `label` is given). */
export function Ms({
  name,
  className = "",
  size = 18,
  label,
}: {
  name: string;
  className?: string;
  size?: number;
  label?: string;
}) {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={{ fontSize: size }}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? "img" : undefined}
    >
      {name}
    </span>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="px-1.5 py-0.5 rounded bg-surface-container-highest text-on-surface font-code-sm text-code-sm border border-outline-variant/40">
      {children}
    </kbd>
  );
}

type Tone = "primary" | "secondary" | "tertiary" | "error" | "neutral" | "warn";
const TONE: Record<Tone, string> = {
  primary: "bg-primary/20 text-primary",
  secondary: "bg-secondary-container/20 text-secondary",
  tertiary: "bg-tertiary-container/20 text-tertiary",
  error: "bg-error-container/40 text-error",
  neutral: "bg-surface-container-highest text-on-surface-variant",
  warn: "bg-secondary-container/20 text-secondary-fixed-dim",
};

export function Pill({
  tone = "neutral",
  icon,
  children,
  className = "",
}: {
  tone?: Tone;
  icon?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`px-2 py-0.5 rounded font-label-badge text-label-badge inline-flex items-center gap-1 ${TONE[tone]} ${className}`}
    >
      {icon && <Ms name={icon} size={12} />}
      {children}
    </span>
  );
}

/** Small uppercase mono label used for card captions. */
export function Caption({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={`font-label-annotation text-label-annotation text-on-surface-variant uppercase tracking-wider ${className}`}
    >
      {children}
    </span>
  );
}

/** An HCI-principle annotation ("[H-01] ...") - hidden when the top-bar toggle is off. */
export function Hci({ children, className = "" }: { children: ReactNode; className?: string }) {
  const { track } = useTrack();
  if (!track.hci) return null;
  return (
    <span className={`font-label-annotation text-label-annotation text-outline ${className}`}>
      {children}
    </span>
  );
}

export interface HciCard {
  tag: string;
  title: string;
  body: string;
  tone?: "primary" | "secondary" | "tertiary";
}

/** The footer ribbon of HCI cards every Stitch screen ends with. */
export function HciRibbon({ title, cards, keys }: { title: string; cards: HciCard[]; keys?: ReactNode }) {
  const { track } = useTrack();
  if (!track.hci) return null;
  const tone = { primary: "text-primary", secondary: "text-secondary", tertiary: "text-tertiary" };
  return (
    <section className="mt-space-lg p-space-lg rounded-xl bg-surface-container-low shadow-sm flex flex-col gap-space-md">
      <div className="flex flex-wrap items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-sm">
          <Ms name="verified_user" className="text-primary" />
          <span className="font-headline-sm text-headline-sm text-on-surface">{title}</span>
        </div>
        <Pill tone="neutral">Design notes · turn off in the top bar</Pill>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-space-md font-label-annotation text-label-annotation">
        {cards.map((c) => (
          <div key={c.tag + c.title} className="p-space-md rounded-lg bg-surface-container flex flex-col gap-1">
            <div className="flex items-center gap-1 text-on-surface font-label-badge text-label-badge">
              <span
                className={`px-1.5 rounded bg-surface-container-highest font-code-sm text-code-sm ${tone[c.tone ?? "primary"]}`}
              >
                [{c.tag}]
              </span>
              <span>{c.title}</span>
            </div>
            <p className="text-on-surface-variant">{c.body}</p>
          </div>
        ))}
      </div>
      {keys && (
        <div className="flex flex-wrap items-center gap-space-md pt-space-xs font-label-annotation text-label-annotation text-outline">
          {keys}
        </div>
      )}
    </section>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-space-sm p-space-lg text-on-surface-variant font-body-sm text-body-sm">
      <Ms name="progress_activity" className="animate-spin text-primary" />
      {label}
    </div>
  );
}

export function ErrorBox({ children }: { children: ReactNode }) {
  return (
    <div role="alert" className="p-space-md rounded-xl bg-error-container/20 text-error font-body-sm text-body-sm flex items-start gap-space-sm">
      <Ms name="error" />
      <div>{children}</div>
    </div>
  );
}

/** A tab strip in the Stitch "segmented" style. */
export function Tabs<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string; icon?: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="flex items-center gap-space-xs p-1 rounded-xl bg-surface-container-low shadow-sm w-fit">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => onChange(o.value)}
            className={
              on
                ? "px-space-md py-1.5 rounded-lg bg-surface-container-highest text-primary font-body-strong text-body-sm shadow-md flex items-center gap-space-xs"
                : "px-space-md py-1.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container font-body-strong text-body-sm transition-all flex items-center gap-space-xs"
            }
          >
            {o.icon && <Ms name={o.icon} size={16} />}
            {on && !o.icon && <span className="inline-block w-2 h-2 rounded-full bg-primary" />}
            <span>{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Human date label for an ISO day, in UTC so it never shifts with timezone. */
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function dayLabel(iso: string): string {
  return `${MONTHS[Number(iso.slice(5, 7)) - 1]} ${Number(iso.slice(8, 10))}`;
}
export function isoToday(): string {
  return localIso();
}
export function addDays(iso: string, n: number): string {
  return new Date(Date.parse(`${iso}T00:00:00Z`) + n * 864e5).toISOString().slice(0, 10);
}
export function hm(minutes: number): string {
  const m = Math.round(minutes);
  return m >= 60 ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m` : `${m} min`;
}
