# -*- coding: utf-8 -*-
"""KB금융(105560) — 매수·매도 신호 각 10가지 기반 1년 일별 백테스트"""
import pandas as pd
import yfinance as yf
import sys
import warnings

from signal_rules import check_buy_signals, check_sell_signals

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

TICKER = '105560.KS'
INITIAL = 10_000_000
COMM_RATE = 0.00015
TAX_RATE = 0.002
TAKE_PROFIT = 0.03
STOP_LOSS = -0.03


def buy_shares(cash, price):
    cost_per = price * (1 + COMM_RATE)
    qty = int(cash // cost_per)
    if qty <= 0:
        return 0, cash
    return qty, cash - qty * cost_per


def sell_shares(qty, price):
    return qty * price * (1 - COMM_RATE - TAX_RATE)


def run_backtest(hist, mode='dual'):
    """
    mode:
      'dual'     — 매수4+ & 매도2- → 매수 / 매도4+ or 익절·손절 → 매도 / 그 외 관망
      'buy_only' — (구버전) 매수신호만: 매수4+ / 매도2- / 익절·손절
      'dual_no_tp' — dual 규칙, 익절·손절 없음
    """
    hist = hist.copy()
    hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index

    trade_days = hist.tail(252)
    start_idx = hist.index.get_loc(trade_days.index[0])

    cash = INITIAL
    shares = 0
    avg_cost = 0.0
    n_buy = n_sell = n_hold = 0
    trades = []
    daily_log = []

    for i in range(start_idx, len(hist) - 1):
        day = hist.index[i]
        next_day = hist.index[i + 1]
        exec_price = hist.loc[next_day, 'Open']
        if pd.isna(exec_price) or exec_price <= 0:
            exec_price = hist.loc[next_day, 'Close']

        window = hist.iloc[: i + 1]
        buy = check_buy_signals(window)
        sell = check_sell_signals(window)
        if buy is None or sell is None:
            continue

        b_hit, s_hit = buy['hit'], sell['hit']
        pnl_pct = (exec_price / avg_cost - 1) if shares > 0 and avg_cost > 0 else 0

        action = '관망'
        reason = f'매수{b_hit}/매도{s_hit}'
        sold = False
        use_tp_sl = mode != 'dual_no_tp'

        # ── 매도 판단 ──
        if shares > 0:
            if use_tp_sl and pnl_pct >= TAKE_PROFIT:
                action, reason, sold = '매도', f'익절+{pnl_pct*100:.1f}%', True
            elif use_tp_sl and pnl_pct <= STOP_LOSS:
                action, reason, sold = '매도', f'손절{pnl_pct*100:.1f}%', True
            elif mode == 'buy_only' and b_hit <= 2:
                action, reason, sold = '매도', f'매수신호{b_hit}개(약함)', True
            elif mode in ('dual', 'dual_no_tp') and s_hit >= 4:
                action, reason, sold = '매도', f'매도신호{s_hit}개({",".join(sell["signals"])})', True

        if sold:
            cash += sell_shares(shares, exec_price)
            trades.append({
                'date': next_day, 'side': 'SELL', 'price': exec_price,
                'qty': shares, 'buy_sig': b_hit, 'sell_sig': s_hit,
                'reason': reason, 'pnl_pct': pnl_pct * 100,
            })
            shares, avg_cost = 0, 0
            n_sell += 1

        # ── 매수 판단 ──
        elif shares == 0:
            do_buy = False
            if mode == 'buy_only' and b_hit >= 4:
                do_buy, reason = True, f'매수신호{b_hit}개'
            elif mode in ('dual', 'dual_no_tp') and b_hit >= 4 and s_hit <= 2:
                do_buy, reason = True, f'매수{b_hit}/매도{s_hit}'

            if do_buy:
                qty, cash = buy_shares(cash, exec_price)
                if qty > 0:
                    shares, avg_cost = qty, exec_price
                    action = '매수'
                    trades.append({
                        'date': next_day, 'side': 'BUY', 'price': exec_price,
                        'qty': qty, 'buy_sig': b_hit, 'sell_sig': s_hit,
                        'reason': reason, 'pnl_pct': None,
                    })
                    n_buy += 1
                else:
                    n_hold += 1
            else:
                n_hold += 1
        else:
            n_hold += 1

        mkt_close = hist.loc[day, 'Close']
        daily_log.append({
            'date': day, 'buy_sig': b_hit, 'sell_sig': s_hit,
            'buy_list': ','.join(buy['signals']), 'sell_list': ','.join(sell['signals']),
            'action': action, 'reason': reason,
            'cash': cash, 'shares': shares, 'close': mkt_close,
            'portfolio': cash + shares * mkt_close,
        })

    last_close = hist.iloc[-1]['Close']
    final_value = cash + shares * last_close
    sells = [t for t in trades if t['side'] == 'SELL']
    wins = sum(1 for t in sells if t['pnl_pct'] > 0)

    return {
        'final': final_value,
        'return_pct': (final_value / INITIAL - 1) * 100,
        'cash': cash, 'shares': shares, 'last_close': last_close,
        'n_buy': n_buy, 'n_sell': n_sell, 'n_hold': n_hold,
        'win_rate': wins / len(sells) * 100 if sells else 0,
        'sells': len(sells), 'wins': wins,
        'daily': pd.DataFrame(daily_log),
        'trades': pd.DataFrame(trades),
    }


# ── 실행 ──
hist = yf.Ticker(TICKER).history(period='2y')
hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index

start_date = hist.tail(252).index[0].strftime('%Y-%m-%d')
end_date = hist.index[-1].strftime('%Y-%m-%d')

r_dual = run_backtest(hist, 'dual')           # ★ 매수·매도 신호 통합 (주요)
r_dual_nt = run_backtest(hist, 'dual_no_tp') # 통합, 익절·손절 없음
r_old = run_backtest(hist, 'buy_only')        # 구버전 (매수신호만)

bh_start = hist.tail(252).iloc[0]['Close']
bh_end = hist.iloc[-1]['Close']
bh_qty = int(INITIAL / (bh_start * (1 + COMM_RATE)))
bh_value = bh_qty * bh_end
bh_return = (bh_value / INITIAL - 1) * 100

print('=' * 85)
print(f'  KB금융(105560) 매수·매도 신호 통합 1년 백테스트')
print(f'  기간: {start_date} ~ {end_date}  |  초기: {INITIAL:,}원')
print('=' * 85)

print('\n[매매 규칙 — 매수·매도 10가지 통합 (시나리오 A)]')
print('  · 전일 종가 기준 매수·매도 신호 각 10가지 → 익일 시가 체결')
print('  · 매수: 매수신호 4개+ AND 매도신호 2개- → 전액 매수')
print('  · 매도: 매도신호 4개+ OR +3% 익절 OR -3% 손절')
print('  · 관망: 그 외 (신호 혼재, 보유 유지 등)')
print(f'  · 수수료 {COMM_RATE*100:.3f}% / 매도세 {TAX_RATE*100:.2f}%')

print('\n' + '-' * 85)
print(f"  {'시나리오':<32} {'최종평가':>13} {'수익률':>8} {'매수':>4} {'매도':>4} {'관망':>4} {'승률':>5}")
print('-' * 85)
for label, r in [
    ('A.매수·매도통합+익절/손절', r_dual),
    ('B.매수·매도통합 (익절/손절없음)', r_dual_nt),
    ('C.매수신호만 (구버전)', r_old),
    ('D.Buy & Hold', {'final': bh_value, 'return_pct': bh_return, 'n_buy': 0, 'n_sell': 0, 'n_hold': 0, 'win_rate': 0}),
]:
    if label.startswith('D'):
        print(f"  {label:<32} {r['final']:>12,.0f}원 {r['return_pct']:>+7.1f}%    -    -    -     -")
    else:
        print(f"  {label:<32} {r['final']:>12,.0f}원 {r['return_pct']:>+7.1f}% {r['n_buy']:>4} {r['n_sell']:>4} {r['n_hold']:>4} {r['win_rate']:>4.0f}%")

r = r_dual
print('\n' + '=' * 85)
print('  ★ 시나리오 A 상세 (매수·매도 10가지 통합)')
print('=' * 85)
print(f"  최종 평가액   : {r['final']:,.0f}원")
print(f"  손익          : {r['final']-INITIAL:+,.0f}원 ({r['return_pct']:+.1f}%)")
print(f"  현재 보유     : 현금 {r['cash']:,.0f}원 + {r['shares']}주 × {r['last_close']:,.0f}원")
print(f"  매수/매도/관망: {r['n_buy']}회 / {r['n_sell']}회 / {r['n_hold']}일")
print(f"  매도 승률     : {r['win_rate']:.0f}% ({r['wins']}/{r['sells']}회)")
print(f"  vs Buy&Hold   : {r['return_pct']-bh_return:+.1f}%p")
print(f"  vs 구버전(매수만): {r['return_pct']-r_old['return_pct']:+.1f}%p")

# 매도 사유 분류
if len(r['trades']) > 0:
    sells = r['trades'][r['trades']['side'] == 'SELL']
    print('\n  [매도 사유별]')
    for reason_prefix in ['매도신호', '익절', '손절']:
        sub = sells[sells['reason'].str.startswith(reason_prefix)]
        if len(sub):
            avg_pnl = sub['pnl_pct'].mean()
            print(f'    {reason_prefix}: {len(sub)}회  평균손익 {avg_pnl:+.1f}%')

# 구버전 vs 통합 비교
print('\n  [구버전 대비 변화]')
print(f"    구버전(매수신호만)  : {r_old['final']:,.0f}원 ({r_old['return_pct']:+.1f}%)  매매 {r_old['n_buy']+r_old['n_sell']}회")
print(f"    통합(매수+매도신호) : {r['final']:,.0f}원 ({r['return_pct']:+.1f}%)  매매 {r['n_buy']+r['n_sell']}회")

daily = r['daily'].copy()
daily['date'] = pd.to_datetime(daily['date'])
daily['month'] = daily['date'].dt.to_period('M')
monthly = daily.groupby('month')['portfolio'].last()

print('\n  [월말 평가액]')
prev = INITIAL
for m, v in monthly.items():
    chg = (v / prev - 1) * 100 if prev else 0
    print(f'    {m}  {v:>12,.0f}원  ({chg:+.1f}%)')
    prev = v

if len(r['trades']) > 0:
    print('\n  [최근 거래 10건]')
    for _, t in r['trades'].tail(10).iterrows():
        pnl = f"  {t['pnl_pct']:+.1f}%" if pd.notna(t['pnl_pct']) else ''
        print(f"    {pd.Timestamp(t['date']).strftime('%Y-%m-%d')}  {t['side']:<4} {int(t['qty']):>3}주 "
              f"@ {t['price']:>8,.0f}  매수{t['buy_sig']}/매도{t['sell_sig']}  {t['reason']}{pnl}")

# 신호 분포
print('\n  [1년간 일별 신호 분포]')
for label, col in [('매수', 'buy_sig'), ('매도', 'sell_sig')]:
    print(f'    [{label}]')
    for h in range(0, 11):
        cnt = (daily[col] == h).sum()
        if cnt:
            print(f'      {h}개: {cnt:>3}일')

# 저장
base = r'c:\Users\seaho\My project\My_investment'
r['trades'].to_csv(f'{base}\\kb_backtest_trades.csv', index=False, encoding='utf-8-sig')
r['daily'].to_csv(f'{base}\\kb_backtest_daily.csv', index=False, encoding='utf-8-sig')
print(f'\n  저장: kb_backtest_trades.csv, kb_backtest_daily.csv')
