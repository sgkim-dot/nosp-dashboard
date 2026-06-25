"""Emergency rescrape: invalidate all active-round NP rows so the next BAT
cycle picks them up from scratch.

Background: a regression in EXTRACT_JS (legacy `i=SC\\d+` ad-id regex that
stopped matching Naver's new `i=nad-…` format) caused 1-slot NP keyword
groups to be persisted as 2-slot rows with the SAME advertiser duplicated.
After fixing the extractor we must rerun every active NP KG so the dashboard
no longer shows the wrong "2 slots / both lactiv" rows.

This script:
  1) NULLs `brands_scraped_at` on every active-period NP KG. The standard
     resume-cycle (`brand_scrape --resume`) then treats them as never-scraped
     and re-queues them at the head of the work list.
  2) DELETEs the existing `round_brands` rows for those KGs so the dashboard
     stops displaying the stale slots before the rescrape lands. Without
     this, broken slots are visible to operators until each KG's rescrape
     completes (~hours).

Run when you trust the EXTRACT_JS fix and accept a short window of empty
slots while the BAT cycle catches back up.
"""

from __future__ import annotations

import argparse
import sys

from worker.db import connect
from worker.logging import configure_logging, get_logger

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--product",
        default="NEW_PRODUCT",
        choices=["NEW_PRODUCT", "SEARCHING_VIEW", "BOTH"],
        help="Which product's active KGs to invalidate (default: NEW_PRODUCT only)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show how many rows would be touched without modifying anything.",
    )
    args = parser.parse_args(argv)

    configure_logging()
    products = (
        ["NEW_PRODUCT", "SEARCHING_VIEW"]
        if args.product == "BOTH" else [args.product]
    )

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.code,
                       COUNT(*)                            AS active_kgs,
                       COUNT(*) FILTER (
                         WHERE rkg.brands_scraped_at IS NOT NULL
                       )                                   AS scraped,
                       COALESCE(SUM(
                         (SELECT COUNT(*) FROM round_brands rb
                          WHERE rb.round_keyword_group_id = rkg.id)
                       ), 0)                               AS brand_rows
                FROM round_keyword_groups rkg
                JOIN rounds r ON r.id = rkg.round_id
                JOIN products p ON p.id = r.product_id
                WHERE r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date
                  AND r.period_end   >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
                  AND p.code = ANY(%s)
                GROUP BY p.code
                ORDER BY p.code
                """,
                (products,),
            )
            for code, active, scraped, brand_rows in cur.fetchall():
                print(
                    f"  {code:<14} active={active:>5}  scraped={scraped:>5}  "
                    f"brand_rows={brand_rows:>5}"
                )

        if args.dry_run:
            print("\n(dry run — no changes made)")
            return 0

        print()
        print("Invalidating brands_scraped_at + deleting round_brands …")

        with conn.cursor() as cur:
            cur.execute(
                """
                WITH targets AS (
                  SELECT rkg.id
                  FROM round_keyword_groups rkg
                  JOIN rounds r ON r.id = rkg.round_id
                  JOIN products p ON p.id = r.product_id
                  WHERE r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date
                    AND r.period_end   >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
                    AND p.code = ANY(%s)
                )
                DELETE FROM round_brands
                WHERE round_keyword_group_id IN (SELECT id FROM targets)
                """,
                (products,),
            )
            deleted = cur.rowcount
            cur.execute(
                """
                UPDATE round_keyword_groups rkg
                SET brands_scraped_at = NULL,
                    detected_slot_count = NULL
                FROM rounds r, products p
                WHERE rkg.round_id = r.id
                  AND r.product_id = p.id
                  AND r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date
                  AND r.period_end   >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
                  AND p.code = ANY(%s)
                """,
                (products,),
            )
            updated = cur.rowcount
        conn.commit()
        print(f"  deleted {deleted} round_brands rows")
        print(f"  invalidated {updated} round_keyword_groups")
        print()
        print("Next: run the BAT (브랜드크롤링.bat) — cycle 1 (--resume) will")
        print("treat every NULL row as never-scraped and pick them all up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
