# 일일 포트폴리오 자동화 (Cloud Agent)

## 목표
매일 **오전 10시 · 오후 3시 (한국시간)** 에 아래를 실행한다.

1. `investment_0815.xlsx`, `investment_0723_W.xlsx` 시세·금액순·배당 탭 갱신
2. 통합 포트폴리오 요약 텔레그램 전송
3. 미국/한국 강한 매수신호 **시장별 TOP10** 텔레그램 전송  
   (기술신호 + EPS/PER/PBR/매출·이익성장 종합순위. 20개가 아님)
4. 주요 경제뉴스 텔레그램 전송
5. 변경된 엑셀·분석 JSON 을 커밋하고 push (PR 불필요하면 만들지 말 것)

## 실행 명령
```bash
cd My_investment
python -m pip install -q openpyxl pandas yfinance requests python-dotenv finance-datareader
python -X utf8 daily_portfolio_report.py --top 10
# --top 20을 넘겨도 스크립트가 시장별 10개로 자른다.
```

## 시크릿 (대시보드 Secrets / .env)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- (선택) 토스 API 키 — 시세 갱신에는 필수는 아님

## 주의
- 현금/CMA 행은 엑셀 수식이므로, 분석 시 `_analyze_combined_portfolio.py` 의 수식 파싱을 유지할 것.
- 포트폴리오 텔레그램에 **이전 전송 대비 증감(만원 단위)** 과 **증감 원인(종목·테마·시세/매매 추정)** 이 포함된다. 기준값은 `_last_telegram_portfolio.json` 에 저장되므로 커밋·push 할 것.
- 실패 시 `daily_portfolio_report.py` 가 텔레그램으로 에러 요약을 보낸다.
