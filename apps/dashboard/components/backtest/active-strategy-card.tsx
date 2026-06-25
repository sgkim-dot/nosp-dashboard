import type { StrategyParamsRow } from "@/lib/db/strategy-params";
import { Settings } from "lucide-react";

const PRODUCT_LABEL: Record<string, string> = {
  SEARCHING_VIEW: "서칭뷰",
  NEW_PRODUCT: "신제품검색",
  ANNIVERSARY: "기념일",
};

type Props = { rows: StrategyParamsRow[] };

export function ActiveStrategyCard({ rows }: Props) {
  if (rows.length === 0) {
    return (
      <section className="rounded-lg border bg-card p-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Settings className="h-4 w-4" />
          활성 파라미터 없음 — 코드 fallback(DEFAULT_STRATEGY)이 사용 중입니다.
        </div>
      </section>
    );
  }

  // Sort: SV first, then NP, then ANN, then anything else alpha
  const orderKey = (p: string) =>
    p === "SEARCHING_VIEW" ? 0 : p === "NEW_PRODUCT" ? 1 : p === "ANNIVERSARY" ? 2 : 9;
  const sorted = [...rows].sort((a, b) => orderKey(a.productCode) - orderKey(b.productCode));

  return (
    <section className="rounded-lg border bg-card p-6">
      <header className="mb-4 flex items-center gap-2">
        <Settings className="h-5 w-5 text-emerald-500" />
        <h2 className="text-lg font-semibold">현재 활성 파라미터</h2>
        <span className="text-xs text-muted-foreground">
          ({rows.length}개 상품 · 실제 추천가 계산에 사용되는 값)
        </span>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="pb-2 pr-4">상품</th>
              <th className="pb-2 pr-4 text-center">가중치</th>
              <th className="pb-2 pr-4 text-center">P-low</th>
              <th className="pb-2 pr-4 text-center">P-high</th>
              <th className="pb-2 pr-4 text-center">Premium-low</th>
              <th className="pb-2 pr-4 text-center">Premium-high</th>
              <th className="pb-2 pr-4 text-center">백테스트 적중률</th>
              <th className="pb-2 text-center">활성화 시각</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.id} className="border-b last:border-0">
                <td className="py-2 pr-4 font-medium">
                  {PRODUCT_LABEL[r.productCode] ?? r.productCode}
                </td>
                <td className="py-2 pr-4 text-center font-mono text-xs">
                  {JSON.stringify(r.weights)}
                </td>
                <td className="py-2 pr-4 text-center">
                  {(r.lowPercentileBps / 100).toFixed(0)}%
                </td>
                <td className="py-2 pr-4 text-center">
                  {(r.highPercentileBps / 100).toFixed(0)}%
                </td>
                <td className="py-2 pr-4 text-center">
                  {(r.lowPremiumBps / 100).toFixed(1)}%
                </td>
                <td className="py-2 pr-4 text-center">
                  {(r.highPremiumBps / 100).toFixed(1)}%
                </td>
                <td className="py-2 pr-4 text-center">
                  {r.backtestScoreBps != null
                    ? `${(r.backtestScoreBps / 100).toFixed(1)}%`
                    : "—"}
                </td>
                <td className="py-2 text-center text-xs text-muted-foreground">
                  {r.activatedAt
                    ? new Date(r.activatedAt).toLocaleDateString("ko-KR")
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Premium-low/high의 100%는 1.00배 (가산 없음), 120%는 1.20배 의미.
        가중치는 최근 회차부터 적용되는 weighted percentile의 weight 배열.
      </p>
    </section>
  );
}
