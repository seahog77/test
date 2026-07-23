# -*- coding: utf-8 -*-
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

BACKUP = r'c:\Users\seaho\My project\My_investment\investment_backup_before_dividend.xlsx'
hold = pd.read_excel(BACKUP, sheet_name='3. 종목현황', header=None).iloc[8:]
hold.columns = ['계좌','번호','국가','티커','종목명','수량','평단가','_7','현재가','_9',
                '평가액','비중','배당','수익','수익률','카테고리','_16','_17']
hold['평가액'] = pd.to_numeric(hold['평가액'], errors='coerce')
hold = hold[hold['평가액'] > 0]

print('=== 계좌별 현금 ===')
cash = hold[hold['카테고리'].isin(['현금','예금','예수금']) | hold['티커'].astype(str).eq('현금')]
for _, r in cash.iterrows():
    print(f"  {r['계좌'] or '(미지정)':<10} {str(r['종목명'])[:25]:<25} {int(r['평가액']):>12,}원")

print('\n=== 매수 후보 보유 계좌 ===')
candidates = {
    '498410': 'KODEX금융고배당TOP10커버드콜',
    '329200': 'TIGER리츠부동산인프ra',
    '446720': 'SOL미국배당다우존스',
    '490490': 'SOL미국배당미국채혼합50',
    '024110': '기업은행',
    '000270': '기아',
    'MSFT': '마이크로소프트',
}
for tic, label in candidates.items():
    sub = hold[hold['티커'].astype(str) == tic]
    if len(sub):
        print(f'\n[{label} / {tic}]')
        for _, r in sub.iterrows():
            print(f"  {r['계좌'] or '-':<10} 평가 {int(r['평가액']):>10,}원  수익률 {r['수익률']}")

print('\n=== 커버드콜 보유 계좌 (458760/474220) ===')
for tic in ['458760','474220','498410']:
    sub = hold[hold['티커'].astype(str)==tic]
    if len(sub):
        for _, r in sub.iterrows():
            print(f"  {r['계좌']:<10} {str(r['종목명'])[:28]}")

print('\nAccounts:', sorted(hold['계좌'].dropna().unique().tolist()))
