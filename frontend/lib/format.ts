export const num = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

export const pct = (v: number | null | undefined, d = 2, sign = true) =>
  v === null || v === undefined ? "—" : `${sign && v > 0 ? "+" : ""}${v.toFixed(d)}%`;

export const ratioPct = (v: number | null | undefined, d = 1, sign = false) => (v === null || v === undefined ? "—" : pct(v * 100, d, sign));

export function compact(v: number | null | undefined, prefix = "") {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  for (const [div, unit] of [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]] as const) {
    if (a >= div) return `${v < 0 ? "-" : ""}${prefix}${(a / div).toFixed(2)}${unit}`;
  }
  return `${v < 0 ? "-" : ""}${prefix}${a.toFixed(0)}`;
}

export const tone = (v: number | null | undefined) => (v === null || v === undefined || v === 0 ? "" : v > 0 ? "up" : "down");

export function ago(iso: string | null | undefined) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  if (m < 2880) return `${Math.round(m / 60)}h ago`;
  return `${Math.round(m / 1440)}d ago`;
}

export const daysAgo = (days: number) => new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);

export function toCsv(table: HTMLTableElement) {
  const cell = (c: Element) => `"${(c.textContent ?? "").replace(/"/g, '""').trim()}"`;
  return [...table.rows].map((r) => [...r.cells].map(cell).join(",")).join("\n");
}
