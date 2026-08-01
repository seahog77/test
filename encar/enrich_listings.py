#!/usr/bin/env python3
"""기존 엔카 매물 엑셀/JSONL에 색상·성능점검·보험이력공개 여부를 보강한다.

참고:
- 색상/성능점검: /v1/readside/vehicles 배치 조회로 확보 (최대 20대)
- 보험사고건수: 엔카 record API가 Authorization 필요 → 공개 수집 불가.
  대신 보험이력공개여부(Y/N)를 기록한다.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BATCH_URL = "https://api.encar.com/v1/readside/vehicles"
BATCH_SIZE = 20
MAX_WORKERS = 8
MAX_RETRIES = 4

OUT_DIR = Path(__file__).resolve().parent
OUT_XLSX = OUT_DIR / "encar_adaptive_cruise_autohold.xlsx"
OUT_JSONL = OUT_DIR / "encar_adaptive_cruise_autohold.jsonl"


def http_get_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Referer": "https://fem.encar.com/",
        },
    )
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"요청 실패: {url} ({last_err})")


def fetch_batch(ids: list[str]) -> dict[str, dict[str, Any]]:
    """vehicleId(또는 dummyVehicleId) -> enrichment dict."""
    qs = urllib.parse.urlencode({"vehicleIds": ",".join(ids)})
    data = http_get_json(f"{BATCH_URL}?{qs}")
    out: dict[str, dict[str, Any]] = {}
    for item in data or []:
        manage = item.get("manage") or {}
        # 검색 목록의 Id 는 dummyVehicleId 인 경우가 많음
        keys = {
            str(item.get("vehicleId") or ""),
            str(manage.get("dummyVehicleId") or ""),
        }
        keys.discard("")
        spec = item.get("spec") or {}
        cond = item.get("condition") or {}
        insp = cond.get("inspection") or {}
        formats = insp.get("formats") or []
        accident = cond.get("accident") or {}
        adv = item.get("advertisement") or {}
        row = {
            "색상": spec.get("colorName") or spec.get("customColor") or "",
            "성능점검여부": "Y" if formats else ("Y" if adv.get("directInspected") else "N"),
            "보험이력공개여부": "Y" if accident.get("recordView") else "N",
            # 건수는 비공개 API
            "보험사고건수": "",
        }
        # 검색 Condition 플래그도 보조로 반영할 수 있게 원본 보관
        row["_inspection_formats"] = ",".join(formats)
        for k in keys:
            out[k] = row
    return out


def load_rows() -> list[dict[str, Any]]:
    if OUT_JSONL.exists():
        rows = []
        with OUT_JSONL.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        if rows:
            return rows
    if OUT_XLSX.exists():
        df = pd.read_excel(OUT_XLSX, sheet_name="매물목록")
        return df.to_dict(orient="records")
    raise FileNotFoundError("보강할 엑셀/JSONL이 없습니다. 먼저 fetch_acc_epb_listings.py 를 실행하세요.")


def write_outputs(rows: list[dict[str, Any]]) -> None:
    # 내부 필드 제거
    clean = []
    for r in rows:
        clean.append({k: v for k, v in r.items() if not str(k).startswith("_")})

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in clean:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    df = pd.DataFrame(clean)
    if not df.empty:
        sort_cols = [c for c in ["차종구분", "제조사", "모델", "가격_만원", "주행거리_km"] if c in df.columns]
        if sort_cols:
            df = df.sort_values(by=sort_cols, ascending=[True] * len(sort_cols), kind="mergesort")

    note = pd.DataFrame(
        [
            {
                "항목": "검색조건",
                "내용": (
                    "어댑티브 크루즈 컨트롤(엔카옵션 079) AND "
                    "전자식 주차브레이크 EPB(엔카옵션 094)"
                ),
            },
            {
                "항목": "오토홀드 안내",
                "내용": (
                    "엔카 공개 옵션 필터에 '오토홀드' 항목이 없어 "
                    "오토홀드와 가장 가까운 EPB를 대체 조건으로 사용함."
                ),
            },
            {
                "항목": "추가컬럼",
                "내용": "색상, 성능점검여부, 보험이력공개여부, 보험사고건수(공란)",
            },
            {
                "항목": "보험사고건수 안내",
                "내용": (
                    "엔카 보험/사고 이력 상세(건수) API는 로그인(Authorization)이 필요해 "
                    "공개 수집이 불가함. 대신 보험이력공개여부(Y/N)만 제공."
                ),
            },
            {
                "항목": "수집시각_UTC",
                "내용": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            },
            {"항목": "매물수", "내용": str(len(df))},
        ]
    )

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        note.to_excel(writer, sheet_name="안내", index=False)
        df.to_excel(writer, sheet_name="매물목록", index=False)
        if not df.empty:
            group_cols = [c for c in ["차종구분", "제조사", "모델"] if c in df.columns]
            if group_cols:
                summary = (
                    df.groupby(group_cols, dropna=False)
                    .agg(
                        대수=("매물ID", "count"),
                        최저가_만원=("가격_만원", "min") if "가격_만원" in df.columns else ("매물ID", "count"),
                        최고가_만원=("가격_만원", "max") if "가격_만원" in df.columns else ("매물ID", "count"),
                    )
                    .reset_index()
                )
                summary.to_excel(writer, sheet_name="모델별요약", index=False)

    print(f"엑셀 저장: {OUT_XLSX}")
    print(f"JSONL 저장: {OUT_JSONL}")


def main() -> None:
    rows = load_rows()
    print(f"보강 대상: {len(rows):,}대")

    # 컬럼 초기화
    for r in rows:
        r.setdefault("색상", "")
        r.setdefault("성능점검여부", "")
        r.setdefault("보험이력공개여부", "")
        r.setdefault("보험사고건수", "")
        # 검색 결과 Condition 플래그가 있으면 선반영
        cond = str(r.get("성능조건") or "")
        if not r.get("성능점검여부"):
            r["성능점검여부"] = "Y" if "Inspection" in cond else "N"
        if not r.get("보험이력공개여부"):
            r["보험이력공개여부"] = "Y" if "Record" in cond else "N"

    ids = [str(r.get("매물ID")) for r in rows if r.get("매물ID")]
    batches = [ids[i : i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]
    enrich_map: dict[str, dict[str, Any]] = {}

    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(fetch_batch, b): b for b in batches}
        for fut in as_completed(futs):
            part = fut.result()
            enrich_map.update(part)
            done += 1
            if done % 50 == 0 or done == len(batches):
                print(f"  배치 {done}/{len(batches)} 완료 (누적키 {len(enrich_map):,})")

    hit = 0
    for r in rows:
        cid = str(r.get("매물ID"))
        info = enrich_map.get(cid)
        if not info:
            continue
        hit += 1
        if info.get("색상"):
            r["색상"] = info["색상"]
        r["성능점검여부"] = info.get("성능점검여부") or r.get("성능점검여부")
        r["보험이력공개여부"] = info.get("보험이력공개여부") or r.get("보험이력공개여부")
        # 보험사고건수는 비공개

    print(f"상세 매칭: {hit:,}/{len(rows):,} ({time.time() - t0:.1f}s)")
    write_outputs(rows)


if __name__ == "__main__":
    main()
