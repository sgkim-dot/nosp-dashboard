"use client";

import { createContext, useContext, useState, useTransition, type ReactNode } from "react";
import { RefreshCw, Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import { formatKRW } from "@/lib/format";
import type { TuneResult } from "@/lib/db/queries";
import { runTuneAction } from "@/app/backtest/actions";

const PRODUCT_LABEL: Record<string, string> = {
  SEARCHING_VIEW: "서칭뷰",
  NEW_PRODUCT: "신제품검색",
};

type TuneCtx = {
  results: TuneResult[] | null;
  error: string | null;
  pending: boolean;
  run: () => void;
  expanded: boolean;
  setExpanded: (v: boolean) => void;
};

const Ctx = createContext<TuneCtx | null>(null);

export function TuneProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<TuneResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [pending, startTransition] = useTransition();

  const run = () => {
    setError(null);
    startTransition(async () => {
      try {
        const r = await runTuneAction();
        setResults(r);
        setExpanded(true);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    });
  };

  return (
    <Ctx.Provider value={{ results, error, pending, run, expanded, setExpanded }}>
      {children}
    </Ctx.Provider>
  );
}

function useTune() {
  const c = useContext(Ctx);
  if (!c) throw new Error("TuneProvider missing");
  return c;
}

/** Compact button + status — meant for the page header right side. */
export function TuneTrigger() {
  const { pending, run, results } = useTune();
  return (
    <button
      type="button"
      onClick={run}
      disabled={pending}
      className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/90 disabled:opacity-60"
      title="3,024개 파라미터 조합을 백테스트해 최적 조합을 찾습니다 (5~15초)"
    >
      {pending ? (
        <RefreshCw className="h-4 w-4 animate-spin" />
      ) : (
        <Sparkles className="h-4 w-4" />
      )}
      {pending ? "튜닝 중…" : results ? "다시 튜닝" : "파라미터 자동 튜닝"}
    </button>
  );
}

/** Full results panel — shows the top-N candidates per product. */
export function TuneResults() {
  const { results, error, expanded, setExpanded } = useTune();

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        ⚠️ {error}
      </div>
    );
  }
  if (!results) return null;

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="h-5 w-5" />
          </span>
          <div>
            <div className="text-base font-semibold">튜닝 결과</div>
            <div className="text-xs text-muted-foreground">
              {results.reduce((s, r) => s + r.evaluated, 0).toLocaleString()}개 조합 평가됨 · 각 제품군 Top 5
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" /> 접기
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" /> 펼치기
            </>
          )}
        </button>
      </div>

      {expanded && (
        <div className="mt-4 space-y-4">
          {results.map((r) => (
            <div key={r.product} className="rounded-lg border bg-background">
              <div className="border-b bg-muted/30 px-4 py-2 text-sm font-semibold">
                {PRODUCT_LABEL[r.product] ?? r.product} · Top 5
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold">#</th>
                      <th className="px-3 py-2 text-left font-semibold">weights</th>
                      <th className="px-3 py-2 text-right font-semibold">lowP</th>
                      <th className="px-3 py-2 text-right font-semibold">highP</th>
                      <th className="px-3 py-2 text-right font-semibold">lowMul</th>
                      <th className="px-3 py-2 text-right font-semibold">highMul</th>
                      <th className="px-3 py-2 text-right font-semibold">sims</th>
                      <th className="px-3 py-2 text-right font-semibold">win%</th>
                      <th className="px-3 py-2 text-right font-semibold">평균 과지불</th>
                      <th className="px-3 py-2 text-right font-semibold">평균 부족액</th>
                      <th className="px-3 py-2 text-right font-semibold">score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.top.map((m, i) => (
                      <tr key={i} className={i === 0 ? "bg-emerald-50/50" : "border-t"}>
                        <td className="px-3 py-2 font-mono">{i + 1}</td>
                        <td className="px-3 py-2 font-mono text-[11px]">
                          ({m.candidate.weights.join(",")})
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {m.candidate.lowPercentile}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {m.candidate.highPercentile}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {m.candidate.lowPremium}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {m.candidate.highPremium}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {m.sims.toLocaleString()}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <span
                            className={`tabular-nums ${
                              m.winRate >= 0.95
                                ? "font-semibold text-emerald-700"
                                : ""
                            }`}
                          >
                            {(m.winRate * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                          {formatKRW(Math.round(m.avgOverpayWhenWon))}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          <span
                            className={
                              m.avgUnderbidWhenLost > 300_000
                                ? "text-amber-700"
                                : "text-muted-foreground"
                            }
                          >
                            {formatKRW(Math.round(m.avgUnderbidWhenLost))}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums font-semibold">
                          {m.score.toFixed(3)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}

          <div className="rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">
            💡 1위 조합이 마음에 들면{" "}
            <code className="rounded bg-background px-1.5 py-0.5 font-mono">
              apps/dashboard/lib/strategy.ts
            </code>{" "}
            의 STRATEGY 상수에 적용하면 됩니다. 코드 수정 요청하시면 적용해드려요.
          </div>
        </div>
      )}
    </div>
  );
}
