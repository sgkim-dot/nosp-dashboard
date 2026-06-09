"""Reconcile the brands table with the current HOST_TO_BRAND map.

Run this after EVERY edit to `canonical_brand.py` HOST_TO_BRAND or
DISPLAY_CANONICAL. It performs the full reconciliation in one transaction:

  Step 1. Backfill canonical display_name
      For every brand row, recompute canonical_brand_name(business_name,
      display_name) and update display_name if it differs.

  Step 2. Merge duplicate brand rows with same canonical
      Group rows by their (post-step-1) canonical display_name. When two
      or more rows share a canonical, pick the "best" survivor (cleanest
      host, highest usage, lowest id) and merge the rest into it:
        - Repoint all round_brands.brand_id to the survivor.
        - Append losing-row business_names + aliases to survivor.aliases.
        - Delete losing rows.

  Step 3. Regenerate apps/dashboard/lib/canonical-hosts.json

Usage:
    uv run python scripts/reconcile_brands.py            # dry-run
    uv run python scripts/reconcile_brands.py --apply    # commit
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from worker.db import connect
from worker.lib.canonical_brand import (
    DISPLAY_FULL_CANONICAL,
    HOST_TO_BRAND,
    canonical_brand_name,
)

JSON_OUT = (
    Path(__file__).resolve().parent.parent.parent
    / "apps"
    / "dashboard"
    / "lib"
    / "canonical-hosts.json"
)


def _is_clean_host(s: str) -> bool:
    """Mirror brand_match._is_junk_host inverted, plus exclude sentinels.

    A 'clean' host is suitable as the SURVIVOR in a merge — preferred over
    junk or sentinel-prefixed business_names.
    """
    if not s:
        return False
    if s.startswith("__unverified__::") or s.startswith("__manual__::"):
        return False
    if any(c in s for c in " ()[]:,\\"):
        return False
    if any(k in s for k in ("주식회사", "회사명", "본점", "대표", "사업자", "주소")):
        return False
    if any("가" <= c <= "힯" for c in s):
        return False
    return True


def _canonical_to_hosts() -> dict[str, list[str]]:
    """Reverse-lookup HOST_TO_BRAND: canonical_name → list of mapped hosts.

    Hosts are sorted so the 'preferred' clean host comes first:
    non-www variant before www. variant, shortest first.
    """
    out: dict[str, list[str]] = {}
    for host, canon in HOST_TO_BRAND.items():
        out.setdefault(canon, []).append(host)
    for canon in out:
        out[canon].sort(key=lambda h: (h.startswith("www."), h.startswith("m."), len(h), h))
    return out


def main(apply: bool) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.id, b.business_name, b.display_name, b.aliases,
                       COUNT(rb.id) AS uses
                FROM brands b
                LEFT JOIN round_brands rb ON rb.brand_id = b.id
                GROUP BY b.id, b.business_name, b.display_name, b.aliases
                """
            )
            rows = cur.fetchall()

        # ── Step 0: rehome junk business_names to clean hosts ──────────
        # For any brand row whose business_name is junk (Korean, parens, …)
        # but whose canonical resolves to a name that HOST_TO_BRAND has a
        # clean host for, UPDATE the business_name to that clean host —
        # unless another row already occupies it (then step 2 merges).
        canon_to_hosts = _canonical_to_hosts()
        existing_bns = {r[1] for r in rows}
        rehome_plan: list[tuple[int, str, str]] = []  # (id, old_bn, new_bn)
        for bid, bn, dn, _aliases, _uses in rows:
            if not bn or _is_clean_host(bn):
                continue
            # Skip sentinel-prefixed names — those are intentional placeholders
            if bn.startswith("__manual__::") or bn.startswith("__unverified__::"):
                continue
            canon = canonical_brand_name(bn, dn)
            if not canon or canon == "(미확인 브랜드)":
                continue
            hosts = canon_to_hosts.get(canon, [])
            if not hosts:
                continue
            target = hosts[0]  # most preferred clean host for this canonical
            if target == bn or target in existing_bns:
                continue  # already there, or another row owns it (step 2 will merge)
            rehome_plan.append((bid, bn, target))
            existing_bns.add(target)
            existing_bns.discard(bn)

        # ── Step 1: figure out new canonical display per row ───────────
        # We consult aliases — they store the ORIGINAL full ad copy
        # (e.g. "현장의 신뢰를 기록하다!") which can match DISPLAY_FULL_CANONICAL
        # even when the stored display_name has already been trimmed to the
        # heuristic first word (e.g. "현장의"). RESTRICTED to exact-phrase
        # matches in DISPLAY_FULL_CANONICAL — aliases are noisy (mix of past
        # mis-identifications) so we do NOT run them through first-word
        # heuristics, which would propagate noise into stable rows.
        backfill_updates: list[tuple[int, str, str]] = []  # (id, old, new)
        new_display_by_id: dict[int, str] = {}
        for bid, bn, dn, aliases, _uses in rows:
            canon = canonical_brand_name(bn, dn)
            if not canon or canon == "(미확인 브랜드)" or canon == dn:
                for alias in aliases or []:
                    stripped = (alias or "").strip()
                    if stripped and stripped in DISPLAY_FULL_CANONICAL:
                        canon = DISPLAY_FULL_CANONICAL[stripped]
                        break
            canon = canon or "(미확인 브랜드)"
            if canon != dn:
                backfill_updates.append((bid, dn, canon))
            new_display_by_id[bid] = canon

        # ── Step 2: group by NEW canonical, plan merges ────────────────
        by_canon: dict[str, list[tuple]] = defaultdict(list)
        for r in rows:
            bid = r[0]
            canon = new_display_by_id[bid]
            by_canon[canon].append(r)

        merge_plan: list[tuple[int, int]] = []  # (loser_id, winner_id)
        for canon, group in by_canon.items():
            if len(group) < 2:
                continue
            # Skip the unverified bucket — never auto-merge those (they're
            # ad-copies, all different advertisers that happen to lack a host).
            if canon == "(미확인 브랜드)":
                continue
            def rank(g):
                bid, bn, dn, aliases, uses = g
                # 1) Prefer rows whose business_name is in HOST_TO_BRAND
                #    (the most authoritative mapping)
                in_map = int(bn in HOST_TO_BRAND)
                # 2) Prefer ASCII/clean hosts
                clean = int(_is_clean_host(bn or ""))
                # 3) Higher usage wins
                # 4) Older row wins (lower id, more stable references)
                return (-in_map, -clean, -uses, bid)
            winner, *losers = sorted(group, key=rank)
            for loser in losers:
                merge_plan.append((loser[0], winner[0]))

        # If we rehomed any rows, update the local `rows` snapshot's bn
        # so step 1/2 see the new values (avoids double-canonicalization edge).
        if rehome_plan:
            new_bn = {bid: target for bid, _old, target in rehome_plan}
            rows = [
                (r[0], new_bn.get(r[0], r[1]), r[2], r[3], r[4])
                for r in rows
            ]

        # ── Report ─────────────────────────────────────────────────────
        print(f"=== Step 0: rehome junk business_names to clean hosts ===")
        print(f"  rows: {len(rehome_plan)}")
        for bid, old_bn, new_bn in rehome_plan:
            print(f"    id={bid:<5} {old_bn!r:<40} → {new_bn!r}")
        print()
        print(f"=== Step 1: display_name backfill ===")
        print(f"  rows needing update: {len(backfill_updates)}")
        for bid, old, new in backfill_updates[:30]:
            print(f"    id={bid:<5} {old!r:<30} → {new!r}")
        if len(backfill_updates) > 30:
            print(f"    ... and {len(backfill_updates) - 30} more")

        print(f"\n=== Step 2: duplicate merges ===")
        print(f"  pairs to merge: {len(merge_plan)}")
        # Group display by winner for readability
        by_winner: dict[int, list[int]] = defaultdict(list)
        for loser, winner in merge_plan:
            by_winner[winner].append(loser)
        for winner_id, losers in list(by_winner.items())[:20]:
            winner_row = next(r for r in rows if r[0] == winner_id)
            print(f"    {len(losers)} → id={winner_id} ({winner_row[1]!r}, canon={new_display_by_id[winner_id]!r})")
            for loser_id in losers:
                loser_row = next(r for r in rows if r[0] == loser_id)
                print(f"        from id={loser_id:<5} bn={loser_row[1]!r:<40} dn={loser_row[2]!r}")
        if len(by_winner) > 20:
            print(f"    ... and {len(by_winner) - 20} more winner groups")

        if not apply:
            print("\n[dry-run] re-run with --apply to commit.")
            return

        # ── Apply ──────────────────────────────────────────────────────
        with conn.cursor() as cur:
            # Step 0 rehome (must run BEFORE merges/updates so subsequent
            # operations see the new business_names)
            for bid, _old, new_bn_val in rehome_plan:
                cur.execute(
                    "UPDATE brands SET business_name = %s WHERE id = %s",
                    (new_bn_val, bid),
                )

            # Step 1 updates
            for bid, _old, new in backfill_updates:
                cur.execute(
                    "UPDATE brands SET display_name = %s WHERE id = %s",
                    (new, bid),
                )

            # Step 2 merges
            for loser_id, winner_id in merge_plan:
                # Repoint round_brands
                cur.execute(
                    """
                    UPDATE round_brands SET brand_id = %s
                    WHERE brand_id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM round_brands rb2
                          WHERE rb2.round_keyword_group_id = round_brands.round_keyword_group_id
                            AND rb2.slot_no = round_brands.slot_no
                            AND rb2.brand_id = %s
                      )
                    """,
                    (winner_id, loser_id, winner_id),
                )
                # If any round_brands rows still point to loser (because the
                # winner already had a row for that (rkg, slot)), delete them.
                cur.execute(
                    "DELETE FROM round_brands WHERE brand_id = %s",
                    (loser_id,),
                )
                # Merge aliases: append loser.business_name + loser.aliases
                cur.execute(
                    "SELECT business_name, aliases FROM brands WHERE id = %s",
                    (loser_id,),
                )
                lbn, laliases = cur.fetchone() or (None, [])
                cur.execute(
                    "SELECT aliases FROM brands WHERE id = %s",
                    (winner_id,),
                )
                waliases = (cur.fetchone() or ([],))[0] or []
                merged = list(waliases)
                for a in list(laliases or []) + ([lbn] if lbn else []):
                    if a and a not in merged:
                        merged.append(a)
                cur.execute(
                    "UPDATE brands SET aliases = %s::jsonb WHERE id = %s",
                    (json.dumps(merged, ensure_ascii=False), winner_id),
                )
                cur.execute("DELETE FROM brands WHERE id = %s", (loser_id,))

        conn.commit()

        # ── Step 3: regenerate canonical-hosts.json ────────────────────
        hosts = sorted(HOST_TO_BRAND.keys())
        JSON_OUT.write_text(
            json.dumps(hosts, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n=== Step 3: regenerated {JSON_OUT}")
        print(f"  {len(hosts)} canonical hosts")
        print(f"\nDone. {len(backfill_updates)} displays updated, {len(merge_plan)} rows merged.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
