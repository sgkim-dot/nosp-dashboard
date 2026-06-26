"""다이어그램 SVG 를 PNG 로 변환.

vercel public/guide/*.svg 를 localhost:3100 으로 직접 로드해서 캡쳐.
"""
import time
import os
from browser_harness.helpers import js, capture_screenshot, cdp, goto_url

GUIDE = r"C:\Users\MADUP\Documents\SearchingviewNewProduct\apps\dashboard\public\guide"
BASE = "http://localhost:3100"

SVGS = [
    ("menu-map.svg", "menu-map.png", 900, 360),
    ("flow-bid-decision.svg", "flow-bid-decision.png", 1000, 580),
    ("terms-relation.svg", "terms-relation.png", 1000, 620),
]


def main() -> None:
    for src, dst, vw, vh in SVGS:
        url = f"{BASE}/guide/{src}"
        print(f"▶ {src} → {dst} ({vw}x{vh})")

        # viewport 사이즈 조정
        cdp("Emulation.setDeviceMetricsOverride",
            width=vw, height=vh, deviceScaleFactor=2, mobile=False)

        goto_url(url)
        time.sleep(1.0)

        # SVG 파일은 documentElement 가 곧 svg root. body 없음.
        # 흰 배경 + viewport fit 적용.
        js("""
            (() => {
                const svg = document.documentElement;
                if (svg && svg.tagName.toLowerCase() === 'svg') {
                    svg.setAttribute('width', '100%');
                    svg.setAttribute('height', '100%');
                    svg.style.background = '#ffffff';
                }
                return svg ? svg.tagName : 'no-root';
            })()
        """)
        time.sleep(0.3)

        capture_screenshot(os.path.join(GUIDE, dst), max_dim=max(vw, vh) * 2)
        print(f"  saved: {dst}")

    # viewport 복구
    cdp("Emulation.clearDeviceMetricsOverride")
    print("\nDone.")


main()
