export function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function addDaysISO(iso: string, days: number) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function presetRange(days: number): { start: string; end: string } {
  const end = todayISO();
  const start = addDaysISO(end, 1 - days);
  return { start, end };
}

export function formatRangeLabel(start: string, end: string) {
  const opts: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
  };
  const s = new Date(`${start}T00:00:00`).toLocaleDateString("en-PH", opts);
  const e = new Date(`${end}T00:00:00`).toLocaleDateString("en-PH", opts);
  return s === e ? s : `${s} – ${e}`;
}

export function dateQuery(start: string, end: string) {
  return `start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
}

export function mechanicLaborHref(
  mechanicId: string | null | undefined,
  start: string,
  end: string,
) {
  const slug = mechanicId || "unassigned";
  return `/mechanic-labor/${slug}?${dateQuery(start, end)}`;
}
