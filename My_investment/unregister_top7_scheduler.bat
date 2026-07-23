@echo off
REM TOP7 자동매매 — Windows 작업 스케줄러 해제

chcp 65001 >nul

echo TOP7 작업 스케줄러 해제 중...

schtasks /Delete /TN "TOP7-Trader-Morning" /F 2>nul
if %ERRORLEVEL%==0 (echo [OK] TOP7-Trader-Morning 삭제) else (echo [--] TOP7-Trader-Morning 없음)

schtasks /Delete /TN "TOP7-Trader-Afternoon" /F 2>nul
if %ERRORLEVEL%==0 (echo [OK] TOP7-Trader-Afternoon 삭제) else (echo [--] TOP7-Trader-Afternoon 없음)

echo.
echo 완료.
pause
