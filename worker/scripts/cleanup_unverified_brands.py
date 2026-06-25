"""Delete `__unverified__::<copy>` brand rows so the next cycle gets a clean slate.

Background
----------
When `fetch_business_name` fails (timeout, 429, dead URL), `upsert_brand`
falls back to a sentinel row keyed by the ad copy. These rows accumulate
on the brand-cleanup dashboard as "호스트 깨짐". Each variant of the same
advertiser's ad copy spawns its OWN sentinel row, so a single rate-limit
storm can produce dozens of bogus rows in one cycle.

Running this script between cycles makes sense because:
  1. Cycle N+1 is `--full` — it re-fetches every KG and will create the
     correct (host-keyed) brand row this time (or retry the timeout).
  2. We don't want the dashboard's "긴급정정" count to compound across
     cycles; it should reflect only what the FINAL cycle couldn't resolve.

Behaviour
---------
- Deletes round_brands rows pointing to any `__unverified__::*` brand
  whose brand_id is referenced ONLY by sentinel rows.
- Then deletes the brand rows themselves once they are orphaned.
- Resets `brands_scraped_at` on KGs that lost rows so the next `--full`
  cycle re-scrapes them with a clean slate.

Run:
    uv run python scripts/cleanup_unverified_brands.py            # dry-run
    uv run python scripts/cleanup_unverified_brands.py --apply    # commit
"""

from __future__ import annotations

import argparse
import sys

from worker.db import connect


def main(apply: bool) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT b.id, b.business_name, COUNT(rb.id)
            FROM brands b
            JOIN round_brands rb ON rb.brand_id = b.id
            WHERE b.business_name LIKE '__unverified__::%'
            GROUP BY b.id, b.business_name
            ORDER BY COUNT(rb.id) DESC
            """
        )
        rows = cur.fetchall()
        if not rows:
            print("__unverified__:: 행 없음.")
            return 0

        total_brands = len(rows)
        total_round_brands = sum(r[2] for r in rows)
        print(
            f"정리 대상: {total_brands} brand 행 / {total_round_brands} round_brands 참조"
        )
        for bid, bn, cnt in rows[:10]:
            print(f"  brand_id={bid:5d} uses={cnt:3d}  {bn[:80]}")
        if total_brands > 10:
            print(f"  ... +{total_brands - 10}건")

        if not apply:
            print("\n[dry-run] --apply 를 붙이면 실제로 삭제합니다.")
            return 0

        # Step 1: collect affected KGs so we can reset their scraped_at later
        cur.execute(
            """
            SELECT DISTINCT rb.round_keyword_group_id
            FROM round_brands rb
            JOIN brands b ON b.id = rb.brand_id
            WHERE b.business_name LIKE '__unverified__::%'
            """
        )
        affected_kgs = [r[0] for r in cur.fetchall()]

        # Step 2: delete round_brands rows tied to unverified brands
        cur.execute(
            """
            DELETE FROM round_brands rb
            USING brands b
            WHERE rb.brand_id = b.id
              AND b.business_name LIKE '__unverified__::%'
            """
        )
        deleted_rb = cur.rowcount
        print(f"  - round_brands 삭제: {deleted_rb}건")

        # Step 3: delete brand rows that are now orphaned
        cur.execute(
            """
            DELETE FROM brands b
            WHERE b.business_name LIKE '__unverified__::%'
              AND NOT EXISTS (
                  SELECT 1 FROM round_brands rb WHERE rb.brand_id = b.id
              )
            """
        )
        deleted_b = cur.rowcount
        print(f"  - brand 삭제:        {deleted_b}건")

        # Step 4: reset brands_scraped_at on affected KGs so the next --full
        # cycle (or sweep) treats them as fresh work.
        if affected_kgs:
            cur.execute(
                """
                UPDATE round_keyword_groups
                SET brands_scraped_at = NULL
                WHERE id = ANY(%s)
                """,
                (affected_kgs,),
            )
            print(f"  - brands_scraped_at NULL 처리: {cur.rowcount} KG")

        conn.commit()
        print("\n[applied]")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    sys.exit(main(parser.parse_args().apply))
