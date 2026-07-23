# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv

from toss_client import TossInvestClient, TossInvestError

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).resolve().parent / ".env")

print("=== 국내 TOP3 ===")
kr = [
    ("010120", "LS ELECTRIC"),
    ("000810", "삼성화재"),
    ("086790", "하나금융지주"),
]
try:
    client = TossInvestClient.from_env()
    syms = [s for s, _ in kr]
    prices = {p.get("symbol"): p for p in client.get_prices(syms)}
    stocks = {s.get("symbol"): s for s in client.get_stocks(syms)}
    for i, (sym, fallback) in enumerate(kr, 1):
        px = prices.get(sym, {})
        st = stocks.get(sym, {})
        last = px.get("lastPrice")
        chg = px.get("changeRate")
        name = st.get("name") or fallback
        chg_s = f"{float(chg) * 100:+.2f}%" if chg not in (None, "") else "-"
        if last not in (None, ""):
            print(f"{i}. {sym} {name}: {float(last):,.0f}원 ({chg_s})")
        else:
            print(f"{i}. {sym} {name}: -")
except TossInvestError as e:
    print(f"(토스 API 실패 → yfinance) {e}")
    for i, (sym, name) in enumerate(kr, 1):
        t = yf.Ticker(f"{sym}.KS")
        last = getattr(t.fast_info, "last_price", None)
        prev = getattr(t.fast_info, "previous_close", None)
        chg_s = f"{(last / prev - 1) * 100:+.2f}%" if last and prev else "-"
        print(f"{i}. {sym} {name}: {last:,.0f}원 ({chg_s})" if last else f"{i}. {sym} {name}: -")

print()
print("=== 미국 TOP3 ===")
us = [("XOM", "Exxon"), ("CVX", "Chevron"), ("WMT", "Walmart")]
for i, (sym, name) in enumerate(us, 1):
    t = yf.Ticker(sym)
    last = getattr(t.fast_info, "last_price", None)
    prev = getattr(t.fast_info, "previous_close", None)
    chg_s = f"{(last / prev - 1) * 100:+.2f}%" if last and prev else "-"
    if last:
        print(f"{i}. {sym} {name}: ${last:,.2f} ({chg_s})")
    else:
        print(f"{i}. {sym} {name}: -")
