import type { HeatmapCell } from "@/lib/db/queries";

export function CategoryHeatmap({ rows }: { rows: HeatmapCell[] }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-md border bg-muted/30 p-8 text-center text-sm text-muted-foreground">
        해당 조건의 브랜드 데이터가 아직 없습니다. (W4 스크래핑이 진행 중이라면 잠시 후 다시 확인)
      </div>
    );
  }

  // Count appearances per (brand, round)
  const byKey = new Map<string, number>();
  const brandSet = new Set<string>();
  const roundSet = new Set<number>();
  for (const r of rows) {
    const k = `${r.brandDisplayName}|${r.roundNo}`;
    byKey.set(k, (byKey.get(k) ?? 0) + 1);
    brandSet.add(r.brandDisplayName);
    roundSet.add(r.roundNo);
  }
  const brands = Array.from(brandSet).sort((a, b) => a.localeCompare(b, "ko"));
  const roundNos = Array.from(roundSet).sort((a, b) => a - b);
  const maxCount = Math.max(...byKey.values());

  return (
    <div className="overflow-x-auto rounded-md border bg-background">
      <table className="text-xs">
        <thead className="bg-muted/40">
          <tr>
            <th className="sticky left-0 bg-muted/40 px-3 py-2 text-left">브랜드 ({brands.length})</th>
            {roundNos.map((r) => (
              <th key={r} className="min-w-[60px] px-2 py-2 text-center font-mono">
                {r}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {brands.map((b) => (
            <tr key={b} className="border-t">
              <td className="sticky left-0 bg-background px-3 py-1.5 font-medium">{b}</td>
              {roundNos.map((rn) => {
                const count = byKey.get(`${b}|${rn}`) ?? 0;
                const intensity = count === 0 ? 0 : 0.2 + (0.8 * count) / maxCount;
                return (
                  <td key={rn} className="px-2 py-1.5 text-center">
                    {count > 0 ? (
                      <span
                        className="inline-flex h-5 w-5 items-center justify-center rounded-sm text-[10px] font-medium text-white"
                        style={{ backgroundColor: `rgba(14, 165, 233, ${intensity})` }}
                        title={`${b} · ${rn} · ${count} kg`}
                      >
                        {count}
                      </span>
                    ) : (
                      <span className="text-muted-foreground/40">·</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
