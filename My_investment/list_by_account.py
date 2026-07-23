# -*- coding: utf-8 -*-
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

B = r'c:\Users\seaho\My project\My_investment\investment_backup_before_dividend.xlsx'
h = pd.read_excel(B, sheet_name='3. 종목현황', header=None).iloc[8:]
h.columns = ['acct','n','country','tic','name','qty','avg','_7','px','_9','val','w','d','p','ret','cat','a','b']
h['val'] = pd.to_numeric(h['val'], errors='coerce')
h = h[h['val'] > 0]

for acct in ['일반계좌', 'DC', '개인연금1', '개인연금2', 'CMA', 'ISA', 'IRP', '직투']:
    sub = h[h['acct'] == acct]
    if len(sub):
        print(f'=== {acct} ({sub["val"].sum():,.0f}원) ===')
        for _, r in sub.sort_values('val', ascending=False).iterrows():
            print(f'  {r["tic"]} {str(r["name"])[:30]} {int(r["val"]):,}')

print('\n=== 계좌 미기재 (500만+) ===')
for _, r in h[h['acct'].isna()].sort_values('val', ascending=False).iterrows():
    if r['val'] >= 500000:
        print(f'  [{r["country"]}] {r["tic"]} {str(r["name"])[:28]} {int(r["val"]):,}')

# dividend estimate for DC and 개인연금1 from earlier - rough
print('\n=== CMA ===')
cma = h[(h['acct']=='CMA') | (h['name'].astype(str).str.contains('CMA', na=False))]
for _, r in cma.iterrows():
    print(int(r['val']))
