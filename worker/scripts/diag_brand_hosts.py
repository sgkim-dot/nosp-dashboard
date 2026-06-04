"""Diagnose why brand cleanup issues keep recurring.

For each (host, expected_canonical_name) pair the user reported, look for:
  1. All brand rows whose business_name matches ANY variant of the host
     (with/without www., m., trailing slash, etc.)
  2. All brand rows whose display_name is the "wrong" name the user wants
     replaced (e.g. '뻬를리', 'Qrevo', 'Pro+', '강력한', '에스클래스', '알레르망').
  3. What canonical_brand_name() returns for the row's current host.
  4. round_brands usage count per brand_id.

Output reveals: are mappings missing? are display_names stale? are there
duplicate rows for the same canonical brand?
"""
from __future__ import annotations

from collections import defaultdict

from worker.db import connect
from worker.lib.canonical_brand import HOST_TO_BRAND, canonical_brand_name, normalize_host

# (host_as_user_provided, expected_canonical, wrong_display_we_want_to_replace_if_any)
CASES: list[tuple[str, str, str | None]] = [
    ("www.esthermall.co.kr",   "에스더포뮬러",     None),
    ("curtainmaster.kr",        "커튼명장",         None),
    ("www.vancleefarpels.com",  "반클리프아펠",     "뻬를리"),
    ("www.coway.com",           "코웨이",           None),
    ("kr.roborock.com",         "로보락",           "Qrevo"),
    ("www.hej.life",            "헤이홈",           "Pro+"),
    ("direct.hi.co.kr",         "현대해상",         None),
    ("bodranmall.com",          "발렌",             "강력한"),
    ("evckorea.cafe24.com",     "이브이씨코리아",   None),
    ("m.farfe.co.kr",           "파르페by알레르망", "알레르망"),
    ("modelomall.co.kr",        "모델로",           None),
    ("1544-0024.co.kr",         "로젠이사",         None),
    ("www.keyang.kr",           "계양공구",         None),
    ("webiommall.co.kr",        "위바이옴",         "에스클래스"),
]


def host_variants(h: str) -> set[str]:
    """All plausible stored forms of a host (with/without www., m., etc.)."""
    h = h.lower().strip()
    base = h
    if base.startswith("www."):
        base = base[4:]
    if base.startswith("m."):
        base = base[2:]
    return {h, base, f"www.{base}", f"m.{base}"}


def main() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.id, b.business_name, b.display_name, COUNT(rb.id) AS uses
                FROM brands b
                LEFT JOIN round_brands rb ON rb.brand_id = b.id
                GROUP BY b.id, b.business_name, b.display_name
                """
            )
            all_brands = cur.fetchall()
    brands_by_host: dict[str, list[tuple[int, str, str, int]]] = defaultdict(list)
    brands_by_display: dict[str, list[tuple[int, str, str, int]]] = defaultdict(list)
    for bid, bn, dn, uses in all_brands:
        brands_by_host[bn].append((bid, bn, dn, uses))
        brands_by_display[dn].append((bid, bn, dn, uses))

    print(f"Total brand rows in DB: {len(all_brands)}")
    print(f"HOST_TO_BRAND entries: {len(HOST_TO_BRAND)}\n")

    for raw_host, expected, wrong_display in CASES:
        print("=" * 70)
        print(f"USER REQUEST: {raw_host}  →  expected canonical: {expected!r}"
              + (f"  (replace wrong display {wrong_display!r})" if wrong_display else ""))

        # 1. Check HOST_TO_BRAND mappings for variants
        print("\n  HOST_TO_BRAND status:")
        any_mapped = False
        for v in sorted(host_variants(raw_host)):
            if v in HOST_TO_BRAND:
                print(f"    [map] {v!r:<35} → {HOST_TO_BRAND[v]!r}")
                any_mapped = True
        if not any_mapped:
            print("    [map] NO ENTRY for any variant")

        # 2. Find brand rows by host variants
        print("\n  brand rows by host variant:")
        found_by_host = False
        for v in sorted(host_variants(raw_host)):
            for row in brands_by_host.get(v, []):
                bid, bn, dn, uses = row
                canon = canonical_brand_name(bn, dn) or "(unmapped)"
                stale = "STALE" if canon != dn else "ok"
                print(f"    id={bid:<5} bn={bn!r:<35} dn={dn!r:<20} canon={canon!r:<20} [{stale}] uses={uses}")
                found_by_host = True
        if not found_by_host:
            print("    (no brand row found by host)")

        # 3. Find brand rows by wrong display_name (if user specified one)
        if wrong_display:
            print(f"\n  brand rows with display_name={wrong_display!r}:")
            for row in brands_by_display.get(wrong_display, []):
                bid, bn, dn, uses = row
                canon = canonical_brand_name(bn, dn) or "(unmapped)"
                print(f"    id={bid:<5} bn={bn!r:<35} dn={dn!r:<20} canon={canon!r:<20} uses={uses}")

        # 4. Find brand rows with the EXPECTED canonical as display
        print(f"\n  brand rows with display_name={expected!r}:")
        for row in brands_by_display.get(expected, []):
            bid, bn, dn, uses = row
            canon = canonical_brand_name(bn, dn) or "(unmapped)"
            print(f"    id={bid:<5} bn={bn!r:<35} dn={dn!r:<20} canon={canon!r:<20} uses={uses}")
        print()


if __name__ == "__main__":
    main()
