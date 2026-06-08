@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title NOSP Brand Crawling
cd /d "C:\Users\MADUP\Documents\SearchingviewNewProduct\worker"

echo ============================================================
echo   NOSP Brand Crawling   (resume-safe)
echo ============================================================
echo.
echo   - Safe to stop mid-run and resume later (within 24h).
echo     Closing this window (X) is OK — completed KGs are saved.
echo   - On next launch, --resume skips already-done KGs and
echo     picks up exactly where you left off.
echo   - Look for the message  brand scrape done  when finished.
echo.
echo ============================================================
echo.

uv run python -m worker.jobs.brand_scrape --resume

echo.
echo ============================================================
echo   Reconciling brand mappings (auto-cleanup)...
echo ============================================================
echo.
uv run python scripts/reconcile_brands.py --apply

echo.
echo ============================================================
echo   Crawl finished!  Press any key to close.
echo ============================================================
pause