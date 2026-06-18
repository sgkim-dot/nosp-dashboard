"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RoundRow } from "@/types/bid-decision";
import { formatDate } from "@/lib/format";

type ChartDatum = {
  round: string;
  periodStart: string;
  periodEnd: string;
  minBid: number | null;
  winning: number | null;
  brands: string[];
};

type TooltipEntry = { name?: string; value?: number | null; payload?: ChartDatum };

function ChartTooltip(props: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
}) {
  const { active, payload } = props;
  if (!active || !payload || payload.length === 0) return null;
  const datum = payload[0].payload as ChartDatum;
  return (
    <div className="rounded-xl border bg-background px-5 py-4 text-sm shadow-lg min-w-[200px]">
      {/* Round badge — same chip style as the table status badges */}
      <div className="mb-2.5 flex items-center gap-2">
        <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 font-mono text-sm font-bold text-primary ring-1 ring-primary/20">
          {datum.round}회차
        </span>
      </div>
      {/* Execution period */}
      <div className="mb-3 font-mono text-xs tabular-nums text-muted-foreground">
        {formatDate(datum.periodStart)}
        <span className="mx-1.5">~</span>
        {formatDate(datum.periodEnd)}
      </div>
      {/* Prices */}
      <div className="space-y-1 border-t pt-2.5">
        {payload.map((p) => (
          <div key={p.name} className="flex items-center justify-between gap-4 tabular-nums">
            <span className="text-muted-foreground">{p.name}</span>
            <span className="font-semibold">
              {p.value == null ? "-" : `${Number(p.value).toLocaleString()}원`}
            </span>
          </div>
        ))}
      </div>
      {datum.brands.length > 0 && (
        <div className="mt-2.5 border-t pt-2.5 text-xs">
          <span className="text-muted-foreground">집행: </span>
          <span className="font-medium">{datum.brands.join(" / ")}</span>
        </div>
      )}
    </div>
  );
}

export function TrendChart({ rounds }: { rounds: RoundRow[] }) {
  const data: ChartDatum[] = rounds.map((r) => ({
    round: String(r.roundNo),
    periodStart: r.periodStart,
    periodEnd: r.periodEnd,
    minBid: r.minBidPrice,
    winning: r.regularWinningBid,
    brands: r.brands.map((b) => b.displayName),
  }));

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary/10 text-primary">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="3 17 9 11 13 15 21 7" /></svg>
        </span>
        <span className="text-base font-semibold">회차별 추이</span>
      </div>
      <div className="h-[460px] w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey="round" tick={{ fontSize: 13 }} />
          <YAxis
            tick={{ fontSize: 13 }}
            width={88}
            tickFormatter={(v) => Number(v).toLocaleString()}
          />
          <Tooltip content={<ChartTooltip />} />
          <Legend
            verticalAlign="top"
            align="right"
            iconType="line"
            wrapperStyle={{ fontSize: "14px", paddingBottom: "12px", fontWeight: 500 }}
          />
          <Line
            type="monotone"
            dataKey="minBid"
            name="최저입찰가"
            stroke="#64748b"
            strokeWidth={2}
            strokeDasharray="4 4"
            dot={{ r: 3, fill: "#64748b" }}
          />
          <Line
            type="monotone"
            dataKey="winning"
            name="낙찰가"
            stroke="#0e7a76"
            strokeWidth={3}
            dot={{ r: 4.5, fill: "#0e7a76" }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
