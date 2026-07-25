# -*- coding: utf-8 -*-
"""
yfinance 기반 펀더멘털 조회 + 점수화

사용 지표:
  - EPS (trailing / forward)
  - PER (trailing / forward)
  - PBR (priceToBook)
  - 매출 성장 (revenueGrowth)
  - 이익 성장 (earningsGrowth / earningsQuarterlyGrowth)
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import yfinance as yf


def _f(v) -> float | None:
    try:
        if v is None:
            return None
        x = float(v)
        if x != x or x in (float("inf"), float("-inf")):  # NaN / inf
            return None
        return x
    except Exception:
        return None


def fetch_fundamentals(symbol: str) -> dict[str, Any]:
    """단일 종목 펀더멘털. 실패 시 빈 dict 필드."""
    out = {
        "symbol": symbol,
        "eps": None,
        "fwd_eps": None,
        "per": None,
        "fwd_per": None,
        "pbr": None,
        "rev_g": None,  # decimal, 0.1 = 10%
        "earn_g": None,
        "earn_qg": None,
        "ok": False,
    }
    try:
        t = yf.Ticker(symbol)
        info = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}
        # fast_info fallbacks
        try:
            fi = t.fast_info
        except Exception:
            fi = None

        out["eps"] = _f(info.get("trailingEps"))
        out["fwd_eps"] = _f(info.get("forwardEps"))
        out["per"] = _f(info.get("trailingPE") or info.get("perRatio"))
        out["fwd_per"] = _f(info.get("forwardPE"))
        out["pbr"] = _f(info.get("priceToBook"))
        if out["pbr"] is None and fi is not None:
            out["pbr"] = _f(getattr(fi, "price_to_book", None))
        out["rev_g"] = _f(info.get("revenueGrowth"))
        out["earn_g"] = _f(info.get("earningsGrowth"))
        out["earn_qg"] = _f(info.get("earningsQuarterlyGrowth"))
        out["ok"] = any(
            out[k] is not None
            for k in ("eps", "per", "pbr", "rev_g", "earn_g", "earn_qg")
        )
    except Exception:
        pass
    return out


def fetch_fundamentals_many(symbols: list[str], max_workers: int = 12) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not symbols:
        return result
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(fetch_fundamentals, s): s for s in symbols}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                result[sym] = fut.result()
            except Exception:
                result[sym] = fetch_fundamentals("__none__")
                result[sym]["symbol"] = sym
                result[sym]["ok"] = False
    return result


def fundamental_score(f: dict[str, Any]) -> tuple[float, list[str]]:
    """
    0~10점 펀더멘털 점수 + 근거 태그.
    - 성장(매출/이익) 가점
    - 합리적 PER/PBR 가점, 과도한 밸류 감점
    - EPS 양수 가점
    """
    score = 0.0
    tags: list[str] = []

    eps = f.get("eps")
    fwd_eps = f.get("fwd_eps")
    per = f.get("per")
    fwd_per = f.get("fwd_per")
    pbr = f.get("pbr")
    rev_g = f.get("rev_g")
    earn_g = f.get("earn_g")
    earn_qg = f.get("earn_qg")

    # EPS
    if eps is not None and eps > 0:
        score += 1.5
        tags.append("EPS+")
    elif eps is not None and eps <= 0:
        score -= 1.0
        tags.append("EPSneg")
    if fwd_eps is not None and eps is not None and fwd_eps > eps > 0:
        score += 0.5
        tags.append("EPS↑")

    # PER (낮을수록 가점, 단 적자/비정상 제외)
    use_per = fwd_per if fwd_per is not None and fwd_per > 0 else per
    if use_per is not None and use_per > 0:
        if use_per < 12:
            score += 2.0
            tags.append("PER저")
        elif use_per < 20:
            score += 1.2
            tags.append("PER중")
        elif use_per < 35:
            score += 0.4
            tags.append("PER고")
        else:
            score -= 0.8
            tags.append("PER과고")

    # PBR (0 이하는 결측으로 간주)
    if pbr is not None and pbr > 0.05:
        if pbr < 1.0:
            score += 1.5
            tags.append("PBR저")
        elif pbr < 2.5:
            score += 0.8
            tags.append("PBR중")
        elif pbr < 5:
            score += 0.2
        else:
            score -= 0.5
            tags.append("PBR고")

    # Revenue growth
    if rev_g is not None:
        pct = rev_g * 100
        if pct >= 20:
            score += 2.0
            tags.append(f"매출+{pct:.0f}%")
        elif pct >= 8:
            score += 1.2
            tags.append(f"매출+{pct:.0f}%")
        elif pct >= 0:
            score += 0.3
            tags.append(f"매출+{pct:.0f}%")
        else:
            score -= 0.8
            tags.append(f"매출{pct:.0f}%")

    # Earnings growth (연/분기 중 더 나은 쪽 위주)
    eg = earn_g if earn_g is not None else earn_qg
    if eg is not None:
        pct = eg * 100
        if pct >= 25:
            score += 2.0
            tags.append(f"이익+{pct:.0f}%")
        elif pct >= 10:
            score += 1.2
            tags.append(f"이익+{pct:.0f}%")
        elif pct >= 0:
            score += 0.3
            tags.append(f"이익+{pct:.0f}%")
        else:
            score -= 1.0
            tags.append(f"이익{pct:.0f}%")

    # clamp
    score = max(0.0, min(10.0, score))
    return score, tags


def fmt_pct(v: float | None) -> str:
    v = _f(v)
    if v is None:
        return "-"
    return f"{v * 100:+.0f}%"


def fmt_num(v: float | None, digits: int = 1) -> str:
    v = _f(v)
    if v is None:
        return "-"
    if abs(v) < 0.0001 and digits <= 1:
        return "-"
    return f"{v:.{digits}f}"
