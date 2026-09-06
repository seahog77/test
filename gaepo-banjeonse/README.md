# 개포 3단지·4단지 20·30평대 반전세 매물

수집일: 2026-08-13  
3단지 디에이치아너힐즈 / 4단지 개포자이프레지던스

전세환산가 = 보증금 + 월세 × 12 ÷ 4.5% (주택 법정 전환율 상한)

## 구글 스프레드시트로 열기

1. https://sheet.new 를 연다 (구글 로그인 상태)
2. A1 셀에 아래 수식을 붙여넣는다

**전체 매물 (추천)**

```
=IMPORTDATA("https://raw.githubusercontent.com/seahog77/test/cursor/gaepo-banjeonse-sheets-a985/gaepo-banjeonse/all.csv")
```

**3단지만**

```
=IMPORTDATA("https://raw.githubusercontent.com/seahog77/test/cursor/gaepo-banjeonse-sheets-a985/gaepo-banjeonse/complex3-honor-hills.csv")
```

**4단지만**

```
=IMPORTDATA("https://raw.githubusercontent.com/seahog77/test/cursor/gaepo-banjeonse-sheets-a985/gaepo-banjeonse/complex4-xi.csv")
```

또는 구글 시트에서 **파일 → 가져오기 → URL**에 위 raw 주소를 넣어도 됩니다.
