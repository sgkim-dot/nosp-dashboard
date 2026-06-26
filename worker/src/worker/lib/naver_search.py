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


class NaverBlockedError(RuntimeError):
    """Raised when Naver returns a bot-block / "검색 서비스 제한" page.

    The fetcher pages out — keyword scraping must STOP for this BAT run, or
    the IP block will escalate. Caller (brand_scrape) catches this and aborts
    the rest of the cycle so the user can clear the IP block manually.
    """


# Phrases that Naver's "검색 서비스 이용이 제한되었습니다" interstitial reliably
# contains. We check page text after navigation. The interstitial is served
# instead of the real SERP when Naver flags the client IP/UA as automated.
_BLOCK_MARKERS = (
    "검색 서비스 이용이 제한",
    "검색서비스 이용이 제한",
    "안정적인 검색 서비스를 방해",
    "프로그램을 이용한 자동 검색",
    "보안 절차를 거치",
    "제한 해제",
)

_PC_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# JS extracted in the rendered page. Returns deduplicated ad placements.
#
# Two paths, run in this order so a card-scoped extraction wins over the
# generic link scan when both apply:
#
#   1) NP card path — iterate `.new_product_wrap > .flick_item` (one card =
#      one ad placement) and pull display_name, sub_title, description and
#      the canonical destination link out of that single card's `.info_area`.
#      This is the ONLY path that produces correct results for NP, because
#      a single NP ad renders FOUR ader.naver.com links (thumbnail / info /
#      "상세보기" / brand-specific action button) all with different opaque
#      query tokens but the SAME `i=...` placement id, plus the carousel
#      renders each card twice for infinite scrolling. Scanning by link and
#      deduping by href fingerprint produces up to 8 spurious "slots" per
#      single real ad.
#
#   2) SV / fallback link path — for SV (PC, no `.new_product_wrap`) and any
#      stray NP link that wasn't captured by the card path, fall back to
#      per-link extraction with a per-card walk-up (smallest ancestor with
#      exactly one `strong.tit`) so we never reach into a sibling card.
#
# Placement identity: prefer Naver's `i=...` parameter inside the onclick
# handler. Naver rotated the format in mid-2026 from `i=SC1234567` (legacy
# Searching View) to `i=nad-a001-04-…` (current NP & SV). Match BOTH; if
# neither matches, fall back to a card fingerprint (sub_tit + tit) — the
# href itself is NOT safe to use as the dedup key because every ader.naver
# redirect token is unique per link even within the same ad.
_EXTRACT_JS = r"""
() => {
  const placements = new Map();  // dedup key -> placement object
  const consumedLinks = new WeakSet();  // ader links captured by card path

  const productFromHref = (href) => {
    const m = (href || '').match(/[?&]c=([^&]+)/);
    if (!m) return null;
    const c = decodeURIComponent(m[1]);
    if (c === 'naver.search.pc.sv' || c === 'mnaver.search.sv') return 'SEARCHING_VIEW';
    if (c === 'mnaver.search.newproduct') return 'NEW_PRODUCT';
    return null;
  };

  const extractAdId = (a) => {
    const onclick = a.getAttribute('onclick') || '';
    // Current format: i=nad-a001-04-000000537550529
    let m = onclick.match(/[?&]i=(nad-[A-Za-z0-9_-]+)/);
    if (m) return m[1];
    // Legacy format: i=SC1234567
    m = onclick.match(/[?&]i=(SC\d+)/);
    if (m) return m[1];
    return null;
  };

  const truncate = (s, n) => (s && s.length > n) ? s.slice(0, n) : s;

  // === 1) NP card path ===========================================
  const npWraps = document.querySelectorAll('.new_product_wrap');
  for (const wrap of npWraps) {
    // Mobile NP renders as .new_product_wrap > .flick_container > .flick_item.
    // Each .flick_item is one ad card. The carousel duplicates each card for
    // infinite scrolling — duplicates share the same ad_id so the dedup map
    // collapses them naturally.
    const cards = wrap.querySelectorAll('.flick_item');
    for (const card of cards) {
      const infoArea = card.querySelector('.info_area');
      if (!infoArea) continue;

      // The primary ader link is the anchor wrapping `.info_area`. It carries
      // the canonical destination URL we follow to resolve the advertiser
      // host. Fall back to any ader link inside the card if needed.
      const infoLink = infoArea.querySelector('a[href*="ader.naver.com"]')
        || infoArea.closest('a[href*="ader.naver.com"]');
      const cardLinks = card.querySelectorAll('a[href*="ader.naver.com"]');
      const primaryLink = infoLink || cardLinks[0] || null;
      if (!primaryLink) continue;

      const product = productFromHref(primaryLink.href);
      if (product !== 'NEW_PRODUCT') continue;

      // Mark ALL ader links inside this card as consumed so the link-scan
      // path below doesn't double-count thumbnail / "상세보기" / action button.
      for (const l of cardLinks) consumedLinks.add(l);

      // display_name: brand headline from `.info_area strong.tit`. We scope
      // to `.info_area` deliberately — the `.direct_link_area` of every NP
      // card has its own `strong.tit` containing the label "신제품소개"
      // which must NOT be used as the ad's display name.
      const titEl = infoArea.querySelector('strong.tit')
        || infoArea.querySelector('.tit');
      let displayName = titEl ? (titEl.textContent || '').trim() : '';
      if (!displayName || displayName === '신제품소개') {
        // Defensive — if for some reason we picked up the label or empty,
        // skip this card so we never emit a placement with a junk title.
        continue;
      }
      displayName = truncate(displayName, 100);

      const subEl = infoArea.querySelector('.sub_tit, em.sub_tit');
      let subTitle = subEl ? (subEl.textContent || '').trim() : null;
      if (!subTitle) subTitle = null; else subTitle = truncate(subTitle, 200);

      const descEls = infoArea.querySelectorAll('.desc');
      let description = null;
      if (descEls.length) {
        description = Array.from(descEls)
          .map(e => (e.textContent || '').trim())
          .filter(s => s)
          .join(' ');
        description = description ? truncate(description, 400) : null;
      }

      const adId = extractAdId(primaryLink);
      // Card-level dedup key: real ad_id if available, otherwise fingerprint
      // by visible content (subtitle + brand title). The fingerprint collapses
      // carousel duplicates even when Naver removes the placement id entirely.
      const key = adId
        ? ('NP::' + adId)
        : ('NP-fp::' + (subTitle || '') + '::' + displayName);

      if (!placements.has(key)) {
        placements.set(key, {
          product: 'NEW_PRODUCT',
          ad_id: adId || ('fp-' + key.slice(0, 40)),
          display_name: displayName,
          sub_title: subTitle,
          description: description,
          destination_url: primaryLink.href,
        });
      }
    }
  }

  // === 2) SV + fallback link path ================================
  const aders = document.querySelectorAll('a[href*="ader.naver.com"]');
  for (const a of aders) {
    if (consumedLinks.has(a)) continue;  // already captured by card path

    const product = productFromHref(a.href);
    if (product !== 'SEARCHING_VIEW' && product !== 'NEW_PRODUCT') continue;

    // Defense: a stray NP-tagged link OUTSIDE .new_product_wrap is usually
    // a "related brand" widget reusing the c-param. We never count those.
    if (product === 'NEW_PRODUCT' && !a.closest('.new_product_wrap')) continue;

    const adId = extractAdId(a);

    // Per-card scoped title: walk up until the smallest ancestor with
    // exactly one matching tit element. Returning the first match in a
    // multi-tit ancestor (the old behaviour) was the original source of
    // wrong-brand assignments — refuse rather than pick.
    let card = a;
    let titEl = null;
    const titSelector = 'strong.tit, .info_area strong, .info_area .tit, a.sub_title';
    for (let i = 0; i < 10 && card; i++) {
      const matches = card.querySelectorAll(titSelector);
      if (matches.length === 1) { titEl = matches[0]; break; }
      if (matches.length > 1) { card = null; break; }
      card = card.parentElement;
    }
    let displayName = titEl ? (titEl.textContent || '').trim() : '';

    if (!displayName) {
      const txt = (a.textContent || '').trim();
      if (!/^(상세보기|보험료계산|이벤트가입|간편계산|즉시가입가능|보장내용확인|혜택보기|상품안내|가입하기|할인받기|문의하기|.{0,2}$)$/.test(txt)) {
        displayName = txt;
      }
    }
    if (!displayName) continue;
    displayName = truncate(displayName, 100);

    // SV does NOT have NP-style sub_tit / desc; leave them null.
    const key = adId
      ? (product + '::' + adId)
      : (product + '-href::' + a.href.slice(0, 80));

    if (!placements.has(key)) {
      placements.set(key, {
        product,
        ad_id: adId || ('href-' + key.slice(0, 40)),
        display_name: displayName,
        sub_title: null,
        description: null,
        destination_url: a.href,
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
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # ── Bot-block detection ──────────────────────────────────
                # Naver returns 403 OR a 200-with-interstitial when the IP/UA
                # is flagged. Either signal is a stop-the-world event: we MUST
                # abort the whole BAT or the block escalates.
                status = response.status if response is not None else 0
                if status >= 400:
                    raise NaverBlockedError(
                        f"HTTP {status} on {url[:120]} — Naver appears to be blocking this IP"
                    )
                # 200 OK but interstitial body? Scan the text.
                try:
                    body_text = page.evaluate("() => document.body && document.body.innerText || ''")
                except Exception:
                    body_text = ""
                if body_text and any(m in body_text for m in _BLOCK_MARKERS):
                    raise NaverBlockedError(
                        f"검색 제한 페이지 감지 ({url[:120]}) — IP 차단 가능성"
                    )
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
        except NaverBlockedError:
            # IP block is a stop-the-world event — do NOT retry, do NOT swallow.
            # Propagate up so brand_scrape aborts the cycle.
            raise
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


# Single-cycle strategy (2026-06-26): the 3-cycle BAT was retired after Naver
# IP-blocked the operator's network during a back-to-back cycle 1→2→3 run.
# Recovery: one cycle only, fetch count stays at 4 per KG (tested optimum),
# but inter-fetch wait is doubled below to spread rotation observation across
# more seconds. Across the round we now do 4 × 1 = 4 fetches per KG instead
# of the old 4 × 3 = 12, reducing total Naver requests by 67%.
# Misses are caught by:
#   1) bid-aware retry inside _process_one_kg (winning_bid > 0 + 0 caught)
#   2) post-scrape sweep (detected > caught)
#   3) dawn reset (KST 03-09 0-caught → NULL on next BAT start)
#   4) operator re-runs the BAT if needed (manual)
_NP_RETRIES = 4
_SV_RETRIES = 1

# Unconditional 0-empty retry removed: it cost ~30s per KG on the 80% of
# KGs that legitimately have no running ad. Hydration misses on bid=0 KGs
# are rare enough to let the next cycle pick them up.
_NP_ZERO_RETRY_COUNT = 0
_NP_ZERO_RETRY_PAUSE_SECONDS = 0.0
_NP_ZERO_RETRY_JITTER_SECONDS = 0.0


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
            # Inter-fetch jittered pause — disguise burst pattern AND let
            # Naver's ad-rotation move on between observations so we get
            # better coverage of the rotating advertiser set.
            # 2026-06-26: increased from (0.8s + 0.7) → (2.0s + 1.5s, avg 2.75s)
            # to give carousel rotation more time to surface alternative
            # advertisers between observation passes. Trade-off: per-KG
            # latency +6s, but recovers some of the recall lost when the
            # 3-cycle BAT was retired.
            if num > 1 and i < num - 1:
                time.sleep(2.0 + random.uniform(0, 1.5))
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
