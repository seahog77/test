# -*- coding: utf-8 -*-
"""오늘 기준 S&P500 TOP7 랭킹 출력."""
import sys
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from backtest_sp500_top7 import get_sp500_top30
from signal_rules import check_buy_signals, check_sell_signals

sys.stdout.reconfigure(encoding="utf-8")

print("=== US S&P500 TOP7 ===", flush=True)
top30 = get_sp500_top30()
hist_start = (datetime.now() - timedelta(days=450)).strftime("%Y-%m-%d")
hist_end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
tickers = [t["tic"] for t in top30]
raw = yf.download(
    tickers, start=hist_start, end=hist_end,
    auto_adjust=True, group_by="ticker", threads=True, progress=False,
)
hist_map = {}
for item in top30:
    tic = item["tic"]
    try:
        h = raw[tic].copy().dropna(how="all") if len(tickers) > 1 else raw.copy().dropna(how="all")
        if h.empty or len(h) < 60:
            continue
        h.index = h.index.tz_localize(None) if h.index.tz else h.index
        hist_map[tic] = {"name": item["name"], "hist": h}
    except Exception:
        continue

dates = sorted(set().union(*[set(v["hist"].index) for v in hist_map.values()]))
sig, trade = dates[-2], dates[-1]
rows = []
for tic, info in hist_map.items():
    h = info["hist"]
    if sig not in h.index:
        continue
    loc = h.index.get_loc(sig)
    buy = check_buy_signals(h.iloc[: loc + 1])
    sell = check_sell_signals(h.iloc[: loc + 1])
    if buy is None:
        continue
    s_hit = sell["hit"] if sell else 99
    rows.append({
        "tic": tic, "name": info["name"],
        "buy_hit": buy["hit"], "sell_hit": s_hit,
        "net": buy["hit"] - s_hit,
        "signals": ",".join(buy["signals"]),
        "ma_up": buy["ma5_gt_20"],
    })

df = pd.DataFrame(rows).sort_values(
    ["buy_hit", "net", "sell_hit", "ma_up"],
    ascending=[False, False, True, False],
).reset_index(drop=True)

print(f"신호일: {sig.date()}  기준가일: {trade.date()}")
print(f"{'순위':>4} {'심볼':<8} {'종목명':<18} {'매수':>4} {'매도':>4} {'순점':>4}  신호")
print("-" * 78)
for i, r in df.head(7).iterrows():
    print(
        f"{i+1:>4} {r['tic']:<8} {str(r['name'])[:16]:<18} "
        f"{r['buy_hit']:>4} {r['sell_hit']:>4} {r['net']:>4}  {r['signals']}"
    )
