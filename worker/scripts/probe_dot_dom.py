"""Refine: confirm dot pagination is INSIDE the NP wrap and count is correct."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from worker.lib.naver_search import _get_pool, close_pool

PROBE_JS = r"""
() => {
  const wrap = document.querySelector('.new_product_wrap, .api_subject_bx.brand_wrap');
  if (!wrap) return { wrap: false };

  // Dot pagination INSIDE the NP wrap?
  const dotsInside = wrap.querySelectorAll('.sds-comps-dot-pagination-bullet');
  const pagInside = wrap.querySelector('.sds-comps-dot-pagination');

  // For comparison — total in document
  const dotsAllDoc = document.querySelectorAll('.sds-comps-dot-pagination-bullet');

  // Unique ad_id count from extracted ader links.
  // Naver rotated placement-id format in mid-2026 from `i=SC1234567` to
  // `i=nad-a001-04-…`. Match BOTH so the probe stays accurate.
  const placements = new Map();
  wrap.querySelectorAll('a[href*="ader.naver.com"]').forEach(a => {
    const onclick = a.getAttribute('onclick') || '';
    let m = onclick.match(/[?&]i=(nad-[A-Za-z0-9_-]+)/);
    if (!m) m = onclick.match(/[?&]i=(SC\d+)/);
    const adId = m ? m[1] : null;
    if (adId) placements.set(adId, true);
  });

  return {
    flick_items_in_wrap: wrap.querySelectorAll('.flick_item').length,
    unique_ad_ids_in_wrap: placements.size,
    dots_inside_wrap: dotsInside.length,
    dots_total_in_doc: dotsAllDoc.length,
    pagination_inside: pagInside ? {
      class: pagInside.className,
      child_count: pagInside.children.length,
      outer: (pagInside.outerHTML || '').slice(0, 600),
    } : null,
  };
};
"""


def probe(keyword: str) -> dict:
    from urllib.parse import quote
    pool = _get_pool()
    context = pool.get_context(True)
    page = context.new_page()
    try:
        page.goto(
            f"https://m.search.naver.com/search.naver?query={quote(keyword)}",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        page.wait_for_timeout(800)
        page.evaluate("window.scrollTo(0, 400)")
        page.wait_for_timeout(1500)
        return page.evaluate(PROBE_JS)
    finally:
        page.close()


# Test on multiple keywords with known slot counts
KEYWORDS = [
    ("해외여행자보험", "expect 2"),
    ("단기여행자보험", "expect 1"),
    ("실비보험",      "expect ? (2 per NOSP, 1 caught earlier)"),
    ("자동차보험",    "popular"),
    ("운전자보험",    "had dot=2 in earlier note"),
]

try:
    for kw, note in KEYWORDS:
        print("=" * 80)
        print(f"keyword: {kw}  ({note})")
        print("=" * 80)
        data = probe(kw)
        print(json.dumps(data, ensure_ascii=False, indent=2))
finally:
    close_pool()
