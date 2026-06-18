import type { KeywordGroupSummary } from "@/types/bid-decision";
import { formatKRW } from "@/lib/format";

export function SummaryCard({ summary }: { summary: KeywordGroupSummary }) {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-primary text-primary-foreground shadow-sm">
      {/* Decorative gradient blob */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-accent/20 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute right-12 -bottom-12 h-48 w-48 rounded-full bg-accent/10 blur-2xl"
      />
      <div className="relative p-8 sm:p-10">
        {/* Two columns sharing identical typography scale and line heights, so
            both label rows and both value rows sit exactly on the same
            baseline / mid-line. */}
        <div className="flex flex-wrap items-stretch gap-x-16 gap-y-6">
          {/* KG identity */}
          <div className="flex flex-col">
            <div className="flex h-10 items-center gap-3">
              <span className="rounded-full bg-accent/20 px-5 py-1.5 text-xl font-semibold text-accent leading-none">
                {summary.product === "SEARCHING_VIEW" ? "서칭뷰" : "신제품검색"}
              </span>
              <span className="text-xl font-medium text-primary-foreground/80">
                {summary.categoryLvl1} · {summary.categoryLvl2}
              </span>
            </div>
            <div className="mt-4 text-5xl font-bold tracking-tight leading-none">
              {summary.keywordGroupName}
            </div>
          </div>

          {/* 최근 낙찰가 */}
          <div className="flex flex-col">
            <div className="flex h-10 items-center">
              <span className="text-xl font-medium text-primary-foreground/80">
                최근 낙찰가 (VAT-)
              </span>
            </div>
            <div className="mt-4 text-5xl font-bold tabular-nums leading-none">
              {formatKRW(summary.latestWinning)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
