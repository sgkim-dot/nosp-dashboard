@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title NOSP Brand Crawling (3-cycle)
cd /d "C:\Users\MADUP\Documents\SearchingviewNewProduct\worker"

echo ============================================================
echo   NOSP Brand Crawling   (3-cycle convergence)
echo ============================================================
echo.
echo   - 3 cycles back-to-back, each ~14h
echo   - Cycle 1: --resume (incremental, 24h skip)
echo   - Cycle 2: --full   (re-scrape all active to cover misses)
echo   - Cycle 3: --full   (final convergence pass)
echo   - Reconcile + post-scrape sweep run after each cycle
echo.
echo   - Safe to stop mid-run: completed KGs are saved per-cycle.
echo   - Look for "all cycles done" at the very end.
echo.
echo ============================================================
echo.

echo === Cycle 1/3: incremental (--resume) ===
uv run python -m worker.jobs.brand_scrape --resume
echo.
echo --- Reconcile (cycle 1) ---
uv run python scripts/reconcile_brands.py --apply

echo.
echo === Cycle 2/3: full re-scrape (--full) ===
uv run python -m worker.jobs.brand_scrape --full
echo.
echo --- Reconcile (cycle 2) ---
uv run python scripts/reconcile_brands.py --apply

echo.
echo === Cycle 3/3: full re-scrape (--full) ===
uv run python -m worker.jobs.brand_scrape --full
echo.
echo --- Reconcile (cycle 3) ---
uv run python scripts/reconcile_brands.py --apply

echo.
echo ============================================================
echo   all cycles done!  Press any key to close.
echo ============================================================
pause
