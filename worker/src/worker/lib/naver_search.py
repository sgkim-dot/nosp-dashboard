"""Stage 1: scrape SV/NP brand ads from Naver search.

SV (서칭뷰) lives on PC desktop (search.naver.com).
NP (신제품검색) lives on mobile (m.search.naver.com).
ANNIVERSARY (기념일 광고) is mobile-only, like NP.

Ad type is determined by the `c=` query param of ader.naver.com links:
  c=naver.search.pc.sv         → PC SV
  c=mnaver.search.sv           → Mobile SV (rare)
  c=mnaver.search.newproduct   → Mobile NP / Anniversary

Multiple links may belong to the same ad placement (thumbnail, title, menu
items). We group them by the `i=SC*****` ad identifier embedded in the onclick
handler so each placement is counted once.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright

from worker.logging import get_logger
from worker.models import SlotExtract

log = get_logger(__name__)

_PC_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# JS extracted in the rendered page. Returns deduplicated ad placements.
_EXTRACT_JS = r"""
() => {
  const placements = new Map();  // ad_id -> placement object

  const aders = document.querySelectorAll('a[href*="ader.naver.com"]');
  for (const a of aders) {
    const href = a.href || '';
    let cParam = null;
    const m = href.match(/[?&]c=([^&]+)/);
    if (m) cParam = decodeURIComponent(m[1]);

    let product = null;
    if (cParam === 'naver.search.pc.sv' || cParam === 'mnaver.search.sv') {
      product = 'SEARCHING_VIEW';
    } else if (cParam === 'mnaver.search.newproduct') {
      product = 'NEW_PRODUCT';
    } else {
      continue;  // content widget, unrelated ad
    }

    // Ad placement id from onclick handler ("i=SC1234567")
    const onclick = a.getAttribute('onclick') || '';
    const im = onclick.match(/i=(SC\d+)/);
    const adId = im ? im[1] : ('hash-' + href.slice(0, 60));

    // Headline element: prefer <strong class="tit"> in the nearest container.
    let parent = a;
    let titEl = null;
    for (let i = 0; i < 8 && parent; i++) {
      titEl = parent.querySelector('strong.tit, .info_area strong, .info_area .tit, a.sub_title');
      if (titEl) break;
      parent = parent.parentElement;
    }
    let displayName = titEl ? (titEl.textContent || '').trim() : '';

    if (!displayName) {
      const txt = (a.textContent || '').trim();
      if (!/^(상세보기|보험료계산|이벤트가입|간편계산|즉시가입가능|보장내용확인|혜택보기|상품안내|가입하기|할인받기|문의하기|.{0,2}$)$/.test(txt)) {
        displayName = txt;
      }
    }
    if (!displayName) continue;
    if (displayName.length > 100) displayName = displayName.slice(0, 100);

    if (!placements.has(adId)) {
      placements.set(adId, {
        product,
        ad_id: adId,
        display_name: displayName,
        destination_url: href,
      });
    }
  }
  return Array.from(placements.values());
};
"""


def _run(keyword: str, *, mobile: bool, timeout_ms: int) -> list[dict]:
    url = (
        f"https://m.search.naver.com/search.naver?query={keyword}"
        if mobile
        else f"https://search.naver.com/search.naver?query={keyword}"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx_kwargs: dict = {
            "user_agent": _MOBILE_UA if mobile else _PC_UA,
            "locale": "ko-KR",
        }
        if mobile:
            ctx_kwargs.update(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
            )
        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollBy(0, 600)")
            page.wait_for_timeout(700)
            raw = page.evaluate(_EXTRACT_JS)
        finally:
            context.close()
            browser.close()
    return raw or []


def scrape_brands_for_keyword(
    keyword: str, product_code: str = "NEW_PRODUCT", *, timeout_ms: int = 20000
) -> list[SlotExtract]:
    """Render the appropriate viewport for `product_code` and extract ads.

    - SEARCHING_VIEW → PC search.naver.com
    - NEW_PRODUCT / ANNIVERSARY → mobile m.search.naver.com

    Slot numbering is 1-based per product, in DOM order.
    """
    mobile = product_code != "SEARCHING_VIEW"
    raw = _run(keyword, mobile=mobile, timeout_ms=timeout_ms)

    slots: list[SlotExtract] = []
    counters: dict[str, int] = {}
    for item in raw:
        prod = item.get("product")
        if prod not in ("SEARCHING_VIEW", "NEW_PRODUCT"):
            continue
        counters[prod] = counters.get(prod, 0) + 1
        slots.append(
            SlotExtract(
                product=prod,
                slot_no=counters[prod],
                display_name=item["display_name"],
                destination_url=item.get("destination_url"),
            )
        )
    log.info(
        "scraped",
        keyword=keyword,
        product=product_code,
        mobile=mobile,
        sv=counters.get("SEARCHING_VIEW", 0),
        np=counters.get("NEW_PRODUCT", 0),
    )
    return slots
