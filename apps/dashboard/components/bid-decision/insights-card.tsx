import { Card, CardContent } from "@/components/ui/card";
import type { Insights } from "@/types/bid-decision";
import { formatKRW, formatRatio } from "@/lib/format";

export function InsightsCard({ insights }: { insights: Insights }) {
  const vacancyPct =
    insights.vacancyRate == null
      ? "-"
      : `${Math.round(insights.vacancyRate * 100)}%`;

  return (
    <Card>
      <CardContent className="grid grid-cols-1 gap-4 p-4 md:grid-cols-3">
        <Stat label="평균 낙찰/최저 배수" value={formatRatio(insights.meanRatio)} />
        <Stat label="공실 발생률" value={vacancyPct} />
        <Stat
          label="추천 입찰가 레인지 (VAT-)"
          value={
            insights.recommendedLow && insights.recommendedHigh
              ? `${formatKRW(insights.recommendedLow)} ~ ${formatKRW(insights.recommendedHigh)}`
              : "-"
          }
        />
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}
