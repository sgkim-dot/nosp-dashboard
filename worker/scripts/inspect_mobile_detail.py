"""Dump full inner HTML of SV/NP sections on mobile for 운전자보험 to design selectors."""
from playwright.sync_api import sync_playwright

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

JS = r"""
() => {
  const out = {};
  // SV section: class contains "sp_brand" (브랜드검색)
  const sv = document.querySelector('[class*="sp_brand"]');
  if (sv) {
    out.sv_outer = sv.outerHTML;
    out.sv_class = sv.className;
  }
  // NP section: class contains "new_product_wrap"
  const np = document.querySelector('[class*="new_product_wrap"]');
  if (np) {
    out.np_outer = np.outerHTML;
    out.np_class = np.className;
  }
  // Also dump every section with [AD] indicator that we might have missed
  const ad_sections = [];
  document.querySelectorAll('section, div').forEach(d => {
    const cls = d.className || '';
    if (typeof cls !== 'string') return;
    // Look for likely ad-section root classes
    if (/(sp_brand|new_product|brand_wrap|sp_ad|sa_brand|sa_new_product)/.test(cls)) {
      ad_sections.push({
        cls: cls.slice(0, 120),
        tag: d.tagName,
        text_first_120: (d.innerText || '').slice(0, 120),
      });
    }
  });
  out.candidate_classes = ad_sections;
  return out;
};
"""


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent=MOBILE_UA, locale="ko-KR",
        viewport={"width": 390, "height": 844},
        device_scale_factor=2, is_mobile=True, has_touch=True,
    )
    page = ctx.new_page()
    page.goto("https://m.search.naver.com/search.naver?query=운전자보험", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(3000)
    page.evaluate("window.scrollBy(0, 500)")
    page.wait_for_timeout(1500)
    data = page.evaluate(JS)
    print("=== Candidate classes ===")
    for c in data.get("candidate_classes", []):
        print(f"  {c['tag']} cls={c['cls']!r}")
        print(f"    text={c['text_first_120']!r}")
    print(f"\n\n=== SV class: {data.get('sv_class')!r} ===")
    print(f"=== SV outer (8000 chars) ===")
    print((data.get("sv_outer") or "")[:8000])
    print(f"\n\n=== NP class: {data.get('np_class')!r} ===")
    print(f"=== NP outer (8000 chars) ===")
    print((data.get("np_outer") or "")[:8000])
    ctx.close()
    browser.close()
