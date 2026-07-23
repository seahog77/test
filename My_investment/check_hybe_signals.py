# -*- coding: utf-8 -*-
"""하이브(352820) 10가지 매수 신호 점검"""
import yfinance as yf
import pandas as pd
import numpy as np
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

TICKER = '352820.KS'
NAME = '하이브'

# 최근 1년+ 일봉
df = yf.Ticker(TICKER).history(period='2y')
df.index = df.index.tz_localize(None) if df.index.tz else df.index
df = df.sort_index()
close = df['Close']
high = df['High']
low = df['Low']
vol = df['Volume']

# 이동평균
df['MA5'] = close.rolling(5).mean()
df['MA20'] = close.rolling(20).mean()
df['MA60'] = close.rolling(60).mean()
df['MA120'] = close.rolling(120).mean()
df['MA200'] = close.rolling(200).mean()

# RSI
delta = close.diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / loss.replace(0, np.nan)
df['RSI'] = 100 - 100 / (1 + rs)

# MACD
ema12 = close.ewm(span=12, adjust=False).mean()
ema26 = close.ewm(span=26, adjust=False).mean()
df['MACD'] = ema12 - ema26
df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
df['MACD_hist'] = df['MACD'] - df['MACD_signal']

# Bollinger
df['BB_mid'] = close.rolling(20).mean()
std = close.rolling(20).std()
df['BB_lower'] = df['BB_mid'] - 2 * std
df['BB_upper'] = df['BB_mid'] + 2 * std

# Stochastic
low14 = low.rolling(14).min()
high14 = high.rolling(14).max()
df['STO_K'] = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
df['STO_D'] = df['STO_K'].rolling(3).mean()

df = df.dropna(subset=['MA20', 'RSI', 'MACD', 'BB_mid', 'STO_K'])
recent = df.tail(60)
last = df.iloc[-1]
prev = df.iloc[-2]
prev5 = df.iloc[-6]

results = []

# ── 1. 골든크로스 (5/20 또는 20/60) ──
gc_5_20 = prev5['MA5'] <= prev5['MA20'] and last['MA5'] > last['MA20']
gc_20_60 = (df['MA20'].iloc[-20] <= df['MA60'].iloc[-20] and last['MA20'] > last['MA60'])
gc_recent = gc_5_20 or (prev['MA5'] <= prev['MA20'] and last['MA5'] > last['MA20'])
# also check if happened in last 10 days
gc_10d = False
for i in range(-10, 0):
    if i-1 >= -len(df):
        a, b = df.iloc[i-1], df.iloc[i]
        if a['MA5'] <= a['MA20'] and b['MA5'] > b['MA20']:
            gc_10d = True
            break
s1 = gc_10d or (last['MA5'] > last['MA20'] and prev5['MA5'] <= prev5['MA20'])
results.append(('1. 이동평균 골든크로스 (5/20)', s1,
                f"MA5={last['MA5']:,.0f} MA20={last['MA20']:,.0f} {'5>20' if last['MA5']>last['MA20'] else '5<20'}"))

# ── 2. 지지선 반등 ──
# 최근 60일 저점 클러스터
support = recent['Low'].min()
support_zone = support * 1.03
near_support = last['Close'] <= support_zone * 1.05 and last['Close'] >= support * 0.98
bounce = last['Close'] > prev['Close'] and last['Low'] <= support_zone
vol_avg = recent['Volume'].mean()
vol_up = last['Volume'] > vol_avg * 1.1
s2 = near_support and bounce
results.append(('2. 지지선 반등', s2,
                f"지지~{support:,.0f}원, 현재={last['Close']:,.0f}, {'반등' if bounce else '미반등'}, 거래량{'↑' if vol_up else '보통'}"))

# ── 3. RSI 과매도 탈출 ──
rsi_was_low = (df['RSI'].tail(10).min() <= 35)
rsi_exit = prev['RSI'] <= 40 and last['RSI'] > 40 and last['RSI'] < 60
rsi_cross_30 = rsi_was_low and last['RSI'] > 35 and last['Close'] > prev['Close']
s3 = rsi_exit or rsi_cross_30
results.append(('3. RSI 과매도 탈출', s3,
                f"RSI={last['RSI']:.1f} (10일최저 {df['RSI'].tail(10).min():.1f})"))

# ── 4. MACD 상향 돌파 ──
macd_cross = prev['MACD'] <= prev['MACD_signal'] and last['MACD'] > last['MACD_signal']
macd_0 = last['MACD'] > 0 or (last['MACD_hist'] > prev['MACD_hist'] and last['MACD_hist'] > 0)
macd_10d = False
for i in range(-10, 0):
    if df.iloc[i-1]['MACD'] <= df.iloc[i-1]['MACD_signal'] and df.iloc[i]['MACD'] > df.iloc[i]['MACD_signal']:
        macd_10d = True
        break
s4 = macd_cross or macd_10d
results.append(('4. MACD 상향 돌파', s4,
                f"MACD={last['MACD']:.0f} Signal={last['MACD_signal']:.0f} Hist={last['MACD_hist']:.0f}"))

# ── 5. 볼린저 하단 터치 후 중심 회귀 ──
touch_lower = (recent['Low'] <= recent['BB_lower'] * 1.02).any()
moving_to_mid = last['Close'] > last['BB_lower'] and last['Close'] > prev['Close']
below_mid = last['Close'] < last['BB_mid']
s5 = touch_lower and moving_to_mid
results.append(('5. 볼린저 하단→중심 회귀', s5,
                f"현재={last['Close']:,.0f} 하단={last['BB_lower']:,.0f} 중심={last['BB_mid']:,.0f}"))

# ── 6. 거래량 동반 돌파 ──
resistance = recent['High'].max()
breakout = last['Close'] >= resistance * 0.98 and last['Close'] > prev['Close']
vol_break = last['Volume'] >= vol_avg * 1.5
s6 = breakout and vol_break
results.append(('6. 거래량 동반 돌파', s6,
                f"60일고점~{resistance:,.0f}, 현재={last['Close']:,.0f}, 거래량={last['Volume']/vol_avg:.1f}x"))

# ── 7. 이중바닥(W) / 넥라인 ──
# 간단: 최근 90일 두 저점
r90 = df.tail(90)
troughs = []
for i in range(2, len(r90)-2):
    l = r90.iloc[i]['Low']
    if l <= r90.iloc[i-1]['Low'] and l <= r90.iloc[i-2]['Low'] and l <= r90.iloc[i+1]['Low'] and l <= r90.iloc[i+2]['Low']:
        troughs.append((r90.index[i], l))
w_pattern = False
neckline_break = False
if len(troughs) >= 2:
    t1, t2 = troughs[-2], troughs[-1]
    if abs(t1[1] - t2[1]) / t1[1] < 0.05:  # 두 저점 비슷
        w_pattern = True
        mid_high = r90.loc[t1[0]:t2[0]]['High'].max()
        neckline_break = last['Close'] > mid_high * 0.98
s7 = w_pattern and neckline_break
results.append(('7. 이중바닥+넥라인 돌파', s7,
                f"W패턴={'유' if w_pattern else '무'} 넥라인돌파={'유' if neckline_break else '무'}"))

# ── 8. 200일선 근처 지지 ──
if pd.notna(last['MA200']):
    near_200 = abs(last['Close'] - last['MA200']) / last['MA200'] < 0.05
    bounce_200 = last['Close'] > last['MA200'] * 0.97 and last['Close'] > prev['Close']
    above_200 = last['Close'] > last['MA200']
    s8 = near_200 and bounce_200
    ma200_txt = f"200일선={last['MA200']:,.0f} 현재={last['Close']:,.0f}"
else:
    s8 = False
    ma200_txt = "200일선 데이터 부족"
results.append(('8. 200일선 지지 반등', s8, ma200_txt))

# ── 9. 스토캐스틱 과매도 골든크로스 ──
sto_os = prev['STO_K'] <= 25 or prev['STO_D'] <= 25
sto_gc = prev['STO_K'] <= prev['STO_D'] and last['STO_K'] > last['STO_D']
sto_10d = False
for i in range(-10, 0):
    a, b = df.iloc[i-1], df.iloc[i]
    if (a['STO_K'] <= 25 or a['STO_D'] <= 25) and a['STO_K'] <= a['STO_D'] and b['STO_K'] > b['STO_D']:
        sto_10d = True
        break
s9 = (sto_os and sto_gc) or sto_10d
results.append(('9. 스토캐스틱 과매도 GC', s9,
                f"K={last['STO_K']:.1f} D={last['STO_D']:.1f}"))

# ── 10. 피보나치 0.5~0.618 지지 ──
lookback = df.tail(120)
swing_high = lookback['High'].max()
swing_low = lookback['Low'].min()
diff = swing_high - swing_low
fib50 = swing_high - diff * 0.5
fib618 = swing_high - diff * 0.618
in_fib = fib618 * 0.98 <= last['Close'] <= fib50 * 1.02
fib_bounce = in_fib and last['Close'] > prev['Close']
s10 = fib_bounce
results.append(('10. 피보나치 0.5~0.618 지지', s10,
                f"고점={swing_high:,.0f} 저점={swing_low:,.0f} 50%={fib50:,.0f} 61.8%={fib618:,.0f}"))

# ── 출력 ──
print('=' * 70)
print(f'  {NAME} ({TICKER}) 매수 신호 점검')
print(f'  기준일: {df.index[-1].strftime("%Y-%m-%d")}  |  종가: {last["Close"]:,.0f}원')
print(f'  최근 5일: ', ', '.join(f'{df.index[i].strftime("%m/%d")} {df.iloc[i]["Close"]:,.0f}' for i in range(-5, 0)))
print('=' * 70)

hit = 0
partial = 0
for name, ok, detail in results:
    mark = '✅ 해당' if ok else '❌ 미해당'
    if ok:
        hit += 1
    print(f'\n{mark}  {name}')
    print(f'       {detail}')

# 부분 해당 (곧 될 수 있는 것)
print('\n' + '─' * 70)
print('  [참고] 근접·부분 신호')
near_items = []
if last['RSI'] < 40:
    near_items.append(f"RSI {last['RSI']:.1f} — 과매도권이나 '탈출'은 아직")
if last['Close'] < last['BB_mid']:
    near_items.append("볼린저 중심선 아래 — 하단 터치는 있었으나 중심 회귀 미완")
if last['MA5'] < last['MA20']:
    near_items.append("단기 이평 역배열 — 골든크로스 전")
if touch_lower and not moving_to_mid:
    near_items.append("볼린저 하단 접촉 이력 있음, 반등 약함")
if w_pattern and not neckline_break:
    near_items.append("W형 유사하지만 넥라인 미돌파")
for x in near_items:
    print(f'  · {x}')

print('\n' + '=' * 70)
print(f'  ▶ 10가지 중 **{hit}가지 해당** / **{10-hit}가지 미해당**')
print('=' * 70)

if hit <= 2:
    verdict = '매수 신호 약함 — 관망 또는 분할 대기 권장'
elif hit <= 4:
    verdict = '일부 신호 — 소량 분할만 검토, 2~3개 추가 확인 필요'
else:
    verdict = '복수 신호 — 분할 매수 검토 가능 (펀더멘털·비중 별도 확인)'
print(f'\n  종합: {verdict}')
print('  ※ 하이브는 MDD·미회복 구간 — 投機·테마 성격, 신호만으로 매수 판단 비권장')
