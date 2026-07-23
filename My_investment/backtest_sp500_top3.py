# -*- coding: utf-8 -*-
"""S&P500 TOP30 — TOP3 분산, 익절 +20% / 손절 -10% (최근 1년)"""
import sys
import warnings
from datetime import timedelta

import pandas as pd
import yfinance as yf

import backtest_sp500_top7 as bt

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

TOP_N = 3
TAKE_PROFIT = 0.20
STOP_LOSS = -0.10
LABEL = "TP20_SL10"


def main():
    base = r"c:\Users\seaho\My project\My_investment"

    print("S&P500 시총 TOP30 조회 중...", flush=True)
    top30 = bt.get_sp500_top30()
    print(f"  유니버스: {', '.join(t['tic'] for t in top30[:8])} ... ({len(top30)}종)")

    print("OHLCV 로드 중...", flush=True)
    hist_map = {}
    hist_start = bt.HIST_START.strftime("%Y-%m-%d")
    hist_end = (bt.END + timedelta(days=1)).strftime("%Y-%m-%d")
    tickers = [item["tic"] for item in top30]
    raw = yf.download(
        tickers, start=hist_start, end=hist_end,
        auto_adjust=True, group_by="ticker", threads=True, progress=False,
    )
    for item in top30:
        tic = item["tic"]
        try:
            h = raw[tic].copy().dropna(how="all")
            if h.empty or len(h) < 60:
                continue
            h.index = h.index.tz_localize(None) if h.index.tz else h.index
            hist_map[tic] = {"name": item["name"], "hist": h}
        except Exception:
            continue

    all_dates = sorted(set().union(*[set(v["hist"].index) for v in hist_map.values()]))
    trade_dates = [d for d in all_dates if bt.START <= d <= bt.END]
    if len(trade_dates) < 20:
        print("거래일 부족")
        sys.exit(1)

    spy = yf.Ticker("SPY").history(
        start=trade_dates[0], end=trade_dates[-1] + pd.Timedelta(days=1)
    )
    spy.index = spy.index.tz_localize(None) if spy.index.tz else spy.index
    spy_bh = bt.INITIAL * spy["Close"].iloc[-1] / spy["Close"].iloc[0]
    spy_ret = (spy_bh / bt.INITIAL - 1) * 100

    print("=" * 88)
    print("  S&P500 TOP30 — TOP3 분산 / +20% 익절(익일) / -10% 손절")
    print(
        f"  기간: {trade_dates[0].strftime('%Y-%m-%d')} ~ "
        f"{trade_dates[-1].strftime('%Y-%m-%d')}  (최근 1년)"
    )
    print(f"  초기자금: ${bt.INITIAL:,.0f}  |  수수료: {bt.COMM_RATE*100:.2f}%")
    print("=" * 88)

    # monkey-patch deploy size
    bt.TOP_N = TOP_N
    print(f"\n  ▶ TOP{TOP_N} {LABEL} (+20%/-10%) 실행 중...", flush=True)
    r = bt.run_backtest(
        hist_map, trade_dates, take_profit=TAKE_PROFIT, stop_loss=STOP_LOSS
    )

    pd.DataFrame(r["trades"]).to_csv(
        f"{base}\\sp500_top3_{LABEL}_trades.csv", index=False, encoding="utf-8-sig"
    )
    r["daily"].to_csv(
        f"{base}\\sp500_top3_{LABEL}_daily.csv", index=False, encoding="utf-8-sig"
    )

    print(f"\n  최종평가    : ${r['final']:,.2f}")
    print(f"  수익률      : {r['return_pct']:+.1f}%")
    print(f"  매수/매도   : {r['buys']}/{r['sells']}")
    print(f"  승률        : {r['win_rate']:.0f}%")
    print(f"  익절/손절   : {r['tp_cnt']}/{r['sl_cnt']}")
    print(f"  평균보유    : {r['avg_hold']:.1f}일")
    print(f"  재배치 횟수 : {r['n_deploy']}")
    print(f"  미청산 종목 : {r['n_positions']}종")
    print(f"\n  [비교] SPY 단순보유 : ${spy_bh:,.2f} ({spy_ret:+.1f}%)")
    print(f"         TOP7 +20%/-10% (이전) : 약 +17.9%")

    if r["pick_counts"]:
        print("\n  ── 종목별 매수 횟수 (상위) ──")
        for tic, cnt in sorted(r["pick_counts"].items(), key=lambda x: -x[1])[:10]:
            name = hist_map[tic]["name"]
            print(f"    {tic:<6} {name[:16]:<16} {cnt}회")

    sells = [t for t in r["trades"] if t["side"] == "SELL"]
    if sells:
        print("\n  ── 최근 매도 5건 ──")
        for t in sells[-5:]:
            d = pd.Timestamp(t["date"]).strftime("%Y-%m-%d")
            print(
                f"    {d} {t['tic']:<6} {str(t['name'])[:12]:<12} "
                f"{t['pnl_pct']:+.1f}%  {t['reason']}"
            )

    print(f"\n  저장: sp500_top3_{LABEL}_trades.csv, _daily.csv")


if __name__ == "__main__":
    main()
