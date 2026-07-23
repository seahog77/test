# -*- coding: utf-8 -*-
"""2024상반기~2025상반기 — TOP7 분산, 익절 10/20/30% × 손절 -10% 비교"""
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
STOP_LOSS = -0.10
TOP_N = 7
START = pd.Timestamp('2024-01-02')
END = pd.Timestamp('2025-06-30')
SCENARIOS = [
    ('TP10', 0.10),
    ('TP20', 0.20),
    ('TP30', 0.30),
]


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


def check_sl(bar, avg_cost, stop_loss):
    sl = avg_cost * (1 + stop_loss)
    o = open_px(bar)
    if o <= sl:
        return True, o, f'손절(갭){(o/avg_cost-1)*100:.1f}%'
    if bar['Low'] <= sl:
        return True, sl, f'손절{stop_loss*100:.0f}%'
    return False, None, ''


def check_tp_reached(bar, avg_cost, take_profit):
    tp = avg_cost * (1 + take_profit)
    if open_px(bar) >= tp:
        return True
    return bar['High'] >= tp


def deploy_cash(cash, picks, hist_map, today, positions, trades, pick_counts, top_n):
    if cash <= 0 or picks.empty:
        return cash
    n = min(top_n, len(picks))
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
            'reason': f'TOP{n} 1/{n}',
        })
    return cash


def run_backtest(hist_map, trade_dates, take_profit, stop_loss=STOP_LOSS, top_n=TOP_N):
    cash = INITIAL
    positions = {}
    trades, daily_log, pick_counts = [], [], {}
    n_deploy = 0
    end_date = trade_dates[-1]

    for di in range(1, len(trade_dates)):
        prev_date = trade_dates[di - 1]
        today = trade_dates[di]
        day_sells = 0

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
                'reason': f'익절+{take_profit*100:.0f}%(익일시가)',
            })
            del positions[tic]
            day_sells += 1

        for tic in list(positions.keys()):
            pos = positions[tic]
            if pos['tp_pending']:
                continue
            bar = get_bar(hist_map, tic, today)
            if bar is None:
                continue
            pos['hold_days'] += 1
            hit, sell_px, sell_reason = check_sl(bar, pos['avg_cost'], stop_loss)
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
            elif check_tp_reached(bar, pos['avg_cost'], take_profit):
                pos['tp_pending'] = True

        ranking = rank_stocks(hist_map, prev_date)
        if cash >= 200_000 and (day_sells > 0 or len(positions) == 0) and not ranking.empty:
            before = cash
            cash = deploy_cash(cash, ranking, hist_map, today, positions, trades, pick_counts, top_n)
            if cash < before:
                n_deploy += 1

        port = cash
        for tic, pos in positions.items():
            bar = get_bar(hist_map, tic, today)
            if bar is not None:
                port += pos['qty'] * bar['Close']
        daily_log.append({'date': today, 'portfolio': port, 'n_pos': len(positions), 'cash': cash})

    last_val = cash
    for tic, pos in positions.items():
        bar = get_bar(hist_map, tic, end_date)
        if bar is not None:
            last_val += pos['qty'] * bar['Close']

    sells = [t for t in trades if t['side'] == 'SELL']
    wins = sum(1 for t in sells if t['pnl_pct'] > 0)
    return {
        'final': last_val,
        'return_pct': (last_val / INITIAL - 1) * 100,
        'buys': sum(1 for t in trades if t['side'] == 'BUY'),
        'sells': len(sells),
        'wins': wins,
        'win_rate': wins / len(sells) * 100 if sells else 0,
        'tp_cnt': sum(1 for t in sells if '익절' in t['reason']),
        'sl_cnt': sum(1 for t in sells if '손절' in t['reason']),
        'avg_hold': sum(t['hold_days'] for t in sells) / len(sells) if sells else 0,
        'n_deploy': n_deploy,
        'n_positions': len(positions),
        'trades': trades,
        'daily': pd.DataFrame(daily_log),
        'pick_counts': pick_counts,
    }


# ── 데이터 로드 ──
print('데이터 로드 중...')
top30 = get_kospi_top30()
hist_map = {}
for item in top30:
    tic = item['tic']
    try:
        h = yf.Ticker(f'{str(tic).zfill(6)}.KS').history(start='2023-01-01', end='2025-07-15')
        if h.empty or len(h) < 60:
            continue
        h.index = h.index.tz_localize(None) if h.index.tz else h.index
        hist_map[tic] = {'name': item['name'], 'hist': h}
    except Exception:
        pass

all_dates = sorted(set().union(*[set(v['hist'].index) for v in hist_map.values()]))
trade_dates = [d for d in all_dates if START <= d <= END]
if len(trade_dates) < 20:
    print('거래일 부족'); sys.exit(1)

kospi = yf.Ticker('^KS11').history(start=trade_dates[0], end=trade_dates[-1] + pd.Timedelta(days=1))
kospi.index = kospi.index.tz_localize(None) if kospi.index.tz else kospi.index
kospi_bh = INITIAL * kospi['Close'].iloc[-1] / kospi['Close'].iloc[0]
kospi_ret = (kospi_bh / INITIAL - 1) * 100

print('=' * 90)
print('  코스피 TOP30 — TOP7 분산 / 익절·손절 3시나리오 비교')
print(f'  기간: {trade_dates[0].strftime("%Y-%m-%d")} ~ {trade_dates[-1].strftime("%Y-%m-%d")}  (2024상반기~2025상반기)')
print(f'  초기자금: {INITIAL:,}원  |  보유: 상위7종 1/7 배분  |  손절: -10%')
print('=' * 90)

results = []
base = r'c:\Users\seaho\My project\My_investment'
for label, tp in SCENARIOS:
    print(f'\n  ▶ {label} (+{tp*100:.0f}%/-10%) 실행 중...')
    r = run_backtest(hist_map, trade_dates, take_profit=tp)
    r['label'] = label
    r['tp'] = tp
    results.append(r)
    pd.DataFrame(r['trades']).to_csv(
        f'{base}\\kospi30_top7_{label}_trades.csv', index=False, encoding='utf-8-sig')
    r['daily'].to_csv(
        f'{base}\\kospi30_top7_{label}_daily.csv', index=False, encoding='utf-8-sig')

print('\n' + '=' * 90)
print('  시나리오 비교 요약')
print('=' * 90)
print(f"\n  {'시나리오':<10} {'최종평가':>12} {'수익률':>8} {'매수/매도':>10} {'승률':>6} {'익절/손절':>10} {'평균보유':>8} {'보유중':>5}")
print('  ' + '-' * 75)
for r in results:
    print(f"  +{r['tp']*100:.0f}%/-10%  {r['final']:>11,.0f}원 {r['return_pct']:>+7.1f}% "
          f"{r['buys']:>4}/{r['sells']:<4} {r['win_rate']:>5.0f}% "
          f"{r['tp_cnt']:>4}/{r['sl_cnt']:<4} {r['avg_hold']:>6.1f}일 {r['n_positions']:>4}종")

print(f"\n  [비교] KOSPI 단순보유 : {kospi_bh:,.0f}원 ({kospi_ret:+.1f}%)")
print(f"         KOSPI 구간     : {kospi['Close'].iloc[0]:,.0f} → {kospi['Close'].iloc[-1]:,.0f}")

best = max(results, key=lambda x: x['final'])
print(f"\n  ★ 최고 수익: +{best['tp']*100:.0f}% 익절 → {best['final']:,.0f}원 ({best['return_pct']:+.1f}%)")

for r in results:
    print(f"\n  ── +{r['tp']*100:.0f}% 익절 월말 평가 ──")
    d = r['daily'].copy()
    d['date'] = pd.to_datetime(d['date'])
    d['month'] = d['date'].dt.to_period('M')
    prev = INITIAL
    for m, v in d.groupby('month')['portfolio'].last().items():
        print(f"    {m}  {v:>11,.0f}원  ({(v/prev-1)*100:+.1f}%)")
        prev = v

print('\n  저장: kospi30_top7_TP10/TP20/TP30_trades.csv, _daily.csv')
