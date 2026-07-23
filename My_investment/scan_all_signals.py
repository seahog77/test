# -*- coding: utf-8 -*-
"""보유 전 종목 매수·매도 신호 각 10가지 일괄 점검"""
import pandas as pd
import yfinance as yf
import sys
import warnings
from datetime import datetime

from signal_rules import check_all_signals, BUY_NAMES, SELL_NAMES

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

BACKUP = r'c:\Users\seaho\My project\My_investment\investment_backup_before_dividend.xlsx'


def to_yf(ticker, country):
    t = str(ticker).strip()
    if t in ['현금', '예금', 'nan']:
        return None
    if country == '미국':
        return t
    if len(t) <= 6:
        return f'{t.zfill(6)}.KS' if t.isdigit() else f'{t}.KS'
    return None


# ── 보유종목 로드 ──
hold = pd.read_excel(BACKUP, sheet_name='3. 종목현황', header=None).iloc[8:]
hold.columns = ['acct', 'n', 'country', 'tic', 'name', 'qty', 'avg', '_7', 'px', '_9', 'val', 'w', 'd', 'p', 'ret', 'cat', 'a', 'b']
hold['val'] = pd.to_numeric(hold['val'], errors='coerce')
hold = hold[hold['val'] > 0]

grp = hold.groupby(['tic', 'name', 'country', 'cat']).agg(
    val=('val', 'sum'), accts=('acct', lambda x: '/'.join(sorted(set(str(a) for a in x if pd.notna(a)))))
).reset_index().sort_values('val', ascending=False)

results = []
errors = []

for _, row in grp.iterrows():
    yf_t = to_yf(row['tic'], row['country'])
    if not yf_t:
        continue
    try:
        hist = yf.Ticker(yf_t).history(period='2y')
        if hist.empty or len(hist) < 60:
            errors.append((row['name'], '데이터부족'))
            continue
        hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
        r = check_all_signals(hist)
        if r is None:
            errors.append((row['name'], '계산실패'))
            continue
        buy, sell = r['buy'], r['sell']
        results.append({
            '종목': str(row['name'])[:28],
            '티커': row['tic'],
            '계좌': str(row['accts'])[:20],
            '평가액': int(row['val']),
            '종가': int(buy['price']),
            '매수신호': buy['hit'],
            '매수해당': ','.join(buy['signals']) if buy['signals'] else '-',
            '매도신호': sell['hit'],
            '매도해당': ','.join(sell['signals']) if sell['signals'] else '-',
            '순신호': r['net'],
            '판단': r['action'],
            'RSI': round(buy['RSI'], 1),
            '고점DD': round(buy['cur_dd'], 1),
            '1M': round(buy['m1'], 1),
            '추세': '단기↑' if buy['ma5_gt_20'] else '단기↓',
        })
    except Exception as e:
        errors.append((row['name'], str(e)[:30]))

res = pd.DataFrame(results)

print('=' * 90)
print(f'  보유 전 종목 매수·매도 신호 분석 (각 10가지)  |  {datetime.now().strftime("%Y-%m-%d")}')
print(f'  분석 종목: {len(res)}개')
print('=' * 90)

print('\n[매수 10가지] GC, 지지반등, RSI탈출, MACD, BB회귀, 거래량돌파, W패턴, 200일선, STO_GC, 피보나치')
print('[매도 10가지] DC, 저항거부, RSI이탈, MACD, BB거부, 거래량이탈, M패턴, 200일선, STO_DC, 피보나치')

# 매도 신호 강함
print('\n▶ 매도 신호 4개+ [매도 검토]')
sell_strong = res[res['매도신호'] >= 4].sort_values('평가액', ascending=False)
if len(sell_strong):
    for _, r in sell_strong.iterrows():
        print(f"  · {r['종목']:<24} 매도{r['매도신호']} 매수{r['매수신호']} ({r['매도해당']})  [{r['판단']}]")
else:
    print('  (해당 없음)')

# 매수 신호 강함 & 매도 약함
print('\n▶ 매수 4+ & 매도 2- [매수 검토]')
buy_strong = res[(res['매수신호'] >= 4) & (res['매도신호'] <= 2)].sort_values('평가액', ascending=False)
for _, r in buy_strong.iterrows():
    print(f"  · {r['종목']:<24} 매수{r['매수신호']} 매도{r['매도신호']} ({r['매수해당']})")

# 관망 (신호 혼재)
print('\n▶ 매수·매도 모두 2~3개 [관망]')
mid = res[(res['매수신호'].between(2, 3)) & (res['매도신호'].between(2, 3))].sort_values('평가액', ascending=False)
for _, r in mid.head(10).iterrows():
    print(f"  · {r['종목']:<24} 매수{r['매수신호']} 매도{r['매도신호']}")
if len(mid) > 10:
    print(f'  ... 외 {len(mid)-10}종목')

# 신호별 빈도
print('\n' + '=' * 90)
print('  신호별 해당 종목 수')
print('=' * 90)
print('  [매수]')
for s in BUY_NAMES:
    print(f'    {s:<10} {res["매수해당"].str.contains(s, na=False).sum():>3}종목')
print('  [매도]')
for s in SELL_NAMES:
    print(f'    {s:<10} {res["매도해당"].str.contains(s, na=False).sum():>3}종목')

out = r'c:\Users\seaho\My project\My_investment\signal_scan_all.csv'
res.to_csv(out, index=False, encoding='utf-8-sig')
print(f'\n  저장: signal_scan_all.csv')

if errors:
    print(f'  [분석불가] {len(errors)}건')
