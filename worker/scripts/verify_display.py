from worker.db import connect
with connect() as conn, conn.cursor() as cur:
    cur.execute("""
        SELECT p.code, kg.name, rb.display_name, b.display_name, b.business_name
        FROM round_brands rb
        JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
        JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
        JOIN rounds r ON r.id = rkg.round_id
        JOIN products p ON p.id = r.product_id
        JOIN brands b ON b.id = rb.brand_id
        WHERE kg.name IN ('운전자보험','간병치매보험','실비보험','자동차보험','암보험','간병인보험','치매보험')
        ORDER BY p.code, kg.name, rb.slot_no
    """)
    print(f"{'product':16s}  {'kg':18s}  {'rb.display_name':45s}  {'b.display_name':45s}  host")
    for r in cur.fetchall():
        print(f"{r[0]:16s}  {r[1]:18s}  {(r[2] or '-')[:45]:45s}  {(r[3] or '-')[:45]:45s}  {r[4]}")
