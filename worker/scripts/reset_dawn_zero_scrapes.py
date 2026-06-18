"""Reset brands_scraped_at to NULL for active-round KGs that:
  - were scraped during KST 03:00-09:00 (= UTC 18:00-23:59), AND
  - have 0 round_brands rows.

These get auto-re-queued by `brand_scrape --resume` on the next BAT run.

The dawn-window check is based on analysis showing recall ~0% in this band
across the current and prior weeks, almost certainly anti-bot throttling.

Run dry by default. Pass --apply to actually update.
"""
from __future__ import annotations

import argparse
import sys

from worker.db import connect


SQL = """
WITH targets AS (
    SELECT rkg.id, rkg.brands_scraped_at, kg.name AS kg_name
    FROM round_keyword_groups rkg
    JOIN rounds r ON r.id = rkg.round_id
    JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
    JOIN products p ON p.id = r.product_id
    WHERE p.code = 'NEW_PRODUCT'
      AND r.period_start <= CURRENT_DATE AND r.period_end >= CURRENT_DATE
      AND rkg.brands_scraped_at IS NOT NULL
      AND EXTRACT(HOUR FROM rkg.brands_scraped_at AT TIME ZONE 'UTC') BETWEEN 18 AND 23
      AND NOT EXISTS (
          SELECT 1 FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id
      )
)
SELECT * FROM targets
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually NULL the rows")
    args = parser.parse_args(argv)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL)
            rows = cur.fetchall()
            print(f"{len(rows)} active-NP KGs to reset (dawn-window 0-caught)")
            for rkg_id, ts, name in rows[:10]:
                ts_str = ts.strftime("%m-%d %H:%M") if ts else "—"
                try:
                    print(f"  rkg={rkg_id}  scraped={ts_str}  {name}")
                except UnicodeEncodeError:
                    print(f"  rkg={rkg_id}  scraped={ts_str}  <korean name>")
            if len(rows) > 10:
                print(f"  … and {len(rows) - 10} more")
            if not args.apply:
                print("\n(dry run; pass --apply to NULL these rows)")
                return 0
            cur.execute(
                """
                UPDATE round_keyword_groups
                SET brands_scraped_at = NULL
                WHERE id = ANY(%s)
                """,
                ([r[0] for r in rows],),
            )
            print(f"Updated {cur.rowcount} rows.")
        conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
