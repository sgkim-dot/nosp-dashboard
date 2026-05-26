export function formatKRW(value: number | null | undefined): string {
  if (value == null) return "-";
  return `${Number(value).toLocaleString()}원`;
}

export function formatRatio(ratio: number | null | undefined): string {
  if (ratio == null) return "-";
  return `${ratio.toFixed(2)}x`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return iso.slice(5).replace("-", ".");
}
