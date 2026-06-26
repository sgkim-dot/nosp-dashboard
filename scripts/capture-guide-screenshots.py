"""대시보드 가이드용 스크린샷 자동 캡쳐 (11장).

실행:
    uv run --project "C:/Users/MADUP/Developer/browser-harness" python scripts/capture-guide-screenshots.py

전제:
    - localhost:3100 dev 서버 실행 중 (PM2)
    - 사용자 Chrome 에 dashboard 로그인 세션 유지

캡쳐 산출물: apps/dashboard/public/guide/*.png
"""
import time
import os
from browser_harness.helpers import (
    js, click_at_xy, capture_screenshot, cdp, goto_url,
)

GUIDE = r"C:\Users\MADUP\Documents\SearchingviewNewProduct\apps\dashboard\public\guide"
BASE = "http://localhost:3100"

os.makedirs(GUIDE, exist_ok=True)


def wait(sec: float = 1.5) -> None:
    time.sleep(sec)


def hide_admin_menu() -> None:
    """사이드바의 '관리자' 헤더와 그 아래 MaintenanceMenu 를 숨긴다."""
    js("""
        (() => {
            const headers = Array.from(document.querySelectorAll('aside div'));
            for (const h of headers) {
                const t = (h.textContent || '').trim();
                if (t === '관리자') {
                    h.style.display = 'none';
                    let n = h.nextElementSibling;
                    while (n) { n.style.display = 'none'; n = n.nextElementSibling; }
                    return 'hidden';
                }
            }
            return 'no-admin-header';
        })()
    """)


def shot(name: str) -> None:
    path = os.path.join(GUIDE, name)
    capture_screenshot(path, max_dim=1600)
    print(f"  ✓ {name}")


def main() -> None:
    print("▶ Step 1: 메인 페이지 + 사이드바 (KG 미선택)")
    goto_url(f"{BASE}/")
    wait(2.5)
    hide_admin_menu()
    wait(0.3)
    shot("sidebar.png")
    shot("bid-overview-empty.png")

    print("▶ Step 2: 빠른 검색 자동완성 동작")
    js("""
        (() => {
            const i = document.querySelector('input[placeholder*="키워드그룹 검색"]');
            if (i) { i.focus(); i.click(); }
        })()
    """)
    wait(0.5)
    js("""
        (() => {
            const i = document.querySelector('input[placeholder*="키워드그룹 검색"]');
            if (!i) return 'no-input';
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(i, '보험');
            i.dispatchEvent(new Event('input', { bubbles: true }));
            return 'typed';
        })()
    """)
    wait(0.8)
    shot("quick-search.png")

    print("▶ Step 3: 자동완성 첫 결과 클릭 → KG 선택")
    clicked = js("""
        (() => {
            const btns = Array.from(document.querySelectorAll('ul li button'));
            if (btns.length > 0) { btns[0].click(); return btns.length; }
            return 0;
        })()
    """)
    print(f"  자동완성 결과 수: {clicked}")
    if not clicked:
        # fallback: 빈 검색 → 모든 KG → 첫 결과
        js("""
            (() => {
                const i = document.querySelector('input[placeholder*="키워드그룹 검색"]');
                if (!i) return;
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(i, '');
                i.dispatchEvent(new Event('input', { bubbles: true }));
                i.focus();
            })()
        """)
        wait(0.8)
        clicked = js("""
            (() => {
                const btns = Array.from(document.querySelectorAll('ul li button'));
                if (btns.length > 0) { btns[0].click(); return btns.length; }
                return 0;
            })()
        """)
        print(f"  fallback 결과 수: {clicked}")

    wait(3.5)  # KG 데이터 로드 대기
    hide_admin_menu()  # 페이지 이동 후 다시 숨기기
    wait(0.3)

    print("▶ Step 4: KG 선택 후 전체 화면")
    shot("bid-overview.png")

    print("▶ Step 5: 추천 입찰가 카드 영역 클로즈업 (스크롤 0 위치)")
    js("window.scrollTo(0, 0)")
    wait(0.5)
    shot("recommend-card.png")

    print("▶ Step 6: 회차 테이블 영역 (스크롤)")
    js("""
        (() => {
            const t = document.querySelector('table');
            if (t) t.scrollIntoView({ block: 'start' });
        })()
    """)
    wait(0.8)
    shot("round-table.png")
    shot("download.png")  # 같은 뷰 — 우상단 다운로드 버튼 보임

    print("▶ Step 7: 회차 첫 행 클릭 → 상세 모달")
    js("""
        (() => {
            const rows = document.querySelectorAll('tbody tr');
            if (rows.length > 0) rows[0].click();
        })()
    """)
    wait(1.5)
    shot("round-detail.png")

    print("▶ Step 8: 모달 닫기 + 차트 영역 캡쳐")
    cdp('Input.dispatchKeyEvent', type='keyDown', key='Escape', code='Escape', windowsVirtualKeyCode=27)
    wait(0.3)
    cdp('Input.dispatchKeyEvent', type='keyUp', key='Escape', code='Escape', windowsVirtualKeyCode=27)
    wait(0.8)
    # 차트는 xl 화면에서 우측 sticky. 메인 영역 스크롤 위로.
    js("window.scrollTo(0, 0)")
    wait(0.5)
    shot("trend-chart.png")

    print("▶ Step 9: 브랜드 점유 페이지")
    goto_url(f"{BASE}/brand")
    wait(3.5)
    hide_admin_menu()
    wait(0.3)
    shot("brand-heatmap.png")

    print("▶ Step 10: 브랜드 추적 페이지")
    goto_url(f"{BASE}/brand-tracker")
    wait(3.5)
    hide_admin_menu()
    wait(0.3)
    # 좌측 첫 브랜드 행 클릭 — aside 밖, 좌측 패널 안의 첫 button
    label = js("""
        (() => {
            const all = document.querySelectorAll('button');
            for (const b of all) {
                if (b.closest('aside')) continue;
                if (b.offsetWidth < 200 || b.offsetWidth > 400) continue;
                if (!(b.textContent || '').trim()) continue;
                b.click();
                return (b.textContent || '').trim().slice(0, 40);
            }
            return null;
        })()
    """)
    print(f"  좌측 브랜드 클릭: {label}")
    wait(2)
    shot("brand-tracker.png")

    print("▶ Step 11: 로그인 화면")
    # Clerk dev: /sign-in 직접 이동 — 로그인된 사용자도 일단 한 번은 페이지 보임
    # 보장은 안 됨. logged in 이면 redirect 됨. 그땐 사용자가 직접 캡쳐하도록 지시.
    goto_url(f"{BASE}/sign-in")
    wait(3.0)
    cur = js("(() => location.pathname)()")
    if "/sign-in" in cur:
        shot("login.png")
    else:
        print(f"  ⚠ sign-in 이 {cur} 로 redirect 됨 → login.png 는 사용자 직접 캡쳐 필요")

    print("\n✅ 캡쳐 완료")
    # 파일 목록
    for f in sorted(os.listdir(GUIDE)):
        size = os.path.getsize(os.path.join(GUIDE, f)) // 1024
        print(f"  {f} ({size} KB)")


main()
