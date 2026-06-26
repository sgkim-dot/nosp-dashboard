@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title NOSP Brand Crawling (single-cycle, anti-block)
cd /d "C:\Users\MADUP\Documents\SearchingviewNewProduct\worker"

echo ============================================================
echo   NOSP Brand Crawling   (single-cycle, anti-block)
echo ============================================================
echo.
echo   - 1 cycle only (--resume, 24h skip)
echo   - Per-KG pause: ~11.5s avg (anti-bot cadence)
echo   - Per-KG fetches: 4 (NP) / 1 (SV), inter-fetch ~2.75s
echo   - High-bid 0-result retry (25s) for KGs with winning_bid >= 1M
echo   - Naver IP-block detection: aborts cycle, exit code 4
echo   - Auto-retry: if Python crashes (codes 1/2/3), BAT waits 10s
echo                 and resumes (max 5 attempts). Exit 4 = block, NO retry.
echo.
echo   - Safe to stop: completed KGs are saved per-KG.
echo   - Look for "cycle done" at the very end.
echo   - Expected wall-clock: ~22-26 hours for a full ~2,700 KG round.
echo.
echo   - If exit code 4: clear Naver IP block manually
echo     1) Open browser → https://m.naver.com
echo     2) Click the "제한 해제" button + solve CAPTCHA
echo     3) Wait 30-60 min before re-running this BAT
echo.
echo ============================================================
echo.

set RETRY=0
:cycle
echo === Brand crawl attempt %RETRY% (resume) ===
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
        echo --- crashed (exit %EXITCODE%), retry in 10s ---
        timeout /t 10 /nobreak >nul
        goto cycle
    )
    echo --- hit max retries, moving on to reconcile ---
)
echo --- Reconcile ---
uv run python scripts/reconcile_brands.py --apply
rem No cleanup after the single cycle: any remaining __unverified__ rows are
rem permanently un-resolvable hosts; operator handles them in the dashboard.

echo.
echo ============================================================
echo   cycle done!  Press any key to close.
echo ============================================================
pause
