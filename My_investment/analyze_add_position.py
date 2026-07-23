# -*- coding: utf-8 -*-
"""직접투자 종목 물타기/불타기/추격매수 분석"""
import pandas as pd
import yfinance as yf
import sys
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

BACKUP = r'c:\Users\seaho\My project\My_investment\investment_backup_before_dividend.xlsx'
FX = 1530

hold = pd.read_excel(BACKUP, sheet_name='3. 종목현황', header=None).iloc[8:].copy()
hold.columns = ['계좌','번호','국가','티커','종목명','수량','평단가','_7','현재가','_9',
                '평가액','투자비중','배당금','누적수익','총수익률','종목카테고리','_16','_17']
hold['수량'] = pd.to_numeric(hold['수량'], errors='coerce')
hold['평단가'] = pd.to_numeric(hold['평단가'], errors='coerce')
hold['현재가'] = pd.to_numeric(hold['현재가'], errors='coerce')
hold['평가액'] = pd.to_numeric(hold['평가액'], errors='coerce')
hold['총수익률'] = pd.to_numeric(hold['총수익률'], errors='coerce')
hold = hold[(hold['수량'] > 0) & (hold['평가액'] > 0)]

ETF_KW = ['TIGER','KODEX','SOL','ACE','RISE','KIWOOM','커버드','S&P','나스닥100','테크TOP',
          '배당','국채','하이일드','금융고배당','비만치료','양자컴퓨팅','2차전지','금현물','리츠부동산']
ETF_T = {'SCHD','QLD','SPCX'}

def is_etf(n, t):
    if str(t) in ETF_T or str(t) in ['현금','예금']: return True
    return any(k in str(n) for k in ETF_KW)

def to_yf(ticker, country):
    t = str(ticker).strip()
    return t if country == '미국' else (f'{t.zfill(6)}.KS' if t.isdigit() else f'{t}.KS')

def mdd_info(close):
    close = close.dropna()
    if len(close) < 20: return None
    rm = close.cummax()
    dd = (close - rm) / rm
    mdd = dd.min() * 100
    cur_dd = dd.iloc[-1] * 100
    trough_i = dd.idxmin()
    peak_i = close.loc[:trough_i].idxmax()
    rec = close.iloc[-1] >= close.loc[peak_i] * 0.98
    # MDD 대비 현재 위치 (0=저점, 100=완전회복)
    mdd_val = dd.min()
    recovery_pct = (dd.iloc[-1] - mdd_val) / abs(mdd_val) * 100 if mdd_val < 0 else 100
    return {'mdd5': mdd, 'cur_dd': cur_dd, 'recovery': rec, 'recovery_pct': recovery_pct,
            'peak': close.loc[peak_i], 'trough': close.loc[trough_i], 'now': close.iloc[-1]}

def ret_months(close, months):
    if len(close) < months * 15: return None
    ago = close.iloc[-1 - min(months * 21, len(close)-1)]
    return (close.iloc[-1] / ago - 1) * 100

direct = hold[~hold.apply(lambda r: is_etf(r['종목명'], r['티커']), axis=1)]
direct = direct[direct['티커'].astype(str).str.len() <= 6]
direct = direct[~direct['티커'].astype(str).isin(['현금','예금'])]

grp = direct.groupby(['티커','종목명','국가','종목카테고리']).agg(
    수량=('수량','sum'), 평단가=('평단가','mean'), 현재가=('현재가','first'),
    평가액=('평가액','sum'), 수익률=('총수익률','mean')
).reset_index()

rows = []
for _, r in grp.iterrows():
    yf_t = to_yf(r['티커'], r['국가'])
    try:
        hist = yf.Ticker(yf_t).history(period='5y')
        hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
        close = hist['Close']
    except Exception:
        continue
    m = mdd_info(close)
    if not m: continue

    # 평단 대비
    avg = r['평단가']
    cur = r['현재가'] if r['국가'] != '미국' else r['현재가']  # 원화 stored for KR
    if r['국가'] == '미국':
        cur_krw = close.iloc[-1] * FX
        avg_krw = avg * FX if avg < 10000 else avg  # 평단가 달러
        pnl_pct = (close.iloc[-1] / avg - 1) * 100 if avg > 0 else r['수익률'] * 100
    else:
        cur_krw = cur
        avg_krw = avg
        pnl_pct = (cur / avg - 1) * 100 if avg > 0 else r['수익률'] * 100

    r1m = ret_months(close, 1)
    r3m = ret_months(close, 3)
    r6m = ret_months(close, 6)

    # 점수화 (분석용, 투자 권유 아님)
    score_avgdown = 0   # 물타기 매력
    score_pyramid = 0 # 불타기 매력
    reasons = []

    # 물타기: 우량+깊은낙폭+MDD저점근처+단기반등
    if r['티커'] in ['005930','AAPL','MSFT','NVDA','TSM','O','024110','000270']:
        score_avgdown += 2
        reasons.append('우량/배당')
    if m['cur_dd'] < -30 and m['recovery_pct'] < 40:
        score_avgdown += 2
        reasons.append('깊은낙폭')
    if m['recovery_pct'] < 25:
        score_avgdown += 1
        reasons.append('MDD저점근접')
    if r3m and r3m > 5:
        score_avgdown += 1
        reasons.append('3M반등')
    if pnl_pct < -20:
        score_avgdown += 1
        reasons.append('평단대비손실')

    # 불타기: 회복완료+모멘텀+수익중
    if m['recovery']:
        score_pyramid += 2
        reasons.append('고점회복')
    if r6m and r6m > 15:
        score_pyramid += 2
        reasons.append('6M강세')
    if r3m and r3m > 10:
        score_pyramid += 1
        reasons.append('3M상승')
    if pnl_pct > 10:
        score_pyramid += 1
        reasons.append('수익중')

    # 추격매수 부적합 (投機/깊은손실+하락추세)
    avoid = False
    avoid_reason = []
    if r['티커'] in ['AI','SMR','IONQ','OKLO','JOBY','COIN','NVO','352820','041510','NKE']:
        if m['cur_dd'] < -40 and (not r3m or r3m < 0):
            avoid = True
            avoid_reason.append('投機주+하락지속')
    if m['cur_dd'] < -60:
        avoid = True
        avoid_reason.append('극심한낙폭')

    # 분류
    if avoid:
        action = '⛔ 보류/축소'
    elif score_pyramid >= 4 and score_pyramid > score_avgdown:
        action = '🔥 불타기(추세)'
    elif score_avgdown >= 4 and not avoid:
        action = '💧 물타기(분할)'
    elif score_avgdown >= 2 and m['cur_dd'] < -20:
        action = '👀 추격매수(소량)'
    else:
        action = '⏸ 관망'

    rows.append({
        '티커': r['티커'], '종목명': str(r['종목명'])[:20], '평가액': int(r['평가액']),
        '수익률': round(pnl_pct, 1), 'MDD5': round(m['mdd5'], 1), '현재낙폭': round(m['cur_dd'], 1),
        '회복': 'O' if m['recovery'] else 'X', '3M': round(r3m, 1) if r3m else None,
        '6M': round(r6m, 1) if r6m else None,
        '물타기': score_avgdown, '불타기': score_pyramid,
        '판단': action, '근거': ', '.join(reasons[:3]) or ', '.join(avoid_reason),
    })

df = pd.DataFrame(rows).sort_values('평가액', ascending=False)

print('=' * 72)
print('  직접투자 종목 — 물타기 / 불타기 / 추격매수 분석')
print('=' * 72)
print(f'  기준일: {datetime.now().strftime("%Y-%m-%d")}  |  투자 판단 보조용 (매수 권유 아님)\n')

for label, filt in [
    ('🔥 불타기 후보 (추세·회복 확인)', df['판단'].str.contains('불타기')),
    ('💧 물타기 후보 (우량·깊은낙폭·분할)', df['판단'].str.contains('물타기')),
    ('👀 추격매수 소량 (신중)', df['판단'].str.contains('추격')),
    ('⛔ 보류 (投機·하락 지속)', df['판단'].str.contains('보류')),
    ('⏸ 관망', df['판단'].str.contains('관망')),
]:
    sub = df[filt]
    if len(sub) == 0: continue
    print(f'\n{label}  ({len(sub)}개)')
    print(f"  {'종목':<18} {'평가액':>8} {'손익':>7} {'현재DD':>7} {'3M':>6} {'6M':>6}  근거")
    print('  ' + '-' * 66)
    for _, r in sub.sort_values('평가액', ascending=False).iterrows():
        print(f"  {r['종목명']:<18} {r['평가액']:>7,}만 {r['수익률']:>+6.1f}% {r['현재낙폭']:>6.1f}% "
              f"{str(r['3M'] or '-'):>5}% {str(r['6M'] or '-'):>5}%  {r['근거']}")

print('\n' + '=' * 72)
print('  [핵심 요약]')
print('=' * 72)

# top picks
bt = df[df['판단'].str.contains('불타기')].head(3)
wt = df[df['판단'].str.contains('물타기')].head(3)
av = df[df['판단'].str.contains('보류')]

if len(bt): print('\n  불타기: ', ', '.join(bt['종목명'].tolist()))
if len(wt): print('  물타기: ', ', '.join(wt['종목명'].tolist()))
if len(av): print('  보류:   ', ', '.join(av['종목명'].tolist()))

print('''
  [판단 기준]
  · 불ta기: 고점 회복 + 3~6개월 상승 추세 + 보유 종목 수익 중
  · 물타기: 우량주 + MDD 대비 저점 근처 + 평단 대비 손실 → 분할 매수
  · 추격매수: 반등 초입, 소량만
  · 보류: 投機/테마주 + -40% 이상 낙폭 + 하락 지속 → 물타기 위험

  ⚠️ 직접투자는 전체의 ~11%이나 MDD -50%↑ — 비중 한도(종목당 3~5%) 준수 권장
''')
