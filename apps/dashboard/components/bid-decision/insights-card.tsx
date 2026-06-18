import type { Insights } from "@/types/bid-decision";
import { formatKRW, formatRatio } from "@/lib/format";
import {
  TrendingUp,
  AlertCircle,
  Target,
  CheckCircle2,
  HelpCircle,
} from "lucide-react";

export function InsightsCard({ insights }: { insights: Insights }) {
  const vacancyPct =
    insights.vacancyRate == null
      ? "-"
      : `${Math.round(insights.vacancyRate * 100)}%`;

  const recValue =
    insights.recommendedLow && insights.recommendedHigh
      ? `${formatKRW(insights.recommendedLow)}~${formatKRW(insights.recommendedHigh)}`
      : "-";

  return (
    // 좌측 1: 가중평균 + 공실 발생률을 한 카드에 합침
    // 우측 2: 추천 입찰가가 공실 자리까지 확장
    <div className="grid gap-3 lg:grid-cols-[1fr_2fr]">
      {/* Combined stats card */}
      <div className="rounded-xl border bg-card p-5 shadow-sm divide-y divide-border">
        <StatRow
          icon={<TrendingUp className="h-5 w-5" />}
          iconClass="bg-emerald-50 text-emerald-600"
          label="가중평균 낙찰/최저 배수"
          sublabel="최근 4회차 가중치 (5·3·2·1)"
          value={formatRatio(insights.meanRatio)}
        />
        <StatRow
          icon={<AlertCircle className="h-5 w-5" />}
          iconClass="bg-amber-50 text-amber-600"
          label="공실 발생률"
          sublabel="202622회차부터 측정"
          value={vacancyPct}
        />
      </div>

      {/* Recommended bid card (wider) */}
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary/10 text-primary">
            <Target className="h-5 w-5" />
          </span>
          <span className="text-sm font-medium text-muted-foreground">
            추천 입찰가 (VAT-)
          </span>
          <span className="group relative inline-flex">
            <HelpCircle className="h-4 w-4 cursor-help text-muted-foreground/60 hover:text-muted-foreground" />
            <span
              role="tooltip"
              className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 w-80 -translate-x-1/2 rounded-lg border bg-popover px-4 py-3 text-xs leading-relaxed text-popover-foreground opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 whitespace-pre-line"
            >
              {[insights.strategyLabel, "최근 4회차 가중치 (5·3·2·1)"]
                .filter(Boolean)
                .join("\n")}
              {insights.strategyHint ? `\n\n${insights.strategyHint}` : ""}
            </span>
          </span>
        </div>
        <div className="mt-3 text-2xl font-bold tabular-nums">{recValue}</div>
        <div className="mt-4 space-y-2.5">
          {insights.hitRate != null && (
            <div className="flex items-center justify-between gap-2 rounded-lg bg-muted/50 px-4 py-3">
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <CheckCircle2 className="h-4 w-4" />
                과거 적중률
                <span className="text-xs text-muted-foreground/70">
                  ({insights.hitRateSims}회 시뮬레이션)
                </span>
              </span>
              <span
                className={`text-xl font-bold tabular-nums ${
                  insights.hitRate >= 0.8
                    ? "text-emerald-700"
                    : insights.hitRate >= 0.6
                      ? "text-amber-700"
                      : "text-red-700"
                }`}
              >
                {Math.round(insights.hitRate * 100)}%
              </span>
            </div>
          )}
          {insights.expectedActualCost != null && (
            <div className="flex items-center justify-between gap-2 rounded-lg bg-muted/50 px-4 py-3">
              <span className="text-sm text-muted-foreground">
                예상 실 지불액
                <span className="ml-1 text-xs text-muted-foreground/70">
                  (2순위 가격)
                </span>
              </span>
              <span className="text-xl font-bold tabular-nums text-foreground">
                {formatKRW(insights.expectedActualCost)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatRow({
  icon,
  iconClass,
  label,
  sublabel,
  value,
}: {
  icon: React.ReactNode;
  iconClass: string;
  label: string;
  sublabel?: string;
  value: string;
}) {
  return (
    <div className="flex flex-col items-center py-4 text-center first:pt-0 last:pb-0">
      <div className="flex flex-col items-center gap-2">
        <span
          className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${iconClass}`}
        >
          {icon}
        </span>
        <div>
          <div className="text-base font-medium text-muted-foreground">
            {label}
          </div>
          {sublabel && (
            <div className="mt-0.5 text-xs text-muted-foreground/70">
              {sublabel}
            </div>
          )}
        </div>
      </div>
      <div className="mt-3 text-4xl font-bold tabular-nums">{value}</div>
    </div>
  );
}
