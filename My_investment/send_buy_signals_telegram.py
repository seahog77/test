# -*- coding: utf-8 -*-
"""
미국(S&P500 시총상위) + 국내(코스피 시총상위) 강한 매수 신호 → 텔레그램

순위 기준(기본):
  기술 매수신호 + 펀더멘털(EPS/PER/PBR/매출·이익성장) 종합점수

사용:
  python send_buy_signals_telegram.py --top 10
  python send_buy_signals_telegram.py --top 10 --tech-only
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
from fundamentals import (
    fetch_fundamentals_many,
    fmt_num,
    fmt_pct,
    fundamental_score,
)
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
    fund_map: dict[str, dict],
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
        f = fund_map.get(sym) or {}
        f_score, f_tags = fundamental_score(f)
        # 종합: 기술 순점(가중) + 펀더 점수
        tech_comp = buy["hit"] * 1.2 + (buy["hit"] - sell_hit) * 0.8
        if buy["ma5_gt_20"]:
            tech_comp += 0.3
        total = tech_comp + f_score
        per_v = f.get("fwd_per") if f.get("fwd_per") else f.get("per")
        earn_v = f.get("earn_g") if f.get("earn_g") is not None else f.get("earn_qg")
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
                "date": str(buy["date"]),
                "eps": f.get("eps"),
                "per": per_v,
                "pbr": f.get("pbr"),
                "rev_g": f.get("rev_g"),
                "earn_g": earn_v,
                "fund_score": round(f_score, 2),
                "fund_tags": f_tags,
                "tech_comp": round(tech_comp, 2),
                "total_score": round(total, 2),
                "fund_ok": bool(f.get("ok")),
            }
        )
    return rows


def build_market_message(market: str, top: list[dict], asof: str, n: int, with_fund: bool) -> str:
    label = "미국 S&P500 시총상위" if market == "US" else "코스피 시총상위"
    flag = "US" if market == "US" else "KR"
    if with_fund:
        basis = "기술신호 + EPS/PER/PBR/매출·이익성장 종합점수"
    else:
        basis = "매수신호 많은 순 · 순점(매수-매도) · 단기이평"
    lines = [
        f"[{flag}] 강한 매수 신호 TOP{n} ({asof})",
        f"유니버스: {label}",
        f"기준: {basis}",
        "",
    ]
    for i, r in enumerate(top, 1):
        sig = ",".join(r["signals"][:3]) if r["signals"] else "-"
        more = f"+{len(r['signals'])-3}" if len(r["signals"]) > 3 else ""
        lines.append(f"{i:2d}. {r['name'][:16]} ({r['tic']})")
        if with_fund:
            lines.append(
                f"    종합{r.get('total_score', 0):.1f} "
                f"(기술{r.get('tech_comp', 0):.1f}+펀더{r.get('fund_score', 0):.1f})  "
                f"매수{r['buy']} 매도{r['sell']}"
            )
            lines.append(
                f"    PER{fmt_num(r.get('per'))} PBR{fmt_num(r.get('pbr'))} "
                f"EPS{fmt_num(r.get('eps'), 2)}  "
                f"매출{fmt_pct(r.get('rev_g'))} 이익{fmt_pct(r.get('earn_g'))}"
            )
            tags = ",".join((r.get("fund_tags") or [])[:4]) or "-"
            lines.append(f"    {sig}{more} · {tags}")
        else:
            lines.append(
                f"    매수{r['buy']} 매도{r['sell']} 순{r['net']:+d}  "
                f"RSI{r['rsi']} 1M{r['m1']:+.1f}%"
            )
            lines.append(f"    {sig}{more}")
    lines += ["", "※ 참고용 신호. 투자 판단은 본인 책임."]
    msg = "\n".join(lines)
    if len(msg) > 3900:
        msg = msg[:3900] + "\n…(생략)"
    return msg


def pick_top(df: pd.DataFrame, n: int, with_fund: bool) -> list[dict]:
    if df.empty:
        return []
    # 최소 매수 신호 1개 이상 우선
    strong = df[df["buy"] >= 1].copy()
    if len(strong) < n:
        strong = df.copy()
    if with_fund:
        strong = strong.sort_values(
            ["total_score", "buy", "net", "fund_score", "ma_up"],
            ascending=[False, False, False, False, False],
        )
    else:
        strong = strong.sort_values(
            ["buy", "net", "sell", "ma_up", "m1"],
            ascending=[False, False, True, False, False],
        )
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
    ap.add_argument(
        "--tech-only",
        action="store_true",
        help="펀더멘털 제외, 기술신호만으로 순위",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="전송 없이 출력만",
    )
    args = ap.parse_args()
    with_fund = not args.tech_only

    load_dotenv(BASE / ".env")
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not args.dry_run and (not token or not chat_id):
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

    fund_map: dict[str, dict] = {}
    if with_fund:
        syms = list(dict.fromkeys(list(us_yf.values()) + list(kr_yf.values())))
        print(f"펀더멘털 조회: {len(syms)}종목...", flush=True)
        fund_map = fetch_fundamentals_many(syms)
        ok_n = sum(1 for v in fund_map.values() if v.get("ok"))
        print(f"펀더멘털 성공: {ok_n}/{len(syms)}", flush=True)

    us_rows = score_universe(us_items, "US", us_yf, hist, fund_map)
    kr_rows = score_universe(kr_items, "KR", kr_yf, hist, fund_map)
    rows = us_rows + kr_rows

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("신호 계산 결과 없음")

    asof = datetime.now().strftime("%Y-%m-%d")
    n = max(1, args.top)

    if args.combined:
        top = pick_top(df, n, with_fund)
        msg = build_market_message("US", top, asof, n, with_fund)
        # rewrite header for combined
        msg = msg.replace("[US] 강한 매수 신호", "강한 매수 신호(미·한합산)")
        msg = msg.replace("유니버스: 미국 S&P500 시총상위", "유니버스: 미국+코스피 시총상위")
        print(msg)
        if not args.dry_run:
            result = send_telegram(token, chat_id, msg)
            if not result.get("ok"):
                raise SystemExit(f"전송 실패: {result}")
        payload = top
    else:
        us_top = pick_top(df[df["market"] == "US"].copy(), n, with_fund)
        kr_top = pick_top(df[df["market"] == "KR"].copy(), n, with_fund)
        for market, top in (("US", us_top), ("KR", kr_top)):
            msg = build_market_message(market, top, asof, n, with_fund)
            print(msg)
            print("---", flush=True)
            if not args.dry_run:
                result = send_telegram(token, chat_id, msg)
                if not result.get("ok"):
                    raise SystemExit(f"전송 실패 [{market}]: {result}")
                print(f"텔레그램 전송 완료 [{market}].", flush=True)
        payload = {"US": us_top, "KR": kr_top}

    out = BASE / ("_buy_signals_top20.json" if n >= 20 else "_buy_signals_top10.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("완료.", flush=True)


if __name__ == "__main__":
    main()
