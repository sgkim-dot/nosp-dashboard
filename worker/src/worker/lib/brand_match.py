"""Brand normalization: fuzzy match incoming brand text against existing rows."""

from __future__ import annotations

import json

from psycopg import Connection
from rapidfuzz import fuzz, process

_FUZZY_THRESHOLD = 92


def upsert_brand(
    conn: Connection,
    *,
    business_name: str | None,
    display_name: str,
) -> int:
    if not display_name:
        raise ValueError("display_name required")

    with conn.cursor() as cur:
        if business_name:
            cur.execute(
                "SELECT id, display_name, aliases FROM brands WHERE business_name = %s",
                (business_name,),
            )
            row = cur.fetchone()
            if row:
                bid, existing_display, aliases = row
                _maybe_append_alias(conn, bid, existing_display, aliases, display_name)
                return bid

        cur.execute("SELECT id, display_name, aliases FROM brands")
        candidates = cur.fetchall()
        if candidates:
            choices = {row[0]: row[1] for row in candidates}
            best = process.extractOne(
                display_name,
                choices,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=_FUZZY_THRESHOLD,
            )
            if best is not None:
                _matched_display, _score, bid = best
                row = next(r for r in candidates if r[0] == bid)
                _maybe_append_alias(conn, bid, row[1], row[2], display_name)
                return bid

        effective_bn = business_name or f"__unverified__::{display_name}"
        cur.execute(
            """
            INSERT INTO brands (business_name, display_name, aliases)
            VALUES (%s, %s, '[]'::jsonb)
            ON CONFLICT (business_name) DO UPDATE SET display_name = EXCLUDED.display_name
            RETURNING id
            """,
            (effective_bn, display_name),
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
