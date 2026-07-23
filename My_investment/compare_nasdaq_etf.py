# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
import numpy as np
import sys
sys.stdout.reconfigure(encoding='utf-8')

BACKUP = r'c:\Users\seaho\My project\My_investment\investment_backup_before_dividend.xlsx'

US_GROWTH = ['IONQ','TSLA','AAPL','NVDA','MSFT','RKLB','PLTR','TSM','AI','COIN','SMR','OKLO','JOBY','NVO','ORCL']

def mdd(close):
    dd = (close - close.cummax()) / close.cummax()
    return dd.min() * 100, dd.iloc[-1] * 100

def stats(ticker, period='5y'):
    h = yf.Ticker(ticker).history(period=period)
    if h.empty:
        return None
    c = h['Close']
    m5, cur = mdd(c)
    ret = (c.iloc[-1] / c.iloc[0] - 1) * 100
    vol = c.pct_change().std() * np.sqrt(252) * 100
    div_y = yf.Ticker(ticker).info.get('dividendYield') or 0
    return {'ret': ret, 'mdd': m5, 'cur_dd': cur, 'vol': vol, 'div_y': div_y * 100 if div_y else 0}

etfs = [
    ('QQQ (나스닥100)', 'QQQ'),
    ('TIGER 나스닥100', '133690.KS'),
    ('KODEX 나스닥100', '379810.KS'),
    ('QLD (2배 레버리지)', 'QLD'),
    ('SCHD (배당)', 'SCHD'),
]

print('=' * 65)
print('  나스닥 ETF vs 직접투자(미국 성장주) 비교 — 5년')
print('=' * 65)
print(f"{'종목':<24} {'수익률':>8} {'MDD':>8} {'현재DD':>8} {'변동성':>8}")
print('-' * 65)

etf_stats = {}
for name, t in etfs:
    s = stats(t)
    if s:
        etf_stats[name] = s
        print(f"{name:<24} {s['ret']:>+7.1f}% {s['mdd']:>7.1f}% {s['cur_dd']:>7.1f}% {s['vol']:>7.1f}%")

rets, mdds, vols, cur_dds = [], [], [], []
for t in US_GROWTH:
    s = stats(t)
    if s:
        rets.append(s['ret'])
        mdds.append(s['mdd'])
        vols.append(s['vol'])
        cur_dds.append(s['cur_dd'])

print(f"{'미국 성장주 15종(균등)':<24} {np.mean(rets):>+7.1f}% {np.mean(mdds):>7.1f}% {np.mean(cur_dds):>7.1f}% {np.mean(vols):>7.1f}%")
print(f"{'미국 성장주 (중앙값)':<24} {np.median(rets):>+7.1f}% {np.median(mdds):>7.1f}%")

# win rate vs QQQ
qqq = stats('QQQ')
wins = sum(1 for t in US_GROWTH if stats(t) and stats(t)['ret'] > qqq['ret'])
print(f"\n5년 수익률 QQQ({qqq['ret']:+.1f}%) 초과 종목: {wins}/{len(US_GROWTH)}개")

# portfolio overlap
hold = pd.read_excel(BACKUP, sheet_name='3. 종목현황', header=None).iloc[8:]
hold['v'] = pd.to_numeric(hold[10], errors='coerce')
hold['name'] = hold[4]

nasdaq_etf = hold[hold['name'].astype(str).str.contains('나스닥', na=False) & (hold['v'] > 0)]
tech_etf = hold[hold['name'].astype(str).str.contains('테크TOP|AI테크', na=False) & (hold['v'] > 0)]

ETF_KW = ['TIGER','KODEX','SOL','ACE','RISE','KIWOOM','커버드','S&P','나스닥','테크TOP','배당','국채','하이일드']
def is_etf(n):
    return any(k in str(n) for k in ETF_KW)

direct = hold[(hold['v'] > 0) & ~hold['name'].apply(is_etf)]
total = hold[hold['v'] > 0]['v'].sum()

print('\n' + '=' * 65)
print('  현재 포트폴리오 나스닥/테크 노출')
print('=' * 65)
print(f"  총 자산:        {total:,.0f}원")
print(f"  직접투자:       {direct['v'].sum():,.0f}원 ({direct['v'].sum()/total*100:.1f}%)")
print(f"  나스닥 ETF:     {nasdaq_etf['v'].sum():,.0f}원 ({nasdaq_etf['v'].sum()/total*100:.1f}%)")
print(f"  테크 ETF:       {tech_etf['v'].sum():,.0f}원 ({tech_etf['v'].sum()/total*100:.1f}%)")
print(f"  → 나스닥+테크 ETF 합: {(nasdaq_etf['v'].sum()+tech_etf['v'].sum())/total*100:.1f}%")

print('\n  [보유 나스닥 ETF]')
for _, r in nasdaq_etf.iterrows():
    print(f"    {r['name']}: {r['v']:,.0f}원")

# 1yr comparison
print('\n' + '=' * 65)
print('  1년 수익률 비교')
print('=' * 65)
for name, t in etfs[:3]:
    s = stats(t, '1y')
    if s:
        print(f"  {name}: {s['ret']:+.1f}%  (MDD {s['mdd']:.1f}%)")
yr1 = [stats(t, '1y')['ret'] for t in US_GROWTH if stats(t, '1y')]
print(f"  미국 성장주 균등: {np.mean(yr1):+.1f}%")
