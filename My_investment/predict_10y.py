# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

BASE_2026 = 47_974_181
PORT_VAL = 836_142_589
CASH_INT = 3_754_476

weights = {
    '커버드콜ETF': 0.78,
    '개별주/기타': 0.14,
    '현금이자': CASH_INT / BASE_2026,
}
cat_growth = {
    '커버드콜ETF': 0.01,
    '개별주/기타': 0.05,
    '현금이자': 0.00,
}
blended = sum(weights[k] * cat_growth[k] for k in weights)

print('=== 현실적 가정 ===')
print(f'2026년 기준 연배당: {BASE_2026:,.0f}원 (월 {BASE_2026/12:,.0f}원)')
print(f'포트폴리오 가중 평균 성장률: {blended*100:.1f}%/년')
print()

scenarios = {
    '보수 (성장 0%, 수량고정)': (0.0, False),
    '기본 (성장 1.5%, 수량고정)': (0.015, False),
    '낙관 (성장 3%, 수량고정)': (0.03, False),
    '기본+배당재투자 (1.5%성장)': (0.015, True),
}

for name, (gr, reinvest) in scenarios.items():
    print(f'--- {name} ---')
    amt = BASE_2026
    port = PORT_VAL
    for yr in range(11):
        y = 2026 + yr
        if yr > 0:
            if reinvest:
                prev_port = port
                port += amt
                amt = amt * (1 + gr) * (port / prev_port)
            else:
                amt *= (1 + gr)
        if yr in [0, 5, 10]:
            tag = '현재' if y == 2026 else f'{y}년'
            extra = f', 평가액 {port/1e8:.1f}억' if reinvest and y > 2026 else ''
            print(f'  {tag}: 연 {amt:,.0f}원 (월 {amt/12:,.0f}원){extra}')

    if not reinvest:
        cum10 = sum(BASE_2026 * ((1 + gr) ** i) for i in range(10))
        print(f'  10년 누적 수령: {cum10:,.0f}원')
    else:
        cum10 = 0
        amt = BASE_2026
        port = PORT_VAL
        for _ in range(10):
            cum10 += amt
            prev_port = port
            port += amt
            amt = amt * (1 + gr) * (port / prev_port)
        print(f'  10년 누적 수령: {cum10:,.0f}원')
    print()

print('--- 배당수익률 추이 (수량/구성 고정) ---')
for y in [2026, 2031, 2036]:
    yrs = y - 2026
    a = BASE_2026 * (1.015 ** yrs)
    print(f'  {y}년: {a/PORT_VAL*100:.2f}%')
