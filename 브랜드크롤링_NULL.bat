@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title NOSP Brand Crawling — NULL-only sprint
cd /d "C:\Users\MADUP\Documents\SearchingviewNewProduct\worker"

echo ============================================================
echo   NOSP Brand Crawling   (NULL-only sprint)
echo ============================================================
echo.
echo   - brands_scraped_at IS NULL 인 KG 만 처리
echo   - 데드라인 sprint용 (월요일 새 회차 전 마무리)
echo   - 24h 이상 된 KG 는 어제 BAT 결과 그대로 둔다
echo.
echo ============================================================
echo.

uv run python -m worker.jobs.brand_scrape --null-only

echo.
echo ============================================================
echo   Reconciling brand mappings (auto-cleanup)...
echo ============================================================
echo.
uv run python scripts/reconcile_brands.py --apply

echo.
echo ============================================================
echo   NULL sprint finished!  Press any key to close.
echo ============================================================
pause
