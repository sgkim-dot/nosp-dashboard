@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title NOSP Brand Crawling (3-cycle, auto-retry)
cd /d "C:\Users\MADUP\Documents\SearchingviewNewProduct\worker"

echo ============================================================
echo   NOSP Brand Crawling   (3-cycle convergence + auto-retry)
echo ============================================================
echo.
echo   - 3 cycles back-to-back
echo   - Cycle 1: --resume (incremental, 24h skip)
echo   - Cycle 2: --full   (re-scrape all active to cover misses)
echo   - Cycle 3: --full   (final convergence pass)
echo   - Reconcile after each cycle
echo   - Auto-retry: if Python crashes, BAT waits 10s and resumes
echo                 (max 5 attempts per cycle, then moves on)
echo.
echo   - Safe to stop: completed KGs are saved per-KG.
echo   - Look for "all cycles done" at the very end.
echo.
echo ============================================================
echo.

set CYCLE_NUM=1
set RETRY=0
:cycle1
echo === Cycle 1/3 attempt %RETRY% (resume) ===
uv run python -m worker.jobs.brand_scrape --resume
if errorlevel 1 (
    set /a RETRY+=1
    if %RETRY% lss 5 (
        echo --- cycle 1 crashed, retry in 10s ---
        timeout /t 10 /nobreak >nul
        goto cycle1
    )
    echo --- cycle 1 hit max retries, moving on ---
)
echo --- Reconcile cycle 1 ---
uv run python scripts/reconcile_brands.py --apply

set RETRY=0
:cycle2
echo === Cycle 2/3 attempt %RETRY% (full) ===
uv run python -m worker.jobs.brand_scrape --full
if errorlevel 1 (
    set /a RETRY+=1
    if %RETRY% lss 5 (
        echo --- cycle 2 crashed, retry in 10s ---
        timeout /t 10 /nobreak >nul
        goto cycle2
    )
    echo --- cycle 2 hit max retries, moving on ---
)
echo --- Reconcile cycle 2 ---
uv run python scripts/reconcile_brands.py --apply

set RETRY=0
:cycle3
echo === Cycle 3/3 attempt %RETRY% (full) ===
uv run python -m worker.jobs.brand_scrape --full
if errorlevel 1 (
    set /a RETRY+=1
    if %RETRY% lss 5 (
        echo --- cycle 3 crashed, retry in 10s ---
        timeout /t 10 /nobreak >nul
        goto cycle3
    )
    echo --- cycle 3 hit max retries, moving on ---
)
echo --- Reconcile cycle 3 ---
uv run python scripts/reconcile_brands.py --apply

echo.
echo ============================================================
echo   all cycles done!  Press any key to close.
echo ============================================================
pause
