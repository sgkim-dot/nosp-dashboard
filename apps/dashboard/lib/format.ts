export function formatKRW(value: number | null | undefined): string {
  if (value == null) return "-";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}k`;
  return String(value);
}

export function formatRatio(ratio: number | null | undefined): string {
  if (ratio == null) return "-";
  return `${ratio.toFixed(2)}x`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return iso.slice(5).replace("-", ".");
}
