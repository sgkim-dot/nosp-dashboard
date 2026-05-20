import { FilterBar } from "@/components/bid-decision/filter-bar";
import { InsightsCard } from "@/components/bid-decision/insights-card";
import { RoundTable } from "@/components/bid-decision/round-table";
import { SummaryCard } from "@/components/bid-decision/summary-card";
import { TrendChart } from "@/components/bid-decision/trend-chart";
import { computeInsights, getKeywordGroupSummary } from "@/lib/db/queries";
import type { ProductCode } from "@/types/bid-decision";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function pickStr(v: string | string[] | undefined): string | null {
  if (Array.isArray(v)) return v[0] ?? null;
  return v ?? null;
}
function pickInt(v: string | string[] | undefined, fallback: number): number {
  const s = pickStr(v);
  const n = s ? Number(s) : NaN;
  return Number.isFinite(n) ? n : fallback;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;

  const product = (pickStr(sp.product) as ProductCode | null) ?? "SEARCHING_VIEW";
  const cat1 = pickStr(sp.cat1);
  const cat2 = pickStr(sp.cat2);
  const kgIdStr = pickStr(sp.kg);
  const keywordGroupId = kgIdStr ? Number(kgIdStr) : null;
  const lastNRounds = pickInt(sp.last, 12);

  const summary = keywordGroupId
    ? await getKeywordGroupSummary({ keywordGroupId, lastNRounds })
    : null;

  return (
    <div>
      <header className="border-b px-6 py-3">
        <h1 className="text-lg font-semibold">입찰 의사결정</h1>
        <p className="text-xs text-muted-foreground">
          키워드그룹별 회차 추이로 다음 입찰가를 결정합니다.
        </p>
      </header>

      <FilterBar
        product={product}
        categoryLvl1={cat1}
        categoryLvl2={cat2}
        keywordGroupId={keywordGroupId}
        lastNRounds={lastNRounds}
      />

      <div className="space-y-4 px-6 py-4">
        {!summary ? (
          <div className="rounded-md border border-dashed bg-muted/30 p-12 text-center text-sm text-muted-foreground">
            좌측 필터에서 키워드그룹을 선택하세요.
          </div>
        ) : (
          <>
            <SummaryCard summary={summary} />
            <TrendChart rounds={summary.rounds} />
            <InsightsCard insights={computeInsights(summary)} />
            <RoundTable rounds={summary.rounds} />
          </>
        )}
      </div>
    </div>
  );
}
