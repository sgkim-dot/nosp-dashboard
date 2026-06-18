import type { ProductCode } from "@/types/bid-decision";

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
export const STRATEGY: Record<string, StrategyPreset> = {
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
): Recommendation {
  const strategy = STRATEGY[productCode] ?? STRATEGY.SEARCHING_VIEW;
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
