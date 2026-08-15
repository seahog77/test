# Daily portfolio Telegram report (KST 10:00 & 15:00)

You are a Cloud Agent. Run the daily portfolio pipeline and persist Excel updates.

## Workbooks
- MAIN: `investment_0815.xlsx`
- W: `investment_0723_W.xlsx` (unchanged name)

## Steps
1. Ensure deps: `pip install -q openpyxl pandas yfinance requests python-dotenv finance-datareader`
2. From `My_investment/`, run:
   `python -X utf8 daily_portfolio_report.py --top 20`
3. Commit and push any changed files under `My_investment/` (xlsx, json). Do **not** create a PR unless asked.
4. Never commit `.env`. Use dashboard secrets / existing ignored `.env` for Telegram.
5. If the script fails, still try to send a short Telegram error (the script does this automatically when tokens exist). Reply with a short Korean summary of success/failure.

## Expected Telegram messages
- Portfolio summary (MAIN + W)
- US buy-signal TOP20 (technical + EPS/PER/PBR/revenue & earnings growth)
- KR buy-signal TOP20 (same fundamental-aware ranking)
- Market news summary
