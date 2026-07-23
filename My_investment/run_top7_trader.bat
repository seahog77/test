@echo off
REM TOP7 자동매매 실행 스크립트 (작업 스케줄러에서 호출)
REM 사용: run_top7_trader.bat [morning^|afternoon]
REM   morning   = 장 시작 후 (기본)
REM   afternoon = 장 마감 전
REM
REM 환경변수 TOP7_DRY_RUN=1 이면 시뮬레이션만 (실주문 없음)

chcp 65001 >nul
setlocal EnableDelayedExpansion

cd /d "%~dp0"

set MODE=%~1
if "%MODE%"=="" set MODE=morning

set LOGDIR=%~dp0logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%i
set LOGFILE=%LOGDIR%\top7_%MODE%_%STAMP%.log

echo ==================================================>> "%LOGFILE%"
echo  TOP7 Trader  %DATE% %TIME%  mode=%MODE%>> "%LOGFILE%"
echo ==================================================>> "%LOGFILE%"

REM Python 찾기 (py 런처 우선)
set PY_CMD=
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    set PY_CMD=py -3
) else (
    where python >nul 2>&1
    if !ERRORLEVEL!==0 (
        set PY_CMD=python
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python 을 찾을 수 없습니다.>> "%LOGFILE%"
    echo Python 을 찾을 수 없습니다.
    exit /b 1
)

echo Python: %PY_CMD%>> "%LOGFILE%"
echo CWD: %CD%>> "%LOGFILE%"

if /i "%TOP7_DRY_RUN%"=="1" (
    echo [DRY-RUN] top7_trader.py run>> "%LOGFILE%"
    %PY_CMD% top7_trader.py run>> "%LOGFILE%" 2>&1
) else (
    echo [EXECUTE] top7_trader.py run --execute>> "%LOGFILE%"
    %PY_CMD% top7_trader.py run --execute>> "%LOGFILE%" 2>&1
)

set RC=!ERRORLEVEL!
echo Exit code: !RC!>> "%LOGFILE%"
echo.>> "%LOGFILE%"

exit /b !RC!
