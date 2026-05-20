import { Card, CardContent } from "@/components/ui/card";
import type { KeywordGroupSummary } from "@/types/bid-decision";
import { formatKRW } from "@/lib/format";

export function SummaryCard({ summary }: { summary: KeywordGroupSummary }) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-6 p-4">
        <div>
          <div className="text-xs text-muted-foreground">키워드그룹</div>
          <div className="text-lg font-semibold">
            {summary.keywordGroupName}
            <span className="ml-2 text-xs text-muted-foreground">
              {summary.product === "SEARCHING_VIEW" ? "서칭뷰" : "신제품검색"}
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            {summary.categoryLvl1} · {summary.categoryLvl2}
          </div>
        </div>

        <Stat label="최근 낙찰가" value={formatKRW(summary.latestWinning)} />
        <Stat
          label="공실 구좌"
          value={summary.latestEmptySlots == null ? "-" : `${summary.latestEmptySlots}구좌`}
          accent={(summary.latestEmptySlots ?? 0) > 0 ? "warn" : undefined}
        />
        <Stat label="현재 집행 브랜드" value="- (W4 예정)" muted />
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  accent,
  muted,
}: {
  label: string;
  value: string;
  accent?: "warn";
  muted?: boolean;
}) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={`text-lg font-semibold ${
          accent === "warn" ? "text-amber-600" : muted ? "text-muted-foreground" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}
