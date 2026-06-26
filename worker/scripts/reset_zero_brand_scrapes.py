"""Reset KGs in the current active round that came back with 0 brands.

This is the broader variant of reset_high_bid_zero_scrapes.py. Use it when
you have reason to distrust this round's scrape coverage as a whole — e.g.
after a Naver IP-block recovery — and want to force a fresh re-scrape of
every "0 brands captured" KG.

Selection criteria:
  - in the active round (KST today between period_start..period_end)
  - already scraped this round (brands_scraped_at IS NOT NULL)
  - 0 brands captured (NOT EXISTS in round_brands)
  - regular_winning_bid >= --min-bid (default 1, i.e. any KG with a known bid)

The --min-bid filter exists because KGs with bid=0 typically have no ad
running and a re-scrape would just re-confirm 0. Use --min-bid 0 to force
include those too (NULL bid is still excluded — those legitimately have no
auction data).

Run:
    uv run python scripts/reset_zero_brand_scrapes.py                         # dry-run, bid >= 1
    uv run python scripts/reset_zero_brand_scrapes.py --apply                 # commit
    uv run python scripts/reset_zero_brand_scrapes.py --min-bid 0 --apply     # also include bid=0 KGs
    uv run python scripts/reset_zero_brand_scrapes.py --min-bid 1000000 --apply  # high-bid only (legacy behavior)
"""

from __future__ import annotations

import argparse
import sys

from worker.db import connect


def main(apply: bool, min_bid: int) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT rkg.id, kg.name, p.code, rkg.regular_winning_bid
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = kg.product_id
            WHERE r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date
              AND r.period_end   >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
              AND rkg.brands_scraped_at IS NOT NULL
              AND rkg.regular_winning_bid IS NOT NULL
              AND rkg.regular_winning_bid >= %s
              AND NOT EXISTS (
                  SELECT 1 FROM round_brands rb
                  WHERE rb.round_keyword_group_id = rkg.id
              )
            ORDER BY rkg.regular_winning_bid DESC
            """,
            (min_bid,),
        )
        rows = cur.fetchall()

        if not rows:
            print(f"0건 미수집 KG 없음 (bid >= {min_bid:,}).")
            return 0

        # Quick stats by product
        by_product: dict[str, int] = {}
        bid_buckets = {"=0": 0, "1-99999": 0, "100k-999k": 0, ">=1M": 0}
        for _rkg_id, _name, product, bid in rows:
            by_product[product] = by_product.get(product, 0) + 1
            if bid == 0:
                bid_buckets["=0"] += 1
            elif bid < 100_000:
                bid_buckets["1-99999"] += 1
            elif bid < 1_000_000:
                bid_buckets["100k-999k"] += 1
            else:
                bid_buckets[">=1M"] += 1

        print(f"reset 대상: {len(rows)}건 (bid >= {min_bid:,})")
        print(f"  상품별: {by_product}")
        print(f"  bid 분포: {bid_buckets}")
        print()
        top = rows[:15]
        for rkg_id, name, product, bid in top:
            print(f"  rkg={rkg_id:6d}  [{product[:3]:3s}]  {name:25s}  bid={bid:>13,}")
        if len(rows) > 15:
            print(f"  ... +{len(rows) - 15}건")

        if not apply:
            print(f"\n[dry-run] --apply 를 붙이면 brands_scraped_at NULL 처리.")
            print(f"          --min-bid <N> 으로 임계 조정 가능 (현재 {min_bid:,}).")
            return 0

        ids = [r[0] for r in rows]
        cur.execute(
            """
            UPDATE round_keyword_groups
            SET brands_scraped_at = NULL,
                detected_slot_count = NULL
            WHERE id = ANY(%s)
            """,
            (ids,),
        )
        conn.commit()
        print(f"\n[applied] {cur.rowcount} KG의 brands_scraped_at NULL 처리됨.")
        print("다음 BAT 실행 시 (--resume) 자동 재처리됩니다.")
        return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Reset zero-brand-captured KGs in current round so BAT re-scrapes them."
    )
    p.add_argument("--apply", action="store_true", help="실제 reset 실행 (없으면 dry-run)")
    p.add_argument(
        "--min-bid", type=int, default=1,
        help="이 값 이상의 bid만 대상. 기본 1 (NULL/0 bid는 제외). "
             "1000000 으로 주면 high-bid 만 (legacy reset_high_bid_zero_scrapes와 동일)."
    )
    args = p.parse_args()
    sys.exit(main(args.apply, args.min_bid))
