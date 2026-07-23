# -*- coding: utf-8 -*-
"""하락장 대응 전략 분석"""
import pandas as pd
import yfinance as yf
import numpy as np
import sys
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = r'c:\Users\seaho\My project\My_investment\investment_backup_before_dividend.xlsx'
FX = 1530

hold = pd.read_excel(BACKUP, sheet_name='3. 종목현황', header=None).iloc[8:].copy()
hold.columns = ['계좌','번호','국가','티커','종목명','수량','평단가','_7','현재가','_9',
                '평가액','비중','배당','수익','수익률','카테고리','_16','_17']
hold['수량'] = pd.to_numeric(hold['수량'], errors='coerce')
hold['평단가'] = pd.to_numeric(hold['평단가'], errors='coerce')
hold['현재가'] = pd.to_numeric(hold['현재가'], errors='coerce')
hold['평가액'] = pd.to_numeric(hold['평가액'], errors='coerce')
hold['수익률'] = pd.to_numeric(hold['수익률'], errors='coerce')
hold = hold[(hold['수량'] > 0) & (hold['평가액'] > 0)]
total = hold['평가액'].sum()

def classify(name, cat, ticker, country):
    n = str(name)
    t = str(ticker)
    if t in ['현금','예금'] or str(cat) in ['현금','예금','예수금']:
        return '현금/예금'
    if any(k in n for k in ['커버드콜','커버드','타겟데일리','타겟위클리','데일리커버드']):
        return '커버드콜ETF'
    if any(k in n for k in ['TIGER','KODEX','SOL','ACE','RISE','KIWOOM']):
        if any(k in n for k in ['채권','국채','혼합','리츠','금융','배당']):
            return '배당/채권ETF'
        if '나스닥' in n or '테크' in n or 'S&P' in n or '슨피' in n.lower():
            return '성장ETF'
        return '기타ETF'
    if t in ['SCHD','QLD','SPCX']:
        return '미국ETF'
    if str(country) == '미국':
        return '미국직접'
    return '국내직접'

hold['유형'] = hold.apply(lambda r: classify(r['종목명'], r['카테고리'], r['티커'], r['국가']), axis=1)

# 유형별 집계
print('=' * 70)
print('  포트폴리오 구조 (하락장 대응 기준)')
print('=' * 70)
grp = hold.groupby('유형')['평가액'].sum().sort_values(ascending=False)
for t, v in grp.items():
    print(f'  {t:<16} {v/1e8:>6.2f}억  ({v/total*100:>5.1f}%)')
print(f'  {"합계":<16} {total/1e8:>6.2f}억')

# 시장 지수 최근 하락
indices = {'KOSPI': '^KS11', 'S&P500': '^GSPC', 'Nasdaq': '^IXIC', 'USD/KRW': 'KRW=X'}
print('\n── 주요 지수 최근 변동 ──')
for name, t in indices.items():
    h = yf.Ticker(t).history(period='6mo')
    if len(h) < 2: continue
    c = h['Close']
    d1m = (c.iloc[-1]/c.iloc[max(0,len(c)-22)]-1)*100 if len(c)>22 else 0
    d3m = (c.iloc[-1]/c.iloc[max(0,len(c)-66)]-1)*100 if len(c)>66 else 0
    dd = ((c - c.cummax())/c.cummax()).iloc[-1]*100
    print(f'  {name:<10}  1M {d1m:+.1f}%  3M {d3m:+.1f}%  고점대비 {dd:.1f}%')

# 직접투자 + 주요 ETF 현재 낙폭
def to_yf(ticker, country):
    t = str(ticker).strip()
    if country == '미국': return t
    return f'{t.zfill(6)}.KS' if t.isdigit() else f'{t}.KS'

def stock_dd(ticker, country):
    try:
        h = yf.Ticker(to_yf(ticker, country)).history(period='1y')
        if h.empty: return None, None, None
        c = h['Close']
        cur = ((c - c.cummax())/c.cummax()).iloc[-1]*100
        m1 = (c.iloc[-1]/c.iloc[max(0,len(c)-22)]-1)*100 if len(c)>22 else 0
        m3 = (c.iloc[-1]/c.iloc[max(0,len(c)-66)]-1)*100 if len(c)>66 else 0
        return cur, m1, m3
    except:
        return None, None, None

# 대표 종목 분석
key = hold.groupby(['티커','종목명','국가','유형']).agg(
    평가액=('평가액','sum'), 수익률=('수익률','mean'), 평단=('평단가','mean')
).reset_index().sort_values('평가액', ascending=False)

rows = []
for _, r in key.iterrows():
    cur, m1, m3 = stock_dd(r['티커'], r['국가'])
    pnl = r['수익률']*100 if pd.notna(r['수익률']) and abs(r['수익률'])<10 else None
    rows.append({
        '종목': str(r['종목명'])[:24], '유형': r['유형'], '평가액': int(r['평가액']),
        '고점DD': cur, '1M': m1, '3M': m3, 'pnl': pnl,
    })
df = pd.DataFrame(rows)

# 전략 분류
def action(row):
    t = row['유형']
    dd = row['고점DD'] or 0
    m1 = row['1M'] or 0
    name = row['종목']

    if t == '현금/예금':
        return '💰 보유', '하락장 탄력 + 추가매수 탄력'
    if t == '커버드콜ETF':
        if dd > -15:
            return '✅ 유지', '배당+방어, 하락장 핵심 — 매도 불필요'
        return '📥 분할매수', '낙폭 시 월배당 ETF 저가 매수 기회'
    if t == '배당/채권ETF':
        return '✅ 유지/소량추가', '채권·배당 — 하락장 방어, 분할 가능'
    if t == '성장ETF':
        if dd < -15 and m1 < -5:
            return '👀 관망→분할', '나스닥·테크 — 급락 시 1회 분할, 추격 금지'
        return '⏸ 관망', '이미 ETF로 노출 충분'
    if t in ['미국직접','국내직접','미국ETF']:
        spec = any(x in name for x in ['C3AI','SMR','IONQ','OKLO','COIN','JOBY','조비','누스케','팔란','로켓','하이브','에스엠','나이키','더본'])
        quality = any(x in name for x in ['삼성','애플','마이크','엔비디','TSMC','MSFT','기업은행','리얼티','기아'])
        if spec and dd < -30:
            return '⛔ 관망·축소', '投機주 — 물타기 금지, 반등 시 비중 축소'
        if quality and dd < -25 and m1 < 0:
            return '📥 1회 분할', '우량주 — 1~2회만 분할, 전량 추격 금지'
        if quality and dd > -15:
            return '✅ 유지', '우량·고점 근처 — 추가 불필요'
        return '⏸ 관망', '추가 매수 보류, 회복 확인'
    return '⏸ 관망', '—'

df['전략'], df['이유'] = zip(*df.apply(action, axis=1))

print('\n' + '=' * 70)
print('  종목별 대응 (평가액 Top 25)')
print('=' * 70)
print(f"  {'종목':<24} {'유형':<10} {'고점DD':>7} {'1M':>6}  {'전략'}")
print('  ' + '-' * 65)
for _, r in df.head(25).iterrows():
    dd = f"{r['고점DD']:.1f}%" if r['고점DD'] else 'N/A'
    m1 = f"{r['1M']:+.1f}%" if r['1M'] else 'N/A'
    print(f"  {r['종목']:<24} {r['유형']:<10} {dd:>7} {m1:>6}  {r['전략']}")

# 전략별 집계
print('\n── 전략별 금액 ──')
for act in ['💰 보유', '✅ 유지', '✅ 유지/소량추가', '📥 분할매수', '📥 1회 분할', '👀 관망→분할', '⏸ 관망', '⛔ 관망·축소']:
    sub = df[df['전략']==act]
    if len(sub):
        print(f'  {act}: {len(sub)}종목, {sub["평가액"].sum()/1e4:.0f}만원')

# 추가매수 우선순위
print('\n' + '=' * 70)
print('  추가 매수 우선순위 (하락장)')
print('=' * 70)
add = df[df['전략'].isin(['📥 분할매수','📥 1회 분할','👀 관망→분할','✅ 유지/소량추가'])].sort_values('고점DD')
for i, (_, r) in enumerate(add.head(8).iterrows(), 1):
    print(f"  {i}. {r['종목']} ({r['유형']}) — {r['전략']}: {r['이유']}")

avoid = df[df['전략']=='⛔ 관망·축소']
print('\n  ⛔ 추가매수 금지:')
for _, r in avoid.iterrows():
    print(f"     {r['종목']}")

print(f'\n  기준일: {datetime.now().strftime("%Y-%m-%d")}')
