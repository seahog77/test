# -*- coding: utf-8 -*-
"""코스피 TOP30 — 매수신호 상위5종 1/N 전액매수, +30%익절(익일)/-10%손절, 잔금 있을 때마다 재배치"""
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
TAKE_PROFIT = 0.30
STOP_LOSS = -0.10
TOP_N = 5
TRADE_DAYS = 504  # 약 2년
HIST_PERIOD = '3y'


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
    if qty <= 0:
        return 0, cash
    spent = qty * cost
    return qty, cash - spent


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


def get_bar(hist_map, tic, date):
    h = hist_map[tic]['hist']
    if date not in h.index:
        return None
    return h.loc[date]


def open_px(bar):
    o = bar['Open']
    return o if pd.notna(o) and o > 0 else bar['Close']


def check_sl(bar, avg_cost):
    sl = avg_cost * (1 + STOP_LOSS)
    o = open_px(bar)
    if o <= sl:
        return True, o, f'손절(갭){(o/avg_cost-1)*100:.1f}%'
    if bar['Low'] <= sl:
        return True, sl, f'손절{STOP_LOSS*100:.0f}%'
    return False, None, ''


def check_tp_reached(bar, avg_cost):
    tp = avg_cost * (1 + TAKE_PROFIT)
    if open_px(bar) >= tp:
        return True
    return bar['High'] >= tp


def deploy_cash(cash, picks, hist_map, today, positions, trades, pick_counts):
    """잔금 전액을 상위 N종에 1/N 배분 매수"""
    if cash <= 0 or picks.empty:
        return cash
    n = min(TOP_N, len(picks))
    picks = picks.head(n)
    per = cash / n
    for _, row in picks.iterrows():
        tic = row['tic']
        bar = get_bar(hist_map, tic, today)
        if bar is None:
            continue
        buy_px = open_px(bar)
        qty, leftover = buy_shares(per, buy_px)
        if qty <= 0:
            continue
        spent = per - leftover
        cash -= spent
        if tic in positions:
            pos = positions[tic]
            total_qty = pos['qty'] + qty
            pos['avg_cost'] = (pos['avg_cost'] * pos['qty'] + buy_px * qty) / total_qty
            pos['qty'] = total_qty
        else:
            positions[tic] = {
                'qty': qty, 'avg_cost': buy_px, 'hold_days': 0,
                'tp_pending': False, 'name': row['name'],
            }
        pick_counts[tic] = pick_counts.get(tic, 0) + 1
        trades.append({
            'date': today, 'side': 'BUY', 'tic': tic, 'name': row['name'],
            'qty': qty, 'price': buy_px, 'buy_hit': row['buy_hit'],
            'signals': row['signals'],
            'reason': f'TOP{n} 1/{n} 배분', 'amount': qty * buy_px,
        })
    return cash


# ── 데이터 ──
top30 = get_kospi_top30()
print(f'코스피 TOP30 종목 로드: {len(top30)}개')

hist_map = {}
for item in top30:
    tic = item['tic']
    yf_t = f'{str(tic).zfill(6)}.KS'
    try:
        h = yf.Ticker(yf_t).history(period=HIST_PERIOD)
        if h.empty or len(h) < 60:
            continue
        h.index = h.index.tz_localize(None) if h.index.tz else h.index
        hist_map[tic] = {'name': item['name'], 'hist': h}
    except Exception:
        pass

print(f'가격 데이터 확보: {len(hist_map)}종목')

all_dates = sorted(set().union(*[set(v['hist'].index) for v in hist_map.values()]))
trade_dates = all_dates[-TRADE_DAYS:]
start_date, end_date = trade_dates[0], trade_dates[-1]

cash = INITIAL
positions = {}  # tic -> {qty, avg_cost, hold_days, tp_pending, name}
trades, daily_log, pick_counts = [], [], {}
n_deploy_days = 0

for di in range(1, len(trade_dates)):
    prev_date = trade_dates[di - 1]
    today = trade_dates[di]
    day_sells = 0
    day_buys = 0

    # 1) 익절 예약 → 익일 시가 매도
    for tic in list(positions.keys()):
        pos = positions[tic]
        if not pos['tp_pending']:
            continue
        bar = get_bar(hist_map, tic, today)
        if bar is None:
            continue
        sell_px = open_px(bar)
        pnl = (sell_px / pos['avg_cost'] - 1) * 100
        cash += sell_shares(pos['qty'], sell_px)
        trades.append({
            'date': today, 'side': 'SELL', 'tic': tic, 'name': pos['name'],
            'qty': pos['qty'], 'price': sell_px, 'pnl_pct': pnl,
            'hold_days': pos['hold_days'],
            'reason': f'익절+{TAKE_PROFIT*100:.0f}%(익일시가)',
        })
        del positions[tic]
        day_sells += 1

    # 2) 손절 (당일 즉시) + 익절 도달 체크
    for tic in list(positions.keys()):
        pos = positions[tic]
        if pos['tp_pending']:
            continue
        bar = get_bar(hist_map, tic, today)
        if bar is None:
            continue
        pos['hold_days'] += 1
        hit, sell_px, sell_reason = check_sl(bar, pos['avg_cost'])
        if hit:
            pnl = (sell_px / pos['avg_cost'] - 1) * 100
            cash += sell_shares(pos['qty'], sell_px)
            trades.append({
                'date': today, 'side': 'SELL', 'tic': tic, 'name': pos['name'],
                'qty': pos['qty'], 'price': sell_px, 'pnl_pct': pnl,
                'hold_days': pos['hold_days'], 'reason': sell_reason,
            })
            del positions[tic]
            day_sells += 1
        elif check_tp_reached(bar, pos['avg_cost']):
            pos['tp_pending'] = True

    # 3) 잔금(매도 후·초기) 있으면 상위5에 1/N 전액 배분
    ranking = rank_stocks(hist_map, prev_date)
    deploy_trigger = cash >= 200_000 and (day_sells > 0 or len(positions) == 0)
    if deploy_trigger and not ranking.empty:
        before = cash
        cash = deploy_cash(cash, ranking, hist_map, today, positions, trades, pick_counts)
        if cash < before:
            n_deploy_days += 1
            day_buys += 1

    port = cash
    for tic, pos in positions.items():
        bar = get_bar(hist_map, tic, today)
        if bar is not None:
            port += pos['qty'] * bar['Close']

    daily_log.append({
        'date': today, 'cash': cash, 'portfolio': port,
        'n_positions': len(positions), 'day_sells': day_sells,
        'day_buys': day_buys,
        'top5': ' | '.join(ranking.head(TOP_N)['name'].tolist()) if len(ranking) else '',
    })

last_close_val = cash
for tic, pos in positions.items():
    bar = get_bar(hist_map, tic, end_date)
    if bar is not None:
        last_close_val += pos['qty'] * bar['Close']

sells = [t for t in trades if t['side'] == 'SELL']
buys = [t for t in trades if t['side'] == 'BUY']
wins = sum(1 for t in sells if t['pnl_pct'] > 0)
tp_cnt = sum(1 for t in sells if '익절' in t['reason'])
sl_cnt = sum(1 for t in sells if '손절' in t['reason'])

try:
    kospi = yf.Ticker('^KS11').history(start=start_date, end=end_date + pd.Timedelta(days=1))
    kospi.index = kospi.index.tz_localize(None) if kospi.index.tz else kospi.index
    bh = INITIAL * kospi['Close'].iloc[-1] / kospi['Close'].iloc[0]
except Exception:
    bh = None

print('=' * 90)
print(f'  코스피 TOP30 — 매수신호 상위5 / 잔금전액 1/5 / +30%익절 / -10%손절 / 잔금시 재매수 ({TRADE_DAYS//252}년)')
print(f'  기간: {start_date.strftime("%Y-%m-%d")} ~ {end_date.strftime("%Y-%m-%d")}  |  초기: {INITIAL:,}원')
print('=' * 90)
print('\n[규칙]')
print('  · 전일 종가: TOP30 매수신호 순위 → **상위 5종**')
print('  · 잔금 전액을 5등분(1/N)하여 당일 시가 매수 (현금 남기지 않음)')
print('  · 매도 후 잔금 발생 시 → 다시 상위5 판단·전액 1/5 배분')
print(f'  · 익절 +{TAKE_PROFIT*100:.0f}% → 익일 시가 / 손절 {STOP_LOSS*100:.0f}% → 당일 즉시')
print(f'  · 수수료 {COMM_RATE*100:.3f}% / 매도세 {TAX_RATE*100:.2f}%')

print('\n' + '=' * 90)
print('  결과')
print('=' * 90)
print(f"  최종 평가(종가)    : {last_close_val:,.0f}원  ({(last_close_val/INITIAL-1)*100:+.1f}%)")
print(f"  손익               : {last_close_val-INITIAL:+,.0f}원")
print(f"  매수/매도          : {len(buys)}회 / {len(sells)}회")
print(f"  잔금 재배치 일수   : {n_deploy_days}일")
print(f"  현재 보유 종목     : {len(positions)}개")
if sells:
    print(f"  매도 승률          : {wins/len(sells)*100:.0f}% ({wins}/{len(sells)})")
    print(f"  익절/손절          : {tp_cnt}회 / {sl_cnt}회")
    holds = [t['hold_days'] for t in sells]
    print(f"  평균 보유일        : {sum(holds)/len(holds):.1f}일")

if positions:
    print('\n  [미청산 보유]')
    for tic, pos in positions.items():
        bar = get_bar(hist_map, tic, end_date)
        unreal = (bar['Close']/pos['avg_cost']-1)*100 if bar is not None else 0
        flag = ' (익절예약)' if pos['tp_pending'] else ''
        print(f"    {pos['name']:<14} {pos['qty']:>4}주  평단 {pos['avg_cost']:>9,.0f}  "
              f"미실현 {unreal:+.1f}%{flag}")

if bh:
    print(f"\n  [비교] KOSPI 단순보유 : {bh:,.0f}원 ({(bh/INITIAL-1)*100:+.1f}%)")
print('\n  [vs 이전]')
print('    1위·잔금50%·+30%/-10% : 960만 (-4.0%)')
print('    1위·전액·익일매도     : 446만 (-55.4%)')
print(f"    5종·전액1/5·+30%/-10% : {last_close_val/10000:.0f}만 ({(last_close_val/INITIAL-1)*100:+.1f}%)")

daily = pd.DataFrame(daily_log)
daily['date'] = pd.to_datetime(daily['date'])
daily['month'] = daily['date'].dt.to_period('M')
print('\n  [월말 평가액]')
prev = INITIAL
for m, v in daily.groupby('month')['portfolio'].last().items():
    print(f'    {m}  {v:>12,.0f}원  ({(v/prev-1)*100:+.1f}%)')
    prev = v

print('\n  [매수 빈도 TOP8]')
for tic, cnt in sorted(pick_counts.items(), key=lambda x: -x[1])[:8]:
    print(f'    {hist_map[tic]["name"]:<14} {cnt:>3}회')

print('\n  [최근 매매 15건]')
for t in trades[-15:]:
    d = pd.Timestamp(t['date']).strftime('%Y-%m-%d')
    if t['side'] == 'BUY':
        print(f"    {d}  BUY  {t['name']:<12} {t['qty']:>4}주 @ {t['price']:>9,.0f}  {t['reason']}")
    else:
        print(f"    {d}  SELL {t['name']:<12} {t['qty']:>4}주 @ {t['price']:>9,.0f}  "
              f"{t['reason']}  ({t['hold_days']}일, {t['pnl_pct']:+.1f}%)")

base = r'c:\Users\seaho\My project\My_investment'
suffix = f'{TRADE_DAYS//252}y'
pd.DataFrame(trades).to_csv(f'{base}\\kospi30_top5_full_{suffix}_trades.csv', index=False, encoding='utf-8-sig')
daily.to_csv(f'{base}\\kospi30_top5_full_{suffix}_daily.csv', index=False, encoding='utf-8-sig')
print(f'\n  저장: kospi30_top5_full_{suffix}_trades.csv, kospi30_top5_full_{suffix}_daily.csv')
