"""Why was NP 간병치매보험 skipped?"""
from worker.db import connect

KW_VARIANTS = ["간병치매보험", "간병/치매보험", "간병치매", "치매보험", "간병보험"]

with connect() as conn:
    with conn.cursor() as cur:
        # All keyword_groups containing "간병" or "치매"
        cur.execute("""
            SELECT kg.id, kg.name, p.code
            FROM keyword_groups kg
            JOIN products p ON p.id = kg.product_id
            WHERE kg.name ILIKE '%간병%' OR kg.name ILIKE '%치매%'
            ORDER BY p.code, kg.name
        """)
        print("=== keyword_groups containing 간병/치매 ===")
        for r in cur.fetchall():
            print(f"  [{r[2]}] id={r[0]} name={r[1]!r}")

        # Check RKG existence + active state for each variant
        print("\n=== Active RKGs (today within period) ===")
        cur.execute("""
            SELECT p.code, kg.name, r.round_no, r.period_start, r.period_end, rkg.id
            FROM round_keyword_groups rkg
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = r.product_id
            WHERE (kg.name ILIKE '%간병%' OR kg.name ILIKE '%치매%')
              AND CURRENT_DATE BETWEEN r.period_start AND r.period_end
            ORDER BY p.code, kg.name
        """)
        for r in cur.fetchall():
            print(f"  [{r[0]}] {r[1]!r} round {r[2]} ({r[3]}~{r[4]}) RKG id={r[5]}")

        # Existing brand captures for this keyword
        print("\n=== Existing brand captures for 간병치매보험 (any round) ===")
        cur.execute("""
            SELECT p.code, kg.name, r.round_no, b.display_name, b.business_name, rb.captured_at
            FROM round_brands rb
            JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = r.product_id
            JOIN brands b ON b.id = rb.brand_id
            WHERE kg.name ILIKE '%간병%' OR kg.name ILIKE '%치매%'
            ORDER BY rb.captured_at DESC
        """)
        for r in cur.fetchall():
            print(f"  [{r[0]}] {r[1]!r} round {r[2]} -> {r[3]} | host={r[4]} | captured {r[5]}")
