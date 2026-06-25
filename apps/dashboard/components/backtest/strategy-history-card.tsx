"use client";

import { useTransition } from "react";
import { Loader2, History } from "lucide-react";
import { activateStrategyAction } from "@/app/backtest/actions";
import type { StrategyParamsRow } from "@/lib/db/strategy-params";

const PRODUCT_LABEL: Record<string, string> = {
  SEARCHING_VIEW: "서칭뷰",
  NEW_PRODUCT: "신제품검색",
  ANNIVERSARY: "기념일",
};

type Props = {
  productCode: string;
  rows: StrategyParamsRow[];
  isAdmin: boolean;
};

export function StrategyHistoryCard({ productCode, rows, isAdmin }: Props) {
  if (rows.length === 0) return null;
  return (
    <section className="rounded-lg border bg-card p-6">
      <header className="mb-4 flex items-center gap-2">
        <History className="h-5 w-5 text-muted-foreground" />
        <h3 className="text-base font-semibold">
          {PRODUCT_LABEL[productCode] ?? productCode} 튜닝 이력
        </h3>
        <span className="text-xs text-muted-foreground">
          (최근 {rows.length}건)
        </span>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="pb-2 pr-4">생성</th>
              <th className="pb-2 pr-4 text-center">상태</th>
              <th className="pb-2 pr-4 text-center">적중률</th>
              <th className="pb-2 pr-4 text-center">가중치</th>
              <th className="pb-2 pr-4 text-center">P-low / P-high</th>
              <th className="pb-2 pr-4 text-center">Prem-low / Prem-high</th>
              <th className="pb-2 pr-4 text-xs">출처</th>
              <th className="pb-2 text-right"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <HistoryRow key={r.id} row={r} isAdmin={isAdmin} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function HistoryRow({ row, isAdmin }: { row: StrategyParamsRow; isAdmin: boolean }) {
  const [pending, startTransition] = useTransition();
  return (
    <tr className="border-b last:border-0">
      <td className="py-2 pr-4 text-xs text-muted-foreground">
        {new Date(row.createdAt).toLocaleString("ko-KR")}
      </td>
      <td className="py-2 pr-4 text-center">
        <StatusBadge status={row.status} />
      </td>
      <td className="py-2 pr-4 text-center">
        {row.backtestScoreBps != null
          ? `${(row.backtestScoreBps / 100).toFixed(1)}%`
          : "—"}
      </td>
      <td className="py-2 pr-4 text-center font-mono text-xs">
        {JSON.stringify(row.weights)}
      </td>
      <td className="py-2 pr-4 text-center text-xs">
        {(row.lowPercentileBps / 100).toFixed(0)}% / {(row.highPercentileBps / 100).toFixed(0)}%
      </td>
      <td className="py-2 pr-4 text-center text-xs">
        {(row.lowPremiumBps / 100).toFixed(1)}% / {(row.highPremiumBps / 100).toFixed(1)}%
      </td>
      <td className="py-2 pr-4 text-xs text-muted-foreground">{row.source}</td>
      <td className="py-2 text-right">
        {isAdmin && row.status === "archived" && (
          <button
            type="button"
            disabled={pending}
            onClick={() =>
              startTransition(async () => {
                await activateStrategyAction(row.id);
              })
            }
            className="inline-flex items-center gap-1 rounded border px-3 py-1 text-xs font-medium transition hover:bg-muted disabled:opacity-60"
          >
            {pending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            롤백
          </button>
        )}
      </td>
    </tr>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "active"
      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
      : status === "pending"
        ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
        : "bg-muted text-muted-foreground";
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
