"""Grid-search the bidding-strategy parameters against historical NOSP data.

For each candidate (weights, low_percentile, high_percentile, low_premium,
high_premium) combination we backtest the same way the dashboard does:

  For every (KG, round R) with a known winning_bid:
    1. Use only rounds strictly before R as training data.
    2. Compute recommendation using the candidate parameters.
    3. Compare to actual winning_bid:
         - wouldWin  = recommendedHigh >= actualWinning
         - overpay   = recommendedHigh - actualWinning  (positive when won)
         - underbid  = actualWinning - recommendedHigh  (positive when lost)

We score each candidate per product:
    score = win_rate
          − overpay_penalty × avg_overpay_when_won / latest_min_bid
          − underbid_penalty × avg_underbid_when_lost / latest_min_bid

Output: top-N candidates by product, with full metrics so the human can
choose how to update the live STRATEGY constants in
`apps/dashboard/lib/strategy.ts`.

Usage:
  uv run python scripts/tune_strategy.py
  uv run python scripts/tune_strategy.py --product NEW_PRODUCT --top 10
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from dataclasses import dataclass
from typing import Sequence

from worker.db import connect


# ±25% — exceeding this delta vs current active triggers 'pending' instead of 'active'.
DELTA_THRESHOLD_BPS = 2500


# ─── Strategy primitives (mirror of apps/dashboard/lib/strategy.ts) ─────────


def weighted_percentile(values: list[tuple[float, float]], pct: float) -> float | None:
    """values = [(ratio, weight), …]"""
    if not values:
        return None
    s = sorted(values, key=lambda v: v[0])
    total = sum(w for _, w in s)
    if total <= 0:
        return s[-1][0]
    cum = 0.0
    for ratio, w in s:
        cum += w
        if cum / total >= pct:
            return ratio
    return s[-1][0]


@dataclass
class StrategyParams:
    weights: tuple[float, ...]
    low_pct: float
    high_pct: float
    low_premium: float
    high_premium: float


def simulate(
    train_ratios: list[float],
    test_min_bid: float,
    p: StrategyParams,
) -> tuple[float, float] | None:
    """Return (recLow, recHigh) using only the most-recent N ratios."""
    weighted = []
    for i, r in enumerate(train_ratios[::-1]):  # newest first
        if i >= len(p.weights):
            break
        weighted.append((r, p.weights[i]))
    if not weighted:
        return None
    low_ratio = weighted_percentile(weighted, p.low_pct)
    high_ratio = weighted_percentile(weighted, p.high_pct)
    if low_ratio is None or high_ratio is None:
        return None
    low = round(test_min_bid * low_ratio * p.low_premium / 1000) * 1000
    high = round(test_min_bid * high_ratio * p.high_premium / 1000) * 1000
    return low, high


# ─── Data loading ────────────────────────────────────────────────────────────


@dataclass
class KgHistory:
    kg_id: int
    kg_name: str
    product: str
    rounds: list[tuple[int, float, float | None]]  # (round_no, min_bid, winning)


def load_data() -> list[KgHistory]:
    by_kg: dict[int, KgHistory] = {}
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT kg.id, kg.name, p.code, r.round_no,
                   rkg.min_bid_price, rkg.regular_winning_bid
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = kg.product_id
            WHERE rkg.min_bid_price IS NOT NULL
            ORDER BY kg.id, r.round_no
            """
        )
        for kg_id, kg_name, product, round_no, min_bid, winning in cur.fetchall():
            entry = by_kg.setdefault(kg_id, KgHistory(kg_id, kg_name, product, []))
            entry.rounds.append((round_no, float(min_bid), float(winning) if winning else None))
    return list(by_kg.values())


# ─── Backtest per candidate ─────────────────────────────────────────────────


@dataclass
class BacktestMetrics:
    sims: int
    wins: int
    win_rate: float
    avg_overpay_when_won: float       # absolute KRW
    avg_underbid_when_lost: float
    score: float


def backtest(
    histories: list[KgHistory],
    p: StrategyParams,
    product_filter: str | None = None,
    overpay_penalty: float = 0.5,
    underbid_penalty: float = 1.0,
) -> BacktestMetrics:
    sims = wins = 0
    overpay_sum = 0.0
    underbid_sum = 0.0
    overpay_n = underbid_n = 0
    for kg in histories:
        if product_filter and kg.product != product_filter:
            continue
        ratios: list[float] = []
        for i, (round_no, min_bid, winning) in enumerate(kg.rounds):
            if winning is None:
                if min_bid > 0:
                    pass
                continue
            ratio = winning / min_bid if min_bid > 0 else None
            if i > 0 and ratios:  # need at least one prior ratio
                rec = simulate(ratios, min_bid, p)
                if rec:
                    _, rec_high = rec
                    sims += 1
                    if rec_high >= winning:
                        wins += 1
                        overpay_sum += rec_high - winning
                        overpay_n += 1
                    else:
                        underbid_sum += winning - rec_high
                        underbid_n += 1
            if ratio is not None:
                ratios.append(ratio)

    win_rate = wins / sims if sims else 0.0
    avg_overpay = overpay_sum / overpay_n if overpay_n else 0.0
    avg_underbid = underbid_sum / underbid_n if underbid_n else 0.0
    # Score: prioritize win_rate, penalize overpay and underbid by their
    # KRW magnitude relative to a reasonable bid size (~1M).
    score = (
        win_rate
        - overpay_penalty * (avg_overpay / 1_000_000)
        - underbid_penalty * (avg_underbid / 1_000_000)
    )
    return BacktestMetrics(sims, wins, win_rate, avg_overpay, avg_underbid, score)


# ─── Grid search ────────────────────────────────────────────────────────────


def make_grid() -> list[StrategyParams]:
    """Reasonable parameter ranges to explore."""
    weight_options: list[tuple[float, ...]] = [
        (4, 3, 2, 1),
        (5, 3, 2, 1),
        (4, 4, 2, 1),
        (3, 3, 2, 1),
        (4, 3, 2, 0),  # last 3 only
        (5, 3, 1, 0),
        (6, 4, 2, 1),
    ]
    low_pcts = [0.3, 0.4, 0.5, 0.6]
    high_pcts = [0.7, 0.8, 0.9, 0.95]
    low_premiums = [0.95, 1.0, 1.05, 1.1, 1.2]
    high_premiums = [1.05, 1.1, 1.2, 1.3, 1.4, 1.5]

    grid = []
    for w, lp, hp, lpr, hpr in itertools.product(
        weight_options, low_pcts, high_pcts, low_premiums, high_premiums
    ):
        if lp >= hp:
            continue
        if lpr > hpr:
            continue
        grid.append(StrategyParams(w, lp, hp, lpr, hpr))
    return grid


# ─── DB write helpers ───────────────────────────────────────────────────────


def _bps(x: float) -> int:
    """Convert a ratio (0..N) to integer basis points (×10000)."""
    return int(round(x * 10000))


def _max_delta_bps(new_row: dict, old_row: dict) -> int:
    """Return max absolute delta (in bps) across the four tuned numeric params."""
    keys = (
        "low_percentile_bps",
        "high_percentile_bps",
        "low_premium_bps",
        "high_premium_bps",
    )
    deltas = [abs(new_row[k] - old_row[k]) for k in keys if k in new_row and k in old_row]
    return max(deltas) if deltas else 0


def write_to_db(
    product_code: str,
    best_params: "StrategyParams",
    metrics: "BacktestMetrics",
) -> str:
    """Insert tune result into strategy_params. Returns 'active' or 'pending'.

    Active if max delta vs current active is <= DELTA_THRESHOLD_BPS, else pending.
    NEW_PRODUCT semantics: lowPercentile/highPercentile aren't used for the
    2-slot 2nd-price math, but we still store the grid value so the row is
    self-describing. (Plan: T8.)
    """
    new_row = {
        "product_code": product_code,
        "weights": list(best_params.weights),
        "low_percentile_bps": _bps(best_params.low_pct),
        "high_percentile_bps": _bps(best_params.high_pct),
        "low_premium_bps": _bps(best_params.low_premium),
        "high_premium_bps": _bps(best_params.high_premium),
        # expected_cost is the same as high_pct for NP/ANN; null for SV
        "expected_cost_percentile_bps": (
            _bps(best_params.high_pct)
            if product_code in ("NEW_PRODUCT", "ANNIVERSARY")
            else None
        ),
        "backtest_score_bps": _bps(metrics.win_rate),
        "sample_size": metrics.sims,
        "avg_overpay": int(metrics.avg_overpay_when_won),
        "avg_underbid": int(metrics.avg_underbid_when_lost),
        "source": "tune_strategy.py",
        "note": f"auto-tuned, score={metrics.score:.3f}",
    }

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT low_percentile_bps, high_percentile_bps, "
            "       low_premium_bps, high_premium_bps "
            "FROM strategy_params "
            "WHERE product_code = %s AND status = 'active'",
            (product_code,),
        )
        row = cur.fetchone()
        if row:
            old = {
                "low_percentile_bps": row[0],
                "high_percentile_bps": row[1],
                "low_premium_bps": row[2],
                "high_premium_bps": row[3],
            }
            delta = _max_delta_bps(new_row, old)
            new_row["delta_max_bps"] = delta
            status = "pending" if delta > DELTA_THRESHOLD_BPS else "active"
        else:
            new_row["delta_max_bps"] = 0
            status = "active"

        # If activating, archive the previous active first.
        if status == "active":
            cur.execute(
                "UPDATE strategy_params SET status = 'archived' "
                "WHERE product_code = %s AND status = 'active'",
                (product_code,),
            )

        cur.execute(
            """
            INSERT INTO strategy_params (
              product_code, status, weights,
              low_percentile_bps, high_percentile_bps,
              low_premium_bps, high_premium_bps,
              expected_cost_percentile_bps,
              backtest_score_bps, sample_size, avg_overpay, avg_underbid,
              delta_max_bps, source, note,
              activated_at, activated_by
            ) VALUES (
              %s, %s, %s::jsonb,
              %s, %s, %s, %s,
              %s,
              %s, %s, %s, %s,
              %s, %s, %s,
              CASE WHEN %s = 'active' THEN NOW() ELSE NULL END,
              CASE WHEN %s = 'active' THEN 'tune_strategy.py' ELSE NULL END
            )
            """,
            (
                new_row["product_code"], status, json.dumps(new_row["weights"]),
                new_row["low_percentile_bps"], new_row["high_percentile_bps"],
                new_row["low_premium_bps"], new_row["high_premium_bps"],
                new_row["expected_cost_percentile_bps"],
                new_row["backtest_score_bps"], new_row["sample_size"],
                new_row["avg_overpay"], new_row["avg_underbid"],
                new_row["delta_max_bps"], new_row["source"], new_row["note"],
                status, status,
            ),
        )
        conn.commit()
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--product",
        help="SEARCHING_VIEW, NEW_PRODUCT, or ANNIVERSARY",
        default=None,
    )
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="Write the best candidate per product to strategy_params table",
    )
    args = parser.parse_args()

    print("loading historical data…", file=sys.stderr)
    histories = load_data()
    print(f"  {len(histories)} keyword groups", file=sys.stderr)

    products = (
        [args.product] if args.product else ["SEARCHING_VIEW", "NEW_PRODUCT", "ANNIVERSARY"]
    )

    grid = make_grid()
    print(f"backtesting {len(grid)} parameter combinations × {len(products)} products…", file=sys.stderr)

    for product in products:
        print(f"\n{'=' * 60}")
        print(f"  Top {args.top} for {product}")
        print("=" * 60)
        results = []
        for p in grid:
            m = backtest(histories, p, product_filter=product)
            if m.sims < 50:
                continue  # too little data
            results.append((m.score, p, m))
        results.sort(reverse=True, key=lambda x: x[0])

        if not results:
            print(f"  [WARN] no candidates met sims threshold for {product} - skipping DB write")
            continue

        print(f"{'rank':<5}{'weights':<18}{'lowP':<7}{'highP':<7}{'lowMul':<8}{'hiMul':<8}{'sims':<6}{'win%':<7}{'overpay':<14}{'underbid':<14}{'score'}")
        for rank, (score, p, m) in enumerate(results[: args.top], 1):
            w = f"{p.weights}"
            print(
                f"{rank:<5}{w:<18}{p.low_pct:<7}{p.high_pct:<7}{p.low_premium:<8}{p.high_premium:<8}"
                f"{m.sims:<6}{m.win_rate * 100:<7.1f}"
                f"{m.avg_overpay_when_won:>10,.0f}원   "
                f"{m.avg_underbid_when_lost:>10,.0f}원   "
                f"{score:.3f}"
            )

        if args.write_db:
            _score, best_p, best_m = results[0]
            status = write_to_db(product, best_p, best_m)
            verdict = "EXCEEDED" if status == "pending" else "within"
            print(f"\n  [DB] {product}: status={status}, delta_max={verdict} ±25%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
