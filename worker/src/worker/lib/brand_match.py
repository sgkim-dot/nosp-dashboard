"""Brand normalization: map hostname → canonical Korean brand name.

The advertiser identity is keyed on `business_name` (resolved hostname).
The displayed `display_name` is the canonical brand (e.g. "삼성화재"),
NOT the per-ad creative copy — that lives on round_brands.display_name.
"""

from __future__ import annotations

import json

from psycopg import Connection

from worker.lib.canonical_brand import HOST_TO_BRAND, canonical_brand_name


# Sentinels that are ALLOWED in business_name even though they aren't URL hosts.
# Anything else with junk characters gets coerced to None (becomes
# __unverified__::<display> via the fallback path below).
_BUSINESS_NAME_SENTINEL_PREFIXES = ("__unverified__::", "__manual__::")


# Cached reverse map: canonical brand name → representative clean host.
_REPRESENTATIVE_HOST: dict[str, str | None] | None = None


def _representative_host(canonical: str) -> str | None:
    """Return the preferred clean host that maps to `canonical`, or None.

    Built lazily by reversing HOST_TO_BRAND. When multiple hosts map to
    the same canonical, prefer non-www → non-m. → no-path → shortest.
    """
    global _REPRESENTATIVE_HOST
    if _REPRESENTATIVE_HOST is None:
        rev: dict[str, list[str]] = {}
        for h, c in HOST_TO_BRAND.items():
            rev.setdefault(c, []).append(h)
        for c, hosts in rev.items():
            hosts.sort(key=lambda h: (
                h.startswith("www."),
                h.startswith("m."),
                "/" in h,
                len(h),
                h,
            ))
        _REPRESENTATIVE_HOST = {c: hs[0] for c, hs in rev.items()}
    return _REPRESENTATIVE_HOST.get(canonical)


def _is_junk_host(s: str) -> bool:
    """Return True if a business_name string is clearly not a URL host.

    Real URL hosts are ASCII, have no whitespace/parens/colons/commas, and
    don't contain Korean tokens like '주식회사' or '회사명'. Strings that
    fail these are typically remnants of HTML footer extraction
    (e.g. '회사명: 주식회사 ABC', '코웨이(주) 본점 : 충남 ...') and must not
    be stored — they only pollute the brand-cleanup dashboard.

    Sentinel prefixes like __unverified__:: / __manual__:: are allowed.
    Naver platform paths (brand.naver.com/foo) are allowed (have '/').
    """
    if any(s.startswith(p) for p in _BUSINESS_NAME_SENTINEL_PREFIXES):
        return False
    if any(c in s for c in " ()[]:,\\"):
        return True
    if any(k in s for k in ("주식회사", "회사명", "본점", "대표", "사업자", "주소")):
        return True
    # Any Korean character → definitely not a hostname.
    if any("가" <= c <= "힯" for c in s):
        return True
    return False


def upsert_brand(
    conn: Connection,
    *,
    business_name: str | None,
    display_name: str,
) -> int:
    """Insert/find a brand row. Use the canonical brand name for display.

    - `business_name` is the hostname returned by Stage 2 (e.g.
      "direct.samsungfire.com"); used as the unique key.
    - `display_name` is the ad creative copy from Stage 1 (e.g. "삼성화재
      다이렉트 실손의료비보험"); used only as the heuristic fallback when the
      hostname isn't in the canonical map.

    Existing aliases keep the historical ad creatives, but the row's
    `display_name` is always normalized to the canonical name when possible.
    """
    if not display_name:
        raise ValueError("display_name required")

    # L1 defense: refuse to store junk strings in business_name. Any caller
    # that passes Korean text, addresses, or company-registration fragments
    # gets coerced to the __unverified__:: sentinel path instead. This
    # makes it physically impossible for the brand-cleanup dashboard to
    # accumulate "호스트 깨짐" rows from new scrapes.
    if business_name and _is_junk_host(business_name):
        business_name = None

    canonical = canonical_brand_name(business_name, display_name) or "(미확인 브랜드)"

    # L1.5 defense: if Stage 2 failed to resolve a host (business_name is
    # None) BUT we determined the canonical brand via DISPLAY_CANONICAL or
    # any other path, jump straight to the representative clean host for
    # that canonical. Without this, every new ad creative (e.g. "뻬를리 워치",
    # "뻬를리 펜던트") spawns its own __unverified__:: row that the
    # cleanup dashboard flags as "호스트 깨짐", even though the brand was
    # correctly identified. With this gate, repeat ad copy variants of the
    # SAME advertiser collapse into the single canonical brand row.
    if not business_name and canonical != "(미확인 브랜드)":
        host = _representative_host(canonical)
        if host:
            business_name = host

    with conn.cursor() as cur:
        if business_name:
            cur.execute(
                "SELECT id, display_name, aliases FROM brands WHERE business_name = %s",
                (business_name,),
            )
            row = cur.fetchone()
            if row:
                bid, existing_display, aliases = row
                # Upgrade existing row's display_name to canonical if differs.
                if existing_display != canonical:
                    cur.execute(
                        "UPDATE brands SET display_name = %s WHERE id = %s",
                        (canonical, bid),
                    )
                _maybe_append_alias(conn, bid, canonical, aliases, display_name)
                return bid

        # No existing row — insert one keyed by hostname (or sentinel for none).
        effective_bn = business_name or f"__unverified__::{display_name}"
        cur.execute(
            """
            INSERT INTO brands (business_name, display_name, aliases)
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (business_name) DO UPDATE SET display_name = EXCLUDED.display_name
            RETURNING id
            """,
            (effective_bn, canonical, json.dumps([display_name], ensure_ascii=False)),
        )
        return cur.fetchone()[0]


def _maybe_append_alias(
    conn: Connection,
    brand_id: int,
    existing_display: str,
    current_aliases: list[str] | None,
    incoming_display: str,
) -> None:
    if incoming_display == existing_display:
        return
    aliases = list(current_aliases or [])
    if incoming_display in aliases:
        return
    aliases.append(incoming_display)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE brands SET aliases = %s::jsonb WHERE id = %s",
            (json.dumps(aliases, ensure_ascii=False), brand_id),
        )
