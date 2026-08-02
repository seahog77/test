#!/usr/bin/env python3
"""엔카: 어댑티브 크루즈 + EPB(오토홀드 대체) 매물 전체 수집 → 엑셀.

엔카 검색 API는 오프셋이 대략 10,000을 넘으면 같은 페이지를 반복 반환하므로
제조사·연식·가격 구간으로 분할 조회한다.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BASE = "https://api.encar.com/search/car/list/general"
PAGE_SIZE = 500
MAX_OFFSET = 9000  # API soft limit ~10000
MAX_RETRIES = 5
SORT = "PriceAsc"

OPTION_ACC = "크루즈 컨트롤(어댑티브_)"
OPTION_EPB = "전자식 주차브레이크(EPB_)"

OUT_DIR = Path(__file__).resolve().parent
OUT_XLSX = OUT_DIR / "encar_adaptive_cruise_autohold.xlsx"
OUT_JSONL = OUT_DIR / "encar_adaptive_cruise_autohold.jsonl"


def http_get_json(url: str, allow_400: bool = False) -> dict[str, Any] | None:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json"}
    )
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if allow_400 and e.code == 400:
                return None
            last_err = e
            time.sleep(1.2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"요청 실패: {url} ({last_err})")


def search(
    query: str,
    offset: int = 0,
    limit: int = PAGE_SIZE,
    allow_400: bool = False,
) -> dict[str, Any] | None:
    params: dict[str, str] = {
        "count": "true",
        "q": query,
        "sr": f"|{SORT}|{offset}|{limit}",
    }
    return http_get_json(
        f"{BASE}?{urllib.parse.urlencode(params)}", allow_400=allow_400
    )


def base_query(car_type_expr: str, extras: list[str] | None = None) -> str:
    """Ryvuss And 쿼리 생성.

    예: (And.Hidden.N._.CarType.Y._.Manufacturer.현대._.Options.크루즈 컨트롤(어댑티브_)._.Options.전자식 주차브레이크(EPB_).)
    """
    chunks: list[str] = [
        "Hidden.N",
        car_type_expr.rstrip("."),
    ]
    for ex in extras or []:
        chunks.append(ex.rstrip("."))
    chunks.append(f"Options.{OPTION_ACC}")
    chunks.append(f"Options.{OPTION_EPB}")
    # 각 조건을 '._.' 로 연결하고, 전체는 (And.....) 형태.
    # 옵션/range 토큰은 값 끝에 '.' 이 붙는 Expression 규칙을 따른다.
    rendered: list[str] = []
    for i, c in enumerate(chunks):
        is_last = i == len(chunks) - 1
        if c.startswith("Options.") or c.startswith("Year.range(") or c.startswith("Price.range("):
            # Expression 자체에 trailing '.' 포함
            piece = c if c.endswith(".") else c + "."
        else:
            piece = c
        rendered.append(piece)
    # join separator is '._.' only between pieces that do not already end with '.'
    # Safer: manually build using working pattern string concat.
    body = rendered[0]
    for piece in rendered[1:]:
        if body.endswith("."):
            body += "_." + piece
        else:
            body += "._." + piece
    if not body.endswith("."):
        body += "."
    return f"(And.{body})"


def flatten_car(car: dict[str, Any], car_type: str) -> dict[str, Any]:
    cid = car.get("Id")
    photo = car.get("Photo") or ""
    if photo and not photo.startswith("http"):
        # Photo prefix looks like /carpicture02/...
        loc = photo if photo.startswith("/") else "/" + photo
        photo = "https://ci.encar.com" + loc
        if not photo.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            photo = photo.rstrip("_") + "_001.jpg"

    conditions = set(car.get("Condition") or [])
    return {
        "매물ID": str(cid),
        "차종구분": car_type,
        "제조사": car.get("Manufacturer"),
        "모델": car.get("Model"),
        "등급": car.get("Badge"),
        "세부등급": car.get("BadgeDetail"),
        "연식": car.get("FormYear"),
        "연식코드": car.get("Year"),
        "주행거리_km": car.get("Mileage"),
        "가격_만원": car.get("Price"),
        "연료": car.get("FuelType"),
        "색상": car.get("Color") or car.get("colorName") or "",
        "판매방식": car.get("SellType"),
        "지역": car.get("OfficeCityState"),
        "엔카서비스": ",".join(car.get("ServiceMark") or []),
        "신뢰": ",".join(car.get("Trust") or []),
        "성능조건": ",".join(car.get("Condition") or []),
        "성능점검여부": "Y" if "Inspection" in conditions else "N",
        "보험이력공개여부": "Y" if "Record" in conditions else "N",
        "보험사고건수": "",  # 로그인(보험개발원 연동) 필요 — enrich에서 보강 시도
        "어댑티브크루즈": "Y",
        "EPB_오토홀드대체": "Y",
        "링크": f"https://fem.encar.com/cars/detail/{cid}",
        "사진": photo,
    }


def manufacturers(car_type_code: str) -> list[str]:
    domestic = "true" if car_type_code == "Y" else "false"
    url = (
        "https://api.encar.com/legacy/usedcar/code/car/manufacturer"
        f"?domestic={domestic}"
    )
    data = http_get_json(url)
    names: list[str] = []
    for row in data or []:
        name = row.get("manufacturerNm")
        if name:
            names.append(str(name))
    return names


def year_windows(start: int = 2005, end: int = 2026, step: int = 1) -> list[tuple[int, int]]:
    windows = []
    for y in range(start, end + 1, step):
        y0 = y * 100 + 1
        y1 = (y + step - 1) * 100 + 12
        windows.append((y0, y1))
    return windows


def price_windows() -> list[tuple[int | None, int | None]]:
    # 만원 단위. None = open-ended
    bounds = [0, 500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 7000, 10000, 15000, None]
    wins: list[tuple[int | None, int | None]] = []
    for i in range(len(bounds) - 1):
        wins.append((bounds[i], bounds[i + 1]))
    return wins


def expr_year(y0: int, y1: int) -> str:
    return f"Year.range({y0}..{y1})."


def expr_price(p0: int | None, p1: int | None) -> str:
    lo = "" if p0 is None else str(p0)
    hi = "" if p1 is None else str(p1)
    return f"Price.range({lo}..{hi})."


def expr_mfr(name: str) -> str:
    return f"Manufacturer.{name}."


def fetch_query_all(query: str) -> list[dict[str, Any]]:
    """한 쿼리의 결과를 오프셋 한도 내에서 모두 가져온다."""
    first = search(query, 0, PAGE_SIZE, allow_400=True)
    if not first:
        return []
    total = int(first.get("Count") or 0)
    if total == 0:
        return []
    if total > MAX_OFFSET + PAGE_SIZE:
        raise RuntimeError(f"분할 필요: count={total} query={query}")

    results = list(first.get("SearchResults") or [])
    for offset in range(PAGE_SIZE, total, PAGE_SIZE):
        if offset > MAX_OFFSET:
            break
        data = search(query, offset, PAGE_SIZE, allow_400=True)
        if not data:
            break
        batch = data.get("SearchResults") or []
        if not batch:
            break
        results.extend(batch)
    return results


def collect_partition(
    car_type_label: str,
    car_type_code: str,
    parts: list[str],
) -> Iterable[dict[str, Any]]:
    query = base_query(f"CarType.{car_type_code}", parts)
    data = search(query, 0, 1, allow_400=True)
    if not data:
        return
    total = int(data.get("Count") or 0)
    if total == 0:
        return
    if total <= MAX_OFFSET:
        print(f"  fetch {car_type_label} {parts} -> {total:,}")
        for car in fetch_query_all(query):
            yield flatten_car(car, car_type_label)
        return

    # 더 쪼개기
    if not any(p.startswith("Manufacturer.") for p in parts):
        for mfr in manufacturers(car_type_code):
            yield from collect_partition(
                car_type_label, car_type_code, parts + [expr_mfr(mfr)]
            )
        return

    if not any(p.startswith("Year.range") for p in parts):
        for y0, y1 in year_windows(2005, 2026, 1):
            yield from collect_partition(
                car_type_label, car_type_code, parts + [expr_year(y0, y1)]
            )
        return

    if not any(p.startswith("Price.range") for p in parts):
        for p0, p1 in price_windows():
            yield from collect_partition(
                car_type_label, car_type_code, parts + [expr_price(p0, p1)]
            )
        return

    raise RuntimeError(f"더 이상 분할 불가: count={total}, parts={parts}")


def main() -> None:
    t0 = time.time()
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []

    for label, code in [("국산", "Y"), ("수입", "N")]:
        print(f"==== {label} 수집 시작")
        # 제조사 단위로 시작 (전체 count가 10k 초과)
        for mfr in manufacturers(code):
            for row in collect_partition(label, code, [expr_mfr(mfr)]):
                cid = row["매물ID"]
                if cid in seen:
                    continue
                seen.add(cid)
                rows.append(row)
        print(f"==== {label} 누적 고유 {len(rows):,}대")

    print(f"수집 완료: {len(rows):,}대 ({time.time() - t0:.1f}s)")

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            by=["차종구분", "제조사", "모델", "가격_만원", "주행거리_km"],
            ascending=[True, True, True, True, True],
            kind="mergesort",
        )

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
                    "오토홀드와 가장 가까운 EPB를 대체 조건으로 사용함. "
                    "EPB가 있어도 오토홀드가 없는 차량이 있을 수 있으니 "
                    "상세 페이지에서 최종 확인 필요."
                ),
            },
            {
                "항목": "수집시각_UTC",
                "내용": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            },
            {"항목": "매물수", "내용": str(len(df))},
            {
                "항목": "국산수",
                "내용": str(int((df["차종구분"] == "국산").sum()) if len(df) else 0),
            },
            {
                "항목": "수입수",
                "내용": str(int((df["차종구분"] == "수입").sum()) if len(df) else 0),
            },
        ]
    )

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        note.to_excel(writer, sheet_name="안내", index=False)
        # 엑셀 시트 행 한도 고려해 매물목록은 그대로 기록
        df.to_excel(writer, sheet_name="매물목록", index=False)
        if not df.empty:
            summary = (
                df.groupby(["차종구분", "제조사", "모델"], dropna=False)
                .agg(
                    대수=("매물ID", "count"),
                    최저가_만원=("가격_만원", "min"),
                    최고가_만원=("가격_만원", "max"),
                    평균가_만원=("가격_만원", "mean"),
                    평균주행_km=("주행거리_km", "mean"),
                )
                .reset_index()
                .sort_values(["차종구분", "대수"], ascending=[True, False])
            )
            summary["평균가_만원"] = summary["평균가_만원"].round(1)
            summary["평균주행_km"] = summary["평균주행_km"].round(0)
            summary.to_excel(writer, sheet_name="모델별요약", index=False)

    print(f"엑셀 저장: {OUT_XLSX}")
    print(f"JSONL 저장: {OUT_JSONL}")


if __name__ == "__main__":
    main()
