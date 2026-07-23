# -*- coding: utf-8 -*-
"""QLD 1억 투입 + 연 5,000만 추가 + 배당재투자 10년 시뮬레이션"""
import yfinance as yf
import sys
sys.stdout.reconfigure(encoding='utf-8')

# ── 현재 포트폴리오 (백업·분석 기준값) ──
TOTAL_ASSETS = 836_142_589
CASH_TOTAL = 114_751_846       # CMA+예금+예수금
QLD_EXISTING = 1_048_712       # QLD 7주
CORE_INIT = TOTAL_ASSETS - CASH_TOTAL  # 주식/ETF (QLD 포함)

# ── 시뮬레이션 파라미터 ──
QLD_INJECT = 100_000_000        # 현금→QLD 즉시 투입
ANNUAL_INVEST = 50_000_000      # 매년 최소 5,000만 추가 투입
YEARS = 10
FX = 1530

# 2026 배당내역 기준
DIV_2026 = 52_624_237
CASH_INT_RATE = 0.033           # 현금 평균 이자
CORE_DIV_YIELD = (DIV_2026 - CASH_TOTAL * CASH_INT_RATE) / (CORE_INIT - QLD_EXISTING)
# ≈ 6.8% (커버드콜 ETF 위주)

# QLD 배당 (극히 낮음)
qld_divs = yf.Ticker('QLD').dividends
qld_divs.index = qld_divs.index.tz_localize(None) if qld_divs.index.tz else qld_divs.index
QLD_DIV_PER_SHARE = qld_divs[qld_divs.index.year >= 2024].sum() / 2  # 연 $0.12 수준
QLD_PRICE = yf.Ticker('QLD').history(period='5d')['Close'].iloc[-1]

# 성장률 가정
CORE_DIV_GROWTH = 0.02          # 배당 성장 2%/년
CORE_PRICE_GROWTH = 0.03        # ETF 시가 성장 3%/년
QLD_SCENARIOS = {
    '보수': {'price': 0.06, 'label': 'QLD 연 6%'},
    '기본': {'price': 0.10, 'label': 'QLD 연 10%'},
    '낙관': {'price': 0.14, 'label': 'QLD 연 14%'},
}


def simulate(qld_price_growth):
    # 초기 배분 (1억 QLD 매수)
    cash_remain = CASH_TOTAL - QLD_INJECT
    qld = QLD_EXISTING + QLD_INJECT
    core = CORE_INIT - QLD_EXISTING  # 기존 QLD 제외 코어

    yearly = []
    for yr in range(YEARS + 1):
        y = 2026 + yr

        # 배당 산출
        core_div = core * CORE_DIV_YIELD * ((1 + CORE_DIV_GROWTH) ** yr)
        qld_shares = qld / (QLD_PRICE * FX)
        qld_div = qld_shares * QLD_DIV_PER_SHARE * FX
        cash_int = cash_remain * CASH_INT_RATE
        total_div = core_div + qld_div + cash_int
        monthly_div = total_div / 12

        total = core + qld + cash_remain

        yearly.append({
            'year': y,
            'total': total,
            'core': core,
            'qld': qld,
            'cash': cash_remain,
            'annual_div': total_div,
            'monthly_div': monthly_div,
            'qld_pct': qld / total * 100,
        })

        if yr == YEARS:
            break

        # 가격 상승
        core *= (1 + CORE_PRICE_GROWTH)
        qld *= (1 + qld_price_growth)

        # 배당 재투자: 코어 배당→코어, QLD배당→QLD, 현금이자→QLD
        core += core_div
        qld += qld_div + ANNUAL_INVEST + cash_int
        # 현금은 CMA 잔여분만 유지 (이자는 QLD로)

    return yearly


print('=' * 64)
print('  10년 시뮬레이션: QLD 1억 + 연 5,000만 + 배당 재투자')
print('=' * 64)
print(f'\n[현재 포트폴리오]')
print(f'  총 자산:     {TOTAL_ASSETS/1e8:.2f}억 원')
print(f'  현금/예금:   {CASH_TOTAL/1e8:.2f}억 원')
print(f'  QLD 보유:    {QLD_EXISTING/1e4:.0f}만 원 ({QLD_EXISTING/QLD_PRICE/FX:.0f}주)')
print(f'  2026 연배당: {DIV_2026/1e4:.0f}만 원 (월 {DIV_2026/12/1e4:.0f}만)')

print(f'\n[시뮬레이션 조건]')
print(f'  · 즉시 현금 1억 → QLD 매수')
print(f'  · 매년 추가 5,000만 원 → QLD 투입')
print(f'  · 전 종목 배당금 재투자 (코어→코어, 이자/QLD배당→QLD)')
print(f'  · 코어 ETF: 시가 +3%/년, 배당 +2%/년 (수익률 {CORE_DIV_YIELD*100:.1f}%)')
print(f'  · QLD 배당: 극히 낮음 (연 ~0.1%)')

for sname, sparam in QLD_SCENARIOS.items():
    result = simulate(sparam['price'])
    start = result[0]
    end = result[-1]
    mid = result[5]

    print(f'\n{"─"*64}')
    print(f'  시나리오: {sname} ({sparam["label"]})')
    print(f'{"─"*64}')
    print(f'  {"연도":>6}  {"총자산":>10}  {"QLD":>9}  {"월배당":>8}  {"QLD비중":>6}')
    for r in [result[0], result[5], result[10]]:
        print(f'  {r["year"]:>6}  {r["total"]/1e8:>8.1f}억  {r["qld"]/1e8:>7.1f}억  '
              f'{r["monthly_div"]/1e4:>6.0f}만  {r["qld_pct"]:>5.1f}%')

    growth = (end['total'] / start['total'] - 1) * 100
    div_growth = (end['monthly_div'] / start['monthly_div'] - 1) * 100
    cum_div = sum(r['annual_div'] for r in result[1:])
    cum_invest = QLD_INJECT + ANNUAL_INVEST * YEARS

    print(f'\n  ▶ 2036년 총자산:  {end["total"]/1e8:.1f}억 원  (현재 대비 +{growth:.0f}%)')
    print(f'  ▶ 2036년 QLD:     {end["qld"]/1e8:.1f}억 원  (비중 {end["qld_pct"]:.0f}%)')
    print(f'  ▶ 2036년 월배당:  {end["monthly_div"]/1e4:.0f}만 원  (연 {end["annual_div"]/1e4:.0f}만)')
    print(f'  ▶ 월배당 성장:    +{div_growth:.0f}%  (현재 {start["monthly_div"]/1e4:.0f}만 → {end["monthly_div"]/1e4:.0f}만)')
    print(f'  ▶ 10년 누적 배당: {cum_div/1e8:.1f}억 원')
    print(f'  ▶ 10년 추가투자:  {cum_invest/1e8:.1f}억 원 (1억+5천만×10)')

# 기본 시나리오 연도별 상세
print(f'\n{"="*64}')
print('  [기본 시나리오] 연도별 상세')
print(f'{"="*64}')
result = simulate(QLD_SCENARIOS['기본']['price'])
print(f'  {"연도":>4} {"총자산":>8} {"코어":>8} {"QLD":>8} {"현금":>6} {"연배당":>8} {"월배당":>6}')
for r in result:
    print(f'  {r["year"]:>4} {r["total"]/1e8:>7.1f}억 {r["core"]/1e8:>7.1f}억 '
          f'{r["qld"]/1e8:>7.1f}억 {r["cash"]/1e4:>5.0f}만 '
          f'{r["annual_div"]/1e4:>7.0f}만 {r["monthly_div"]/1e4:>5.0f}만')

print(f'\n{"─"*64}')
print('  [주의사항]')
print('  · QLD는 2배 레버리지 ETF로 변동성·괴리(decay) 큼 (2022년 -61%)')
print('  · 장기 보유 시 레버리지 괴리로 기대수익률이 나스닥 2배보다 낮을 수 있음')
print('  · 월배당 대부분은 커버드콜 ETF에서 발생, QLD는 자산성장 중심')
print('  · 5,000만 = 5,000만 원(5천만) 기준. QLD 추가투자에 우선 배분 가정')
print(f'{"─"*64}')

# 현재 유지 vs 본 시나리오 비교
base_end_assets = TOTAL_ASSETS * (1.03 ** YEARS)  # 단순 3% 성장
base_end_div = DIV_2026 * (1.02 ** YEARS)
r = simulate(QLD_SCENARIOS['기본']['price'])[-1]
print(f'\n  [비교] 10년 후 기본 시나리오 vs 현재 유지(단순추정)')
print(f'  총자산  | 현재유지 ~{base_end_assets/1e8:.1f}억  |  본 시나리오 {r["total"]/1e8:.1f}억')
print(f'  월배당  | 현재유지 ~{base_end_div/12/1e4:.0f}만    |  본 시나리오 {r["monthly_div"]/1e4:.0f}만')
