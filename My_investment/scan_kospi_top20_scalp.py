# -*- coding: utf-8 -*-
"""코스피 시총 상위 20 — 단기 3% 스캘프 적합도 분석"""
import pandas as pd
import yfinance as yf
import numpy as np
import sys
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

# scan_all_signals.py 와 동일 로직
def check_signals(df):
    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df['Volume']

    df = df.copy()
    df['MA5'] = close.rolling(5).mean()
    df['MA20'] = close.rolling(20).mean()
    df['MA200'] = close.rolling(200).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df['RSI'] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    df['BB_mid'] = close.rolling(20).mean()
    std = close.rolling(20).std()
    df['BB_lower'] = df['BB_mid'] - 2 * std
    df['BB_upper'] = df['BB_mid'] + 2 * std

    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    df['STO_K'] = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
    df['STO_D'] = df['STO_K'].rolling(3).mean()

    df = df.dropna(subset=['MA20', 'RSI', 'MACD', 'BB_mid', 'STO_K'])
    if len(df) < 30:
        return None

    last, prev = df.iloc[-1], df.iloc[-2]
    recent = df.tail(60)
    signals = {}

    s1 = False
    for i in range(-10, 0):
        if df.iloc[i - 1]['MA5'] <= df.iloc[i - 1]['MA20'] and df.iloc[i]['MA5'] > df.iloc[i]['MA20']:
            s1 = True
            break
    signals['GC'] = s1

    support = recent['Low'].min()
    bounce = last['Close'] > prev['Close'] and last['Low'] <= support * 1.03
    signals['지지반등'] = last['Close'] <= support * 1.05 and bounce

    rsi_low = df['RSI'].tail(10).min() <= 35
    signals['RSI탈출'] = rsi_low and last['RSI'] > 38 and last['Close'] > prev['Close']

    s4 = False
    for i in range(-10, 0):
        if df.iloc[i - 1]['MACD'] <= df.iloc[i - 1]['MACD_signal'] and df.iloc[i]['MACD'] > df.iloc[i]['MACD_signal']:
            s4 = True
            break
    signals['MACD'] = s4

    touch = (recent['Low'] <= recent['BB_lower'] * 1.02).any()
    signals['BB회귀'] = touch and last['Close'] > prev['Close'] and last['Close'] > last['BB_lower']

    resistance = recent['High'].max()
    vol_avg = recent['Volume'].mean()
    signals['거래량돌파'] = last['Close'] >= resistance * 0.99 and last['Volume'] >= vol_avg * 1.5

    r90 = df.tail(90)
    troughs = []
    for i in range(2, len(r90) - 2):
        l = r90.iloc[i]['Low']
        if l <= r90.iloc[i - 1]['Low'] and l <= r90.iloc[i - 2]['Low'] and l <= r90.iloc[i + 1]['Low']:
            troughs.append((r90.index[i], l))
    w_ok = False
    if len(troughs) >= 2:
        t1, t2 = troughs[-2], troughs[-1]
        if abs(t1[1] - t2[1]) / max(t1[1], 1) < 0.05:
            mid_high = r90.loc[t1[0]:t2[0]]['High'].max()
            w_ok = last['Close'] > mid_high * 0.98
    signals['W패턴'] = w_ok

    if pd.notna(last['MA200']):
        signals['200일선'] = abs(last['Close'] - last['MA200']) / last['MA200'] < 0.05 and last['Close'] > prev['Close']
    else:
        signals['200일선'] = False

    s9 = False
    for i in range(-10, 0):
        a, b = df.iloc[i - 1], df.iloc[i]
        if (a['STO_K'] <= 25 or a['STO_D'] <= 25) and a['STO_K'] <= a['STO_D'] and b['STO_K'] > b['STO_D']:
            s9 = True
            break
    signals['STO_GC'] = s9

    lb = df.tail(120)
    sh, sl = lb['High'].max(), lb['Low'].min()
    diff = sh - sl
    fib50 = sh - diff * 0.5
    fib618 = sh - diff * 0.618
    signals['피보나치'] = fib618 * 0.98 <= last['Close'] <= fib50 * 1.02 and last['Close'] > prev['Close']

    hit = sum(signals.values())
    hit_list = [k for k, v in signals.items() if v]

    cur_dd = ((close - close.cummax()) / close.cummax()).iloc[-1] * 100
    m1 = (close.iloc[-1] / close.iloc[max(-22, -len(close))] - 1) * 100 if len(close) > 5 else 0
    m5 = (close.iloc[-1] / close.iloc[max(-6, -len(close))] - 1) * 100 if len(close) > 5 else 0

    # ATR(14) % — 일일 변동성
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr_pct = tr.rolling(14).mean().iloc[-1] / last['Close'] * 100

    # 20일 고점까지 거리 (3% 목표 여유)
    high20 = recent['High'].max()
    room_to_high = (high20 / last['Close'] - 1) * 100

    # BB 상단까지 여유
    room_bb = (last['BB_upper'] / last['Close'] - 1) * 100

    # 단기 스캘프 점수 (0~100)
    score = 0
    score += min(hit, 6) * 8                    # 신호 (max 48)
    score += 10 if last['MA5'] > last['MA20'] else 0
    score += 8 if 40 <= last['RSI'] <= 62 else (4 if 35 <= last['RSI'] <= 68 else 0)
    score += 6 if m5 > 0 else 0
    score += 6 if signals['거래량돌파'] else 0
    score += 5 if signals['MACD'] or signals['GC'] else 0
    score += 5 if room_to_high >= 3 else (2 if room_to_high >= 1.5 else 0)
    score += 5 if atr_pct >= 1.5 else (2 if atr_pct >= 1.0 else 0)
    score -= 10 if last['RSI'] > 70 else 0
    score -= 8 if m1 < -10 else 0
    score -= 5 if cur_dd < -25 else 0

    return {
        'price': last['Close'],
        'hit': hit,
        'signals': hit_list,
        'RSI': last['RSI'],
        'cur_dd': cur_dd,
        'm1': m1,
        'm5': m5,
        'atr_pct': atr_pct,
        'room_high20': room_to_high,
        'room_bb': room_bb,
        'ma5_gt_20': last['MA5'] > last['MA20'],
        'vol_ratio': last['Volume'] / vol_avg if vol_avg else 0,
        'scalp_score': score,
    }


def get_kospi_top20():
    try:
        from pykrx import stock
        today = datetime.now().strftime('%Y%m%d')
        cap = stock.get_market_cap_by_ticker(today, market='KOSPI')
        if cap.empty:
            cap = stock.get_market_cap_by_ticker(
                stock.get_nearest_business_day_in_a_week(today), market='KOSPI')
        cap = cap.sort_values('시가총액', ascending=False).head(20)
        names = stock.get_market_ticker_name
        rows = []
        for tic in cap.index:
            rows.append({'tic': tic, 'name': names(tic), 'mcap': int(cap.loc[tic, '시가총액'])})
        return pd.DataFrame(rows)
    except Exception:
        pass

    # fallback: 2026년 초 기준 코스피 시총 상위 20 (티커)
    fallback = [
        ('005930', '삼성전자'), ('000660', 'SK하이닉스'), ('373220', 'LG에너지솔루션'),
        ('207940', '삼성바이오로직스'), ('005380', '현대차'), ('000270', '기아'),
        ('068270', '셀트리온'), ('105560', 'KB금융'), ('055550', '신한지주'),
        ('035420', 'NAVER'), ('005490', 'POSCO홀딩스'), ('086790', '하나금융지주'),
        ('006400', '삼성SDI'), ('051910', 'LG화학'), ('035720', '카카오'),
        ('012330', '현대모비스'), ('032830', '삼성생명'), ('138040', '메리츠금융지주'),
        ('033780', 'KT&G'), ('003550', 'LG'),
    ]
    return pd.DataFrame([{'tic': t, 'name': n, 'mcap': 0} for t, n in fallback])


top20 = get_kospi_top20()
results = []

for _, row in top20.iterrows():
    yf_t = f"{str(row['tic']).zfill(6)}.KS"
    try:
        hist = yf.Ticker(yf_t).history(period='2y')
        if hist.empty or len(hist) < 60:
            continue
        hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
        r = check_signals(hist)
        if r is None:
            continue
        target_px = int(r['price'] * 1.03)
        results.append({
            '종목': row['name'],
            '티커': row['tic'],
            '시총': row['mcap'],
            '종가': int(r['price']),
            '3%목표가': target_px,
            '신호수': r['hit'],
            '해당신호': ','.join(r['signals']) if r['signals'] else '-',
            '스캘프점수': r['scalp_score'],
            'RSI': round(r['RSI'], 1),
            '1M': round(r['m1'], 1),
            '5D': round(r['m5'], 1),
            'ATR%': round(r['atr_pct'], 2),
            '20D고점여유%': round(r['room_high20'], 1),
            'BB상단여유%': round(r['room_bb'], 1),
            '고점DD': round(r['cur_dd'], 1),
            '거래량비': round(r['vol_ratio'], 2),
            '추세': '단기↑' if r['ma5_gt_20'] else '단기↓',
        })
    except Exception as e:
        print(f"ERR {row['name']}: {e}")

res = pd.DataFrame(results).sort_values('스캘프점수', ascending=False)

print('=' * 90)
print(f'  코스피 시총 TOP20 — 단기 3% 스캘프 적합도  |  {datetime.now().strftime("%Y-%m-%d")}')
print('=' * 90)
print(f"\n{'순위':<4} {'종목':<14} {'종가':>9} {'3%목표':>9} {'점수':>5} {'신호':>3} {'RSI':>5} {'5D':>6} {'ATR%':>5} {'고점여유':>7}  신호내역")
print('-' * 90)
for i, (_, r) in enumerate(res.iterrows(), 1):
    print(f"{i:<4} {r['종목']:<14} {r['종가']:>9,} {r['3%목표가']:>9,} {r['스캘프점수']:>5} {r['신호수']:>3} {r['RSI']:>5.0f} {r['5D']:>+5.1f}% {r['ATR%']:>5.1f} {r['20D고점여유%']:>+6.1f}%  {r['해당신호']}")

best = res.iloc[0]
print('\n' + '=' * 90)
print('  1순위 추천 (스캘프 점수 기준)')
print('=' * 90)
qty = int(10_000_000 / best['종가'])
print(f"  종목: {best['종목']} ({best['티커']})")
print(f"  종가: {best['종가']:,}원 → 3% 목표: {best['3%목표가']:,}원 (+{best['3%목표가']-best['종가']:,}원)")
print(f"  1,000만원 매수 가능 수량: 약 {qty}주 (실투자 {qty*best['종가']:,}원)")
print(f"  3% 익절 시 수익: 약 {int(qty*best['종가']*0.03):,}원 (세전)")
print(f"  스캘프점수: {best['스캘프점수']} | 신호 {best['신호수']}개 | {best['해당신호']}")

out = r'c:\Users\seaho\My project\My_investment\kospi_top20_scalp.csv'
res.to_csv(out, index=False, encoding='utf-8-sig')
print(f'\n  저장: kospi_top20_scalp.csv')
