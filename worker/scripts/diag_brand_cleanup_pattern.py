"""Diagnose why so many brands ended up in the 긴급정정 bucket.

Reproduces the dashboard suspect list and breaks it down by:
  - reason mix (host broken / 미확인 브랜드)
  - host shape (Korean chars, parens, __unverified__, etc.)
  - whether the brand has an ad_copy / sub_title (extraction trace)
  - when the underlying round_brands rows were created
  - which products/keyword groups are concentrated
"""
from __future__ import annotations

import re
from collections import Counter

from worker.db import connect

_HOST_BROKEN_RE = re.compile(r"[\s()가-힣]|^__unverified__|주식회사|회사명")


def host_shape(host: str | None) -> str:
    if not host:
        return "empty"
    if host.startswith("__unverified__"):
        return "__unverified__"
    if "주식회사" in host or "회사명" in host:
        return "주식회사/회사명"
    if re.search(r"[가-힣]", host):
        return "한글 포함"
    if re.search(r"[\s]", host):
        return "공백 포함"
    if re.search(r"[()]", host):
        return "괄호 포함"
    return "기타"


def main() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              b.id,
              b.display_name,
              b.business_name,
              COUNT(rb.id)::int AS uses,
              MIN(rb.captured_at) AS first_seen,
              MAX(rb.captured_at) AS last_seen,
              array_agg(DISTINCT rb.display_name) FILTER (WHERE rb.display_name IS NOT NULL) AS ad_copies,
              array_agg(DISTINCT rb.sub_title) FILTER (WHERE rb.sub_title IS NOT NULL) AS subs,
              array_agg(DISTINCT p.code) FILTER (WHERE p.code IS NOT NULL) AS products,
              array_agg(DISTINCT kg.name) FILTER (WHERE kg.name IS NOT NULL) AS kgs
            FROM brands b
            LEFT JOIN round_brands rb ON rb.brand_id = b.id
            LEFT JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
            LEFT JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            LEFT JOIN products p ON p.id = kg.product_id
            GROUP BY b.id
            HAVING COUNT(rb.id) > 0
            """
        )
        rows = cur.fetchall()

    suspects = []
    for r in rows:
        bid, display, host, uses, first_seen, last_seen, ad_copies, subs, products, kgs = r
        if not display or not host:
            continue
        display = display.strip()
        host = host.strip()
        reasons = []
        if _HOST_BROKEN_RE.search(host):
            reasons.append("host_broken")
        if display == "(미확인 브랜드)":
            reasons.append("unknown_brand")
        if not reasons:
            continue
        suspects.append(
            dict(
                id=bid,
                display=display,
                host=host,
                uses=uses,
                first_seen=first_seen,
                last_seen=last_seen,
                ad_copies=ad_copies or [],
                subs=subs or [],
                products=products or [],
                kgs=kgs or [],
                reasons=reasons,
            )
        )

    total = len(suspects)
    print(f"\n=== 긴급정정 케이스 총 {total}건 ===\n")

    # Reason mix
    reason_ctr: Counter = Counter()
    for s in suspects:
        reason_ctr[",".join(s["reasons"])] += 1
    print("[1] 사유 분포")
    for k, v in reason_ctr.most_common():
        print(f"  {v:3d}  {k}")

    # Host shape
    shape_ctr: Counter = Counter()
    for s in suspects:
        shape_ctr[host_shape(s["host"])] += 1
    print("\n[2] host 모양 분포")
    for k, v in shape_ctr.most_common():
        print(f"  {v:3d}  {k}")

    # Cycle period — when did these first appear?
    print("\n[3] first_seen 분포 (KST 일자별)")
    day_ctr: Counter = Counter()
    for s in suspects:
        fs = s["first_seen"]
        if fs:
            # convert UTC → KST date
            from datetime import timedelta
            kst = fs + timedelta(hours=9)
            day_ctr[kst.date().isoformat()] += 1
    for k, v in sorted(day_ctr.items()):
        print(f"  {v:3d}  {k}")

    # Product/KG concentration
    prod_ctr: Counter = Counter()
    for s in suspects:
        for p in s["products"]:
            prod_ctr[p] += 1
    print("\n[4] 상품 분포")
    for k, v in prod_ctr.most_common():
        print(f"  {v:3d}  {k}")

    # Top 15 brands by 사용횟수, with host + ad_copy preview
    print("\n[5] 사용횟수 Top 20 (host + ad_copy 1개 미리보기)")
    suspects_sorted = sorted(suspects, key=lambda x: x["uses"], reverse=True)
    for s in suspects_sorted[:20]:
        ad = (s["ad_copies"][0] if s["ad_copies"] else "")[:30]
        host = s["host"][:40]
        display = s["display"][:20]
        kg = (s["kgs"][0] if s["kgs"] else "")[:20]
        print(f"  id={s['id']:5d} uses={s['uses']:3d} | host={host:42s} | display={display:22s} | ad={ad:30s} | kg={kg}")


if __name__ == "__main__":
    main()
