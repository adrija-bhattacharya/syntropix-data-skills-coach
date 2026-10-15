/** Minimal iCalendar (.ics) export - all-day or timed events, one per study item. */
export interface IcsEvent {
  day: string; // YYYY-MM-DD
  title: string;
  description?: string;
  /** "HH:MM" - with both, a timed event instead of an all-day one */
  start?: string;
  end?: string;
}

const esc = (s: string) => s.replace(/[,;]/g, (c) => `\\${c}`).replace(/\r?\n/g, "\\n");
const compact = (iso: string) => iso.replaceAll("-", "");
const nextDay = (iso: string) =>
  new Date(Date.parse(`${iso}T00:00:00Z`) + 864e5).toISOString().slice(0, 10);

export function toIcs(name: string, events: IcsEvent[]): string {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Syntropix//study plan//EN", `X-WR-CALNAME:${esc(name)}`];
  events.forEach((e, i) => {
    lines.push(
      "BEGIN:VEVENT",
      `UID:velpo-${compact(e.day)}-${i}@velpo.local`,
      `DTSTAMP:${stamp}`,
      ...(e.start && e.end
        ? [`DTSTART:${compact(e.day)}T${e.start.replace(":", "")}00`, `DTEND:${compact(e.day)}T${e.end.replace(":", "")}00`]
        : [`DTSTART;VALUE=DATE:${compact(e.day)}`, `DTEND;VALUE=DATE:${compact(nextDay(e.day))}`]),
      `SUMMARY:${esc(e.title)}`,
    );
    if (e.description) lines.push(`DESCRIPTION:${esc(e.description)}`);
    lines.push("END:VEVENT");
  });
  lines.push("END:VCALENDAR");
  return lines.join("\r\n");
}

export function downloadIcs(filename: string, name: string, events: IcsEvent[]): void {
  const blob = new Blob([toIcs(name, events)], { type: "text/calendar" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
