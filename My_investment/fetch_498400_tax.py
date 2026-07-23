"""Fetch KODEX 498400 distribution + taxable amount from Samsung Fund."""
import json
import re
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.samsungfund.com/etf/product/view.do?id=2ETFP4",
}

PRODUCT_ID = "2ETFP4"
FUND_CD = "498400"

# 1) product page
r = requests.get(
    "https://www.samsungfund.com/etf/product/view.do",
    params={"id": PRODUCT_ID},
    headers=HEADERS,
    timeout=20,
)
text = r.text
print("view.do", r.status_code, "len", len(text))

api_paths = sorted(set(re.findall(r'["\'](/etf/[^"\']+)["\']', text)))
print("etf paths sample:")
for p in api_paths[:40]:
    print(" ", p)

# look for embedded JSON config
for key in ["fundCd", "productId", "distribution", "dividend", "taxStd", "tax"]:
    idx = text.find(key)
    if idx >= 0:
        print("context", key, ":", text[max(0, idx - 80) : idx + 120].replace("\n", " ")[:200])

# 2) brute-force common samsung ajax endpoints
candidates = []
for base in [
    "/etf/product/distributionList.do",
    "/etf/product/getDistributionList.do",
    "/etf/product/distribution/list.do",
    "/etf/product/ajax/distribution.do",
    "/etf/product/ajax/dividendList.do",
    "/etf/product/dividendList.do",
    "/etf/product/getDividendList.do",
    "/etf/product/getProductDividend.do",
    "/etf/product/productDividendList.do",
]:
    for params in [
        {"id": PRODUCT_ID},
        {"productId": PRODUCT_ID},
        {"fundCd": FUND_CD},
        {"id": PRODUCT_ID, "pageNo": 1, "pageSize": 100},
    ]:
        candidates.append((base, params))

for path, params in candidates:
    url = "https://www.samsungfund.com" + path
    for method in ("GET", "POST"):
        try:
            if method == "GET":
                resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            else:
                resp = requests.post(url, data=params, headers=HEADERS, timeout=15)
            if resp.status_code == 200 and resp.text and resp.text[0] in "{[":
                print(f"\nHIT {method} {path} {params}")
                print(resp.text[:3000])
                try:
                    data = resp.json()
                    print("keys", data.keys() if isinstance(data, dict) else type(data))
                except Exception:
                    pass
        except Exception:
            pass

# 3) try KRX data portal ETF distribution
krx_headers = {
    **HEADERS,
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "http://data.krx.co.kr",
    "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020102",
}
krx_payload = {
    "bld": "dbms/MDC/STAT/standard/MDCSTAT02401",
    "locale": "ko_KR",
    "isuCd": "KR7498400009",
    "strtDd": "20250101",
    "endDd": "20260630",
    "share": "1",
    "money": "1",
    "csvxls_isNo": "false",
}
try:
    krx = requests.post(
        "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd",
        data=krx_payload,
        headers=krx_headers,
        timeout=20,
    )
    print("\nKRX", krx.status_code)
    if krx.status_code == 200:
        print(krx.text[:2000])
except Exception as e:
    print("KRX err", e)
