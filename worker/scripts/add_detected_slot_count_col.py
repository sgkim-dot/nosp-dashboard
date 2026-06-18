"""Add round_keyword_groups.detected_slot_count INT column.

Tracks the peak single-fetch unique ad_id count observed during the brand
scrape — i.e. the maximum number of placements the Naver page actually
rendered for this KG in any one fetch. This is the most reliable in-band
proxy for the visible dot-indicator count.

Semantic:
  - 0  → no ad widget hydrated on any fetch (genuine 0 OR fully missed)
  - 1  → only one advertiser running
  - 2+ → that many advertisers are in rotation

Combined with len(round_brands):
  - detected_slot_count == len(round_brands)  → we caught everything visible
  - detected_slot_count >  len(round_brands)  → impossible by construction
  - detected_slot_count <  total_slots (NOSP) → NOSP capacity > running ads

The dashboard 'real miss' alert fires only when detected_slot_count > caught.
"""
from worker.db import connect

with connect() as conn, conn.cursor() as cur:
    cur.execute(
        """
        ALTER TABLE round_keyword_groups
        ADD COLUMN IF NOT EXISTS detected_slot_count INT
        """
    )
    conn.commit()
    print("Added detected_slot_count column (nullable, no default).")
    # We do NOT backfill — older scrapes have no record of the per-fetch peak.
    # Future scrapes will populate it; the dashboard alert ignores NULL rows.
