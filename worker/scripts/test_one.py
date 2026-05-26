"""Test new scraper across product types."""
from worker.lib.naver_search import scrape_brands_for_keyword
from worker.jobs.brand_scrape import fetch_business_name

CASES = [
    ("운전자보험", "NEW_PRODUCT"),     # User: 삼성화재 단독 expected
    ("실비보험", "NEW_PRODUCT"),       # NP slot
    ("실비보험", "SEARCHING_VIEW"),    # PC SV — expect 삼성화재
    ("탈모", "SEARCHING_VIEW"),        # PC SV
    ("소파", "NEW_PRODUCT"),            # NP — expect 자코모/others
]

for kw, prod in CASES:
    print(f"\n=== {kw} ({prod}) ===")
    slots = scrape_brands_for_keyword(kw, prod)
    filtered = [s for s in slots if s.product == prod]
    for s in filtered:
        host = fetch_business_name(s.destination_url) if s.destination_url else None
        print(f"  slot={s.slot_no} name={s.display_name!r}")
        print(f"    host={host}")
    if not filtered:
        print("  (no slots)")
