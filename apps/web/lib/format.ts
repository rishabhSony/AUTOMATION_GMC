const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** ₹ with Indian digit grouping, e.g. 500000 → "₹5,00,000". */
export const formatInr = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : `₹${inr.format(value)}`;

/** ISO timestamp → "29-10-2026 14:05" (DD-MM-YYYY, as used across the app). */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export const formatDate = (iso: string) => formatDateTime(iso).slice(0, 10);

/** "2026-10-29" (date input value) → "29-10-2026". */
export const isoToDdMmYyyy = (iso: string) =>
  iso.split("-").reverse().join("-");
