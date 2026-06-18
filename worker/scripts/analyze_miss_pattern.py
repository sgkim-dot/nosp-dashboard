"""Refined: use regular_winning_bid as the 'has an advertiser bid won' signal.

If regular_winning_bid > 0, at least one advertiser won the bid -> ad should run.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        # The currently active NP round + 3 prior. "Active" = period spans today.
        cur.execute(
            """
            SELECT r.id, r.round_no, r.period_start, r.period_end
            FROM rounds r JOIN products p ON p.id = r.product_id
            WHERE p.code = 'NEW_PRODUCT' AND r.period_start <= CURRENT_DATE
            ORDER BY r.round_no DESC LIMIT 4
            """
        )
        rounds_np = cur.fetchall()

        print("=" * 95)
        print("NP per-week: KGs with regular_winning_bid > 0 (likely has running advertiser) — recall")
        print("=" * 95)
        for round_id, round_no, ps, pe in rounds_np:
            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE rkg.brands_scraped_at IS NOT NULL AND rkg.regular_winning_bid > 0) AS bid_won,
                  COUNT(*) FILTER (
                    WHERE rkg.brands_scraped_at IS NOT NULL AND rkg.regular_winning_bid > 0
                      AND NOT EXISTS (SELECT 1 FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id)
                  ) AS bid_won_zero,
                  COUNT(*) FILTER (
                    WHERE rkg.brands_scraped_at IS NOT NULL AND rkg.regular_winning_bid > 0
                      AND EXISTS (SELECT 1 FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id)
                  ) AS bid_won_caught,
                  COUNT(*) FILTER (
                    WHERE rkg.brands_scraped_at IS NOT NULL
                      AND (rkg.regular_winning_bid IS NULL OR rkg.regular_winning_bid = 0)
                  ) AS no_bid,
                  COUNT(*) FILTER (
                    WHERE rkg.brands_scraped_at IS NOT NULL
                      AND (rkg.regular_winning_bid IS NULL OR rkg.regular_winning_bid = 0)
                      AND EXISTS (SELECT 1 FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id)
                  ) AS no_bid_but_caught
                FROM round_keyword_groups rkg
                WHERE rkg.round_id = %s
                """,
                (round_id,),
            )
            bid_won, bid_won_zero, bid_won_caught, no_bid, no_bid_caught = cur.fetchone()
            recall_pct = (100.0 * bid_won_caught / bid_won) if bid_won else 0
            print(
                f"  r{round_no} ({ps}~{pe}): "
                f"won_bid={bid_won}  caught={bid_won_caught}  zero={bid_won_zero}  recall={recall_pct:.1f}%  "
                f"|  no_bid={no_bid} (but_caught={no_bid_caught})"
            )

        # This week NP: among "bid won" KGs, distribution of caught vs not caught
        round_id = rounds_np[0][0]
        print()
        print("=" * 95)
        print(f"This week NP r{rounds_np[0][1]}: top 30 bid-won-but-zero KGs (TRUE misses)")
        print("=" * 95)
        cur.execute(
            """
            SELECT rkg.id, kg.name, rkg.regular_winning_bid, rkg.brands_scraped_at
            FROM round_keyword_groups rkg
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            WHERE rkg.round_id = %s
              AND rkg.brands_scraped_at IS NOT NULL
              AND rkg.regular_winning_bid > 0
              AND NOT EXISTS (SELECT 1 FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id)
            ORDER BY rkg.regular_winning_bid DESC
            LIMIT 30
            """,
            (round_id,),
        )
        rows = cur.fetchall()
        print(f"({len(rows)} shown)")
        for rkg_id, name, bid, ts in rows:
            ts_str = ts.strftime("%m-%d %H:%M") if ts else "—"
            print(f"  rkg={rkg_id:<6}  bid={bid:>8}  scraped={ts_str}  {name}")

        # Has the recent week 'true miss' rate shifted?
        # Compare scraped_at hour vs miss rate AMONG bid-won-KGs (clean denominator)
        print()
        print("=" * 95)
        print("This week NP: bid-won KGs by scrape hour (UTC) — recall")
        print("=" * 95)
        cur.execute(
            """
            SELECT EXTRACT(HOUR FROM rkg.brands_scraped_at AT TIME ZONE 'UTC')::int AS hr,
                   COUNT(*) AS bid_won,
                   COUNT(*) FILTER (
                     WHERE EXISTS (SELECT 1 FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id)
                   ) AS caught
            FROM round_keyword_groups rkg
            WHERE rkg.round_id = %s
              AND rkg.brands_scraped_at IS NOT NULL
              AND rkg.regular_winning_bid > 0
            GROUP BY hr ORDER BY hr
            """,
            (round_id,),
        )
        for hr, bid_won, caught in cur.fetchall():
            kst = (hr + 9) % 24
            r = (100.0 * caught / bid_won) if bid_won else 0
            print(f"  {hr:02d}:00 UTC ({kst:02d}:00 KST)  bid_won={bid_won:<4} caught={caught:<4} recall={r:.0f}%")
