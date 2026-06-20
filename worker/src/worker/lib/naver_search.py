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

    // For NP ads: extract sub-title (above main title) and description
    // (below main title). The OUTER .new_product_wrap contains MULTIPLE ad
    // cards (and sometimes duplicates from a carousel), so we must NOT
    // query .sub_tit / .desc against the wrap — that mixes data across ads.
    //
    // Instead, walk UP from the ad link until we find the smallest ancestor
    // that contains exactly ONE .sub_tit element. That ancestor is the
    // per-ad card. Then read .sub_tit and .desc relative to that card only.
    let subTitle = null;
    let description = null;
    if (product === 'NEW_PRODUCT') {
      let card = a;
      for (let i = 0; i < 12 && card; i++) {
        const sCount = card.querySelectorAll('.sub_tit').length;
        if (sCount === 1) break;  // perfect: exactly one sub_tit → this ad's card
        if (sCount > 1) {
          // We went one level too high — back down isn't possible, but at
          // this point the previous (smaller) ancestor had 0 sub_tit (the
          // card wasn't on this branch). Fall back to null rather than mix.
          card = null;
          break;
        }
        card = card.parentElement;
      }
      if (card) {
        const subEl = card.querySelector('.sub_tit');
        if (subEl) subTitle = (subEl.textContent || '').trim().slice(0, 200) || null;
        const descEls = card.querySelectorAll('.desc');
        if (descEls.length) {
          description = Array.from(descEls)
            .map(e => (e.textContent || '').trim())
            .filter(s => s)
            .join(' ')
            .slice(0, 400) || null;
        }
      }
    }

    if (!placements.has(adId)) {
      placements.set(adId, {
        product,
        ad_id: adId,
        display_name: displayName,
        sub_title: subTitle,
        description: description,
        destination_url: href,
      });
    }
  }
  return Array.from(placements.values());
};
"""


class BrowserPool:
    """Lazy persistent Playwright + browser + contexts (one mobile, one PC).

    The big saving vs. opening fresh per call: Playwright/Chromium startup is
    ~3-4s, and per-call creates of context add ~0.5s each. Reusing them brings
    per-keyword time down to ~1.5-2s.

    Used as a context manager so callers can `with BrowserPool() as pool: …`
    or rely on the module-level singleton (`_pool`).
    """

    def __init__(self):
        self._pw = None
        self._browser = None
        self._mobile_ctx = None
        self._pc_ctx = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        # Use system Chrome (channel="chrome") instead of Playwright's bundled
        # Chromium — Windows Defender on this machine intermittently blocks the
        # bundled chrome-headless-shell.exe from launching even though the file
        # is on disk.
        self._browser = self._pw.chromium.launch(headless=True, channel="chrome")
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        for c in (self._mobile_ctx, self._pc_ctx):
            try:
                if c:
                    c.close()
            except Exception:
                pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._pw = self._browser = self._mobile_ctx = self._pc_ctx = None

    def get_context(self, mobile: bool):
        if mobile:
            if self._mobile_ctx is None:
                self._mobile_ctx = self._browser.new_context(
                    user_agent=_MOBILE_UA,
                    locale="ko-KR",
                    viewport={"width": 390, "height": 844},
                    device_scale_factor=2,
                    is_mobile=True,
                    has_touch=True,
                )
            return self._mobile_ctx
        if self._pc_ctx is None:
            self._pc_ctx = self._browser.new_context(user_agent=_PC_UA, locale="ko-KR")
        return self._pc_ctx


_pool: BrowserPool | None = None


def _get_pool() -> BrowserPool:
    """Module-level singleton — auto-started on first use."""
    global _pool
    if _pool is None:
        _pool = BrowserPool()
        _pool.__enter__()
    return _pool


def close_pool() -> None:
    """Tear down the singleton browser pool. Call at job exit."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _run(keyword: str, *, mobile: bool, timeout_ms: int) -> list[dict]:
    """Fetch + extract once. Auto-recovers from Playwright driver death by
    resetting the BrowserPool and retrying once.

    Playwright's bundled Chromium driver process can die mid-run (memory
    pressure on Windows, Defender interference, an idle socket close). When
    it does, every subsequent `context.new_page()` raises
    "Connection closed while reading from the driver" until the pool is
    rebuilt. We catch that and any other Playwright-level failure here once,
    tear down, and retry. If the second attempt also fails the exception
    propagates to the caller (which will skip the KG and continue).
    """
    url = (
        f"https://m.search.naver.com/search.naver?query={keyword}"
        if mobile
        else f"https://search.naver.com/search.naver?query={keyword}"
    )
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            pool = _get_pool()
            context = pool.get_context(mobile)
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # Brand widgets hydrate quickly on mobile; PC even faster.
                page.wait_for_timeout(800)
                # NP (신제품검색) ad widget is lazy-loaded — without a scroll
                # trigger the .new_product_wrap stays empty and our extractor
                # returns 0 slots even when an ad is live. Scroll a bit and
                # give the widget time to hydrate, then evaluate.
                if mobile:
                    try:
                        page.evaluate("window.scrollTo(0, 400)")
                        page.wait_for_timeout(1200)
                    except Exception:
                        pass
                raw = page.evaluate(_EXTRACT_JS)
            finally:
                try:
                    page.close()
                except Exception:
                    pass
            return raw or []
        except Exception as e:  # noqa: BLE001 — Playwright wraps many types
            last_err = e
            if attempt == 1:
                log.warning(
                    "playwright fetch failed — resetting pool and retrying once",
                    keyword=keyword,
                    error=str(e)[:200],
                )
                try:
                    close_pool()
                except Exception:
                    log.exception("close_pool during _run recovery raised")
                continue
            # Second attempt also failed — let the caller skip the KG.
            log.exception("playwright fetch failed after pool reset", keyword=keyword)
            raise last_err


# Mobile NP ad slots rotate / sometimes fail to hydrate on a given fetch:
# in tests a single keyword with one running advertiser showed the ad on
# only 4 of 5 page loads. Multiple fetches catch all running brands and
# verify "0 slots" really means no ad is running.
#
# 2026-06-18: bumped 5→8 after analysis showed NP recall sitting at
# 16-18% for 4+ weeks against KGs with regular_winning_bid>0. The cheap
# win is more fetches in the first round; expensive retries only fire
# when the first round still came back empty.
_NP_RETRIES = 8
_SV_RETRIES = 1

# When NP returns 0 results we retry the full fetch sequence once after a
# short pause. Earlier this was 3 retries × 30s pause but ~80% of KGs are
# genuinely 0-ad, which made the BAT take ~6 days. detected_slot_count +
# the post-scrape sweep + nightly reset already handle the misses that a
# single retry doesn't catch, so one quick retry is enough to disambiguate
# "genuinely empty" from "first fetch unlucky".
_NP_ZERO_RETRY_COUNT = 1
_NP_ZERO_RETRY_PAUSE_SECONDS = 10.0
_NP_ZERO_RETRY_JITTER_SECONDS = 4.0


def scrape_brands_with_detected_count(
    keyword: str, product_code: str = "NEW_PRODUCT", *, timeout_ms: int = 20000
) -> tuple[list[SlotExtract], int]:
    """Same as `scrape_brands_for_keyword` but also returns the largest single-
    fetch unique-ad-id count observed during the scrape session.

    The returned `detected_slot_count` is the most reliable in-band signal for
    "how many ad placements the page actually showed at peak hydration":
      - 0  → no ad widget hydrated on any fetch (genuine no-ad OR fully missed)
      - 1  → only one advertiser was running (carousel showed a single placement)
      - 2+ → that many advertisers are in rotation on this KG

    Compare against `len(slots)`:
      - detected_slot_count == len(slots) → we captured everything visible
      - detected_slot_count >  len(slots) → impossible by construction
      - detected_slot_count <  any single fetch — also impossible (it's a max)

    The cross-fetch union `len(slots)` can exceed any single fetch's count if
    advertiser A appeared on fetch 1 and B on fetch 3 — that's the union
    catching rotation. In that case detected_slot_count tracks the *peak*
    single-fetch view, which is what the visible "dot indicator" reflects.
    """
    mobile = product_code != "SEARCHING_VIEW"
    n_fetches = _NP_RETRIES if mobile else _SV_RETRIES

    # Aggregate placements across fetches, keyed by ad_id (deduplicates so each
    # advertiser is counted once even if seen on multiple fetches).
    import random
    import time

    detected_slot_count = 0

    def _do_fetches(num: int) -> dict[str, dict]:
        nonlocal detected_slot_count
        m: dict[str, dict] = {}
        for i in range(num):
            raw = _run(keyword, mobile=mobile, timeout_ms=timeout_ms)
            this_fetch_ids: set[str] = set()
            for item in raw:
                ad_id = item.get("ad_id")
                if not ad_id:
                    continue
                # Mobile pages can contain BOTH a NP widget and a mobile-SV
                # widget at the same time. Only count placements matching the
                # product we're scraping — otherwise detected_slot_count gets
                # inflated by the other product's ads and the post-scrape
                # sweep mis-flags KGs as "real miss".
                if item.get("product") != product_code:
                    continue
                this_fetch_ids.add(ad_id)
                if ad_id not in m:
                    m[ad_id] = item
            # Track peak single-fetch slot count — the page's actual visible
            # placement count at its best hydration during this session.
            if len(this_fetch_ids) > detected_slot_count:
                detected_slot_count = len(this_fetch_ids)
            # Inter-fetch jittered pause — disguise burst pattern.
            if num > 1 and i < num - 1:
                time.sleep(2.0 + random.uniform(0, 3.0))
        return m

    merged = _do_fetches(n_fetches)

    # Reliability fix: if the first round found nothing AND we're on NP (where
    # anti-bot or lazy-load misses are common), wait substantially longer and
    # retry up to _NP_ZERO_RETRY_COUNT times. Long pauses outlast bursty IP
    # throttling. The cost only applies to KGs whose first full sweep saw 0
    # ads, so most KGs are unaffected.
    if mobile and not merged:
        for attempt in range(_NP_ZERO_RETRY_COUNT):
            pause = _NP_ZERO_RETRY_PAUSE_SECONDS + random.uniform(
                0, _NP_ZERO_RETRY_JITTER_SECONDS
            )
            log.info(
                "np empty — retrying after long pause",
                keyword=keyword,
                attempt=attempt + 1,
                pause_s=round(pause, 1),
            )
            time.sleep(pause)
            merged = _do_fetches(n_fetches)
            if merged:
                break

    raw = list(merged.values())

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
                sub_title=item.get("sub_title"),
                description=item.get("description"),
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
        detected=detected_slot_count,
    )
    return slots, detected_slot_count


def scrape_brands_for_keyword(
    keyword: str, product_code: str = "NEW_PRODUCT", *, timeout_ms: int = 20000
) -> list[SlotExtract]:
    """Backward-compatible wrapper around `scrape_brands_with_detected_count`.

    Discards the detected-slot-count and returns only the unioned slots.
    Used by older diagnostic scripts; production `brand_scrape` calls the
    new function directly so it can persist the count.
    """
    slots, _ = scrape_brands_with_detected_count(
        keyword, product_code, timeout_ms=timeout_ms
    )
    return slots
