import { getBacktestResults } from "@/lib/db/queries";
import { formatKRW } from "@/lib/format";
import { Activity, CheckCircle2, XCircle } from "lucide-react";
import {
  TuneProvider,
  TuneTrigger,
  TuneResults,
} from "@/components/backtest/tune-button";
import { ActiveStrategyCard } from "@/components/backtest/active-strategy-card";
import { getActiveStrategyParams } from "@/lib/db/strategy-params";
import { createDb } from "@/lib/db/client";

export const dynamic = "force-dynamic";

const PRODUCT_LABEL: Record<string, string> = {
  SEARCHING_VIEW: "서칭뷰",
  NEW_PRODUCT: "신제품검색",
  ANNIVERSARY: "기념일",
};

export default async function BacktestPage() {
  const db = createDb();
  const [{ aggregates, perKg }, activeStrategyRows] = await Promise.all([
    getBacktestResults(),
    getActiveStrategyParams(db),
  ]);

  // Sort aggregates: SV first then NP
  aggregates.sort((a, b) => (a.product === "SEARCHING_VIEW" ? -1 : 1));

  const worstKgs = perKg.filter((k) => k.simulations >= 3).slice(0, 20);
  const bestKgs = [...perKg]
    .filter((k) => k.simulations >= 3)
    .sort((a, b) => b.winRate - a.winRate)
    .slice(0, 10);

  return (
    <TuneProvider>
      <header className="border-b bg-card px-8 py-6">
        <div className="flex items-start justify-between gap-6">
          <div>
            <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
              <Activity className="h-7 w-7 text-emerald-500" />
              추천가 검증 (백테스트)
            </h1>
            <p className="mt-1 text-base text-muted-foreground">
              매주 누적되는 낙찰가 데이터로 현재 추천 로직을 자기 검증합니다.
              과거 회차마다 "그 시점에 이용 가능한 데이터로만 추천했을 때" 실제 낙찰가를 따라잡을 수 있었는지 평가.
            </p>
          </div>
          <TuneTrigger />
        </div>
      </header>

      <div className="space-y-6 px-8 py-6">
        {/* Currently active strategy params (from DB) */}
        <ActiveStrategyCard rows={activeStrategyRows} />
        {/* Tuning results — appears on top after running tune */}
        <TuneResults />
        {/* Per-product aggregates */}
        <div className="grid gap-4 sm:grid-cols-2">
          {aggregates.map((agg) => (
            <div key={agg.product} className="rounded-xl border bg-card p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="text-lg font-semibold">
                  {PRODUCT_LABEL[agg.product] ?? agg.product}
                </div>
                <div
                  className={`rounded-full px-3 py-1 text-sm font-semibold ${
                    agg.winRate >= 0.8
                      ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                      : agg.winRate >= 0.6
                        ? "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
                        : "bg-red-50 text-red-700 ring-1 ring-red-200"
                  }`}
                >
                  적중률 {Math.round(agg.winRate * 100)}%
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <Stat
                  label="시뮬레이션"
                  value={`${agg.totalSimulations.toLocaleString()}회`}
                />
                <Stat
                  label="낙찰 가능"
                  value={`${agg.wins.toLocaleString()}회`}
                  accent="ok"
                />
                <Stat
                  label="평균 과지불 (낙찰 시)"
                  value={formatKRW(Math.round(agg.avgOverpayWhenWon))}
                  accent="muted"
                  hint="추천 상한 − 실제 낙찰가"
                />
                <Stat
                  label="평균 부족액 (실패 시)"
                  value={formatKRW(Math.round(agg.avgUnderbidWhenLost))}
                  accent="warn"
                  hint="실제 낙찰가 − 추천 상한"
                />
              </div>
            </div>
          ))}
        </div>

        {/* Worst KGs (lowest win rate) */}
        <section>
          <h2 className="mb-3 text-xl font-semibold text-red-700">
            🚨 적중률 부진 KG (개선 우선순위)
          </h2>
          <p className="mb-3 text-sm text-muted-foreground">
            추천이 실제 낙찰가를 자주 놓친 키워드그룹. 이 KG들의 시장이 빠르게 움직이고 있거나, 가중치/프리미엄을 조정할 필요가 있을 수 있어요.
          </p>
          <KgTable rows={worstKgs} variant="worst" />
        </section>

        {/* Best KGs */}
        <section>
          <h2 className="mb-3 text-xl font-semibold text-emerald-700">
            ✅ 적중률 우수 KG
          </h2>
          <KgTable rows={bestKgs} variant="best" />
        </section>

        {/* Tip */}
        <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
          💡 매주 NOSP CSV가 새로 들어오면 이 페이지가 자동 갱신됩니다.
          적중률이 점차 떨어지면 → 시장 변동성이 커지는 신호. 우상단 "파라미터 자동 튜닝" 버튼을 눌러 최적 조합을 다시 찾을 수 있어요.
        </div>
      </div>
    </TuneProvider>
  );
}

function Stat({
  label,
  value,
  accent,
  hint,
}: {
  label: string;
  value: string;
  accent?: "ok" | "warn" | "muted";
  hint?: string;
}) {
  const color =
    accent === "ok"
      ? "text-emerald-700"
      : accent === "warn"
        ? "text-amber-700"
        : "text-foreground";
  return (
    <div title={hint}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`mt-0.5 text-lg font-bold tabular-nums ${color}`}>
        {value}
      </div>
    </div>
  );
}

function KgTable({
  rows,
  variant,
}: {
  rows: Awaited<ReturnType<typeof getBacktestResults>>["perKg"];
  variant: "worst" | "best";
}) {
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-4 py-3 text-left font-semibold">키워드그룹</th>
            <th className="px-4 py-3 text-left font-semibold">제품</th>
            <th className="px-4 py-3 text-right font-semibold">시뮬레이션</th>
            <th className="px-4 py-3 text-right font-semibold">낙찰</th>
            <th className="px-4 py-3 text-right font-semibold">적중률</th>
            <th className="px-4 py-3 text-right font-semibold">마지막 회차 차이</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                데이터 부족 (각 KG 최소 3회 시뮬레이션 필요)
              </td>
            </tr>
          )}
          {rows.map((r) => (
            <tr key={r.kgId} className="border-t">
              <td className="px-4 py-3 font-medium">{r.kgName}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {PRODUCT_LABEL[r.product] ?? r.product}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">{r.simulations}</td>
              <td className="px-4 py-3 text-right tabular-nums">{r.wins}</td>
              <td className="px-4 py-3 text-right">
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold tabular-nums ${
                    r.winRate >= 0.8
                      ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                      : r.winRate >= 0.6
                        ? "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
                        : "bg-red-50 text-red-700 ring-1 ring-red-200"
                  }`}
                >
                  {variant === "best" ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : r.winRate >= 0.8 ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : (
                    <XCircle className="h-3 w-3" />
                  )}
                  {Math.round(r.winRate * 100)}%
                </span>
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {r.lastRoundDiff == null ? (
                  "-"
                ) : (
                  <span
                    className={
                      r.lastRoundDiff < 0
                        ? "text-red-600 font-semibold"
                        : "text-muted-foreground"
                    }
                  >
                    {r.lastRoundDiff > 0 ? "+" : ""}
                    {formatKRW(Math.round(r.lastRoundDiff))}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
