"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { BrandSummary, BrandHistoryRow } from "@/lib/db/queries";

const PRODUCT_LABEL: Record<string, string> = {
  SEARCHING_VIEW: "서칭뷰",
  NEW_PRODUCT: "신제품검색",
  ANNIVERSARY: "기념일 광고",
};

type DetailPayload = {
  brand: { displayName: string; businessNames: string[] } | null;
  history: BrandHistoryRow[];
} | null;

export function BrandTracker({
  brands,
  selectedBrandId,
  detail,
}: {
  brands: BrandSummary[];
  selectedBrandId: number | null;
  detail: DetailPayload;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return brands;
    return brands.filter(
      (b) =>
        b.displayName.toLowerCase().includes(q) ||
        b.businessNames.some((n) => n.toLowerCase().includes(q)),
    );
  }, [brands, query]);

  return (
    <div className="grid gap-4 px-6 py-4 lg:grid-cols-[320px_1fr]">
      {/* Brand list */}
      <div className="rounded-md border bg-background">
        <div className="border-b p-2">
          <input
            type="text"
            placeholder="브랜드명 / 호스트 검색"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded border px-2 py-1 text-sm"
          />
          <div className="mt-1 text-xs text-muted-foreground">
            {filtered.length} / {brands.length} brands
          </div>
        </div>
        <ul className="max-h-[calc(100vh-200px)] overflow-y-auto">
          {filtered.map((b) => {
            const active = b.brandId === selectedBrandId;
            const firstHost = b.businessNames[0] ?? "";
            const moreHosts = b.businessNames.length - 1;
            return (
              <li key={b.brandId}>
                <Link
                  href={`/brand-tracker?brandId=${b.brandId}`}
                  className={`flex items-center justify-between border-b px-3 py-2 text-sm hover:bg-muted/40 ${
                    active ? "bg-muted font-semibold" : ""
                  }`}
                  title={b.businessNames.join("\n")}
                >
                  <div className="min-w-0">
                    <div className="truncate">{b.displayName}</div>
                    <div className="truncate text-[10px] text-muted-foreground">
                      {firstHost}
                      {moreHosts > 0 && (
                        <span className="ml-1 text-[10px]">+{moreHosts}</span>
                      )}
                    </div>
                  </div>
                  <div className="ml-2 shrink-0 text-right text-xs">
                    <div className="font-mono">{b.totalAppearances}</div>
                    <div className="text-[10px] text-muted-foreground">
                      {b.distinctKeywordGroups}개 KG
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Detail panel */}
      <div className="rounded-md border bg-background">
        {detail && detail.brand ? (
          <BrandDetail detail={{ brand: detail.brand, history: detail.history }} />
        ) : (
          <div className="p-8 text-center text-sm text-muted-foreground">
            왼쪽 목록에서 브랜드를 선택하세요.
          </div>
        )}
      </div>
    </div>
  );
}

function BrandDetail({
  detail,
}: {
  detail: {
    brand: { displayName: string; businessNames: string[] };
    history: BrandHistoryRow[];
  };
}) {
  const { brand, history } = detail;

  const totalKGs = useMemo(
    () =>
      new Set(
        history.map((h) => `${h.productCode}::${h.keywordGroupName}`),
      ).size,
    [history],
  );
  const rounds = useMemo(
    () => Array.from(new Set(history.map((h) => h.roundNo))).sort((a, b) => b - a),
    [history],
  );
  const products = useMemo(
    () => Array.from(new Set(history.map((h) => h.productCode))),
    [history],
  );

  const titleSet = useMemo(
    () =>
      Array.from(
        new Set(history.map((h) => h.title).filter((x): x is string => !!x)),
      ),
    [history],
  );

  return (
    <div className="space-y-4 p-4">
      <header>
        <div className="text-xl font-semibold">{brand.displayName}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {brand.businessNames.length === 1 ? (
            brand.businessNames[0]
          ) : (
            <span>
              {brand.businessNames.length}개 호스트:{" "}
              {brand.businessNames.join(", ")}
            </span>
          )}
        </div>
      </header>

      <div className="grid grid-cols-4 gap-3 rounded-md bg-muted/30 p-3 text-sm">
        <Stat label="총 노출 횟수" value={String(history.length)} />
        <Stat label="누적 KG 수" value={`${totalKGs}개`} />
        <Stat label="회차 수" value={`${rounds.length}개`} />
        <Stat
          label="제품군"
          value={products.map((p) => PRODUCT_LABEL[p] ?? p).join(" / ")}
        />
      </div>

      <div>
        <div className="mb-1 text-xs font-semibold">
          노출 타이틀 목록 ({titleSet.length}개)
        </div>
        <div className="flex flex-wrap gap-1.5">
          {titleSet.slice(0, 30).map((c, i) => (
            <span
              key={i}
              className="inline-block rounded border bg-muted/40 px-2 py-0.5 text-xs"
            >
              {c}
            </span>
          ))}
          {titleSet.length > 30 && (
            <span className="text-xs text-muted-foreground">
              … 외 {titleSet.length - 30}개
            </span>
          )}
        </div>
      </div>

      <BrandHistoryTable history={history} />
    </div>
  );
}

// Group rows by (round, product, kg) so multi-slot single-brand captures
// collapse into one row labeled "슬롯 1,2 (2슬롯)" rather than duplicating.
function BrandHistoryTable({ history }: { history: BrandHistoryRow[] }) {
  type Group = {
    roundNo: number;
    productCode: string;
    categoryLvl1: string;
    categoryLvl2: string;
    keywordGroupName: string;
    slots: number[];
    adCopies: Set<string>;
    hosts: Set<string>;
    sources: Set<string>;
    confidences: number[];
    capturedAt: string;
  };

  const groups: Group[] = [];
  const groupKey = (h: BrandHistoryRow) =>
    `${h.roundNo}::${h.productCode}::${h.keywordGroupName}`;
  const byKey = new Map<string, Group>();
  for (const h of history) {
    const k = groupKey(h);
    let g = byKey.get(k);
    if (!g) {
      g = {
        roundNo: h.roundNo,
        productCode: h.productCode,
        categoryLvl1: h.categoryLvl1,
        categoryLvl2: h.categoryLvl2,
        keywordGroupName: h.keywordGroupName,
        slots: [],
        adCopies: new Set(),
        hosts: new Set(),
        sources: new Set(),
        confidences: [],
        capturedAt: h.capturedAt,
      };
      byKey.set(k, g);
      groups.push(g);
    }
    g.slots.push(h.slotNo);
    if (h.title) g.adCopies.add(h.title);
    g.hosts.add(h.host);
    g.sources.add(h.source);
    if (h.confidence != null) g.confidences.push(h.confidence);
    // Keep earliest captured_at
    if (h.capturedAt < g.capturedAt) g.capturedAt = h.capturedAt;
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-xs">
        <thead className="bg-muted/40">
          <tr className="text-left">
            <th className="px-2 py-1.5 w-20">회차</th>
            <th className="px-2 py-1.5 w-20">제품</th>
            <th className="px-2 py-1.5">대분류 › 소분류</th>
            <th className="px-2 py-1.5">키워드그룹</th>
            <th className="px-2 py-1.5 w-20 text-center">점유</th>
            <th className="px-2 py-1.5">타이틀</th>
            <th className="px-2 py-1.5">호스트</th>
            <th className="px-2 py-1.5 w-16 text-center">출처</th>
            <th className="px-2 py-1.5 w-16 text-right">신뢰도</th>
            <th className="px-2 py-1.5 w-32">캡쳐 시각</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g, i) => {
            const slotsSorted = [...g.slots].sort((a, b) => a - b);
            const slotLabel =
              slotsSorted.length === 1
                ? `슬롯 ${slotsSorted[0]}`
                : `슬롯 ${slotsSorted.join(",")} (${slotsSorted.length}슬롯)`;
            const avgConf =
              g.confidences.length > 0
                ? g.confidences.reduce((a, b) => a + b, 0) / g.confidences.length
                : null;
            return (
              <tr key={i} className="border-t hover:bg-muted/30">
                <td className="px-2 py-1 font-mono">{g.roundNo}</td>
                <td className="px-2 py-1">
                  {PRODUCT_LABEL[g.productCode] ?? g.productCode}
                </td>
                <td className="px-2 py-1 text-muted-foreground">
                  {g.categoryLvl1} › {g.categoryLvl2}
                </td>
                <td className="px-2 py-1 font-medium">{g.keywordGroupName}</td>
                <td className="px-2 py-1 text-center">
                  {slotsSorted.length === 2 ? (
                    <span className="font-semibold text-blue-600">{slotLabel}</span>
                  ) : (
                    slotLabel
                  )}
                </td>
                <td className="px-2 py-1 text-muted-foreground">
                  {Array.from(g.adCopies).join(" / ") || "-"}
                </td>
                <td className="px-2 py-1 font-mono text-[10px] text-muted-foreground">
                  {Array.from(g.hosts).join(" / ")}
                </td>
                <td className="px-2 py-1 text-center text-[10px]">
                  {Array.from(g.sources).join("/")}
                </td>
                <td className="px-2 py-1 text-right">
                  {avgConf != null ? avgConf.toFixed(2) : "-"}
                </td>
                <td className="px-2 py-1 text-[10px] text-muted-foreground">
                  {g.capturedAt.slice(0, 16).replace("T", " ")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}
