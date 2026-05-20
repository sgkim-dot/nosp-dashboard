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

export function TrendChart({ rounds }: { rounds: RoundRow[] }) {
  const data = rounds.map((r) => ({
    round: String(r.roundNo),
    minBid: r.minBidPrice,
    winning: r.regularWinningBid,
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey="round" className="text-xs" />
          <YAxis
            className="text-xs"
            tickFormatter={(v) =>
              v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : `${Math.round(v / 1000)}k`
            }
          />
          <Tooltip
            formatter={(value, name) => [
              value == null ? "-" : `${Number(value).toLocaleString()}원`,
              name as string,
            ]}
          />
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
