import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { RoundRow } from "@/types/bid-decision";
import { formatDate, formatKRW, formatRatio } from "@/lib/format";

function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-muted-foreground">-</span>;
  const tone =
    status === "정기입찰"
      ? "bg-blue-50 text-blue-700 ring-blue-200"
      : status === "재입찰"
        ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
        : "bg-muted text-muted-foreground ring-border";
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ${tone}`}
    >
      {status}
    </span>
  );
}

export function RoundTable({
  rounds,
  selectedRoundId,
  onSelect,
}: {
  rounds: RoundRow[];
  selectedRoundId?: number | null;
  onSelect?: (roundId: number) => void;
}) {
  const display = [...rounds].reverse();
  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-x-auto w-fit max-w-full">
      <Table className="text-base w-auto">
        <colgroup>
          <col className="w-[96px]" />
          <col className="w-[160px]" />
          <col className="w-[112px]" />
          <col className="w-[140px]" />
          <col className="w-[140px]" />
          <col className="w-[80px]" />
          <col className="w-[88px]" />
          <col className="w-[240px]" />
          <col className="w-[120px]" />
        </colgroup>
        <TableHeader>
          <TableRow className="[&_th]:text-center [&_th]:text-sm [&_th]:font-semibold [&_th]:text-muted-foreground [&_th]:py-3 bg-muted/40">
            <TableHead>회차</TableHead>
            <TableHead>집행기간</TableHead>
            <TableHead>기준조회수</TableHead>
            <TableHead>최저 (VAT-)</TableHead>
            <TableHead>낙찰 (VAT-)</TableHead>
            <TableHead>배수</TableHead>
            <TableHead>공실</TableHead>
            <TableHead>집행 브랜드</TableHead>
            <TableHead>상태</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {display.map((r) => (
            <TableRow
              key={r.roundId}
              onClick={onSelect ? () => onSelect(r.roundId) : undefined}
              className={`[&_td]:text-center [&_td]:py-3 ${
                onSelect
                  ? `cursor-pointer ${
                      r.roundId === selectedRoundId ? "bg-muted/60" : "hover:bg-muted/40"
                    }`
                  : ""
              }`}
            >
              <TableCell className="font-mono text-sm">{r.roundNo}</TableCell>
              <TableCell className="font-mono text-sm whitespace-nowrap tabular-nums">
                {formatDate(r.periodStart)}
                <span className="mx-1.5 text-muted-foreground">~</span>
                {formatDate(r.periodEnd)}
              </TableCell>
              <TableCell className="tabular-nums">
                {r.referenceQueryVolume == null
                  ? "-"
                  : r.referenceQueryVolume.toLocaleString()}
              </TableCell>
              <TableCell className="tabular-nums">{formatKRW(r.minBidPrice)}</TableCell>
              <TableCell className="tabular-nums font-medium">{formatKRW(r.regularWinningBid)}</TableCell>
              <TableCell className="tabular-nums">{formatRatio(r.ratio)}</TableCell>
              <TableCell className="tabular-nums">
                {r.emptySlots == null ? "-" : `${r.emptySlots}구좌`}
              </TableCell>
              <TableCell className="text-sm truncate">
                {r.brands.length > 0 ? (
                  <span title={r.brands.map((b) => `${b.title} (${b.businessName})`).join("\n")}>
                    {r.brands.map((b) => b.displayName).join(" / ")}
                  </span>
                ) : r.brandsScrapedAt ? (
                  <span className="text-muted-foreground" title={`수집 시각: ${r.brandsScrapedAt}`}>
                    집행사 없음
                  </span>
                ) : (
                  <span className="text-amber-600/80" title="아직 스크래핑되지 않은 KG입니다">
                    미수집
                  </span>
                )}
              </TableCell>
              <TableCell>
                <StatusBadge status={r.bidStatus} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
