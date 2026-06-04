"""Merge brand rows with broken business_name into their clean-host twin.

Old extraction code stored Korean company names (e.g. '아이배냇(주') in the
business_name column. The current scraper uses normalized URL hosts
(e.g. 'shop.ivenet.co.kr'), but legacy rows persist and keep surfacing on
the dashboard's 브랜드 정리 필요 page.

For each pair of brand rows sharing the same display_name, where one host
is "broken" (Korean chars, parens, __unverified__, etc.) and the other is
a clean URL host, this script:

  1. Re-points all round_brands rows from the broken brand_id to the clean one.
  2. Merges aliases (broken row's aliases appended to clean row's).
  3. Deletes the broken row.

Run with no args (dry-run) first to preview; pass --apply to commit.

    uv run python scripts/dedupe_broken_brands.py            # dry-run
    uv run python scripts/dedupe_broken_brands.py --apply    # commit
"""

from __future__ import annotations

import json
import re
import sys

from worker.db import connect

_HOST_BROKEN_RE = re.compile(r"[\s()가-힣]|^__unverified__|주식회사|회사명")


def is_broken(host: str | None) -> bool:
    if not host:
        return True
    return bool(_HOST_BROKEN_RE.search(host))


def main(apply: bool) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, business_name, display_name, aliases FROM brands"
            )
            rows = cur.fetchall()

        by_display: dict[str, list[tuple[int, str, str, list]]] = {}
        for bid, bn, dn, aliases in rows:
            by_display.setdefault(dn, []).append((bid, bn, dn, aliases or []))

        merges: list[tuple[int, int, str, str]] = []  # (broken_id, clean_id, broken_bn, clean_bn)
        for dn, group in by_display.items():
            if len(group) < 2:
                continue
            cleans = [g for g in group if not is_broken(g[1])]
            brokens = [g for g in group if is_broken(g[1])]
            if not cleans or not brokens:
                continue
            # Pick the clean row with the most aliases (most likely the active one);
            # ties broken by lowest id (oldest).
            clean = sorted(cleans, key=lambda g: (-len(g[3]), g[0]))[0]
            for broken in brokens:
                merges.append((broken[0], clean[0], broken[1], clean[1]))

        if not merges:
            print("No mergeable broken/clean pairs found.")
            return

        print(f"Found {len(merges)} broken→clean merges:\n")
        for broken_id, clean_id, broken_bn, clean_bn in merges:
            print(f"  brand_id {broken_id} ({broken_bn!r}) → {clean_id} ({clean_bn!r})")

        if not apply:
            print("\n[dry-run] re-run with --apply to commit.")
            return

        with conn.cursor() as cur:
            for broken_id, clean_id, _bbn, _cbn in merges:
                # 1. Re-point round_brands
                cur.execute(
                    "UPDATE round_brands SET brand_id = %s WHERE brand_id = %s",
                    (clean_id, broken_id),
                )
                moved = cur.rowcount
                # 2. Merge aliases
                cur.execute(
                    "SELECT aliases FROM brands WHERE id = %s", (broken_id,)
                )
                broken_aliases = (cur.fetchone() or ([],))[0] or []
                cur.execute(
                    "SELECT aliases FROM brands WHERE id = %s", (clean_id,)
                )
                clean_aliases = (cur.fetchone() or ([],))[0] or []
                merged = list(clean_aliases)
                for a in broken_aliases:
                    if a not in merged:
                        merged.append(a)
                cur.execute(
                    "UPDATE brands SET aliases = %s::jsonb WHERE id = %s",
                    (json.dumps(merged, ensure_ascii=False), clean_id),
                )
                # 3. Delete broken row
                cur.execute("DELETE FROM brands WHERE id = %s", (broken_id,))
                print(f"  [OK] {broken_id} -> {clean_id}: moved {moved} round_brands, merged {len(broken_aliases)} aliases")

        conn.commit()
        print(f"\nCommitted {len(merges)} merges.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
