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

export function RoundTable({ rounds }: { rounds: RoundRow[] }) {
  const display = [...rounds].reverse();
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-24">회차</TableHead>
            <TableHead className="w-40">집행기간</TableHead>
            <TableHead className="text-right">최저</TableHead>
            <TableHead className="text-right">낙찰</TableHead>
            <TableHead className="text-right">배수</TableHead>
            <TableHead className="text-right w-20">공실</TableHead>
            <TableHead className="w-40">집행 브랜드</TableHead>
            <TableHead className="w-32">상태</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {display.map((r) => (
            <TableRow key={r.roundId}>
              <TableCell className="font-mono text-xs">{r.roundNo}</TableCell>
              <TableCell className="text-xs">
                {formatDate(r.periodStart)}~{formatDate(r.periodEnd)}
              </TableCell>
              <TableCell className="text-right">{formatKRW(r.minBidPrice)}</TableCell>
              <TableCell className="text-right">{formatKRW(r.regularWinningBid)}</TableCell>
              <TableCell className="text-right">{formatRatio(r.ratio)}</TableCell>
              <TableCell className="text-right">
                {r.emptySlots == null ? "-" : `${r.emptySlots}구좌`}
              </TableCell>
              <TableCell className="text-muted-foreground text-xs">- (W4)</TableCell>
              <TableCell className="text-xs">{r.bidStatus ?? "-"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
