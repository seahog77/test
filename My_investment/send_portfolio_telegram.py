# -*- coding: utf-8 -*-
"""
통합 포트폴리오 요약 → 텔레그램 전송

.env 에 다음이 필요합니다:
  TELEGRAM_BOT_TOKEN=BotFather에서 받은 토큰
  TELEGRAM_CHAT_ID=getUpdates로 확인한 chat_id

사용:
  python send_portfolio_telegram.py
  python send_portfolio_telegram.py --refresh   # 엑셀 다시 분석 후 전송
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
ANALYSIS = BASE / "_portfolio_analysis.json"
LAST_SENT = BASE / "_last_telegram_portfolio.json"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def won(n: float) -> str:
    if abs(n) >= 1e8:
        return f"{n / 1e8:.1f}억"
    if abs(n) >= 1e4:
        return f"{n / 1e4:.0f}만"
    return f"{n:,.0f}"


def man(n: float) -> str:
    """원 금액을 만원 단위 정수로 (부호 포함). 예: +234만, -12만"""
    v = int(round(float(n) / 1e4))
    return f"{v:+,}만"


def short_name(name: str, n: int = 16) -> str:
    s = (name or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def build_ticker_map(d: dict) -> dict[str, dict]:
    """종목코드별 평가액·수량·테마 집계."""
    out: dict[str, dict] = {}
    rows = d.get("holdings") or []
    if not rows:
        for t in d.get("top_tickers") or []:
            tic = str(t.get("tic") or "")
            if not tic:
                continue
            out[tic] = {
                "name": t.get("name") or tic,
                "val": float(t.get("val") or 0),
                "qty": 0.0,
                "theme": t.get("theme") or "",
            }
        return out

    for h in rows:
        tic = str(h.get("tic") or "")
        if not tic:
            continue
        cur = out.get(tic)
        if cur is None:
            out[tic] = {
                "name": h.get("name") or tic,
                "val": float(h.get("val") or 0),
                "qty": float(h.get("qty") or 0),
                "theme": h.get("theme") or "",
            }
        else:
            cur["val"] += float(h.get("val") or 0)
            cur["qty"] += float(h.get("qty") or 0)
            if h.get("name"):
                cur["name"] = h["name"]
            if h.get("theme"):
                cur["theme"] = h["theme"]
    return out


def build_theme_map(d: dict) -> dict[str, float]:
    themes = d.get("theme") or []
    if themes:
        return {str(t["name"]): float(t["val"]) for t in themes if t.get("name")}
    m: dict[str, float] = {}
    for info in build_ticker_map(d).values():
        th = info.get("theme") or "기타"
        m[th] = m.get(th, 0.0) + float(info.get("val") or 0)
    return m


def load_last_sent() -> dict | None:
    if not LAST_SENT.exists():
        return None
    try:
        return json.loads(LAST_SENT.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_last_sent(d: dict) -> None:
    from datetime import datetime

    tickers = build_ticker_map(d)
    payload = {
        "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "asof": d.get("asof"),
        "total": float(d["total"]),
        "main_total": float(d["main_total"]),
        "w_total": float(d["w_total"]),
        "tickers": {
            k: {
                "name": v["name"],
                "val": round(float(v["val"]), 2),
                "qty": round(float(v["qty"]), 6),
                "theme": v.get("theme") or "",
            }
            for k, v in tickers.items()
        },
        "themes": {k: round(float(v), 2) for k, v in build_theme_map(d).items()},
    }
    LAST_SENT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def delta_line(d: dict, prev: dict | None) -> str:
    if not prev:
        return "이전 전송 대비: (첫 전송 · 비교 기준 없음)"
    d_total = float(d["total"]) - float(prev["total"])
    d_main = float(d["main_total"]) - float(prev["main_total"])
    d_w = float(d["w_total"]) - float(prev["w_total"])
    when = prev.get("sent_at") or prev.get("asof") or "?"
    return (
        f"이전 전송 대비 {man(d_total)} "
        f"(MAIN {man(d_main)} · W {man(d_w)}) · 기준 {when}"
    )


def _split_price_flow(prev_val: float, prev_qty: float, cur_val: float, cur_qty: float):
    """평가액 증감을 시세 효과 / 수량변화(매매·입출)로 대략 분해."""
    delta = cur_val - prev_val
    if prev_qty > 0 and cur_qty > 0:
        prev_px = prev_val / prev_qty
        cur_px = cur_val / cur_qty
        price_effect = prev_qty * (cur_px - prev_px)
        flow_effect = delta - price_effect
        return price_effect, flow_effect
    if prev_qty <= 0 and cur_qty > 0:
        return 0.0, delta  # 신규
    if prev_qty > 0 and cur_qty <= 0:
        return 0.0, delta  # 청산
    return delta, 0.0


def analyze_change_drivers(d: dict, prev: dict | None, top_n: int = 3) -> list[str]:
    """이전 전송 대비 증감 원인 설명 줄 목록."""
    if not prev or not prev.get("tickers"):
        return ["(이전 종목 스냅샷 없음 · 다음 전송부터 원인 분석)"]

    cur_map = build_ticker_map(d)
    prev_map = prev.get("tickers") or {}
    all_tics = set(cur_map) | set(prev_map)

    rows = []
    price_sum = flow_sum = 0.0
    for tic in all_tics:
        cur = cur_map.get(tic) or {"name": tic, "val": 0.0, "qty": 0.0, "theme": ""}
        prv = prev_map.get(tic) or {"name": cur["name"], "val": 0.0, "qty": 0.0, "theme": ""}
        name = cur.get("name") or prv.get("name") or tic
        theme = cur.get("theme") or prv.get("theme") or ""
        cur_val = float(cur.get("val") or 0)
        prev_val = float(prv.get("val") or 0)
        cur_qty = float(cur.get("qty") or 0)
        prev_qty = float(prv.get("qty") or 0)
        delta = cur_val - prev_val
        if abs(delta) < 5000:  # 0.5만원 미만 무시
            continue
        pe, fe = _split_price_flow(prev_val, prev_qty, cur_val, cur_qty)
        price_sum += pe
        flow_sum += fe
        is_cash = "현금" in (theme or "") or tic in {"현금", "CMA", "예금"}
        if is_cash:
            tag = "현금 변동"
            # 현금은 시세보다 입출금으로 보는 편이 맞음
            price_sum -= pe
            flow_sum -= fe
            flow_sum += delta
        elif prev_val <= 0 and cur_val > 0:
            tag = "신규"
        elif cur_val <= 0 and prev_val > 0:
            tag = "제외/매도"
        elif abs(fe) > abs(pe) * 1.2 and abs(fe) >= 1e4:
            tag = "매매·입출 추정"
        else:
            tag = "시세"
        rows.append(
            {
                "tic": tic,
                "name": name,
                "theme": theme,
                "delta": delta,
                "tag": tag,
                "pe": pe,
                "fe": fe,
            }
        )

    if not rows:
        return ["유의미한 종목 변동 없음 (만원 단위 미만)"]

    rows.sort(key=lambda x: x["delta"], reverse=True)
    gainers = [r for r in rows if r["delta"] > 0][:top_n]
    losers = [r for r in rows if r["delta"] < 0][-top_n:]
    losers = sorted(losers, key=lambda x: x["delta"])  # most negative first

    # theme deltas
    cur_th = build_theme_map(d)
    prev_th = prev.get("themes") or {}
    theme_deltas = []
    for name in set(cur_th) | set(prev_th):
        dd = float(cur_th.get(name, 0)) - float(prev_th.get(name, 0))
        if abs(dd) >= 1e4:
            theme_deltas.append((name, dd))
    theme_deltas.sort(key=lambda z: abs(z[1]), reverse=True)

    lines: list[str] = []
    for r in gainers:
        lines.append(f"↑ {short_name(r['name'])} {man(r['delta'])} ({r['tag']})")
    for r in losers:
        lines.append(f"↓ {short_name(r['name'])} {man(r['delta'])} ({r['tag']})")

    # summary narrative
    total_delta = float(d["total"]) - float(prev["total"])
    direction = "증가" if total_delta > 0 else "감소" if total_delta < 0 else "보합"
    parts = []
    if theme_deltas:
        top_th_name, top_th_d = theme_deltas[0]
        parts.append(f"{top_th_name} {man(top_th_d)}")
    if abs(price_sum) >= 1e4 or abs(flow_sum) >= 1e4:
        parts.append(f"시세 {man(price_sum)} · 매매/입출 {man(flow_sum)}")
    if gainers and abs(gainers[0]["delta"]) >= abs(total_delta) * 0.35 and total_delta != 0:
        parts.append(f"주도 {short_name(gainers[0]['name'], 12)}")
    elif losers and total_delta < 0 and abs(losers[0]["delta"]) >= abs(total_delta) * 0.35:
        parts.append(f"하락 주도 {short_name(losers[0]['name'], 12)}")

    summary = f"요약: 자산 {direction}"
    if parts:
        summary += " — " + ", ".join(parts)
    lines.append(summary)
    return lines


def build_message(d: dict, prev: dict | None = None) -> str:
    themes = d.get("theme") or []
    top_theme = ", ".join(f"{t['name']} {t['pct']:.0f}%" for t in themes[:4])
    top = (d.get("top_tickers") or [])[:5]
    top_lines = []
    for t in top:
        top_lines.append(f"· {t['name'][:22]} {t['pct']:.1f}%")

    perf = d.get("perf") or {}
    # weighted from analysis if present
    w1m = d.get("w1m")
    w3m = d.get("w3m")
    if w1m is None or w3m is None:
        tw = w1 = w3 = 0.0
        for p in perf.values():
            if p.get("r1m") is None:
                continue
            w = float(p["val"])
            tw += w
            w1 += w * float(p["r1m"])
            w3 += w * float(p["r3m"])
        if tw > 0:
            w1m, w3m = w1 / tw, w3 / tw
        else:
            w1m = w3m = 0.0

    cc = float(d.get("cc_share") or 0) * 100
    top1 = float(d.get("top1_share") or 0) * 100
    cash = float(d.get("cash_share") or 0) * 100
    bond = float(d.get("bond_share") or 0) * 100

    driver_lines = analyze_change_drivers(d, prev)

    lines = [
        f"📊 통합 포트폴리오 요약 ({d.get('asof', '')})",
        "",
        f"합산 {won(d['total'])} (MAIN {won(d['main_total'])} + W {won(d['w_total'])})",
        delta_line(d, prev),
        f"종목 {d.get('n_tickers', '?')}개 · 행 {d.get('n_main', 0)}+{d.get('n_w', 0)}",
        "",
        "【증감 원인】",
        *driver_lines,
        "",
        f"가중 1개월 {w1m:+.1f}% · 3개월 {w3m:+.1f}%",
        f"커버드콜 {cc:.0f}% · 1위종목 {top1:.0f}%",
        f"현금 {cash:.0f}% · 채권·혼합 {bond:.0f}%",
        "",
        "【테마】",
        top_theme or "-",
        "",
        "【상위】",
        *top_lines,
        "",
        "【총평】",
        "소득형(커버드콜) 방향은 맞음.",
        f"다만 458760 단독 {top1:.0f}%·CC {cc:.0f}%로 집중도 높음.",
        "1위 비중 축소 + 순수 지수 ETF 소폭 증액 권장.",
        "",
        "(텔레그램 → 카톡 붙여넣기용)",
    ]
    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {e.code}: {err_body}") from e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="엑셀 재분석 후 전송 (_analyze_combined_portfolio.py)",
    )
    ap.add_argument("--dry-run", action="store_true", help="전송 없이 메시지만 출력")
    args = ap.parse_args()

    load_dotenv(BASE / ".env")
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

    if args.refresh or not ANALYSIS.exists():
        import subprocess
        import sys

        script = BASE / "_analyze_combined_portfolio.py"
        if not script.exists():
            raise SystemExit(f"분석 스크립트 없음: {script}")
        print("분석 재실행...")
        subprocess.check_call([sys.executable, "-X", "utf8", str(script)], cwd=str(BASE))

    if not ANALYSIS.exists():
        raise SystemExit(f"분석 결과 없음: {ANALYSIS}  (--refresh 로 생성)")

    d = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    # enrich weighted returns for message
    perf = d.get("perf") or {}
    tw = w1 = w3 = 0.0
    for p in perf.values():
        if p.get("r1m") is None:
            continue
        w = float(p["val"])
        tw += w
        w1 += w * float(p["r1m"])
        w3 += w * float(p["r3m"])
    if tw > 0:
        d["w1m"] = w1 / tw
        d["w3m"] = w3 / tw

    prev = load_last_sent()
    msg = build_message(d, prev)
    print(msg)
    print("---")

    if args.dry_run:
        print("(dry-run: 전송 안 함)")
        return

    if not token or not chat_id:
        raise SystemExit(
            ".env 에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없습니다.\n"
            "BotFather 토큰과 getUpdates chat_id 를 .env 에 넣은 뒤 다시 실행하세요."
        )

    result = send_telegram(token, chat_id, msg)
    if not result.get("ok"):
        raise SystemExit(f"전송 실패: {result}")
    save_last_sent(d)
    print(f"텔레그램 전송 완료. (비교 기준 저장: {LAST_SENT.name})")


if __name__ == "__main__":
    main()
