@echo off

chcp 65001 >nul

cd /d "%~dp0"

echo [investment_update] investment_dividend.xlsx 갱신...

echo.



if exist "%~dp0investment_update.exe" (

    "%~dp0investment_update.exe" %*

    exit /b %ERRORLEVEL%

)



where python >nul 2>&1

if errorlevel 1 (

    echo Python이 없고 investment_update.exe 도 없습니다.

    echo build_investment_update_exe.bat 로 exe를 만든 뒤 다시 실행하세요.

    pause

    exit /b 1

)



python run_investment_update.py %*

set RC=%ERRORLEVEL%

echo.

if not %RC%==0 pause

exit /b %RC%

