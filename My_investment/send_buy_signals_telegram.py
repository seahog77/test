# -*- coding: utf-8 -*-
"""
미국(S&P500 시총상위) + 국내(코스피 시총상위) 강한 매수 신호 TOP10 → 텔레그램

사용:
  python send_buy_signals_telegram.py
"""
from __future__ import annotations

import json
import os
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtest_sp500_top7 import get_sp500_top30
from send_portfolio_telegram import load_dotenv, send_telegram
from signal_rules import check_buy_signals, check_sell_signals
from top7_strategy import get_kospi_top30

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent


def download_hist(symbols: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    if not symbols:
        return out
    raw = yf.download(
        symbols,
        start=start,
        end=end,
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    for sym in symbols:
        try:
            if len(symbols) == 1:
                h = raw.copy()
            else:
                h = raw[sym].copy()
            h = h.dropna(how="all")
            if h.empty or len(h) < 60:
                continue
            if h.index.tz is not None:
                h.index = h.index.tz_localize(None)
            out[sym] = h
        except Exception:
            continue
    return out


def score_universe(
    items: list[dict],
    market: str,
    yf_map: dict[str, str],
    hist_map: dict[str, pd.DataFrame],
) -> list[dict]:
    rows = []
    for item in items:
        tic = item["tic"]
        sym = yf_map.get(tic)
        if not sym or sym not in hist_map:
            continue
        h = hist_map[sym]
        buy = check_buy_signals(h)
        sell = check_sell_signals(h)
        if buy is None:
            continue
        sell_hit = sell["hit"] if sell else 99
        rows.append(
            {
                "market": market,
                "tic": tic,
                "name": item["name"],
                "buy": buy["hit"],
                "sell": sell_hit,
                "net": buy["hit"] - sell_hit,
                "signals": buy["signals"],
                "price": buy["price"],
                "rsi": round(float(buy["RSI"]), 1),
                "m1": round(float(buy["m1"]), 1),
                "ma_up": bool(buy["ma5_gt_20"]),
                "date": buy["date"],
            }
        )
    return rows


def build_market_message(market: str, top: list[dict], asof: str, n: int) -> str:
    label = "미국 S&P500 시총상위" if market == "US" else "코스피 시총상위"
    flag = "US" if market == "US" else "KR"
    lines = [
        f"[{flag}] 강한 매수 신호 TOP{n} ({asof})",
        f"유니버스: {label}",
        "기준: 매수신호 많은 순 · 순점(매수-매도) · 단기이평",
        "",
    ]
    for i, r in enumerate(top, 1):
        sig = ",".join(r["signals"][:4]) if r["signals"] else "-"
        more = f"+{len(r['signals'])-4}" if len(r["signals"]) > 4 else ""
        lines.append(f"{i:2d}. {r['name'][:16]} ({r['tic']})")
        lines.append(
            f"    매수{r['buy']} 매도{r['sell']} 순{r['net']:+d}  "
            f"RSI{r['rsi']} 1M{r['m1']:+.1f}%"
        )
        lines.append(f"    {sig}{more}")
    lines += ["", "※ 기술적 신호 참고용. 투자 판단은 본인 책임."]
    msg = "\n".join(lines)
    if len(msg) > 3900:
        msg = msg[:3900] + "\n…(생략)"
    return msg


def pick_top(df: pd.DataFrame, n: int) -> list[dict]:
    if df.empty:
        return []
    strong = df[df["buy"] >= 2].copy()
    if len(strong) < n:
        strong = df.copy()
    return strong.head(n).to_dict("records")


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10, help="시장별 TOP N (기본 10)")
    ap.add_argument(
        "--combined",
        action="store_true",
        help="미국+국내 합산 TOP만 전송 (기존 방식)",
    )
    args = ap.parse_args()

    load_dotenv(BASE / ".env")
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        raise SystemExit(".env 에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 필요")

    end = datetime.now() + timedelta(days=1)
    start = datetime.now() - timedelta(days=450)
    start_s, end_s = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    us_items = get_sp500_top30()
    kr_items = get_kospi_top30()
    print(f"US {len(us_items)} · KR {len(kr_items)} 스캔 중...", flush=True)

    us_yf = {x["tic"]: x["tic"] for x in us_items}
    kr_yf = {x["tic"]: f"{str(x['tic']).zfill(6)}.KS" for x in kr_items}

    hist = {}
    hist.update(download_hist(list(us_yf.values()), start_s, end_s))
    hist.update(download_hist(list(kr_yf.values()), start_s, end_s))
    print(f"시세 로드: {len(hist)}종목", flush=True)

    us_rows = score_universe(us_items, "US", us_yf, hist)
    kr_rows = score_universe(kr_items, "KR", kr_yf, hist)
    rows = us_rows + kr_rows

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("신호 계산 결과 없음")

    df = df.sort_values(
        ["buy", "net", "sell", "ma_up", "m1"],
        ascending=[False, False, True, False, False],
    ).reset_index(drop=True)

    asof = datetime.now().strftime("%Y-%m-%d")
    n = max(1, args.top)

    if args.combined:
        top = pick_top(df, n)
        # 하위호환: 합산 1통
        label_rows = []
        for i, r in enumerate(top, 1):
            flag = "US" if r["market"] == "US" else "KR"
            sig = ",".join(r["signals"][:4]) if r["signals"] else "-"
            more = f"+{len(r['signals'])-4}" if len(r["signals"]) > 4 else ""
            label_rows += [
                f"{i:2d}. [{flag}] {r['name'][:14]} ({r['tic']})",
                f"    매수{r['buy']} 매도{r['sell']} 순{r['net']:+d}  RSI{r['rsi']} 1M{r['m1']:+.1f}%",
                f"    {sig}{more}",
            ]
        msg = "\n".join(
            [
                f"강한 매수 신호 TOP{n} ({asof})",
                "유니버스: 미국 S&P500 시총상위 + 코스피 시총상위",
                "기준: 매수신호 많은 순 · 순점(매수-매도) · 단기이평",
                "",
                *label_rows,
                "",
                "※ 기술적 신호 참고용. 투자 판단은 본인 책임.",
            ]
        )
        print(msg)
        result = send_telegram(token, chat_id, msg)
        if not result.get("ok"):
            raise SystemExit(f"전송 실패: {result}")
        payload = top
    else:
        us_top = pick_top(df[df["market"] == "US"].copy(), n)
        kr_top = pick_top(df[df["market"] == "KR"].copy(), n)
        for market, top in (("US", us_top), ("KR", kr_top)):
            msg = build_market_message(market, top, asof, n)
            print(msg)
            print("---", flush=True)
            result = send_telegram(token, chat_id, msg)
            if not result.get("ok"):
                raise SystemExit(f"전송 실패 [{market}]: {result}")
            print(f"텔레그램 전송 완료 [{market}].", flush=True)
        payload = {"US": us_top, "KR": kr_top}

    out = BASE / ("_buy_signals_top20.json" if n >= 20 else "_buy_signals_top10.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("텔레그램 전송 완료.", flush=True)


if __name__ == "__main__":
    main()
