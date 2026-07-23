@echo off
REM TOP7 자동매매 — Windows 작업 스케줄러 등록
REM 관리자 권한 없이 실행 가능 (현재 사용자 계정으로 등록)
REM
REM 등록되는 작업:
REM   TOP7-Trader-Morning    평일 09:05  장 시작 후 (익절매도·재매수)
REM   TOP7-Trader-Afternoon  평일 15:20  장중 손절·익절대기 체크
REM
REM 테스트(실주문 없음)로 등록하려면:
REM   set TOP7_DRY_RUN=1
REM   register_top7_scheduler.bat

chcp 65001 >nul
setlocal

set TASK_DIR=%~dp0
set RUN_BAT=%TASK_DIR%run_top7_trader.bat

if not exist "%RUN_BAT%" (
    echo [ERROR] run_top7_trader.bat 을 찾을 수 없습니다.
    exit /b 1
)

echo ============================================
echo  TOP7 자동매매 작업 스케줄러 등록
echo ============================================
echo.
echo  폴더: %TASK_DIR%
echo  실행: %RUN_BAT%
if /i "%TOP7_DRY_RUN%"=="1" (
    echo  모드: DRY-RUN ^(실주문 없음^)
) else (
    echo  모드: EXECUTE ^(실제 주문^)
    echo.
    echo  [주의] 실제 주문이 나갑니다. 테스트는 먼저:
    echo    set TOP7_DRY_RUN=1
    echo    register_top7_scheduler.bat
)
echo.

set /p CONFIRM=등록하시겠습니까? (Y/N): 
if /i not "%CONFIRM%"=="Y" (
    echo 취소되었습니다.
    exit /b 0
)

REM 기존 작업 삭제 후 재등록
schtasks /Delete /TN "TOP7-Trader-Morning" /F >nul 2>&1
schtasks /Delete /TN "TOP7-Trader-Afternoon" /F >nul 2>&1

REM 장 시작 후 — 월~금 09:05
schtasks /Create ^
    /TN "TOP7-Trader-Morning" ^
    /TR "\"%RUN_BAT%\" morning" ^
    /SC WEEKLY ^
    /D MON,TUE,WED,THU,FRI ^
    /ST 09:05 ^
    /RL LIMITED ^
    /F

if %ERRORLEVEL% neq 0 (
    echo [ERROR] TOP7-Trader-Morning 등록 실패
    exit /b 1
)
echo [OK] TOP7-Trader-Morning  등록 완료  (평일 09:05)

REM 장 마감 전 — 월~금 15:20
schtasks /Create ^
    /TN "TOP7-Trader-Afternoon" ^
    /TR "\"%RUN_BAT%\" afternoon" ^
    /SC WEEKLY ^
    /D MON,TUE,WED,THU,FRI ^
    /ST 15:20 ^
    /RL LIMITED ^
    /F

if %ERRORLEVEL% neq 0 (
    echo [ERROR] TOP7-Trader-Afternoon 등록 실패
    exit /b 1
)
echo [OK] TOP7-Trader-Afternoon 등록 완료  (평일 15:20)

echo.
echo ============================================
echo  등록 완료
echo ============================================
echo.
echo  확인:  schtasks /Query /TN "TOP7-Trader-Morning"
echo          schtasks /Query /TN "TOP7-Trader-Afternoon"
echo.
echo  수동 실행 테스트:
echo    "%RUN_BAT%" morning
echo.
echo  로그 폴더: %TASK_DIR%logs\
echo  해제:      unregister_top7_scheduler.bat
echo.

endlocal
exit /b 0
