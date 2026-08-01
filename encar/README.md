# 엔카 옵션 매물 수집

어댑티브 크루즈 컨트롤 + EPB(전자식 주차브레이크) 조건 매물을 엔카 공개 검색 API로 모아 엑셀로 저장합니다.

## 중요

엔카 옵션 필터에 **오토홀드** 단독 항목이 없습니다.  
오토홀드와 가장 가까운 **EPB(094)** 를 대체 조건으로 사용합니다. EPB가 있어도 오토홀드가 없는 차량이 있을 수 있으니 상세 페이지에서 확인하세요.

## 실행

```bash
python3 encar/fetch_acc_epb_listings.py
```

생성 파일:
- `encar_adaptive_cruise_autohold.xlsx` (안내 / 매물목록 / 모델별요약)
- `encar_adaptive_cruise_autohold.jsonl`
