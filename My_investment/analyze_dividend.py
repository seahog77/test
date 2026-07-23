# -*- coding: utf-8 -*-
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

FILE = r'c:\Users\seaho\My project\My_investment\investment.xlsx'

df = pd.read_excel(FILE, sheet_name='3. 종목현황', header=None)
data = df.iloc[8:].copy()
data.columns = ['계좌','번호','국가','티커','종목명','수량','평단가','_7','현재가','_9','평가액','투자비중','배당금','누적수익','총수익률','종목카테고리','_16','_17']
data['평가액'] = pd.to_numeric(data['평가액'], errors='coerce')
data['수량'] = pd.to_numeric(data['수량'], errors='coerce')
data = data[data['평가액'] > 0]

grp = data.groupby(['티커','종목명','국가','종목카테고리']).agg({'수량':'sum','평가액':'sum','현재가':'first'}).reset_index()
grp = grp.sort_values('평가액', ascending=False)
print(f'Unique tickers: {len(grp)}')
for _, r in grp.iterrows():
    print(f"{r['티커']}\t{r['종목카테고리']}\t{r['국가']}\t{int(r['수량'])}\t{int(r['평가액'])}\t{r['종목명']}")
