"""Deeper inspection of SV brand_wrap + NP brand cards."""
from playwright.sync_api import sync_playwright
import json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

INSPECT_JS = r"""
() => {
  const out = {};

  // SV — dump ALL elements with class containing brand/title/name
  const sv = document.querySelector('.searching_view');
  if (sv) {
    out.sv_full = sv.outerHTML;
    // Find all links inside
    const links = sv.querySelectorAll('a');
    out.sv_all_links = Array.from(links).map(a => ({
      cls: a.className,
      text: (a.textContent || '').trim().slice(0, 100),
      href: (a.href || '').slice(0, 100),
    }));
    // Find images (brand logos)
    const imgs = sv.querySelectorAll('img');
    out.sv_imgs = Array.from(imgs).map(img => ({
      alt: img.alt,
      src: (img.src || '').slice(0, 100),
      cls: img.className,
    }));
  }

  // NP — find the brand-콘텐츠 section, then list ALL elements that look like brand cards
  const sections = document.querySelectorAll('div[class*="sc_new"]');
  for (const s of sections) {
    const h = s.querySelector('h2, h3, [class*="title"]');
    if (h && h.textContent && h.textContent.includes('브랜드 콘텐츠')) {
      out.np_section = s.outerHTML;
      // Try to find brand cards
      // Possible selectors
      const candidates = {
        'sds-profile-type-basic': s.querySelectorAll('[class*="sds-comps-profile"][class*="type-basic"]').length,
        'profile-info-title': s.querySelectorAll('[class*="profile-info-title"]').length,
        'fds-ugc-single-intention': s.querySelectorAll('[class*="fds-ugc-single-intention"]').length,
        'a_with_ader': s.querySelectorAll('a[href*="ader.naver.com"]').length,
        'sds-comps-profile-info': s.querySelectorAll('[class*="sds-comps-profile-info"]').length,
        'all_anchors': s.querySelectorAll('a').length,
      };
      out.np_card_counts = candidates;
      // Sample first 5 anchors
      const anchors = s.querySelectorAll('a');
      out.np_first_anchors = Array.from(anchors).slice(0, 10).map(a => ({
        cls: a.className.slice(0, 80),
        text: (a.textContent || '').trim().slice(0, 100),
        href: (a.href || '').slice(0, 150),
      }));
      break;
    }
  }

  return out;
};
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent=UA, locale="ko-KR")
    page = ctx.new_page()
    for kw in ["실비보험", "소파"]:
        page.goto(f"https://search.naver.com/search.naver?query={kw}", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2500)
        data = page.evaluate(INSPECT_JS)
        print(f"\n========== {kw} ==========")
        if 'sv_full' in data:
            print("\n--- SV brand_wrap ---")
            print(f"SV all links: {len(data.get('sv_all_links', []))}")
            for a in data.get('sv_all_links', [])[:15]:
                print(f"  cls={a['cls']!r} text={a['text']!r} href={a['href']!r}")
            print(f"SV imgs: {len(data.get('sv_imgs', []))}")
            for img in data.get('sv_imgs', [])[:8]:
                print(f"  alt={img['alt']!r} cls={img['cls']!r}")
            # Print first 6000 chars of SV outer to find brand name structure
            print("\n--- SV outer HTML (first 6000 chars) ---")
            print(data['sv_full'][:6000])

        print(f"\n--- NP card counts: {data.get('np_card_counts')}")
        print("--- NP first anchors ---")
        for a in data.get('np_first_anchors', []):
            print(f"  cls={a['cls']!r}")
            print(f"    text={a['text']!r}")
            print(f"    href={a['href']!r}")
        if 'np_section' in data and kw == "소파":
            # For 소파, dump the full NP section to find brand card structure
            print("\n--- NP section (first 8000 chars) ---")
            print(data['np_section'][:8000])
    ctx.close()
    browser.close()
