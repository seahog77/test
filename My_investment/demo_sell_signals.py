# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
import yfinance as yf
from signal_rules import check_all_signals, BUY_NAMES, SELL_NAMES

hist = yf.Ticker('105560.KS').history(period='2y')
hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
r = check_all_signals(hist)
b, s = r['buy'], r['sell']
print('KB금융 예시')
print(f"  매수 {b['hit']}개: {', '.join(b['signals']) or '-'}")
print(f"  매도 {s['hit']}개: {', '.join(s['signals']) or '-'}")
print(f"  순신호 {r['net']:+d}  판단: {r['action']}")
print()
for i, name in enumerate(BUY_NAMES, 1):
    sn = SELL_NAMES[i - 1]
    bm = 'O' if b['detail'][name] else '-'
    sm = 'O' if s['detail'][sn] else '-'
    print(f'  {i:2}. 매수 {name:<8} {bm:>3}  |  매도 {sn:<8} {sm:>3}')
