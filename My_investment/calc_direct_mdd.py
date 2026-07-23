# -*- coding: utf-8 -*-
"""ETF 외 직접투자 종목 MDD 계산"""
import pandas as pd
import yfinance as yf
import numpy as np
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

FILE = r'c:\Users\seaho\My project\My_investment\investment.xlsx'
BACKUP = r'c:\Users\seaho\My project\My_investment\investment_backup_before_dividend.xlsx'

# ── 보유종목 로드 (백업 우선: 수식 캐시값 포함) ──
from pathlib import Path
src = BACKUP if Path(BACKUP).exists() else FILE
hold = pd.read_excel(src, sheet_name='3. 종목현황', header=None).iloc[8:].copy()
hold.columns = ['계좌', '번호', '국가', '티커', '종목명', '수량', '평단가', '_7', '현재가', '_9',
                '평가액', '투자비중', '배당금', '누적수익', '총수익률', '종목카테고리', '_16', '_17']
hold['수량'] = pd.to_numeric(hold['수량'], errors='coerce')
hold['평단가'] = pd.to_numeric(hold['평단가'], errors='coerce')
hold['현재가'] = pd.to_numeric(hold['현재가'], errors='coerce')
hold['평가액'] = pd.to_numeric(hold['평가액'], errors='coerce').fillna(
    hold['수량'] * hold['현재가'].fillna(hold['평단가']))
hold = hold[(hold['수량'] > 0) & (hold['평가액'] > 0)]

ETF_KEYWORDS = [
    'TIGER', 'KODEX', 'SOL ', 'SOL미', 'ACE', 'RISE', 'KIWOOM', 'ETF',
    '커버드콜', '커버드', '채권혼합', '리츠부동산', '금현물', '2차전지',
    '타겟', '인프라', '혼합', 'S&P500', 'S&P', '나스닥100', '테크TOP',
    '배당', '국채', '하이일드', '금융고배당', '비만치료', '양자컴퓨팅',
]
ETF_TICKERS = {'SCHD', 'QLD', 'SPCX'}  # ETF지만 이름에 ETF 미포함


def is_valid_ticker(ticker, country):
    t = str(ticker).strip()
    if t in ['현금', '예금', 'nan', 'None']:
        return False
    if country == '미국':
        return bool(t) and not t.isdigit()
    # 한국 (국가 미입력 포함)
    if len(t) <= 6:
        return True
    return False


def is_etf(name, cat, ticker):
    t = str(ticker).strip()
    if t in ETF_TICKERS:
        return True
    if t in ['현금', '예금'] or str(cat) in ['현금', '예금', '예수금']:
        return True
    n = str(name)
    if any(k in n for k in ['RP', '예금', 'MMF', '예수금']):
        return True
    return any(k in n for k in ETF_KEYWORDS)


hold = hold[hold.apply(lambda r: is_valid_ticker(r['티커'], r['국가']), axis=1)]

def to_yf(ticker, country):
    t = str(ticker).strip()
    if country == '미국':
        return t
    if t.isdigit():
        return f'{t.zfill(6)}.KS'
    return f'{t}.KS'


def calc_mdd(prices: pd.Series):
    """MDD 및 낙폭 구간 계산"""
    if prices is None or len(prices) < 2:
        return None
    prices = prices.dropna()
    if len(prices) < 2:
        return None

    running_max = prices.cummax()
    drawdown = (prices - running_max) / running_max
    mdd = drawdown.min()
    trough_idx = drawdown.idxmin()
    peak_idx = prices.loc[:trough_idx].idxmax()

    # 현재 낙폭
    current_dd = (prices.iloc[-1] - running_max.iloc[-1]) / running_max.iloc[-1]

    return {
        'mdd': mdd * 100,
        'current_dd': current_dd * 100,
        'peak_date': peak_idx,
        'trough_date': trough_idx,
        'peak_price': prices.loc[peak_idx],
        'trough_price': prices.loc[trough_idx],
        'current_price': prices.iloc[-1],
        'recovery': prices.iloc[-1] >= prices.loc[peak_idx],
    }


hold['is_etf'] = hold.apply(lambda r: is_etf(r['종목명'], r['종목카테고리'], r['티커']), axis=1)
direct = hold[~hold['is_etf']].copy()
unique = direct.groupby(['티커', '종목명', '국가', '종목카테고리'], dropna=False).agg(
    평가액=('평가액', 'sum'), 수량=('수량', 'sum')
).reset_index().sort_values('평가액', ascending=False)

PERIODS = {
    '1년': '1y',
    '3년': '3y',
    '5년': '5y',
    '전체': 'max',
}

results = []
print('=' * 78)
print('  ETF 외 직접투자 종목 MDD (Maximum Drawdown)')
print('=' * 78)
print(f'\n분석 대상: {len(unique)}개 종목  |  직접투자 합계: {unique["평가액"].sum():,.0f}원')
print(f'기준일: {datetime.now().strftime("%Y-%m-%d")}\n')

for _, row in unique.iterrows():
    yf_t = to_yf(row['티커'], row['국가'])
    entry = {
        '티커': row['티커'],
        '종목명': str(row['종목명'])[:32],
        '국가': row['국가'],
        '카테고리': row['종목카테고리'],
        '평가액': int(row['평가액']),
    }

    try:
        tk = yf.Ticker(yf_t)
        hist_max = tk.history(period='max')
    except Exception:
        hist_max = pd.DataFrame()

    if hist_max.empty or 'Close' not in hist_max.columns:
        entry['error'] = '데이터 없음'
        results.append(entry)
        continue

    hist_max.index = hist_max.index.tz_localize(None) if hist_max.index.tz else hist_max.index
    close_max = hist_max['Close']

    for pname, period in PERIODS.items():
        if period == 'max':
            close = close_max
        else:
            close = tk.history(period=period)['Close']
            close.index = close.index.tz_localize(None) if close.index.tz else close.index

        m = calc_mdd(close)
        if m:
            entry[f'MDD_{pname}'] = round(m['mdd'], 1)
            if pname == '5년':
                entry['현재낙폭'] = round(m['current_dd'], 1)
                entry['고점일'] = m['peak_date'].strftime('%Y-%m-%d')
                entry['저점일'] = m['trough_date'].strftime('%Y-%m-%d')
                entry['회복'] = 'O' if m['recovery'] else 'X'

    results.append(entry)

# ── 출력 ──
df = pd.DataFrame(results)
ok = df[~df.get('MDD_5년', pd.Series()).isna() if 'MDD_5년' in df.columns else df.index >= 0]

print(f"{'종목명':<28} {'티커':<8} {'평가액':>10}  {'1년':>6} {'3년':>6} {'5년':>6} {'현재DD':>7} {'회복':>4}")
print('-' * 78)

for _, r in df.sort_values('평가액', ascending=False).iterrows():
    if 'error' in r and pd.notna(r.get('error')):
        print(f"{r['종목명']:<28} {str(r['티커']):<8} {r['평가액']:>10,}  {'N/A':>6} {'N/A':>6} {'N/A':>6}")
        continue
    m1 = r.get('MDD_1년', '-')
    m3 = r.get('MDD_3년', '-')
    m5 = r.get('MDD_5년', '-')
    cdd = r.get('현재낙폭', '-')
    rec = r.get('회복', '-')
    print(f"{r['종목명']:<28} {str(r['티커']):<8} {r['평가액']:>10,}  "
          f"{m1:>5}% {m3:>5}% {m5:>5}% {cdd:>6}% {rec:>4}")

# 포트폴리오 가중 MDD (5년, 평가액 비중)
if 'MDD_5년' in df.columns:
    valid = df.dropna(subset=['MDD_5년'])
    if len(valid) > 0:
        w = valid['평가액'] / valid['평가액'].sum()
        w_mdd = (valid['MDD_5년'] * w).sum()
        print(f'\n── 직접투자 포트폴리오 (평가액 가중 평균 MDD, 5년) ──')
        print(f'  가중 평균 MDD: {w_mdd:.1f}%')
        print(f'  단순 평균 MDD: {valid["MDD_5년"].mean():.1f}%')
        print(f'  최대 MDD 종목: {valid.loc[valid["MDD_5년"].idxmin(), "종목명"]} ({valid["MDD_5년"].min():.1f}%)')
        print(f'  최소 MDD 종목: {valid.loc[valid["MDD_5년"].idxmax(), "종목명"]} ({valid["MDD_5년"].max():.1f}%)')

# MDD 상세 (5년, 상위 5 by 평가액)
print('\n── MDD 상세 (5년, 평가액 Top 10) ──')
top = df.dropna(subset=['MDD_5년']).sort_values('평가액', ascending=False).head(10)
for _, r in top.iterrows():
    print(f"  {r['종목명']}")
    print(f"    MDD {r['MDD_5년']:.1f}%  |  고점 {r['고점일']} → 저점 {r['저점일']}  |  현재낙폭 {r['현재낙폭']:.1f}%  |  회복 {'완료' if r['회복']=='O' else '미회복'}")

print('\n── 참고 ──')
print('  · MDD = 고점 대비 최대 하락폭 (%)')
print('  · 현재낙폭 = 최근 고점 대비 현재 하락폭')
print('  · 미국주식/국내주식 일봉 종가 기준 (yfinance)')
print('  · SCHD 등 미국 ETF형 펀드는 제외, 개별주·성장주 위주')
