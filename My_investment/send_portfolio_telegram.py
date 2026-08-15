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


def load_last_sent() -> dict | None:
    if not LAST_SENT.exists():
        return None
    try:
        return json.loads(LAST_SENT.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_last_sent(d: dict) -> None:
    from datetime import datetime

    payload = {
        "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "asof": d.get("asof"),
        "total": float(d["total"]),
        "main_total": float(d["main_total"]),
        "w_total": float(d["w_total"]),
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

    lines = [
        f"📊 통합 포트폴리오 요약 ({d.get('asof', '')})",
        "",
        f"합산 {won(d['total'])} (MAIN {won(d['main_total'])} + W {won(d['w_total'])})",
        delta_line(d, prev),
        f"종목 {d.get('n_tickers', '?')}개 · 행 {d.get('n_main', 0)}+{d.get('n_w', 0)}",
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
