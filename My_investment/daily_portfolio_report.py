# -*- coding: utf-8 -*-
"""
매일 포트폴리오 리포트 파이프라인

1) investment_0831.xlsx / investment_0723_W.xlsx 시세·금액순·배당 갱신
2) 통합 포트폴리오 분석 → 텔레그램
3) 미국/한국 매수신호 TOP10 → 텔레그램
4) 주요 경제뉴스 → 텔레그램

사용:
  python daily_portfolio_report.py
  python daily_portfolio_report.py --skip-update   # 시세갱신 생략
  python daily_portfolio_report.py --top 10

시장별 추천은 최대 10개. --top 20이 와도 10개로 자른다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

from app_paths import app_dir, safe_reconfigure_stdio
from send_portfolio_telegram import load_dotenv, send_telegram

# send_buy_signals_telegram.BUY_SIGNAL_TOP_N 과 동일. 자동화 --top 20도 여기가 우선.
BUY_SIGNAL_TOP_N = 10


def resolve_top_n(requested: int) -> int:
    n = max(1, int(requested))
    if n > BUY_SIGNAL_TOP_N:
        print(f"매수신호 TOP{n} 요청 → TOP{BUY_SIGNAL_TOP_N}으로 제한", flush=True)
        return BUY_SIGNAL_TOP_N
    return n

safe_reconfigure_stdio()
BASE = app_dir()
MAIN_XLSX = BASE / "investment_0831.xlsx"
W_XLSX = BASE / "investment_0723_W.xlsx"


def run_step(title: str, argv: list[str]) -> None:
    print(f"\n===== {title} =====", flush=True)
    print(">", " ".join(argv), flush=True)
    subprocess.check_call(argv, cwd=str(BASE))


def update_workbooks(year: int) -> None:
    from add_monthly_dividend_tab import run_dividend_tab
    from update_amount_auto import update_amount_sheet
    from update_prices import update_workbook

    for path in (MAIN_XLSX, W_XLSX):
        if not path.exists():
            raise FileNotFoundError(f"엑셀 없음: {path}")
        print(f"\n===== UPDATE {path.name} =====", flush=True)
        update_workbook(path)
        update_amount_sheet(path)
        run_dividend_tab(path, year=year)
        print(f"DONE {path.name}", flush=True)


def notify_error(token: str, chat_id: str, err: str) -> None:
    if not token or not chat_id:
        return
    text = (
        f"포트폴리오 일일 리포트 실패 ({datetime.now():%Y-%m-%d %H:%M})\n\n"
        f"{err[:3500]}"
    )
    try:
        send_telegram(token, chat_id, text)
    except Exception as e:
        print(f"에러 알림 전송 실패: {e}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="일일 포트폴리오·신호·뉴스 텔레그램")
    ap.add_argument("--skip-update", action="store_true", help="엑셀 시세 갱신 생략")
    ap.add_argument("--skip-portfolio", action="store_true", help="포트폴리오 요약 생략")
    ap.add_argument("--skip-signals", action="store_true", help="매수신호 생략")
    ap.add_argument("--skip-news", action="store_true", help="뉴스 생략")
    ap.add_argument(
        "--top",
        type=int,
        default=BUY_SIGNAL_TOP_N,
        help=f"시장별 매수신호 TOP N (기본·최대 {BUY_SIGNAL_TOP_N})",
    )
    ap.add_argument("--year", type=int, default=datetime.now().year, help="배당 연도")
    args = ap.parse_args()
    signal_top = resolve_top_n(args.top)

    load_dotenv(BASE / ".env")
    import os

    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

    py = sys.executable
    try:
        if not args.skip_update:
            update_workbooks(args.year)
        if not args.skip_portfolio:
            run_step(
                "PORTFOLIO TELEGRAM",
                [py, "-X", "utf8", str(BASE / "send_portfolio_telegram.py"), "--refresh"],
            )
        if not args.skip_signals:
            run_step(
                "BUY SIGNALS TOP",
                [
                    py,
                    "-X",
                    "utf8",
                    str(BASE / "send_buy_signals_telegram.py"),
                    "--top",
                    str(signal_top),
                ],
            )
        if not args.skip_news:
            run_step(
                "MARKET NEWS",
                [py, "-X", "utf8", str(BASE / "send_market_news_telegram.py")],
            )
        print("\nALL DONE", flush=True)
        return 0
    except Exception:
        err = traceback.format_exc()
        print(err, flush=True)
        notify_error(token, chat_id, err)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
