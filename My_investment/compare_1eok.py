# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

INITIAL = 100_000_000
COMM = 0.00015
TAXABLE_DIV_RATIO = 0.10  # 과세 비중 ~10%

t = yf.Ticker('498400.KS')
h = t.history(start='2023-12-01', end='2026-07-12')
h.index = h.index.tz_localize(None) if h.index.tz else h.index
div = t.dividends
div.index = div.index.tz_localize(None) if div.index.tz else div.index


def dca_monthly(hist, divs, start, end, total=INITIAL):
    sub = hist[(hist.index >= start) & (hist.index <= end)]
    months = pd.period_range(start[:7], end[:7], freq='M')
    per = total / max(len(months), 1)
    shares = 0
    for m in months:
        days = sub[sub.index.to_period('M') == m]
        if days.empty:
            continue
        px = days['Open'].iloc[0] if days['Open'].iloc[0] > 0 else days['Close'].iloc[0]
        qty = int(per / (px * (1 + COMM)))
        shares += qty
    d = divs[(divs.index >= start) & (divs.index <= end)]
    gross_div = 0.0
    for dt, amt in d.items():
        # approximate shares held at each div (simplified: end shares for all - conservative for early divs)
        pass
    # better: track shares over time
    shares_t = 0
    gross_div = 0.0
    for m in months:
        days = sub[sub.index.to_period('M') == m]
        if days.empty:
            continue
        px = days['Open'].iloc[0] if days['Open'].iloc[0] > 0 else days['Close'].iloc[0]
        qty = int(per / (px * (1 + COMM)))
        shares_t += qty
        month_end = days.index[-1]
        for dt, amt in d.items():
            if dt.to_period('M') == m:
                gross_div += shares_t * amt
    end_px = sub['Close'].iloc[-1]
    net_div = gross_div * (1 - TAXABLE_DIV_RATIO * 0.154)
    final = shares_t * end_px + net_div
    return final, (final / total - 1) * 100, shares_t, gross_div, end_px


def lump_sum(hist, divs, buy_date, end, total=INITIAL):
    sub = hist[hist.index >= buy_date]
    px = sub['Open'].iloc[0] if sub['Open'].iloc[0] > 0 else sub['Close'].iloc[0]
    qty = int(total / (px * (1 + COMM)))
    gross_div = 0.0
    for dt, amt in divs.items():
        if dt >= pd.Timestamp(buy_date) and dt <= pd.Timestamp(end):
            gross_div += qty * amt
    end_px = hist[hist.index <= end]['Close'].iloc[-1]
    net_div = gross_div * (1 - TAXABLE_DIV_RATIO * 0.154)
    final = qty * end_px + net_div
    return final, (final / total - 1) * 100, qty, gross_div, px, end_px


print('=== 498400 1억 시뮬레이션 ===')
for name, s, e in [
    ('상장후 월분할(19개월)', '2024-12-03', '2026-07-10'),
]:
    f, r, sh, gd, ep = dca_monthly(h, div, s, e)
    print(f'{name}: {f/1e8:.2f}억 ({r:+.1f}%)  {sh}주  분배(세전) {gd/1e4:.0f}만  현재가 {ep:,.0f}')

f, r, sh, gd, bp, ep = lump_sum(h, div, '2024-12-03', '2026-07-10')
print(f'상장일 일시 1억: {f/1e8:.2f}억 ({r:+.1f}%)  {sh}주  분배(세전) {gd/1e4:.0f}만')

list_px = h.loc[h.index >= '2024-12-03', 'Close'].iloc[0]
print(f'상장후 주가만: {(ep/list_px-1)*100:+.1f}%  (분배 별도)')

# TOP7 scaled
print('\n=== TOP7+10% 백테스트 (1천만 기준 → 1억 환산) ===')
for label, ret in [('2024상~2025상 횡보장', 37.6), ('최근1년 급등장(추정)', 41.4)]:
    final = INITIAL * (1 + ret/100)
    print(f'{label}: {final/1e8:.2f}억 ({ret:+.1f}%)')

print('\n=== 코스피 단순보유 1억 ===')
k = yf.Ticker('^KS11').history(start='2024-12-03', end='2026-07-12')
k.index = k.index.tz_localize(None) if k.index.tz else k.index
ret = (k['Close'].iloc[-1]/k['Close'].iloc[0]-1)*100
print(f'상장후~현재: {INITIAL*(1+ret/100)/1e8:.2f}억 ({ret:+.1f}%)')
