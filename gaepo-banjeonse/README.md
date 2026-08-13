# 개포 3단지·4단지 20·30평대 반전세 매물

수집일: 2026-08-13  
3단지 디에이치아너힐즈 / 4단지 개포자이프레지던스

## 구글 스프레드시트로 열기

1. [새 구글 시트 만들기](https://sheet.new)
2. A1에 아래 중 하나를 붙여넣기

**전체 매물**

```
=IMPORTDATA("https://raw.githubusercontent.com/seahog77/test/cursor/gaepo-banjeonse-sheets-a985/gaepo-banjeonse/반전세_전체.csv")
```

**3단지 아너힐즈**

```
=IMPORTDATA("https://raw.githubusercontent.com/seahog77/test/cursor/gaepo-banjeonse-sheets-a985/gaepo-banjeonse/3단지_아너힐즈.csv")
```

**4단지 자이프레지던스**

```
=IMPORTDATA("https://raw.githubusercontent.com/seahog77/test/cursor/gaepo-banjeonse-sheets-a985/gaepo-banjeonse/4단지_자이프레지던스.csv")
```

전세환산가 = 보증금 + 월세×12÷4.5% (주택 법정 전환율 상한)
