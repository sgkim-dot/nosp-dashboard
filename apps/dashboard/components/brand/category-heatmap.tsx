"use client";

import { useState } from "react";
import type { HeatmapCell } from "@/lib/db/queries";

const PRODUCT_LABEL: Record<string, string> = {
  SEARCHING_VIEW: "서칭뷰",
  NEW_PRODUCT: "신제품검색",
  ANNIVERSARY: "기념일 광고",
};

type CellMeta = {
  count: number;
  kgs: { product: string; lvl1: string; lvl2: string; kg: string }[];
};

export function CategoryHeatmap({ rows }: { rows: HeatmapCell[] }) {
  const [hover, setHover] = useState<{
    brand: string;
    roundNo: number;
    meta: CellMeta;
    x: number;
    y: number;
  } | null>(null);

  if (rows.length === 0) {
    return (
      <div className="rounded-md border bg-muted/30 p-8 text-center text-sm text-muted-foreground">
        해당 조건의 브랜드 데이터가 아직 없습니다. (스크래핑이 진행 중이라면 잠시 후 다시 확인)
      </div>
    );
  }

  // Build (brand, round) → { count, list of KG breadcrumbs }
  const byKey = new Map<string, CellMeta>();
  const brandSet = new Set<string>();
  const roundSet = new Set<number>();
  for (const r of rows) {
    const k = `${r.brandDisplayName}|${r.roundNo}`;
    let cell = byKey.get(k);
    if (!cell) {
      cell = { count: 0, kgs: [] };
      byKey.set(k, cell);
    }
    // Deduplicate: same KG can have 2 slots filled by the same brand
    const path = {
      product: PRODUCT_LABEL[r.productCode] ?? r.productCode,
      lvl1: r.categoryLvl1,
      lvl2: r.categoryLvl2,
      kg: r.keywordGroupName,
    };
    const exists = cell.kgs.some(
      (k2) => k2.product === path.product && k2.kg === path.kg,
    );
    if (!exists) {
      cell.count += 1;
      cell.kgs.push(path);
    }
    brandSet.add(r.brandDisplayName);
    roundSet.add(r.roundNo);
  }
  const brands = Array.from(brandSet).sort((a, b) => a.localeCompare(b, "ko"));
  const roundNos = Array.from(roundSet).sort((a, b) => a - b);
  const maxCount = Math.max(...Array.from(byKey.values()).map((c) => c.count));

  return (
    <div className="relative">
      <div className="overflow-x-auto rounded-md border bg-background">
        <table className="text-xs">
          <thead className="bg-muted/40">
            <tr>
              <th className="sticky left-0 bg-muted/40 px-3 py-2 text-left">
                브랜드 ({brands.length})
              </th>
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
                  const meta = byKey.get(`${b}|${rn}`);
                  const count = meta?.count ?? 0;
                  const intensity = count === 0 ? 0 : 0.2 + (0.8 * count) / maxCount;
                  return (
                    <td key={rn} className="px-2 py-1.5 text-center">
                      {count > 0 && meta ? (
                        <span
                          className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-sm text-[10px] font-medium text-white"
                          style={{ backgroundColor: `rgba(14, 165, 233, ${intensity})` }}
                          onMouseEnter={(e) => {
                            const rect = (e.target as HTMLElement).getBoundingClientRect();
                            setHover({
                              brand: b,
                              roundNo: rn,
                              meta,
                              x: rect.right + 8,
                              y: rect.top,
                            });
                          }}
                          onMouseLeave={() => setHover(null)}
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

      {hover && (
        <div
          className="pointer-events-none fixed z-50 max-w-md rounded-md border bg-popover px-3 py-2 text-xs shadow-lg"
          style={{ left: hover.x, top: hover.y }}
        >
          <div className="mb-1 font-semibold text-foreground">
            {hover.brand}{" "}
            <span className="font-mono text-muted-foreground">· {hover.roundNo}회차</span>
            <span className="ml-1 text-muted-foreground">· {hover.meta.count}개 KG</span>
          </div>
          <ul className="space-y-0.5 text-muted-foreground">
            {hover.meta.kgs.map((p, i) => (
              <li key={i}>
                <span className="text-foreground">{p.product}</span>
                <span className="mx-1">›</span>
                {p.lvl1}
                <span className="mx-1">›</span>
                {p.lvl2}
                <span className="mx-1">›</span>
                <span className="text-foreground">{p.kg}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
