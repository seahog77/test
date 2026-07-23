# -*- coding: utf-8 -*-
"""
주식 관련 해외/국내 주요 뉴스 요약 → 텔레그램

사용:
  python send_market_news_telegram.py
"""
from __future__ import annotations

import html
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from send_portfolio_telegram import load_dotenv, send_telegram

BASE = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (compatible; MyInvestmentNews/1.0)"

FEEDS = [
    (
        "US",
        "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "US",
        "https://news.google.com/rss/search?q="
        + quote_plus("stock market OR Federal Reserve OR Wall Street")
        + "&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "KR",
        "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko",
    ),
    (
        "KR",
        "https://news.google.com/rss/search?q="
        + quote_plus("증시 OR 코스피 OR 연준 OR 반도체")
        + "&hl=ko&gl=KR&ceid=KR:ko",
    ),
]


def fetch_rss(url: str, limit: int = 12) -> list[dict]:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=25) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    items = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        title = html.unescape(re.sub(r"\s+", " ", title))
        # Google: "Headline - Outlet"
        if " - " in title and not source:
            title, source = title.rsplit(" - ", 1)
        if not title:
            continue
        ts = None
        if pub:
            try:
                ts = parsedate_to_datetime(pub)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                ts = None
        items.append(
            {
                "title": title.strip(),
                "source": source.strip(),
                "link": link,
                "ts": ts,
            }
        )
    return items


def norm_key(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^a-z0-9가-힣\s]", "", t)
    return re.sub(r"\s+", " ", t)[:80]


def collect_news(per_market: int = 6) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {"US": [], "KR": []}
    seen: set[str] = set()
    for market, url in FEEDS:
        try:
            items = fetch_rss(url, limit=15)
        except Exception as e:
            print(f"feed fail [{market}]: {e}")
            continue
        for it in items:
            key = norm_key(it["title"])
            if key in seen or len(key) < 8:
                continue
            seen.add(key)
            buckets[market].append(it)
    for m in buckets:
        buckets[m].sort(
            key=lambda x: x["ts"] or datetime(1970, 1, 1, tzinfo=timezone.utc),
            reverse=True,
        )
        buckets[m] = buckets[m][:per_market]
    return buckets


def theme_hint(title: str) -> str:
    t = title.lower()
    rules = [
        (("fed", "금리", "연준", "rate cut", "rate hike", "fomc", "inflation", "물가"), "금리·물가"),
        (("nvidia", "반도체", "chip", "ai ", "samsung", "sk hynix", "하이닉스", "tsmc"), "반도체·AI"),
        (("oil", "crude", "유가", "opec"), "유가"),
        (("korea", "kospi", "코스피", "코스닥", "한국"), "한국증시"),
        (("earnings", "실적", "guidance"), "실적"),
        (("china", "중국", "관세", "tariff"), "중국·통상"),
        (("bitcoin", "crypto", "비트코인"), "크립토"),
        (("dollar", "환율", "원/달러", "usd"), "환율"),
    ]
    for keys, label in rules:
        if any(k in t or k in title for k in keys):
            return label
    return "시장일반"


def build_message(buckets: dict[str, list[dict]]) -> str:
    asof = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"주식 주요 뉴스 요약 ({asof})",
        "출처: Google News RSS (해외 Business / 국내 경제·증시)",
        "",
    ]

    # theme rollup
    themes: dict[str, int] = {}
    for m in ("US", "KR"):
        for it in buckets.get(m, []):
            th = theme_hint(it["title"])
            themes[th] = themes.get(th, 0) + 1
    if themes:
        top_th = sorted(themes.items(), key=lambda x: -x[1])[:4]
        lines.append("【오늘 키워드】 " + " · ".join(f"{k}({v})" for k, v in top_th))
        lines.append("")

    lines.append("【해외】")
    for i, it in enumerate(buckets.get("US", []), 1):
        src = f" · {it['source']}" if it["source"] else ""
        lines.append(f"{i}. {it['title'][:90]}{src}")
    if not buckets.get("US"):
        lines.append("(수집 실패)")

    lines.append("")
    lines.append("【국내】")
    for i, it in enumerate(buckets.get("KR", []), 1):
        src = f" · {it['source']}" if it["source"] else ""
        lines.append(f"{i}. {it['title'][:90]}{src}")
    if not buckets.get("KR"):
        lines.append("(수집 실패)")

    # short takeaways from titles
    all_titles = [it["title"] for it in buckets.get("US", []) + buckets.get("KR", [])]
    takeaways = []
    blob = " ".join(all_titles).lower()
    if any(k in blob for k in ("fed", "rate", "연준", "금리", "fomc")):
        takeaways.append("금리·연준 관련 헤드라인이 섞여 있음 → 금리 민감 자산 변동성 주의")
    if any(k in blob for k in ("nvidia", "반도체", "ai", "하이닉스", "samsung")):
        takeaways.append("반도체·AI 뉴스가 다수 → 성장/테크 테마 관심 구간")
    if any(k in blob for k in ("kospi", "코스피", "증시", "외국인")):
        takeaways.append("국내 증시·수급 관련 기사 포함 → 코스피/반도체 동반 체크")
    if not takeaways:
        takeaways.append("특이 테마보다 일반 시장·기업 뉴스가 중심")

    lines += ["", "【한줄 정리】", *[f"· {t}" for t in takeaways[:3]], "", "※ 헤드라인 요약. 투자 판단은 본인 책임."]
    msg = "\n".join(lines)
    # Telegram limit ~4096
    if len(msg) > 3900:
        msg = msg[:3900] + "\n…(생략)"
    return msg


def main():
    load_dotenv(BASE / ".env")
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        raise SystemExit(".env 에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 필요")

    print("뉴스 수집 중...", flush=True)
    buckets = collect_news(per_market=6)
    print(f"US {len(buckets['US'])} · KR {len(buckets['KR'])}", flush=True)
    msg = build_message(buckets)
    print(msg)
    print("---", flush=True)
    result = send_telegram(token, chat_id, msg)
    if not result.get("ok"):
        raise SystemExit(f"전송 실패: {result}")
    print("텔레그램 전송 완료.", flush=True)


if __name__ == "__main__":
    main()
