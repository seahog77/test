# -*- coding: utf-8 -*-
"""최근 1년 다우·나스닥·S&P 차트 + JSON 데이터"""
import json
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys

sys.stdout.reconfigure(encoding='utf-8')

SYMS = {
    'Dow Jones': '^DJI',
    'Nasdaq': '^IXIC',
    'S&P 500': '^GSPC',
}
COLORS = {'Dow Jones': '#2563eb', 'Nasdaq': '#16a34a', 'S&P 500': '#dc2626'}

series = {}
for name, sym in SYMS.items():
    h = yf.Ticker(sym).history(period='1y')
    h.index = h.index.tz_localize(None) if h.index.tz else h.index
    base = h['Close'].iloc[0]
    series[name] = {
        'dates': [d.strftime('%Y-%m-%d') for d in h.index],
        'close': [round(float(v), 2) for v in h['Close']],
        'norm': [round(float(v / base * 100), 2) for v in h['Close']],
        'start': round(float(base), 2),
        'end': round(float(h['Close'].iloc[-1]), 2),
        'chg': round(float(h['Close'].iloc[-1] / base - 1) * 100, 2),
    }

# matplotlib 차트 (정규화 100 기준)
fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [2, 1]})

for name, d in series.items():
    dates = [__import__('datetime').datetime.strptime(x, '%Y-%m-%d') for x in d['dates']]
    axes[0].plot(dates, d['norm'], label=f"{name} ({d['chg']:+.1f}%)", color=COLORS[name], lw=1.8)
axes[0].set_ylabel('Index (start=100)')
axes[0].set_title('US Indices — Last 1 Year (Normalized)', fontsize=13)
axes[0].legend(loc='upper left')
axes[0].grid(True, alpha=0.3)
axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

for name, d in series.items():
    dates = [__import__('datetime').datetime.strptime(x, '%Y-%m-%d') for x in d['dates']]
    axes[1].plot(dates, d['close'], label=name, color=COLORS[name], lw=1.2)
axes[1].set_ylabel('Close Price')
axes[1].set_xlabel('Date')
axes[1].set_title('Absolute Close (different scales — see normalized chart above)')
axes[1].legend(loc='upper left', fontsize=8)
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
out_png = r'c:\Users\seaho\My project\My_investment\us_indices_1y.png'
plt.savefig(out_png, dpi=150)
print(f'Chart saved: {out_png}')

out_json = r'c:\Users\seaho\My project\My_investment\us_indices_1y.json'
with open(out_json, 'w', encoding='utf-8') as f:
    json.dump(series, f, ensure_ascii=False)
print(f'Data saved: {out_json}')

for name, d in series.items():
    print(f"{name}: {d['start']:,.0f} -> {d['end']:,.0f} ({d['chg']:+.1f}%)")
