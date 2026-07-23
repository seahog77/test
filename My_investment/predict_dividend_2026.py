# -*- coding: utf-8 -*-
"""2026년 월별 배당금 예측 분석"""
import pandas as pd
import yfinance as yf
from datetime import datetime
from collections import defaultdict
import sys
import warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

FILE = r'c:\Users\seaho\My project\My_investment\investment.xlsx'
YEAR = 2026
FX = 1530  # 엑셀 기준 환율

# ── 보유종목 로드 ──
df = pd.read_excel(FILE, sheet_name='3. 종목현황', header=None)
data = df.iloc[8:].copy()
data.columns = ['계좌','번호','국가','티커','종목명','수량','평단가','_7','현재가','_9','평가액','투자비중','배당금','누적수익','총수익률','종목카테고리','_16','_17']
data['평가액'] = pd.to_numeric(data['평가액'], errors='coerce')
data['수량'] = pd.to_numeric(data['수량'], errors='coerce')
data = data[data['평가액'] > 0]

# 티커별 수량 합산
holdings = data.groupby(['티커','종목명','국가','종목카테고리'], dropna=False).agg(
    수량=('수량','sum'), 평가액=('평가액','sum')
).reset_index()

# 현금/예금 분리
cash_mask = holdings['종목카테고리'].isin(['현금','예금','예수금']) | holdings['티커'].astype(str).isin(['현금','예금'])
cash_holdings = holdings[cash_mask].copy()
stock_holdings = holdings[~cash_mask].copy()

def to_yf_ticker(ticker, country):
    t = str(ticker).strip()
    if country == '미국':
        return t
    # 한국 주식/ETF
    if t.isdigit() or (len(t) == 6 and t[:5].isdigit()):
        return f"{t.zfill(6)}.KS" if t.isdigit() else f"{t}.KS"
    return f"{t}.KS"

# ── 배당 이력 수집 ──
monthly_actual = defaultdict(float)      # 실제/과거 기반 월별
monthly_predict = defaultdict(float)     # 2026 예측 월별
stock_detail = []

for _, row in stock_holdings.iterrows():
    ticker = row['티커']
    qty = row['수량']
    name = row['종목명']
    cat = row['종목카테고리']
    val = row['평가액']
    yf_t = to_yf_ticker(ticker, row['국가'])

    try:
        tk = yf.Ticker(yf_t)
        divs = tk.dividends
    except Exception:
        divs = pd.Series(dtype=float)

    annual_est = 0
    freq = '없음'
    recent_per_share = 0
    months_with_div = set()

    if len(divs) > 0:
        divs.index = divs.index.tz_localize(None) if divs.index.tz else divs.index
        # 최근 12개월 배당
        cutoff = pd.Timestamp(f'{YEAR-1}-01-01')
        recent = divs[divs.index >= cutoff]

        # 2026 실제 수령분
        divs_2026 = divs[(divs.index >= f'{YEAR}-01-01') & (divs.index <= f'{YEAR}-12-31')]
        for dt, amt in divs_2026.items():
            m = dt.month
            if row['국가'] == '미국':
                krw = amt * qty * FX
            else:
                krw = amt * qty
            monthly_actual[m] += krw

        # 최근 6개월 평균 월배당 (per share)
        last6 = divs[divs.index >= pd.Timestamp(f'{YEAR}-01-01') - pd.DateOffset(months=6)]
        if len(last6) >= 2:
            # 월별 그룹
            last6_df = last6.reset_index()
            last6_df.columns = ['date','amt']
            last6_df['month_key'] = last6_df['date'].dt.to_period('M')
            monthly_ps = last6_df.groupby('month_key')['amt'].sum()
            recent_per_share = monthly_ps.mean()
            freq_months = len(monthly_ps)
            if freq_months >= 10:
                freq = '월배당'
            elif freq_months >= 3:
                freq = '분기+'
            else:
                freq = '연/반기'
        elif len(last6) == 1:
            recent_per_share = last6.iloc[0]
            freq = '연간'
        else:
            # 2025 데이터로 추정
            divs_2025 = divs[(divs.index >= f'{YEAR-1}-01-01') & (divs.index < f'{YEAR}-01-01')]
            if len(divs_2025) > 0:
                last6_df = divs_2025.reset_index()
                last6_df.columns = ['date','amt']
                last6_df['month_key'] = last6_df['date'].dt.to_period('M')
                monthly_ps = last6_df.groupby('month_key')['amt']
                recent_per_share = monthly_ps.mean()
                freq = f'연{len(monthly_ps)}회'

        # 연간 예상
        if row['국가'] == '미국':
            annual_est = recent_per_share * qty * FX * 12 if freq == '월배당' else divs[divs.index >= cutoff].sum() * qty * FX / max(1, (cutoff.to_pydatetime().year == YEAR))
        else:
            if freq == '월배당':
                annual_est = recent_per_share * qty * 12
            else:
                annual_est = divs[divs.index >= cutoff].sum() * qty

        # 2026 월별 예측: 과거 지급 월 패턴 반영
        hist = divs[divs.index >= f'{YEAR-2}-01-01']
        hist_df = hist.reset_index()
        hist_df.columns = ['date','amt']
        hist_df['month'] = hist_df['date'].dt.month

        # 월별 평균 주당 배당
        month_pattern = hist_df.groupby('month')['amt'].mean()

        for m in range(1, 13):
            if m in monthly_actual and monthly_actual.get(m, 0) > 0:
                # 이미 2026 실제 데이터 있으면 스킵 (위에서 합산됨)
                pass
            elif m in month_pattern.index:
                ps = month_pattern[m]
                if row['국가'] == '미국':
                    krw = ps * qty * FX
                else:
                    krw = ps * qty
                monthly_predict[m] += krw
            elif freq == '월배당' and recent_per_share > 0:
                if row['국가'] == '미국':
                    krw = recent_per_share * qty * FX
                else:
                    krw = recent_per_share * qty
                monthly_predict[m] += krw
    else:
        # 배당 없음 (성장주, 커버드콜 일부 등)
        annual_est = 0
        freq = '무배당/미확인'

    stock_detail.append({
        '티커': ticker, '종목명': name[:30], '카테고리': cat,
        '수량': int(qty), '평가액': int(val),
        '배당주기': freq, '연예상배당': int(annual_est),
        '배당수익률': round(annual_est / val * 100, 2) if val > 0 else 0
    })

# ── 현금/예금 이자 (월별) ──
# CMA RP ~3.5%, 예금 ~3.0% 가정
for _, row in cash_holdings.iterrows():
    val = row['평가액']
    rate = 0.035 if 'RP' in str(row['종목명']) or row['종목카테고리'] == '현금' else 0.03
    monthly_int = val * rate / 12
    for m in range(1, 13):
        monthly_predict[m] += monthly_int
    stock_detail.append({
        '티커': row['티커'], '종목명': str(row['종목명'])[:30], '카테고리': row['종목카테고리'],
        '수량': int(row['수량']), '평가액': int(val),
        '배당주기': '이자(월)', '연예상배당': int(monthly_int * 12),
        '배당수익률': round(rate * 100, 2)
    })

# ── 결과 합산 ──
months = list(range(1, 13))
month_names = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월']

# 2026 실제 + 예측 병합 (실제 우선)
final_monthly = {}
for m in months:
    actual = sum(
        (amt * (FX if False else 1))  # already in KRW
        for _ in [1]
    )
    # recompute 2026 actual from stock loop - use monthly_actual
    a = monthly_actual.get(m, 0)
    p = monthly_predict.get(m, 0)
    final_monthly[m] = a if a > 0 else p

# Fix: for months with partial actual, blend
total_predict = defaultdict(float)
for m in months:
    a = monthly_actual.get(m, 0)
    p = monthly_predict.get(m, 0)
    total_predict[m] = max(a, p)  # 실제가 있으면 실제, 없으면 예측

annual_total = sum(total_predict.values())
monthly_avg = annual_total / 12

# ── 출력 ──
print('=' * 60)
print(f'  2026년 월별 배당금 예측 분석  (기준일: {datetime.now().strftime("%Y-%m-%d")})')
print('=' * 60)
print(f'\n총 평가액: {holdings["평가액"].sum():,.0f}원')
print(f'배당/이자 예상 종목: {len([s for s in stock_detail if s["연예상배당"]>0])}개')
print(f'\n▶ 2026년 예상 연간 배당+이자: {annual_total:,.0f}원')
print(f'▶ 월평균: {monthly_avg:,.0f}원')
print(f'▶ 포트폴리오 배당수익률: {annual_total/holdings["평가액"].sum()*100:.2f}%')

print('\n── 월별 예상 배당금 ──')
for m in months:
    amt = total_predict[m]
    bar = '█' * int(amt / max(total_predict.values()) * 30) if max(total_predict.values()) > 0 else ''
    actual_mark = ' (실제수령)' if monthly_actual.get(m, 0) > 0 else ' (예측)'
    print(f'  {month_names[m-1]:>4}  {amt:>12,.0f}원  {bar}{actual_mark}')

# 분기별
print('\n── 분기별 합계 ──')
for q, ms in [(1,[1,2,3]),(2,[4,5,6]),(3,[7,8,9]),(4,[10,11,12])]:
    qsum = sum(total_predict[m] for m in ms)
    print(f'  Q{q}: {qsum:,.0f}원  (월평균 {qsum/3:,.0f}원)')

# 상위 배당 기여 종목
detail_df = pd.DataFrame(stock_detail).sort_values('연예상배당', ascending=False)
print('\n── 연간 배당 기여 Top 15 ──')
for _, r in detail_df.head(15).iterrows():
    if r['연예상배당'] > 0:
        print(f"  {r['종목명']:<32} {r['연예상배당']:>10,}원/년  ({r['배당수익률']:.1f}%)  [{r['배당주기']}]")

# 카테고리별
detail_df_pos = detail_df[detail_df['연예상배당'] > 0]
cat_sum = detail_df_pos.groupby('카테고리')['연예상배당'].sum().sort_values(ascending=False)
print('\n── 카테고리별 연간 배당 ──')
for cat, amt in cat_sum.head(10).items():
    print(f'  {cat:<12} {amt:>10,}원  ({amt/annual_total*100:.1f}%)')

# 배당 집중 월
sorted_months = sorted(total_predict.items(), key=lambda x: x[1], reverse=True)
print('\n── 배당 집중 월 Top 3 ──')
for m, amt in sorted_months[:3]:
    print(f'  {month_names[m-1]}: {amt:,.0f}원')
print('\n── 배당 소극 월 Bottom 3 ──')
for m, amt in sorted_months[-3:]:
    print(f'  {month_names[m-1]}: {amt:,.0f}원')

# 분석 코멘트
print('\n── 분석 요약 ──')
cc_pct = cat_sum.get('다우커',0) + cat_sum.get('테커',0) + cat_sum.get('국내금융배당',0) + cat_sum.get('국내리츠',0)
cash_pct = sum(r['연예상배당'] for r in stock_detail if r['카테고리'] in ['현금','예금','예수금'])
print(f'  1) 커버드콜/배당ETF+리츠 기여: {cc_pct/annual_total*100:.0f}%')
print(f'  2) 현금/예금 이자 기여: {cash_pct/annual_total*100:.0f}%')
print(f'  3) 월별 편차: 최대월/최소월 = {max(total_predict.values())/max(min(total_predict.values()),1):.1f}배')
print(f'  4) 1~6월 실제수령 합계: {sum(monthly_actual.get(m,0) for m in range(1,7)):,.0f}원')
print(f'  5) 7~12월 예측 합계: {sum(total_predict.get(m,0) for m in range(7,13)) - sum(monthly_actual.get(m,0) for m in range(7,13)):,.0f}원')
