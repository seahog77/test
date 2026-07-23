# -*- coding: utf-8 -*-
"""코스피 TOP30 — 매수4+ 1위 매수, +3%익절/-3%손절 시만 매도"""
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
TAKE_PROFIT = 0.03
STOP_LOSS = -0.03
MIN_BUY_HIT = 4


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


def rank_candidates(hist_map, date):
    rows = []
    for tic, info in hist_map.items():
        h = info['hist']
        if date not in h.index:
            continue
        loc = h.index.get_loc(date)
        buy = check_buy_signals(h.iloc[: loc + 1])
        sell = check_sell_signals(h.iloc[: loc + 1])
        if buy is None or buy['hit'] < MIN_BUY_HIT:
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


def check_tp_sl(hist_row, avg_cost):
    """당일 OHLC로 +3%/-3% 체크 → (매도여부, 가격, 사유)"""
    tp = avg_cost * (1 + TAKE_PROFIT)
    sl = avg_cost * (1 + STOP_LOSS)
    o = hist_row['Open']
    h = hist_row['High']
    l = hist_row['Low']
    if pd.isna(o) or o <= 0:
        o = hist_row['Close']

    if o <= sl:
        return True, o, f'손절(갭){(o/avg_cost-1)*100:.1f}%'
    if o >= tp:
        return True, o, f'익절(갭)+{(o/avg_cost-1)*100:.1f}%'
    if l <= sl:
        return True, sl, f'손절{STOP_LOSS*100:.0f}%'
    if h >= tp:
        return True, tp, f'익절+{TAKE_PROFIT*100:.0f}%'
    return False, None, ''


def get_bar(hist_map, tic, date):
    h = hist_map[tic]['hist']
    if date not in h.index:
        return None
    return h.loc[date]


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

cash = INITIAL
held_tic, held_qty, avg_cost = None, 0, 0.0
hold_days = 0
trades, daily_log, pick_counts = [], [], {}
n_cash_days = 0

for di in range(1, len(trade_dates)):
    prev_date = trade_dates[di - 1]
    today = trade_dates[di]
    action = '관망'
    reason = ''

    # 1) 보유 중 → 익절/손절만 매도
    if held_tic and held_qty > 0:
        bar = get_bar(hist_map, held_tic, today)
        if bar is not None:
            hold_days += 1
            hit, sell_px, sell_reason = check_tp_sl(bar, avg_cost)
            if hit:
                pnl = (sell_px / avg_cost - 1) * 100
                cash += sell_shares(held_qty, sell_px)
                trades.append({
                    'date': today, 'side': 'SELL', 'tic': held_tic,
                    'name': hist_map[held_tic]['name'], 'qty': held_qty,
                    'price': sell_px, 'pnl_pct': pnl, 'hold_days': hold_days,
                    'reason': sell_reason,
                })
                held_tic, held_qty, avg_cost, hold_days = None, 0, 0.0, 0
                action, reason = '매도', sell_reason

    # 2) 미보유 → 매수4+ 1위 매수 (전일 종가 신호)
    if held_tic is None and cash > 0:
        ranking = rank_candidates(hist_map, prev_date)
        if not ranking.empty:
            top1 = ranking.iloc[0]
            bar = get_bar(hist_map, top1['tic'], today)
            if bar is not None:
                buy_px = bar['Open'] if pd.notna(bar['Open']) and bar['Open'] > 0 else bar['Close']
                qty, cash = buy_shares(cash, buy_px)
                if qty > 0:
                    held_tic, held_qty, avg_cost = top1['tic'], qty, buy_px
                    hold_days = 0
                    pick_counts[top1['tic']] = pick_counts.get(top1['tic'], 0) + 1
                    trades.append({
                        'date': today, 'side': 'BUY', 'tic': top1['tic'],
                        'name': top1['name'], 'qty': qty, 'price': buy_px,
                        'buy_hit': top1['buy_hit'], 'sell_hit': top1['sell_hit'],
                        'signals': top1['signals'], 'reason': f'매수{top1["buy_hit"]}개 1위',
                    })
                    action, reason = '매수', top1['name']
        else:
            n_cash_days += 1

    if held_tic is None and action == '관망' and cash > 0:
        n_cash_days += 1

    port = cash
    if held_tic and held_qty > 0:
        bar = get_bar(hist_map, held_tic, today)
        if bar is not None:
            port += held_qty * bar['Close']

    ranking_all = rank_candidates(hist_map, prev_date)
    daily_log.append({
        'date': today, 'action': action, 'reason': reason,
        'held': hist_map[held_tic]['name'] if held_tic else '현금',
        'candidates': len(ranking_all),
        'top_pick': ranking_all.iloc[0]['name'] if len(ranking_all) else '-',
        'portfolio': port,
    })

last_close_val = cash
if held_tic and held_qty > 0:
    lc = get_bar(hist_map, held_tic, end_date)['Close']
    last_close_val = cash + held_qty * lc

sells = [t for t in trades if t['side'] == 'SELL']
wins = sum(1 for t in sells if t['pnl_pct'] > 0)
tp_cnt = sum(1 for t in sells if '익절' in t['reason'])
sl_cnt = sum(1 for t in sells if '손절' in t['reason'])

print('=' * 90)
print('  코스피 TOP30 — 매수4+ 1위 / +3%익절·-3%손절 시만 매도 (1년)')
print(f'  기간: {start_date.strftime("%Y-%m-%d")} ~ {end_date.strftime("%Y-%m-%d")}  |  초기: {INITIAL:,}원')
print('=' * 90)
print('\n[규칙]')
print(f'  · 후보: 매수신호 {MIN_BUY_HIT}개+ 인 TOP30 종목만 → 1위 선정')
print('  · 매수: 미보유 & 후보 있음 → 전일 신호 1위, 당일 시가 매수')
print('  · 매도: +3% 익절 또는 -3% 손절 도달 시만 (당일 고저가 체크)')
print('  · 후보 없음 → 현금 보유')
print(f'  · 수수료 {COMM_RATE*100:.3f}% / 매도세 {TAX_RATE*100:.2f}%')

print('\n' + '=' * 90)
print('  결과')
print('=' * 90)
print(f"  최종 평가(종가)    : {last_close_val:,.0f}원  ({(last_close_val/INITIAL-1)*100:+.1f}%)")
print(f"  손익               : {last_close_val-INITIAL:+,.0f}원")
print(f"  매수/매도          : {sum(1 for t in trades if t['side']=='BUY')}회 / {len(sells)}회")
print(f"  매도 승률          : {wins/len(sells)*100:.0f}% ({wins}/{len(sells)})" if sells else '')
print(f"  익절/손절          : {tp_cnt}회 / {sl_cnt}회")
print(f"  현금 대기일        : {n_cash_days}일")
if held_tic:
    unreal = (get_bar(hist_map, held_tic, end_date)['Close']/avg_cost-1)*100
    print(f"  현재 보유          : {hist_map[held_tic]['name']} {held_qty}주  (미실현 {unreal:+.1f}%)")

print('\n  [vs 이전 전략 (매일 무조건 매도)]')
print('    무조건 익일매도  : 446만 (-55.4%)  250회 매매')
print(f"    익절/손절만 매도 : {last_close_val/10000:.0f}만 ({(last_close_val/INITIAL-1)*100:+.1f}%)  {len(trades)}회 매매")

daily = pd.DataFrame(daily_log)
daily['date'] = pd.to_datetime(daily['date'])
daily['month'] = daily['date'].dt.to_period('M')
print('\n  [월말 평가액]')
prev = INITIAL
for m, v in daily.groupby('month')['portfolio'].last().items():
    print(f'    {m}  {v:>12,.0f}원  ({(v/prev-1)*100:+.1f}%)')
    prev = v

print('\n  [1위 선정 빈도 TOP8]')
for tic, cnt in sorted(pick_counts.items(), key=lambda x: -x[1])[:8]:
    print(f'    {hist_map[tic]["name"]:<14} {cnt:>3}회')

if sells:
    hold_list = [t['hold_days'] for t in sells]
    print(f'\n  [보유일] 평균 {sum(hold_list)/len(hold_list):.1f}일  최대 {max(hold_list)}일')

print('\n  [최근 매매 10건]')
for t in trades[-10:]:
    d = pd.Timestamp(t['date']).strftime('%Y-%m-%d')
    if t['side'] == 'BUY':
        print(f"    {d}  BUY  {t['name']:<12} {t['qty']:>4}주 @ {t['price']:>9,.0f}  {t['reason']}")
    else:
        print(f"    {d}  SELL {t['name']:<12} {t['qty']:>4}주 @ {t['price']:>9,.0f}  "
              f"{t['reason']}  ({t['hold_days']}일보유, {t['pnl_pct']:+.1f}%)")

base = r'c:\Users\seaho\My project\My_investment'
pd.DataFrame(trades).to_csv(f'{base}\\kospi30_tpsl_trades.csv', index=False, encoding='utf-8-sig')
daily.to_csv(f'{base}\\kospi30_tpsl_daily.csv', index=False, encoding='utf-8-sig')
print(f'\n  저장: kospi30_tpsl_trades.csv, kospi30_tpsl_daily.csv')
