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

type ChartDatum = {
  round: string;
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
  const { active, payload, label } = props;
  if (!active || !payload || payload.length === 0) return null;
  const datum = payload[0].payload as ChartDatum;
  return (
    <div className="rounded-md border bg-background px-3 py-2 text-xs shadow">
      <div className="font-semibold">{label}</div>
      {payload.map((p) => (
        <div key={p.name}>
          <span className="text-muted-foreground">{p.name}:</span>{" "}
          {p.value == null ? "-" : `${Number(p.value).toLocaleString()}원`}
        </div>
      ))}
      {datum.brands.length > 0 && (
        <div className="mt-1 border-t pt-1 text-muted-foreground">
          집행: {datum.brands.join(" / ")}
        </div>
      )}
    </div>
  );
}

export function TrendChart({ rounds }: { rounds: RoundRow[] }) {
  const data: ChartDatum[] = rounds.map((r) => ({
    round: String(r.roundNo),
    minBid: r.minBidPrice,
    winning: r.regularWinningBid,
    brands: r.brands.map((b) => b.displayName),
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey="round" className="text-xs" />
          <YAxis
            className="text-xs"
            width={80}
            tickFormatter={(v) => Number(v).toLocaleString()}
          />
          <Tooltip content={<ChartTooltip />} />
          <Legend
            verticalAlign="top"
            align="right"
            iconType="line"
            wrapperStyle={{ fontSize: "12px", paddingBottom: "8px" }}
          />
          <Line
            type="monotone"
            dataKey="minBid"
            name="최저입찰가"
            stroke="#64748b"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            dot={{ r: 2, fill: "#64748b" }}
          />
          <Line
            type="monotone"
            dataKey="winning"
            name="낙찰가"
            stroke="#0ea5e9"
            strokeWidth={2.5}
            dot={{ r: 3.5, fill: "#0ea5e9" }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
