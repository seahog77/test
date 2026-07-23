# -*- coding: utf-8 -*-
"""본인 포트폴리오 기준 배당 성장률 산출 + 10년 예측"""
import pandas as pd
import yfinance as yf
import numpy as np
from collections import defaultdict
import sys
import warnings

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

FILE = r'c:\Users\seaho\My project\My_investment\investment.xlsx'
FX = 1530
PORT_VAL = 836_142_589
YEARS = list(range(2019, 2027))  # 2019~2026

# ── 1) 배당내역 시트 (2026 예측 실적) ──
div_sheet = pd.read_excel(FILE, sheet_name='7. 배당내역', header=None)
div_data = div_sheet.iloc[4:].copy()
div_data = div_data[div_data[1].notna()].copy()
div_data['일자'] = pd.to_datetime(div_data[1], errors='coerce')
div_data['원화'] = pd.to_numeric(div_data[7], errors='coerce').fillna(0)
div_data['외화'] = pd.to_numeric(div_data[8], errors='coerce').fillna(0)
div_data['원화환산'] = pd.to_numeric(div_data[9], errors='coerce').fillna(0)
div_data['금액'] = div_data['원화환산'].where(div_data['원화환산'] > 0,
                                            div_data['원화'] + div_data['외화'] * FX)
div_data['연도'] = div_data['일자'].dt.year
sheet_2026 = div_data[div_data['연도'] == 2026]['금액'].sum()

# ── 2) 현재 보유종목 (수량은 입력값, 평가액은 수량×현재가로 산출) ──
hold = pd.read_excel(FILE, sheet_name='3. 종목현황', header=None).iloc[8:].copy()
hold.columns = ['계좌', '번호', '국가', '티커', '종목명', '수량', '평단가', '_7', '현재가', '_9',
                '평가액', '투자비중', '배당금', '누적수익', '총수익률', '종목카테고리', '_16', '_17']
hold['수량'] = pd.to_numeric(hold['수량'], errors='coerce')
hold['현재가'] = pd.to_numeric(hold['현재가'], errors='coerce')
hold['평단가'] = pd.to_numeric(hold['평단가'], errors='coerce')
# 평가액: 엑셀 수식 캐시 없으면 수량×현재가(없으면 평단가)로 대체
hold['평가액'] = pd.to_numeric(hold['평가액'], errors='coerce')
hold['평가액'] = hold['평가액'].fillna(hold['수량'] * hold['현재가'].fillna(hold['평단가']))
hold = hold[(hold['수량'] > 0) & (hold['평가액'] > 0)]
holdings = hold.groupby(['티커', '국가', '종목카테고리'], dropna=False).agg(
    수량=('수량', 'sum'), 평가액=('평가액', 'sum'), 종목명=('종목명', 'first')
).reset_index()

cash_mask = holdings['종목카테고리'].isin(['현금', '예금', '예수금'])
cash_h = holdings[cash_mask]
stock_h = holdings[~cash_mask]


def to_yf(ticker, country):
    t = str(ticker).strip()
    return t if country == '미국' else (f'{t.zfill(6)}.KS' if t.isdigit() else f'{t}.KS')


def cat_group(cat):
    if cat in ['다우커', '테커', '슨피커', '국내금융배당']:
        return '커버드콜/배당ETF'
    if cat in ['국내리츠', '미국리츠', '리츠']:
        return '리츠'
    if cat in ['미국채커', '미국채 ', '미배당국채', '테크채권', '달러']:
        return '채권/혼합'
    if cat in ['현금', '예금', '예수금']:
        return '현금이자'
    return '개별주/기타'


# ── 3) 연도별 포트폴리오 배당 역산 (현재 수량 고정) ──
annual_by_year = defaultdict(float)
annual_by_cat = defaultdict(lambda: defaultdict(float))
stock_growth = []

for _, row in stock_h.iterrows():
    yf_t = to_yf(row['티커'], row['국가'])
    qty = row['수량']
    cat = cat_group(row['종목카테고리'])
    try:
        divs = yf.Ticker(yf_t).dividends
        divs.index = divs.index.tz_localize(None) if divs.index.tz else divs.index
    except Exception:
        continue
    if len(divs) == 0:
        continue

    yearly = {}
    for y in YEARS:
        d = divs[(divs.index >= f'{y}-01-01') & (divs.index < f'{y+1}-01-01')]
        if row['국가'] == '미국':
            amt = d.sum() * qty * FX
        else:
            amt = d.sum() * qty
        yearly[y] = amt
        annual_by_year[y] += amt
        annual_by_cat[cat][y] += amt

    # 종목별 CAGR (2019→2025, 양수인 해가 3년 이상)
    vals = [yearly[y] for y in range(2019, 2026) if yearly[y] > 1000]
    if len(vals) >= 3 and vals[0] > 0:
        years_span = len(vals) - 1
        cagr = (vals[-1] / vals[0]) ** (1 / years_span) - 1
        stock_growth.append({
            '종목': str(row['종목명'])[:28],
            '카테고리': cat,
            '2019': int(yearly[2019]),
            '2025': int(yearly[2025]),
            'CAGR': round(cagr * 100, 1),
            '비중': row['평가액'],
        })

# 현금 이자 (고정)
for _, row in cash_h.iterrows():
    rate = 0.035 if 'RP' in str(row['종목명']) or row['종목카테고리'] == '현금' else 0.03
    for y in YEARS:
        amt = row['평가액'] * rate
        annual_by_year[y] += amt
        annual_by_cat['현금이자'][y] += amt

# 2026년은 배당내역 시트 값 우선
annual_by_year[2026] = sheet_2026

# ── 4) 성장률 계산 ──
print('=' * 62)
print('  본인 포트폴리오 기준 배당 성장률 분석')
print('=' * 62)

print('\n── 연도별 포트폴리오 배당 (현재 수량 기준 역산) ──')
for y in YEARS:
    tag = '(배당내역)' if y == 2026 else '(역산)'
    print(f'  {y}년: {annual_by_year[y]:>14,.0f}원  {tag}')

# 전체 CAGR
vals_all = [annual_by_year[y] for y in range(2019, 2027) if annual_by_year[y] > 0]
cagr_19_25 = (annual_by_year[2025] / annual_by_year[2019]) ** (1 / 6) - 1 if annual_by_year[2019] > 0 else 0
cagr_22_25 = (annual_by_year[2025] / annual_by_year[2022]) ** (1 / 3) - 1 if annual_by_year[2022] > 0 else 0
cagr_24_26 = (annual_by_year[2026] / annual_by_year[2024]) ** (1 / 2) - 1 if annual_by_year[2024] > 0 else 0

print('\n── 포트폴리오 성장률 (CAGR) ──')
print(f'  2019→2025 (6년): {cagr_19_25*100:+.1f}%/년')
print(f'  2022→2025 (3년): {cagr_22_25*100:+.1f}%/년')
print(f'  2024→2026 (2년): {cagr_24_26*100:+.1f}%/년')

# 카테고리별 성장률 (2022-2025, 보유 급증 전보다 안정)
print('\n── 카테고리별 성장률 (2022→2025) ──')
cat_cagr = {}
for cat, yrs in annual_by_cat.items():
    v0, v1 = yrs[2022], yrs[2025]
    if v0 > 10000:
        g = (v1 / v0) ** (1 / 3) - 1
        cat_cagr[cat] = g
        share = v1 / annual_by_year[2025] * 100 if annual_by_year[2025] else 0
        print(f'  {cat:<16} {g*100:+5.1f}%/년  (2025 비중 {share:.0f}%)')

# 가중 성장률 (카테고리 비중 × 카테고리 CAGR)
total_25 = annual_by_year[2025]
weighted_g = sum((annual_by_cat[c][2025] / total_25) * cat_cagr[c]
                 for c in cat_cagr if total_25 > 0)

# 보수적 성장률: 최근 3년 CAGR와 카테고리 가중 중 낮은 값, 상한 5%
conservative_g = min(max(weighted_g, cagr_22_25), 0.05)
conservative_g = max(conservative_g, 0)  # 음수면 0%

print(f'\n  카테고리 가중 성장률: {weighted_g*100:+.1f}%/년')
print(f'  → 보수적 적용 성장률: {conservative_g*100:.1f}%/년')

# ── 5) 10년 예측 (3가지) ──
BASE = annual_by_year[2026]
scenarios = {
    f'보수 (성장 0%)': 0.0,
    f'포트 기준 ({conservative_g*100:.1f}%)': conservative_g,
    f'낙관 ({min(weighted_g, 0.05)*100:.1f}%)': min(max(weighted_g, 0), 0.05),
}

print('\n' + '=' * 62)
print('  포트폴리오 기준 10년 배당 예측 (2026년 배당내역 기준)')
print('=' * 62)
print(f'\n2026 기준 연배당: {BASE:,.0f}원 (월 {BASE/12:,.0f}원)')

for name, gr in scenarios.items():
    print(f'\n--- {name} ---')
    amt = BASE
    cumulative = 0
    for yr in range(11):
        y = 2026 + yr
        if yr > 0:
            amt *= (1 + gr)
            cumulative += amt
        else:
            cumulative = 0
        if yr in [0, 5, 10]:
            tag = '현재' if y == 2026 else f'{y}년'
            print(f'  {tag}: 연 {amt:,.0f}원 (월 {amt/12:,.0f}원, 수익률 {amt/PORT_VAL*100:.2f}%)')
    cum10 = sum(BASE * ((1 + gr) ** i) for i in range(10))
    print(f'  10년 누적 수령: {cum10:,.0f}원')

# 배당 재투자
gr = conservative_g
print(f'\n--- 포트기준+배당재투자 ({gr*100:.1f}%) ---')
amt, port, cum10 = BASE, PORT_VAL, 0
for yr in range(11):
    y = 2026 + yr
    if yr > 0:
        cum10 += amt
        prev = port
        port += amt
        amt = amt * (1 + gr) * (port / prev)
    if yr in [0, 5, 10]:
        tag = '현재' if y == 2026 else f'{y}년'
        print(f'  {tag}: 연 {amt:,.0f}원 (월 {amt/12:,.0f}원, 평가액 {port/1e8:.1f}억)')
print(f'  10년 누적 수령: {cum10:,.0f}원')

# Top 성장/감소 종목
if stock_growth:
    sg = pd.DataFrame(stock_growth).sort_values('CAGR', ascending=False)
    print('\n── 배당 성장 Top 5 종목 (2019→2025) ──')
    for _, r in sg.head(5).iterrows():
        print(f"  {r['종목']:<28} {r['CAGR']:+.1f}%/년  ({r['2019']:,}→{r['2025']:,}원)")
    print('── 배당 감소 Top 5 종목 ──')
    for _, r in sg.tail(5).iterrows():
        print(f"  {r['종목']:<28} {r['CAGR']:+.1f}%/년  ({r['2019']:,}→{r['2025']:,}원)")
else:
    print('\n── 종목별 성장률: 역산 데이터 부족 ──')

print('\n── 이전 예측(1.5% 고정) vs 포트 기준 비교 ──')
old_2036 = BASE * (1.015 ** 10)
new_2036 = BASE * ((1 + conservative_g) ** 10)
print(f'  2036년 연배당  |  기존 1.5%: {old_2036:,.0f}원  |  포트기준: {new_2036:,.0f}원')
print(f'  차이: {(new_2036 - old_2036):+,.0f}원 ({(new_2036/old_2036-1)*100:+.1f}%)')

print('\n── 참고 ──')
print('  · 2019~2025는 현재 보유수량 기준 역산 (과거 매매 미반영)')
print('  · 2026은 배당내역 시트 예측값 사용')
print('  · 실제 배당내역이 쌓이면 2026 이후 성장률이 더 정밀해집니다')
