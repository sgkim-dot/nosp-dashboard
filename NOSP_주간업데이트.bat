@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title NOSP Weekly Update
cd /d "C:\Users\MADUP\Documents\SearchingviewNewProduct\worker"

echo ============================================================
echo   NOSP 주간 업데이트
echo ============================================================
echo.
echo   - 회차별 입찰가 / 낙찰가 CSV 4종 다운로드
echo   - DB 업데이트 (대시보드 자동 반영)
echo.
echo   첫 실행: 브라우저가 열리면 네이버 로그인 1회 필요
echo   이후 실행: 저장된 세션으로 자동 처리
echo.
echo ------------------------------------------------------------

uv run python scripts/nosp_download.py
if errorlevel 1 (
    echo.
    echo [WARN] 다운로드 또는 업데이트 중 오류. 아무 키나 누르면 종료.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   완료! CSV 다운로드 + DB 업데이트 끝.
echo   대시보드를 새로고침하면 새 데이터가 보입니다.
echo ============================================================
pause
