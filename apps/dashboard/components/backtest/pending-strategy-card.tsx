"use client";

import { useTransition } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { activateStrategyAction } from "@/app/backtest/actions";
import type { StrategyParamsRow } from "@/lib/db/strategy-params";

const PRODUCT_LABEL: Record<string, string> = {
  SEARCHING_VIEW: "서칭뷰",
  NEW_PRODUCT: "신제품검색",
  ANNIVERSARY: "기념일",
};

type Props = { rows: StrategyParamsRow[]; isAdmin: boolean };

export function PendingStrategyCard({ rows, isAdmin }: Props) {
  if (rows.length === 0) return null;
  return (
    <section className="rounded-lg border border-amber-400 bg-amber-50 p-6 dark:border-amber-700 dark:bg-amber-950/30">
      <header className="mb-3 flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-amber-600" />
        <h2 className="text-lg font-semibold text-amber-900 dark:text-amber-200">
          대기 중인 새 파라미터 ({rows.length}건)
        </h2>
      </header>
      <p className="mb-4 text-sm text-amber-800 dark:text-amber-300">
        직전 활성 값 대비 변동폭이 ±25%를 초과하여 자동 반영이 보류되었습니다.
        백테스트 결과를 확인하고 활성화하세요.
        {!isAdmin && " 관리자만 활성화할 수 있습니다."}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-amber-300/50 text-left text-xs uppercase tracking-wide text-amber-800/80">
              <th className="pb-2 pr-4">상품</th>
              <th className="pb-2 pr-4 text-center">백테스트 적중률</th>
              <th className="pb-2 pr-4 text-center">최대 변동폭</th>
              <th className="pb-2 pr-4 text-center">샘플 수</th>
              <th className="pb-2 pr-4 text-center">생성 시각</th>
              <th className="pb-2 text-right"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <ActivateRow key={r.id} row={r} isAdmin={isAdmin} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ActivateRow({ row, isAdmin }: { row: StrategyParamsRow; isAdmin: boolean }) {
  const [pending, startTransition] = useTransition();
  return (
    <tr className="border-b border-amber-200/50 last:border-0">
      <td className="py-2 pr-4 font-medium text-amber-900 dark:text-amber-200">
        {PRODUCT_LABEL[row.productCode] ?? row.productCode}
      </td>
      <td className="py-2 pr-4 text-center">
        {row.backtestScoreBps != null
          ? `${(row.backtestScoreBps / 100).toFixed(1)}%`
          : "—"}
      </td>
      <td className="py-2 pr-4 text-center">
        {row.deltaMaxBps != null
          ? `±${(row.deltaMaxBps / 100).toFixed(1)}%`
          : "—"}
      </td>
      <td className="py-2 pr-4 text-center">
        {row.sampleSize != null ? row.sampleSize.toLocaleString("ko-KR") : "—"}
      </td>
      <td className="py-2 pr-4 text-center text-xs">
        {new Date(row.createdAt).toLocaleString("ko-KR")}
      </td>
      <td className="py-2 text-right">
        {isAdmin && (
          <button
            type="button"
            disabled={pending}
            onClick={() =>
              startTransition(async () => {
                await activateStrategyAction(row.id);
              })
            }
            className="inline-flex items-center gap-1 rounded bg-amber-600 px-3 py-1 text-xs font-medium text-white shadow-sm transition hover:bg-amber-700 disabled:opacity-60"
          >
            {pending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            활성화
          </button>
        )}
      </td>
    </tr>
  );
}
