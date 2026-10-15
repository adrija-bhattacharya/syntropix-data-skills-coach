/** The learner's *local* calendar date as YYYY-MM-DD (not UTC: in India the
 * UTC date is still yesterday until 05:30). */
export function localIso(d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
