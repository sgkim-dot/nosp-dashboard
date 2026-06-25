import type { ProductCode } from "@/types/bid-decision";
import type { Db } from "@/lib/db/client";
import { getActiveStrategyParams } from "@/lib/db/strategy-params";

// Weight applied to the N most-recent rounds. Newest first.
// Tuned 2026-06-01 via tune_strategy.py: (5,3,2,1) gave the best backtest
// score across both SV and NP. Recent round counts 5x, last counts 1x.
export const RECENT_WEIGHTS = [5, 3, 2, 1] as const;

export type StrategyPreset = {
  label: string;
  hint: string;
  lowPercentile: number;
  highPercentile: number;
  lowPremium: number;
  highPremium: number;
  showExpectedCost: boolean;
  expectedCostPercentile?: number;
};

// Tuned 2026-06-01:
//   SV: 99.3% backtest win-rate (n=2,966), avg overpay 163K, underbid 108K
//   NP: 99.4% backtest win-rate (n=18,446), avg overpay 110K, underbid 530K
// Both use the same (lowPct=0.3, highPct=0.8, highPremium=1.2) sweet spot.
// SV lowPremium=1.0 (neutral floor), NP lowPremium=1.05 (slight aggression
// for #1 since published winning_bid = #2's bid).
export const DEFAULT_STRATEGY: Record<string, StrategyPreset> = {
  SEARCHING_VIEW: {
    label: "1슬롯 방어 전략",
    hint: "1순위 = 본인 입찰가 그대로 지불. P30~P80 구간 + 20% 안전마진. 백테스트 적중률 99.3%.",
    lowPercentile: 0.3,
    highPercentile: 0.8,
    lowPremium: 1.0,
    highPremium: 1.2,
    showExpectedCost: false,
  },
  NEW_PRODUCT: {
    label: "1순위 입찰 전략",
    hint: "2슬롯·2순위가격제. #2가격 예측(P70) 위로 5~30% 안전마진. 실 지불은 #2가격에 가까움. recommendedLow > expectedActualCost > 실 지불 보장.",
    // For NP, low/highPercentile are unused — low/high are derived directly
    // from expectedActualCost via the premium multipliers below.
    lowPercentile: 0.7,
    highPercentile: 0.7,
    lowPremium: 1.05,   // 5% above projected #2 → secure #1
    highPremium: 1.3,   // 30% above projected #2 → safety insurance
    showExpectedCost: true,
    expectedCostPercentile: 0.7,
  },
  ANNIVERSARY: {
    label: "1순위 입찰 전략",
    hint: "기념일 광고도 NP와 동일한 2슬롯·2순위가격제로 운영.",
    lowPercentile: 0.7,
    highPercentile: 0.7,
    lowPremium: 1.05,
    highPremium: 1.3,
    showExpectedCost: true,
    expectedCostPercentile: 0.7,
  },
};

/**
 * Backwards-compat alias. Existing callers that read the hardcoded preset
 * (UI labels, non-server modules) continue to import STRATEGY. New code that
 * specifically wants the fallback should reach for DEFAULT_STRATEGY.
 */
export const STRATEGY = DEFAULT_STRATEGY;

/**
 * Load the active strategy params from DB for all product codes,
 * mapped into the same StrategyPreset shape as DEFAULT_STRATEGY.
 *
 * On any error or missing rows, returns DEFAULT_STRATEGY as fallback so
 * callers always get a usable object.
 */
export async function fetchActiveStrategy(
  db: Db,
): Promise<Record<string, StrategyPreset>> {
  try {
    const rows = await getActiveStrategyParams(db);
    if (rows.length === 0) return DEFAULT_STRATEGY;

    const out: Record<string, StrategyPreset> = { ...DEFAULT_STRATEGY };
    for (const r of rows) {
      out[r.productCode] = {
        label: DEFAULT_STRATEGY[r.productCode]?.label ?? r.productCode,
        hint: DEFAULT_STRATEGY[r.productCode]?.hint ?? "",
        lowPercentile: r.lowPercentileBps / 10000,
        highPercentile: r.highPercentileBps / 10000,
        lowPremium: r.lowPremiumBps / 10000,
        highPremium: r.highPremiumBps / 10000,
        showExpectedCost: r.expectedCostPercentileBps != null,
        expectedCostPercentile:
          r.expectedCostPercentileBps != null
            ? r.expectedCostPercentileBps / 10000
            : undefined,
      };
    }
    return out;
  } catch (e) {
    console.error("[strategy] DB fetch failed, using DEFAULT_STRATEGY", e);
    return DEFAULT_STRATEGY;
  }
}

/**
 * Load the active weights from DB.
 * Currently we keep all products on the same weights (SV is the canonical row).
 * If SV is missing or DB errors, fall back to the hardcoded RECENT_WEIGHTS.
 */
export async function fetchActiveWeights(
  db: Db,
): Promise<readonly number[]> {
  try {
    const rows = await getActiveStrategyParams(db);
    const sv = rows.find((r) => r.productCode === "SEARCHING_VIEW");
    if (sv?.weights && sv.weights.length > 0) return sv.weights;
    return RECENT_WEIGHTS;
  } catch {
    return RECENT_WEIGHTS;
  }
}

export type WeightedRatio = { ratio: number; weight: number };

/** Weighted percentile across [{ratio, weight}] pairs. */
export function weightedPercentile(
  values: WeightedRatio[],
  pct: number,
): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a.ratio - b.ratio);
  const total = sorted.reduce((s, v) => s + v.weight, 0);
  if (total <= 0) return sorted[sorted.length - 1].ratio;
  let cum = 0;
  for (const v of sorted) {
    cum += v.weight;
    if (cum / total >= pct) return v.ratio;
  }
  return sorted[sorted.length - 1].ratio;
}

/** Build {ratio, weight} pairs from rounds (newest-first input). */
export function buildWeighted(
  rounds: { ratio: number | null }[],
  weights: readonly number[] = RECENT_WEIGHTS,
): WeightedRatio[] {
  const out: WeightedRatio[] = [];
  let wIdx = 0;
  for (const r of rounds) {
    if (r.ratio == null) continue;
    const w = weights[wIdx];
    if (w == null) break;
    out.push({ ratio: r.ratio, weight: w });
    wIdx += 1;
  }
  return out;
}

export type Recommendation = {
  low: number | null;
  high: number | null;
  expectedCost: number | null;
  meanRatio: number | null;
  strategy: StrategyPreset;
};

/**
 * Compute the recommended bid range for one keyword group given a set of
 * historical rounds (ASC by round_no) and the next round's min_bid_price.
 *
 * Used both by the live dashboard and the backtest. By passing only the
 * rounds the user "would have seen" at decision time, the backtest gets an
 * honest out-of-sample evaluation.
 */
export function computeRecommendation(
  pastRoundsAsc: { ratio: number | null }[],
  latestMin: number | null,
  productCode: ProductCode,
  weights: readonly number[] = RECENT_WEIGHTS,
  strategies: Record<string, StrategyPreset> = DEFAULT_STRATEGY,
): Recommendation {
  const strategy = strategies[productCode] ?? strategies.SEARCHING_VIEW;
  const newestFirst = [...pastRoundsAsc].reverse();
  const weighted = buildWeighted(newestFirst, weights);

  if (weighted.length === 0 || latestMin == null) {
    return { low: null, high: null, expectedCost: null, meanRatio: null, strategy };
  }

  const totalW = weighted.reduce((s, v) => s + v.weight, 0);
  const meanRatio =
    weighted.reduce((s, v) => s + v.ratio * v.weight, 0) / totalW;
  const round1k = (n: number) => Math.round(n / 1000) * 1000;

  // Auction-rule-aware computation:
  //
  // SV (1-slot first-price): winner pays own bid. low/high are independent
  //   percentile-based recommendations directly anchored on latestMin.
  //
  // NP (2-slot second-price): winner pays #2's bid. We first project the
  //   #2 clearing price (expectedActualCost), then derive low/high as a
  //   premium ABOVE that projection. This keeps the math consistent:
  //   recommendedLow ≥ expectedActualCost ≥ actual payment in all cases.
  //   (Bidding the low end already secures #1 over the projected #2.)
  let low: number | null = null;
  let high: number | null = null;
  let expectedCost: number | null = null;

  if (strategy.showExpectedCost && strategy.expectedCostPercentile != null) {
    // NP / 2-slot 2nd-price family
    const expRatio = weightedPercentile(weighted, strategy.expectedCostPercentile);
    if (expRatio != null) {
      const projectedSecond = latestMin * expRatio;
      expectedCost = round1k(projectedSecond);
      low = round1k(projectedSecond * strategy.lowPremium);
      high = round1k(projectedSecond * strategy.highPremium);
    }
  } else {
    // SV / 1-slot 1st-price family
    const lowRatio = weightedPercentile(weighted, strategy.lowPercentile);
    const highRatio = weightedPercentile(weighted, strategy.highPercentile);
    low = lowRatio != null ? round1k(latestMin * lowRatio * strategy.lowPremium) : null;
    high = highRatio != null ? round1k(latestMin * highRatio * strategy.highPremium) : null;
  }

  return { low, high, expectedCost, meanRatio, strategy };
}
