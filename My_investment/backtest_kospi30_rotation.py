# -*- coding: utf-8 -*-
"""코스피 TOP30 — 매일 매수신호 1위 매수 → 익일 시가 무조건 매도 로테이션 1년 백테스트"""
import pandas as pd
import yfinance as yf
import sys
import warnings
from datetime import datetime

from signal_rules import check_buy_signals, check_sell_signals

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

INITIAL = 10_000_000
COMM_RATE = 0.00015
TAX_RATE = 0.002


def get_kospi_top30():
    try:
        from pykrx import stock
        today = datetime.now().strftime('%Y%m%d')
        cap = stock.get_market_cap_by_ticker(today, market='KOSPI')
        if cap.empty:
            cap = stock.get_market_cap_by_ticker(
                stock.get_nearest_business_day_in_a_week(today), market='KOSPI')
        cap = cap.sort_values('시가총액', ascending=False).head(30)
        name_fn = stock.get_market_ticker_name
        return [{'tic': t, 'name': name_fn(t)} for t in cap.index]
    except Exception:
        pass

    fallback = [
        ('005930', '삼성전자'), ('000660', 'SK하이닉스'), ('373220', 'LG에너지솔루션'),
        ('207940', '삼성바이오로직스'), ('005380', '현대차'), ('000270', '기아'),
        ('068270', '셀트리온'), ('105560', 'KB금융'), ('055550', '신한지주'),
        ('035420', 'NAVER'), ('005490', 'POSCO홀딩스'), ('086790', '하나금융지주'),
        ('006400', '삼성SDI'), ('051910', 'LG화학'), ('035720', '카카오'),
        ('012330', '현대모비스'), ('032830', '삼성생명'), ('138040', '메리츠금융지주'),
        ('033780', 'KT&G'), ('003550', 'LG'), ('009150', '삼성전기'),
        ('034730', 'SK'), ('096770', 'SK이노베이션'), ('015760', '한국전력'),
        ('316140', '우리금융지주'), ('010130', '고려아연'), ('024110', '기업은행'),
        ('011200', 'HMM'), ('017670', 'SK텔레콤'), ('028260', '삼성물산'),
    ]
    return [{'tic': t, 'name': n} for t, n in fallback]


def buy_shares(cash, price):
    cost = price * (1 + COMM_RATE)
    qty = int(cash // cost)
    return qty, cash - qty * cost if qty else 0


def sell_shares(qty, price):
    return qty * price * (1 - COMM_RATE - TAX_RATE)


def rank_stocks(hist_map, as_of_idx, date):
    """전일 종가 기준 TOP30 매수신호 순위"""
    rows = []
    for tic, info in hist_map.items():
        h = info['hist']
        if date not in h.index:
            continue
        loc = h.index.get_loc(date)
        window = h.iloc[: loc + 1]
        buy = check_buy_signals(window)
        sell = check_sell_signals(window)
        if buy is None:
            continue
        s_hit = sell['hit'] if sell else 99
        rows.append({
            'tic': tic, 'name': info['name'],
            'buy_hit': buy['hit'], 'sell_hit': s_hit,
            'net': buy['hit'] - s_hit,
            'signals': ','.join(buy['signals']),
            'ma_up': buy['ma5_gt_20'],
            'RSI': buy['RSI'],
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.sort_values(
        ['buy_hit', 'net', 'sell_hit', 'ma_up'],
        ascending=[False, False, True, False]
    ).reset_index(drop=True)
    df['rank'] = df.index + 1
    return df


# ── 데이터 수집 ──
top30 = get_kospi_top30()
print(f'코스피 TOP30 종목 로드: {len(top30)}개')

hist_map = {}
for item in top30:
    tic = item['tic']
    yf_t = f'{str(tic).zfill(6)}.KS'
    try:
        h = yf.Ticker(yf_t).history(period='2y')
        if h.empty or len(h) < 60:
            continue
        h.index = h.index.tz_localize(None) if h.index.tz else h.index
        hist_map[tic] = {'name': item['name'], 'hist': h}
    except Exception:
        pass

print(f'가격 데이터 확보: {len(hist_map)}종목')

# 공통 거래일 (1년 ≈ 252일)
all_dates = sorted(set().union(*[set(v['hist'].index) for v in hist_map.values()]))
trade_dates = all_dates[-252:]
start_date, end_date = trade_dates[0], trade_dates[-1]

cash = INITIAL
shares = 0
held_tic = None
held_qty = 0
held_open = 0.0

trades = []
daily_log = []
pick_counts = {}

for di in range(1, len(trade_dates)):
    prev_date = trade_dates[di - 1]   # 신호 기준일 (전일 종가)
    today = trade_dates[di]           # 체결일 (당일 시가)

    ranking = rank_stocks(hist_map, None, prev_date)
    if ranking.empty:
        continue
    top1 = ranking.iloc[0]

    # 당일 시가 조회
    def get_open(tic):
        h = hist_map[tic]['hist']
        if today not in h.index:
            return None
        p = h.loc[today, 'Open']
        return p if pd.notna(p) and p > 0 else h.loc[today, 'Close']

    # 1) 보유분 무조건 매도
    day_pnl = None
    if held_tic and held_qty > 0:
        sell_px = get_open(held_tic)
        if sell_px:
            proceeds = sell_shares(held_qty, sell_px)
            day_pnl = (sell_px / held_open - 1) * 100
            cash += proceeds
            trades.append({
                'date': today, 'side': 'SELL', 'tic': held_tic,
                'name': hist_map[held_tic]['name'], 'qty': held_qty,
                'price': sell_px, 'pnl_pct': day_pnl,
                'prev_buy_hit': trades[-1]['buy_hit'] if trades else None,
            })
            held_tic, held_qty, held_open = None, 0, 0

    # 2) 매수 1위 전액 매수
    buy_tic = top1['tic']
    buy_px = get_open(buy_tic)
    if buy_px and cash > 0:
        qty, cash = buy_shares(cash, buy_px)
        if qty > 0:
            held_tic, held_qty, held_open = buy_tic, qty, buy_px
            pick_counts[buy_tic] = pick_counts.get(buy_tic, 0) + 1
            trades.append({
                'date': today, 'side': 'BUY', 'tic': buy_tic,
                'name': top1['name'], 'qty': qty, 'price': buy_px,
                'pnl_pct': None, 'buy_hit': top1['buy_hit'],
                'sell_hit': top1['sell_hit'], 'signals': top1['signals'],
                'rank2': ranking.iloc[1]['name'] if len(ranking) > 1 else '',
                'rank2_hit': ranking.iloc[1]['buy_hit'] if len(ranking) > 1 else None,
            })

    # 종가 평가
    port = cash
    if held_tic and held_qty > 0:
        h = hist_map[held_tic]['hist']
        if today in h.index:
            port += held_qty * h.loc[today, 'Close']

    daily_log.append({
        'date': today, 'pick': top1['name'], 'buy_hit': top1['buy_hit'],
        'sell_hit': top1['sell_hit'], 'signals': top1['signals'],
        'held': hist_map[held_tic]['name'] if held_tic else '',
        'day_pnl': day_pnl, 'portfolio': port,
        'top3': ' | '.join(ranking.head(3)['name'].tolist()),
    })

# 마지막 날 보유분 종가 청산 (평가용)
last_close_val = cash
if held_tic and held_qty > 0:
    h = hist_map[held_tic]['hist']
    lc = h.loc[end_date, 'Close']
    last_close_val = cash + held_qty * lc

# 통계
sells = [t for t in trades if t['side'] == 'SELL' and t['pnl_pct'] is not None]
wins = sum(1 for t in sells if t['pnl_pct'] > 0)
avg_pnl = sum(t['pnl_pct'] for t in sells) / len(sells) if sells else 0

# 현금 보유 비교
cash_return = 0.0

print('=' * 90)
print('  코스피 TOP30 — 매일 매수신호 1위 매수 → 익일 시가 무조건 매도 (1년)')
print(f'  기간: {start_date.strftime("%Y-%m-%d")} ~ {end_date.strftime("%Y-%m-%d")}  |  초기: {INITIAL:,}원')
print('=' * 90)

print('\n[규칙]')
print('  · 전일 종가: TOP30 전 종목 매수신호 10가지 계산 → 1위 선정')
print('  · 순위: 매수신호수 ↓ → 순신호(매수-매도) ↓ → 매도신호수 ↑')
print('  · 당일 시가: 전날 보유 종목 무조건 매도 → 1위 종목 전액 매수')
print('  · 보유 기간: 정확히 1거래일 (오버나이트)')
print(f'  · 수수료 {COMM_RATE*100:.3f}% / 매도세 {TAX_RATE*100:.2f}%')

print('\n' + '=' * 90)
print('  결과')
print('=' * 90)
print(f"  최종 평가(종가기준) : {last_close_val:,.0f}원")
print(f"  수익률              : {(last_close_val/INITIAL-1)*100:+.1f}%")
print(f"  손익                : {last_close_val-INITIAL:+,.0f}원")
print(f"  1일 보유 거래       : {len(sells)}회  (매수 {sum(1 for t in trades if t['side']=='BUY')}회)")
print(f"  익일 매도 승률      : {wins/len(sells)*100:.0f}% ({wins}/{len(sells)}회)" if sells else '')
print(f"  1일 평균 수익률     : {avg_pnl:+.2f}% (시가→익일시가)")

if held_tic:
    print(f"  현재 보유          : {hist_map[held_tic]['name']} {held_qty}주 (마지막 매수, 아직 미매도)")

# 월별
daily = pd.DataFrame(daily_log)
daily['date'] = pd.to_datetime(daily['date'])
daily['month'] = daily['date'].dt.to_period('M')
monthly = daily.groupby('month')['portfolio'].last()
print('\n  [월말 평가액]')
prev = INITIAL
for m, v in monthly.items():
    print(f'    {m}  {v:>12,.0f}원  ({(v/prev-1)*100:+.1f}%)')
    prev = v

# 픽 빈도 TOP10
print('\n  [매수 1위 선정 빈도 TOP10]')
pick_df = pd.Series(pick_counts).sort_values(ascending=False).head(10)
for tic, cnt in pick_df.items():
    print(f'    {hist_map[tic]["name"]:<16} {cnt:>3}일  ({cnt/len(sells)*100:.0f}%)' if sells else f'    {hist_map[tic]["name"]} {cnt}')

# 최근 10거래
print('\n  [최근 매매 10건]')
for t in trades[-10:]:
    if t['side'] == 'BUY':
        print(f"    {pd.Timestamp(t['date']).strftime('%Y-%m-%d')}  BUY  {t['name']:<12} "
              f"{t['qty']:>4}주 @ {t['price']:>9,.0f}  신호{t['buy_hit']}개 ({t['signals']})")
    else:
        print(f"    {pd.Timestamp(t['date']).strftime('%Y-%m-%d')}  SELL {t['name']:<12} "
              f"{t['qty']:>4}주 @ {t['price']:>9,.0f}  {t['pnl_pct']:+.1f}%")

# 일별 수익 분포
if sells:
    pnls = [t['pnl_pct'] for t in sells]
    print('\n  [1일 수익률 분포]')
    print(f'    평균 {sum(pnls)/len(pnls):+.2f}%  |  최대 {max(pnls):+.1f}%  |  최소 {min(pnls):+.1f}%')
    print(f'    +3% 이상: {sum(1 for p in pnls if p>=3)}일  |  -3% 이하: {sum(1 for p in pnls if p<=-3)}일')

base = r'c:\Users\seaho\My project\My_investment'
pd.DataFrame(trades).to_csv(f'{base}\\kospi30_rotation_trades.csv', index=False, encoding='utf-8-sig')
daily.to_csv(f'{base}\\kospi30_rotation_daily.csv', index=False, encoding='utf-8-sig')
print(f'\n  저장: kospi30_rotation_trades.csv, kospi30_rotation_daily.csv')
