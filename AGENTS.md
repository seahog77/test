# AGENTS.md

## Cursor Cloud specific instructions

### What this repo is
A single Python CLI toolkit lives in `My_investment/` (Korean/US stock-investment automation).
There is no web server, database, container, or frontend — everything is standalone Python
scripts plus Excel workbooks (`investment_*.xlsx`) and CSV/JSON data files. The Windows
`*.bat` / `*.spec` / `build_*_exe.bat` files are for PyInstaller packaging on Windows and are
not used on Linux.

### Dependencies (handled by the startup update script)
- Python deps come from `My_investment/requirements-toss.txt`, **plus `openpyxl`**, which is
  required by the Excel scripts but is missing from that requirements file (see
  `My_investment/AUTOMATION.md`, which installs `openpyxl` explicitly). The update script
  installs both.
- `pip install` resolves to a user-site install (`~/.local`) on this VM; no venv is used.

### Run / test / build
- Canonical run command and flags are documented in `My_investment/AUTOMATION.md` and
  `My_investment/AUTOMATION_PROMPT.md`. Primary pipeline (run from `My_investment/`):
  `python -X utf8 daily_portfolio_report.py --top 20`.
- There is **no lint config and no automated test suite** (no pytest/ruff/flake8/pyproject).
  "Build" only exists as Windows PyInstaller specs, which are irrelevant on Linux.

### Non-obvious gotchas
- `daily_portfolio_report.py` and the `send_*_telegram.py` scripts **send real Telegram
  messages** and `update_prices.py` / `update_amount_auto.py` **overwrite the tracked
  `investment_*.xlsx` workbooks**. For safe testing use `send_portfolio_telegram.py --dry-run`
  and the pipeline's `--skip-update` / `--skip-portfolio` / `--skip-signals` / `--skip-news`
  flags.
- Telegram is configured via the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets (already
  injected as env vars). Scripts also read a git-ignored `My_investment/.env`; env vars take
  precedence over that file. Toss Open-API keys are optional and only needed for live account
  queries / order placement (`toss_app.py`, `top7_trader.py --execute`).
- Running `send_portfolio_telegram.py --refresh` or `_analyze_combined_portfolio.py`
  **overwrites the tracked `My_investment/_portfolio_analysis.json`**; `git checkout --` it
  afterwards if the regeneration was only for testing.
- Market data: KR prices come from Naver, US/FX from `yfinance`/Yahoo and KRX listings from
  FinanceDataReader — all require outbound network. A raw `curl` to Yahoo may return HTTP 429,
  but the `yfinance` client still fetches successfully.
