@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo PyInstaller로 investment_update.exe 빌드 중...
echo (최초 1회: pip install pyinstaller)
echo.

pip install pyinstaller openpyxl pandas yfinance requests -q
if errorlevel 1 (
    echo pip 설치 실패. Python/pip 환경을 확인하세요.
    pause
    exit /b 1
)

python -m PyInstaller --noconfirm --clean ^
  --onefile ^
  --windowed ^
  --name investment_update ^
  --hidden-import=update_prices ^
  --hidden-import=add_monthly_dividend_tab ^
  --hidden-import=app_paths ^
  --hidden-import=update_amount_auto ^
  --collect-all tkinter ^
  --collect-submodules=yfinance ^
  --collect-submodules=pandas ^
  run_investment_update.py

if errorlevel 1 (
    echo 빌드 실패.
    pause
    exit /b 1
)

copy /Y "dist\investment_update.exe" "investment_update.exe" >nul
echo.
echo 완료: %~dp0investment_update.exe
echo.
echo 사용법: exe와 investment_dividend.xlsx 를 같은 폴더에 두고 exe 실행
echo        (엑셀 파일은 반드시 닫은 상태)
echo.
pause
