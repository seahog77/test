# -*- coding: utf-8 -*-
"""코스피 TOP30 — 매수신호 1위 매수 → 5거래일(1주) 후 무조건 매도"""
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
HOLD_DAYS = 5  # 1주 = 5거래일


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
    return qty, cash - qty * cost if qty else cash


def sell_shares(qty, price):
    return qty * price * (1 - COMM_RATE - TAX_RATE)


def rank_stocks(hist_map, date):
    rows = []
    for tic, info in hist_map.items():
        h = info['hist']
        if date not in h.index:
            continue
        loc = h.index.get_loc(date)
        buy = check_buy_signals(h.iloc[: loc + 1])
        sell = check_sell_signals(h.iloc[: loc + 1])
        if buy is None:
            continue
        s_hit = sell['hit'] if sell else 99
        rows.append({
            'tic': tic, 'name': info['name'],
            'buy_hit': buy['hit'], 'sell_hit': s_hit,
            'net': buy['hit'] - s_hit,
            'signals': ','.join(buy['signals']),
            'ma_up': buy['ma5_gt_20'],
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ['buy_hit', 'net', 'sell_hit', 'ma_up'],
        ascending=[False, False, True, False]
    ).reset_index(drop=True)


def get_open(hist_map, tic, date):
    h = hist_map[tic]['hist']
    if date not in h.index:
        return None
    p = h.loc[date, 'Open']
    return p if pd.notna(p) and p > 0 else h.loc[date, 'Close']


# ── 데이터 ──
top30 = get_kospi_top30()
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

all_dates = sorted(set().union(*[set(v['hist'].index) for v in hist_map.values()]))
trade_dates = all_dates[-252:]
start_date, end_date = trade_dates[0], trade_dates[-1]
date_to_idx = {d: i for i, d in enumerate(trade_dates)}

cash = INITIAL
held_tic, held_qty, avg_cost = None, 0, 0.0
buy_idx = None
trades, daily_log, pick_counts = [], [], {}

for di in range(1, len(trade_dates)):
    prev_date = trade_dates[di - 1]
    today = trade_dates[di]

    # 1) 5거래일 경과 → 무조건 매도
    if held_tic and held_qty > 0 and buy_idx is not None:
        if di - buy_idx >= HOLD_DAYS:
            sell_px = get_open(hist_map, held_tic, today)
            if sell_px:
                pnl = (sell_px / avg_cost - 1) * 100
                cash += sell_shares(held_qty, sell_px)
                trades.append({
                    'date': today, 'side': 'SELL', 'tic': held_tic,
                    'name': hist_map[held_tic]['name'], 'qty': held_qty,
                    'price': sell_px, 'pnl_pct': pnl, 'hold_days': di - buy_idx,
                    'reason': f'{HOLD_DAYS}일보유 후 매도',
                })
                held_tic, held_qty, avg_cost, buy_idx = None, 0, 0.0, None

    # 2) 미보유 → 매수 1위
    if held_tic is None and cash > 0:
        ranking = rank_stocks(hist_map, prev_date)
        if not ranking.empty:
            top1 = ranking.iloc[0]
            buy_px = get_open(hist_map, top1['tic'], today)
            if buy_px:
                qty, cash = buy_shares(cash, buy_px)
                if qty > 0:
                    held_tic, held_qty, avg_cost = top1['tic'], qty, buy_px
                    buy_idx = di
                    pick_counts[top1['tic']] = pick_counts.get(top1['tic'], 0) + 1
                    trades.append({
                        'date': today, 'side': 'BUY', 'tic': top1['tic'],
                        'name': top1['name'], 'qty': qty, 'price': buy_px,
                        'buy_hit': top1['buy_hit'], 'signals': top1['signals'],
                    })

    port = cash
    if held_tic and held_qty > 0:
        h = hist_map[held_tic]['hist']
        if today in h.index:
            port += held_qty * h.loc[today, 'Close']

    ranking = rank_stocks(hist_map, prev_date)
    daily_log.append({
        'date': today,
        'held': hist_map[held_tic]['name'] if held_tic else '현금',
        'hold_left': max(0, HOLD_DAYS - (di - buy_idx)) if buy_idx is not None else 0,
        'top1': ranking.iloc[0]['name'] if len(ranking) else '-',
        'portfolio': port,
    })

last_close_val = cash
if held_tic and held_qty > 0:
    lc = hist_map[held_tic]['hist'].loc[end_date, 'Close']
    last_close_val = cash + held_qty * lc

sells = [t for t in trades if t['side'] == 'SELL']
wins = sum(1 for t in sells if t['pnl_pct'] > 0)
avg_pnl = sum(t['pnl_pct'] for t in sells) / len(sells) if sells else 0

print('=' * 90)
print(f'  코스피 TOP30 — 매수신호 1위 → {HOLD_DAYS}거래일(1주) 후 무조건 매도')
print(f'  기간: {start_date.strftime("%Y-%m-%d")} ~ {end_date.strftime("%Y-%m-%d")}  |  초기: {INITIAL:,}원')
print('=' * 90)
print('\n[규칙] TOP30 매수신호 1위 / 전일 신호·당일 시가 / 5거래일 후 시가 매도 / 수수료·세금 반영')

print('\n' + '=' * 90)
print('  결과')
print('=' * 90)
print(f"  최종 평가     : {last_close_val:,.0f}원  ({(last_close_val/INITIAL-1)*100:+.1f}%)")
print(f"  손익          : {last_close_val-INITIAL:+,.0f}원")
print(f"  매수/매도     : {sum(1 for t in trades if t['side']=='BUY')} / {len(sells)}회")
print(f"  1주 승률      : {wins/len(sells)*100:.0f}% ({wins}/{len(sells)})" if sells else '')
print(f"  1주 평균 수익 : {avg_pnl:+.2f}%")
if held_tic:
    print(f"  현재 보유     : {hist_map[held_tic]['name']} (아직 {HOLD_DAYS}일 미경과)")

print('\n  [vs 다른 전략]')
print('    1일 보유 무조건 매도  : 446만 (-55.4%)')
print('    4+ / 익절3%·손절-3%  : 427만 (-57.3%)')
print(f'    1주 보유 무조건 매도  : {last_close_val/10000:.0f}만 ({(last_close_val/INITIAL-1)*100:+.1f}%)')

daily = pd.DataFrame(daily_log)
daily['date'] = pd.to_datetime(daily['date'])
print('\n  [월말 평가액]')
prev = INITIAL
for m, v in daily.groupby(daily['date'].dt.to_period('M'))['portfolio'].last().items():
    print(f'    {m}  {v:>12,.0f}원  ({(v/prev-1)*100:+.1f}%)')
    prev = v

print('\n  [1위 빈도 TOP8]')
for tic, cnt in sorted(pick_counts.items(), key=lambda x: -x[1])[:8]:
    print(f'    {hist_map[tic]["name"]:<14} {cnt}회')

if sells:
    pnls = [t['pnl_pct'] for t in sells]
    print(f'\n  [1주 수익률] 평균 {avg_pnl:+.2f}%  최대 {max(pnls):+.1f}%  최소 {min(pnls):+.1f}%')
    print(f'    +5% 이상: {sum(1 for p in pnls if p>=5)}회  |  -5% 이하: {sum(1 for p in pnls if p<=-5)}회')

print('\n  [최근 매매 8건]')
for t in trades[-8:]:
    d = pd.Timestamp(t['date']).strftime('%Y-%m-%d')
    if t['side'] == 'BUY':
        print(f"    {d}  BUY  {t['name']:<12} {t['qty']:>4}주 @ {t['price']:>9,.0f}  신호{t['buy_hit']}개")
    else:
        print(f"    {d}  SELL {t['name']:<12} {t['qty']:>4}주 @ {t['price']:>9,.0f}  {t['pnl_pct']:+.1f}%")

base = r'c:\Users\seaho\My project\My_investment'
pd.DataFrame(trades).to_csv(f'{base}\\kospi30_weekly_trades.csv', index=False, encoding='utf-8-sig')
daily.to_csv(f'{base}\\kospi30_weekly_daily.csv', index=False, encoding='utf-8-sig')
print(f'\n  저장: kospi30_weekly_trades.csv')
