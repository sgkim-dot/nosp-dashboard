@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title NOSP Brand Crawling
cd /d "C:\Users\MADUP\Documents\SearchingviewNewProduct\worker"

echo ============================================================
echo   NOSP Brand Crawling - single cycle, anti-block
echo ============================================================
echo.
echo   - 1 cycle resume mode, skips KGs scraped within 24h
echo   - Slower cadence: ~11s pause between KGs, ~22-26h total
echo   - High-bid retry: 25s pause on 0-result for bid greater than 1M
echo   - Auto-stop on Naver IP-block (exit code 4, no retry)
echo   - Auto-retry on crash codes 1/2/3 up to 5 times
echo.
echo   If you see exit code 4 STOP message:
echo     1. Open m.naver.com in browser
echo     2. Click 'block release' and solve CAPTCHA
echo     3. Wait 30-60 min before re-running
echo.
echo ============================================================
echo.

set RETRY=0
:cycle
echo === Brand crawl attempt %RETRY% ===
uv run python -m worker.jobs.brand_scrape --resume
set EXITCODE=%errorlevel%

if %EXITCODE% EQU 4 (
    echo.
    echo ============================================================
    echo   [STOP] Naver IP-block detected. BAT aborted.
    echo   Clear the block on m.naver.com before re-running.
    echo ============================================================
    pause
    exit /b 4
)

if %EXITCODE% NEQ 0 (
    set /a RETRY+=1
    if %RETRY% lss 5 (
        echo --- crashed exit=%EXITCODE%, retry in 10s ---
        timeout /t 10 /nobreak >nul
        goto cycle
    )
    echo --- hit max retries, moving on to reconcile ---
)

echo --- Reconcile ---
uv run python scripts/reconcile_brands.py --apply

echo.
echo ============================================================
echo   cycle done!  Press any key to close.
echo ============================================================
pause
