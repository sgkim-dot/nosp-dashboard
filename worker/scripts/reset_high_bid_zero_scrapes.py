"""Reset high-bid KGs that came back 0건 in the current round.

A 0건 result on a low-bid KG is almost always legitimate (no ad running).
A 0건 result on a high-bid KG (>= 1,000,000) is overwhelmingly a Naver
burst-throttle false negative — verified 2026-06-25 with 217 high-bid KGs
all going 0건 in cycle 3's first 45 minutes.

This script NULLs their brands_scraped_at so the next BAT run (or sweep)
treats them as fresh work. Combined with the cycle-start warm-up and
high-bid 0-result retry added in the same patch, the next cycle should
produce real results for nearly all of them.

Run:
    uv run python scripts/reset_high_bid_zero_scrapes.py             # dry-run
    uv run python scripts/reset_high_bid_zero_scrapes.py --apply     # commit
"""

from __future__ import annotations

import argparse
import sys

from worker.db import connect


THRESHOLD = 1_000_000


def main(apply: bool) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT rkg.id, kg.name, rkg.regular_winning_bid
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            WHERE r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date
              AND r.period_end   >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
              AND rkg.regular_winning_bid >= %s
              AND COALESCE(rkg.detected_slot_count, 0) = 0
              AND NOT EXISTS (
                  SELECT 1 FROM round_brands rb
                  WHERE rb.round_keyword_group_id = rkg.id
              )
            ORDER BY rkg.regular_winning_bid DESC
            """,
            (THRESHOLD,),
        )
        rows = cur.fetchall()

        if not rows:
            print("high-bid 0건 KG 없음.")
            return 0

        print(f"reset 대상: {len(rows)}건 (bid >= {THRESHOLD:,})")
        top = rows[:10]
        for rkg_id, name, bid in top:
            print(f"  rkg={rkg_id:6d}  {name:25s}  bid={bid:>13,}")
        if len(rows) > 10:
            print(f"  ... +{len(rows) - 10}건")

        if not apply:
            print("\n[dry-run] --apply 를 붙이면 brands_scraped_at NULL 처리.")
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
        print("다음 BAT 실행 시 cycle 1(--resume) 또는 cycle 2/3(--full)이 자동 재처리.")
        return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    sys.exit(main(p.parse_args().apply))
