const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

export function fmtDay(iso: string): string {
  const d = parseDate(iso);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

export function fmtWeekday(iso: string): string {
  return `${DAYS[(parseDate(iso).getUTCDay() + 6) % 7]} ${fmtDay(iso)}`;
}

export function monthOf(iso: string): string {
  return MONTHS[parseDate(iso).getUTCMonth()];
}

export function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

export function fmtMinutes(min: number): string {
  const h = Math.floor(min / 60), m = Math.round(min % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

const LONG_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];

/** "10 January" */
export function fmtLongDay(iso: string): string {
  const d = parseDate(iso);
  return `${d.getUTCDate()} ${LONG_MONTHS[d.getUTCMonth()]}`;
}
