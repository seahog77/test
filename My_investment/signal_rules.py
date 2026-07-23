# -*- coding: utf-8 -*-
"""
매수·매도 각 10가지 기술적 신호 (scan_all_signals.py 등에서 공통 사용)

매수 10가지                    매도 10가지 (대칭)
─────────────────────────────────────────────────
1. GC (골든크로스)              1. DC (데드크로스)
2. 지지반등                     2. 저항거부
3. RSI탈출 (과매도→회복)        3. RSI이탈 (과매→하락)
4. MACD 상향돌파                4. MACD 하향돌파
5. BB 하단 회귀                 5. BB 상단 거부
6. 거래량 돌파 (상향)           6. 거래량 이탈 (하향)
7. W패턴 (쌍바닥)               7. M패턴 (쌍봉)
8. 200일선 지지                 8. 200일선 이탈
9. STO_GC (과매도 구간)         9. STO_DC (과매수 구간)
10. 피보나치 지지(50~61.8%)     10. 피보나치 저항(23.6~38.2%)
"""
import pandas as pd
import numpy as np


BUY_NAMES = ['GC', '지지반등', 'RSI탈출', 'MACD', 'BB회귀', '거래량돌파', 'W패턴', '200일선', 'STO_GC', '피보나치']
SELL_NAMES = ['DC', '저항거부', 'RSI이탈', 'MACD', 'BB거부', '거래량이탈', 'M패턴', '200일선', 'STO_DC', '피보나치']


def prepare_indicators(df):
    """OHLCV → 지표 DataFrame (최소 30행 필요)"""
    close = df['Close']
    high = df['High']
    low = df['Low']

    out = df.copy()
    out['MA5'] = close.rolling(5).mean()
    out['MA20'] = close.rolling(20).mean()
    out['MA200'] = close.rolling(200).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    out['RSI'] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out['MACD'] = ema12 - ema26
    out['MACD_signal'] = out['MACD'].ewm(span=9, adjust=False).mean()

    out['BB_mid'] = close.rolling(20).mean()
    std = close.rolling(20).std()
    out['BB_lower'] = out['BB_mid'] - 2 * std
    out['BB_upper'] = out['BB_mid'] + 2 * std

    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    out['STO_K'] = 100 * (close - low14) / (high14 - low14).replace(0, np.nan)
    out['STO_D'] = out['STO_K'].rolling(3).mean()

    out = out.dropna(subset=['MA20', 'RSI', 'MACD', 'BB_mid', 'STO_K'])
    if len(out) < 30:
        return None
    return out


def _find_troughs(r90):
    troughs = []
    for i in range(2, len(r90) - 2):
        l = r90.iloc[i]['Low']
        if l <= r90.iloc[i - 1]['Low'] and l <= r90.iloc[i - 2]['Low'] and l <= r90.iloc[i + 1]['Low']:
            troughs.append((r90.index[i], l))
    return troughs


def _find_peaks(r90):
    peaks = []
    for i in range(2, len(r90) - 2):
        h = r90.iloc[i]['High']
        if h >= r90.iloc[i - 1]['High'] and h >= r90.iloc[i - 2]['High'] and h >= r90.iloc[i + 1]['High']:
            peaks.append((r90.index[i], h))
    return peaks


def check_buy_signals(df):
    """매수 신호 10가지 → dict[name -> bool]"""
    df = prepare_indicators(df)
    if df is None:
        return None

    last, prev = df.iloc[-1], df.iloc[-2]
    recent = df.tail(60)
    close = df['Close']
    signals = {}

    # 1 골든크로스
    s1 = False
    for i in range(-10, 0):
        if df.iloc[i - 1]['MA5'] <= df.iloc[i - 1]['MA20'] and df.iloc[i]['MA5'] > df.iloc[i]['MA20']:
            s1 = True
            break
    signals['GC'] = s1

    # 2 지지선 반등
    support = recent['Low'].min()
    bounce = last['Close'] > prev['Close'] and last['Low'] <= support * 1.03
    signals['지지반등'] = last['Close'] <= support * 1.05 and bounce

    # 3 RSI 과매도 탈출
    rsi_low = df['RSI'].tail(10).min() <= 35
    signals['RSI탈출'] = rsi_low and last['RSI'] > 38 and last['Close'] > prev['Close']

    # 4 MACD 상향
    s4 = False
    for i in range(-10, 0):
        if df.iloc[i - 1]['MACD'] <= df.iloc[i - 1]['MACD_signal'] and df.iloc[i]['MACD'] > df.iloc[i]['MACD_signal']:
            s4 = True
            break
    signals['MACD'] = s4

    # 5 볼린저 하단 회귀
    touch = (recent['Low'] <= recent['BB_lower'] * 1.02).any()
    signals['BB회귀'] = touch and last['Close'] > prev['Close'] and last['Close'] > last['BB_lower']

    # 6 거래량 돌파 (상향)
    resistance = recent['High'].max()
    vol_avg = recent['Volume'].mean()
    signals['거래량돌파'] = last['Close'] >= resistance * 0.99 and last['Volume'] >= vol_avg * 1.5

    # 7 W패턴
    r90 = df.tail(90)
    troughs = _find_troughs(r90)
    w_ok = False
    if len(troughs) >= 2:
        t1, t2 = troughs[-2], troughs[-1]
        if abs(t1[1] - t2[1]) / max(t1[1], 1) < 0.05:
            mid_high = r90.loc[t1[0]:t2[0]]['High'].max()
            w_ok = last['Close'] > mid_high * 0.98
    signals['W패턴'] = w_ok

    # 8 200일선 지지
    if pd.notna(last['MA200']):
        signals['200일선'] = abs(last['Close'] - last['MA200']) / last['MA200'] < 0.05 and last['Close'] > prev['Close']
    else:
        signals['200일선'] = False

    # 9 스토캐스틱 골든크로스 (과매도)
    s9 = False
    for i in range(-10, 0):
        a, b = df.iloc[i - 1], df.iloc[i]
        if (a['STO_K'] <= 25 or a['STO_D'] <= 25) and a['STO_K'] <= a['STO_D'] and b['STO_K'] > b['STO_D']:
            s9 = True
            break
    signals['STO_GC'] = s9

    # 10 피보나치 지지 (50~61.8% 되돌림)
    lb = df.tail(120)
    sh, sl = lb['High'].max(), lb['Low'].min()
    diff = sh - sl
    fib50 = sh - diff * 0.5
    fib618 = sh - diff * 0.618
    signals['피보나치'] = fib618 * 0.98 <= last['Close'] <= fib50 * 1.02 and last['Close'] > prev['Close']

    hit_list = [k for k, v in signals.items() if v]
    cur_dd = ((close - close.cummax()) / close.cummax()).iloc[-1] * 100
    m1 = (close.iloc[-1] / close.iloc[max(-22, -len(close))] - 1) * 100 if len(close) > 5 else 0

    return {
        'date': df.index[-1].strftime('%Y-%m-%d'),
        'price': last['Close'],
        'hit': sum(signals.values()),
        'signals': hit_list,
        'detail': signals,
        'RSI': last['RSI'],
        'cur_dd': cur_dd,
        'm1': m1,
        'ma5_gt_20': last['MA5'] > last['MA20'],
    }


def check_sell_signals(df):
    """매도 신호 10가지 → dict[name -> bool]"""
    df = prepare_indicators(df)
    if df is None:
        return None

    last, prev = df.iloc[-1], df.iloc[-2]
    recent = df.tail(60)
    close = df['Close']
    signals = {}

    # 1 데드크로스
    s1 = False
    for i in range(-10, 0):
        if df.iloc[i - 1]['MA5'] >= df.iloc[i - 1]['MA20'] and df.iloc[i]['MA5'] < df.iloc[i]['MA20']:
            s1 = True
            break
    signals['DC'] = s1

    # 2 저항선 거부
    resistance = recent['High'].max()
    rejection = last['Close'] < prev['Close'] and last['High'] >= resistance * 0.97
    signals['저항거부'] = last['Close'] >= resistance * 0.92 and rejection

    # 3 RSI 과매수 이탈
    rsi_high = df['RSI'].tail(10).max() >= 65
    signals['RSI이탈'] = rsi_high and last['RSI'] < 62 and last['Close'] < prev['Close']

    # 4 MACD 하향
    s4 = False
    for i in range(-10, 0):
        if df.iloc[i - 1]['MACD'] >= df.iloc[i - 1]['MACD_signal'] and df.iloc[i]['MACD'] < df.iloc[i]['MACD_signal']:
            s4 = True
            break
    signals['MACD'] = s4

    # 5 볼린저 상단 거부
    touch_upper = (recent['High'] >= recent['BB_upper'] * 0.98).any()
    signals['BB거부'] = touch_upper and last['Close'] < prev['Close'] and last['Close'] < last['BB_upper']

    # 6 거래량 이탈 (지지 붕괴)
    support = recent['Low'].min()
    vol_avg = recent['Volume'].mean()
    signals['거래량이탈'] = (
        last['Close'] <= support * 1.01
        and last['Close'] < prev['Close']
        and last['Volume'] >= vol_avg * 1.5
    )

    # 7 M패턴 (쌍봉)
    r90 = df.tail(90)
    peaks = _find_peaks(r90)
    m_ok = False
    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        if abs(p1[1] - p2[1]) / max(p1[1], 1) < 0.05:
            mid_low = r90.loc[p1[0]:p2[0]]['Low'].min()
            m_ok = last['Close'] < mid_low * 1.02
    signals['M패턴'] = m_ok

    # 8 200일선 이탈·저항
    if pd.notna(last['MA200']):
        near = abs(last['Close'] - last['MA200']) / last['MA200'] < 0.05
        reject = last['Close'] < prev['Close'] and last['High'] >= last['MA200'] * 0.98
        break_below = prev['Close'] >= last['MA200'] and last['Close'] < last['MA200']
        signals['200일선'] = break_below or (near and reject)
    else:
        signals['200일선'] = False

    # 9 스토캐스틱 데드크로스 (과매수)
    s9 = False
    for i in range(-10, 0):
        a, b = df.iloc[i - 1], df.iloc[i]
        if (a['STO_K'] >= 75 or a['STO_D'] >= 75) and a['STO_K'] >= a['STO_D'] and b['STO_K'] < b['STO_D']:
            s9 = True
            break
    signals['STO_DC'] = s9

    # 10 피보나치 저항 (23.6~38.2% 되돌림 구간에서 하락)
    lb = df.tail(120)
    sh, sl = lb['High'].max(), lb['Low'].min()
    diff = sh - sl
    fib382 = sh - diff * 0.382
    fib236 = sh - diff * 0.236
    signals['피보나치'] = fib236 * 0.98 <= last['Close'] <= fib382 * 1.02 and last['Close'] < prev['Close']

    hit_list = [k for k, v in signals.items() if v]
    cur_dd = ((close - close.cummax()) / close.cummax()).iloc[-1] * 100
    m1 = (close.iloc[-1] / close.iloc[max(-22, -len(close))] - 1) * 100 if len(close) > 5 else 0

    return {
        'date': df.index[-1].strftime('%Y-%m-%d'),
        'price': last['Close'],
        'hit': sum(signals.values()),
        'signals': hit_list,
        'detail': signals,
        'RSI': last['RSI'],
        'cur_dd': cur_dd,
        'm1': m1,
        'ma5_gt_20': last['MA5'] > last['MA20'],
    }


def check_all_signals(df):
    """매수·매도 신호 동시 계산 + 종합 판단"""
    buy = check_buy_signals(df)
    sell = check_sell_signals(df)
    if buy is None or sell is None:
        return None

    net = buy['hit'] - sell['hit']
    if sell['hit'] >= 4:
        action = '매도검토'
    elif buy['hit'] >= 4 and sell['hit'] <= 2:
        action = '매수검토'
    elif sell['hit'] >= buy['hit'] + 2:
        action = '매도우위'
    elif buy['hit'] >= sell['hit'] + 2:
        action = '매수우위'
    else:
        action = '관망'

    return {
        'buy': buy,
        'sell': sell,
        'net': net,
        'action': action,
    }


def check_signals(df):
    """하위 호환 — 매수 신호만 (기존 backtest 등)"""
    return check_buy_signals(df)
