"""Force re-scrape the NEW_PRODUCT 여행자보험 family of KGs.

User reported 2026-06-25 that 신제품검색 '여행자보험' is showing 0 advertisers
but 현대해상 / 롯데손보 are currently running. Re-scrapes the 4 active 여행자보험
KGs with a fresh BrowserPool (separate process from the running BAT) and
prints which ads were captured.
"""
from __future__ import annotations

from worker.db import connect
from worker.lib.naver_search import scrape_brands_with_detected_count
from worker.jobs.brand_scrape import fetch_business_name, _persist_kg_brands


def find_targets(conn) -> list[tuple[int, str, str, int]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rkg.id, kg.name,
                   COALESCE(kg.search_keyword, kg.name) AS kw,
                   p.max_brands_per_group
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = r.product_id
            WHERE p.code = 'NEW_PRODUCT'
              AND kg.name LIKE %s
              AND r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date
              AND r.period_end   >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
            ORDER BY rkg.regular_winning_bid DESC NULLS LAST, kg.name
            """,
            ("%여행자보험%",),
        )
        return cur.fetchall()


def main() -> None:
    with connect() as conn:
        targets = find_targets(conn)
        print(f"대상 KG {len(targets)}개:")
        for rkg_id, name, kw, mx in targets:
            print(f"  rkg={rkg_id}  name={name}  kw={kw}  max_brands={mx}")

        for rkg_id, name, kw, max_brands in targets:
            print(f"\n=== {name} (rkg={rkg_id}) ===")
            try:
                raw_slots, detected = scrape_brands_with_detected_count(
                    kw, "NEW_PRODUCT", timeout_ms=20000
                )
            except Exception as e:
                print(f"  [scrape err] {e}")
                continue

            np_slots = [s for s in raw_slots if s.product == "NEW_PRODUCT"]

            business_names: dict[str | None, str | None] = {}
            for s in np_slots:
                url = s.destination_url
                if url and url not in business_names:
                    business_names[url] = fetch_business_name(url)

            # Same dedup + dot-aware cap as _process_one_kg.
            seen: set[str] = set()
            unique = []
            for s in np_slots:
                host = business_names.get(s.destination_url)
                key = host or f"_url::{s.destination_url}"
                if key in seen:
                    continue
                seen.add(key)
                unique.append(s)
            cap = min(max_brands, detected) if detected and detected > 0 else max_brands
            slots = unique[:cap]
            # Reassign slot_no to 1-based after dedup so DB rows are contiguous.
            slots = [s.model_copy(update={"slot_no": i + 1}) for i, s in enumerate(slots)]
            print(
                f"  scraped raw={len(np_slots)} unique={len(unique)} "
                f"detected={detected} cap={cap} → kept={len(slots)}"
            )

            try:
                _persist_kg_brands(
                    rkg_id, slots, business_names,
                    detected_slot_count=detected,
                )
                for s in slots:
                    bn = business_names.get(s.destination_url)
                    print(f"  - slot={s.slot_no} {s.display_name[:40]:40s} → host={bn}")
            except Exception as e:
                print(f"  [persist err] {e}")


if __name__ == "__main__":
    main()
