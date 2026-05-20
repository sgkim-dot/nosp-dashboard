"""Stage 1: scrape brand display name + destination URL from Naver search results.

Uses Playwright Python (headless Chromium). Run `uv run playwright install chromium`
once before invocation.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright

from worker.logging import get_logger
from worker.models import SlotExtract

log = get_logger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_EXTRACT_JS = r"""
() => {
    const slots = [];

    // SV
    const sv = document.querySelector('.searching_view');
    if (sv) {
        const link = sv.querySelector('a.sub_title');
        if (link) {
            slots.push({
                product: 'SEARCHING_VIEW',
                slot_no: 1,
                display_name: link.textContent.trim(),
                destination_url: link.href || null,
            });
        }
    }

    // NP — find section whose heading contains '브랜드 콘텐츠'
    const sections = document.querySelectorAll('div[class*="sc_new"]');
    let npSection = null;
    for (const s of sections) {
        const h = s.querySelector('h2, h3, [class*="title"]');
        if (h && h.textContent && h.textContent.includes('브랜드 콘텐츠')) {
            npSection = s;
            break;
        }
    }
    if (npSection) {
        const cards = npSection.querySelectorAll('[class*="sds-comps-profile"][class*="type-basic"]');
        let slot = 0;
        for (const card of cards) {
            const titleEl = card.querySelector('[class*="profile-info-title"]');
            if (!titleEl) continue;
            slot += 1;
            const cardWithLink = card.closest('div');
            const linkEl = cardWithLink && cardWithLink.querySelector('a[href*="ader.naver.com"]');
            slots.push({
                product: 'NEW_PRODUCT',
                slot_no: slot,
                display_name: titleEl.textContent.trim(),
                destination_url: linkEl ? linkEl.href : null,
            });
        }
    }

    return slots;
}
"""


def scrape_brands_for_keyword(keyword: str, *, timeout_ms: int = 20000) -> list[SlotExtract]:
    """Render Naver search for `keyword` and extract SV+NP ad slots.

    Returns an empty list if no slots are found (no ads running, or DOM changed).
    Raises on Playwright errors.
    """
    url = f"https://search.naver.com/search.naver?query={keyword}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=_USER_AGENT, locale="ko-KR")
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Allow SDS-based components to fully hydrate (NP cards lazy-load).
            page.wait_for_timeout(1500)
            raw = page.evaluate(_EXTRACT_JS)
        finally:
            context.close()
            browser.close()

    slots: list[SlotExtract] = []
    for s in raw or []:
        if not s.get("display_name"):
            continue
        slots.append(SlotExtract(**s))
    log.info("scraped", keyword=keyword, slot_count=len(slots))
    return slots
