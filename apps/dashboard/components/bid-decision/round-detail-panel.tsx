import { Card, CardContent } from "@/components/ui/card";
import type { RoundRow } from "@/types/bid-decision";
import { formatDate, formatKRW, formatRatio } from "@/lib/format";

function statusClass(status: string | null | undefined): string {
  if (status === "정기입찰") return "bg-blue-50 text-blue-700 ring-blue-200";
  if (status === "재입찰") return "bg-green-50 text-green-700 ring-green-200";
  return "bg-muted text-muted-foreground ring-border";
}

export function RoundDetailPanel({ round }: { round: RoundRow | null }) {
  if (!round) {
    return (
      <Card>
        <CardContent className="p-8 text-base text-muted-foreground">
          좌측 회차를 선택하면 상세가 표시됩니다.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardContent className="space-y-7 p-8">
        {/* Header */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-muted-foreground">회차</div>
            <div className="mt-1 font-mono text-2xl font-bold">{round.roundNo}</div>
            <div className="mt-1.5 font-mono text-sm tabular-nums text-muted-foreground">
              {formatDate(round.periodStart)}
              <span className="mx-1.5">~</span>
              {formatDate(round.periodEnd)}
            </div>
          </div>
          <span
            className={`rounded-full px-3.5 py-1.5 text-sm font-semibold ring-1 ${statusClass(round.bidStatus)}`}
          >
            {round.bidStatus ?? "-"}
          </span>
        </div>

        {/* Bid stats */}
        <div className="grid grid-cols-3 gap-4 rounded-xl border bg-muted/30 p-4">
          <Stat label="최저 (VAT-)" value={formatKRW(round.minBidPrice)} />
          <Stat label="낙찰 (VAT-)" value={formatKRW(round.regularWinningBid)} />
          <Stat label="배수" value={formatRatio(round.ratio)} />
        </div>

        {/* Vacancy */}
        <div className="flex items-center justify-between border-b pb-4">
          <span className="text-base font-medium text-muted-foreground">공실 구좌</span>
          <span
            className={`text-lg font-bold tabular-nums ${
              (round.emptySlots ?? 0) > 0 ? "text-amber-600" : ""
            }`}
          >
            {round.emptySlots == null
              ? "정보 없음"
              : round.emptySlots === 0
                ? "풀집행"
                : `${round.emptySlots}구좌`}
          </span>
        </div>

        {/* Brands */}
        <div className="space-y-3">
          <div className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            집행 브랜드
          </div>
          {round.brands.length === 0 ? (
            round.brandsScrapedAt ? (
              <div className="rounded-xl border border-dashed bg-muted/20 p-6 text-center text-base text-muted-foreground">
                집행사 없음
                <div className="mt-1 text-sm">
                  수집 시각 {formatDate(round.brandsScrapedAt)}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed bg-amber-50/40 p-6 text-center text-base text-amber-700">
                아직 스크래핑되지 않은 회차입니다
              </div>
            )
          ) : (
            <ul className="space-y-3">
              {round.brands.map((b) => (
                <li
                  key={`${b.slotNo}-${b.businessName}`}
                  className="rounded-xl border p-5"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="text-xl font-bold">{b.displayName}</div>
                    <div className="font-mono text-sm font-medium text-muted-foreground">
                      슬롯 {b.slotNo}
                    </div>
                  </div>
                  {b.subTitle && (
                    <div className="mt-3 text-sm font-semibold text-accent">
                      {b.subTitle}
                    </div>
                  )}
                  <div className="mt-1.5 text-base font-semibold" title={b.title}>
                    {b.title}
                  </div>
                  {b.description && (
                    <div
                      className="mt-2 text-sm leading-relaxed text-muted-foreground"
                      title={b.description}
                    >
                      {b.description}
                    </div>
                  )}
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                    <span className="truncate font-mono" title={b.businessName}>
                      {b.businessName}
                    </span>
                    {b.confidence != null && (
                      <span className="shrink-0 tabular-nums">
                        신뢰도 {b.confidence.toFixed(2)}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-bold tabular-nums">{value}</div>
    </div>
  );
}
