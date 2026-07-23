# -*- coding: utf-8 -*-
"""
토스증권 Open API — 계좌 조회 · 종목 검색 CLI

사전 준비
---------
1. 토스증권 WTS > 설정 > Open API 에서 client_id / client_secret 발급
2. 허용 IP 등록 (집/사무실 공인 IP)
3. .env 파일 작성 (.env.example 참고)

사용 예
-------
  python toss_app.py accounts
  python toss_app.py holdings
  python toss_app.py holdings --symbol 005930
  python toss_app.py buying-power
  python toss_app.py search 005930
  python toss_app.py search 삼성전자
  python toss_app.py search AAPL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from toss_client import TossInvestClient, TossInvestError

_PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(_PROJECT_DIR / ".env")
sys.stdout.reconfigure(encoding="utf-8")


def _fmt_money(v, currency="KRW") -> str:
    if v is None:
        return "-"
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v)
    if currency == "KRW":
        return f"{n:,.0f}원"
    return f"{n:,.2f} {currency}"


def cmd_accounts(client: TossInvestClient) -> None:
    accounts = client.get_accounts()
    if not accounts:
        print("등록된 종합매매 계좌가 없습니다.")
        return
    print(f"{'SEQ':>4}  {'계좌번호':<14}  {'유형'}")
    print("-" * 40)
    for a in accounts:
        print(f"{a.get('accountSeq', ''):>4}  {a.get('accountNo', ''):<14}  {a.get('accountType', '')}")


def _pct(rate) -> str:
    if rate in (None, ""):
        return "-"
    try:
        return f"{float(rate) * 100:.2f}%"
    except (TypeError, ValueError):
        return str(rate)


def cmd_holdings(client: TossInvestClient, account_seq: int | None, symbol: str | None) -> None:
    data = client.get_holdings(account_seq=account_seq, symbol=symbol)
    items = data.get("items", [])
    mv = data.get("marketValue", {}).get("amount", {})
    pl = data.get("profitLoss", {})
    pl_amt = pl.get("amount", {})
    tpa = data.get("totalPurchaseAmount", {})

    print("=== 보유 요약 ===")
    print(f"  평가금액(KRW): {_fmt_money(mv.get('krw'))}")
    print(f"  평가금액(USD): {_fmt_money(mv.get('usd'), 'USD')}")
    print(f"  매입금액(KRW): {_fmt_money(tpa.get('krw'))}")
    print(f"  평가손익(KRW): {_fmt_money(pl_amt.get('krw'))}")
    print(f"  수익률       : {_pct(pl.get('rate'))}")
    print(f"  보유종목수   : {len(items)}")
    print()

    if not items:
        print("보유 종목 없음")
        return

    print(f"{'심볼':<8} {'종목명':<16} {'수량':>8} {'평단':>12} {'현재가':>12} {'수익률':>8}")
    print("-" * 72)
    for it in items:
        sym = it.get("symbol", "")
        name = (it.get("name") or "")[:14]
        qty = it.get("quantity", "")
        avg = it.get("averagePurchasePrice", "")
        cur = it.get("lastPrice", "")
        rate = _pct(it.get("profitLoss", {}).get("rate"))
        print(f"{sym:<8} {name:<16} {qty:>8} {avg:>12} {cur:>12} {rate:>8}")


def cmd_buying_power(
    client: TossInvestClient, account_seq: int | None, currency: str | None
) -> None:
    currencies = [currency.upper()] if currency else ["KRW", "USD"]
    print("=== 매수 가능 금액 ===")
    for cur in currencies:
        data = client.get_buying_power(account_seq=account_seq, currency=cur)
        amount = data.get("cashBuyingPower")
        print(f"  {cur}: {_fmt_money(amount, cur)}")


def cmd_search(client: TossInvestClient, query: str) -> None:
    rows = client.search(query)
    if not rows:
        print(f"'{query}' 검색 결과 없음")
        return
    print(f"{'심볼':<10} {'종목명':<18} {'시장':<10} {'현재가':>12} {'등락률':>8}")
    print("-" * 64)
    for r in rows:
        sym = r.get("symbol", "")
        name = (r.get("name") or "")[:16]
        market = r.get("market", "")
        price = r.get("price", "-")
        chg = r.get("changeRate", "-")
        if chg not in (None, "-"):
            chg = f"{chg}%"
        print(f"{sym:<10} {name:<18} {market:<10} {str(price):>12} {str(chg):>8}")


def cmd_raw(client: TossInvestClient, path: str) -> None:
    """디버그용 raw 호출."""
    result = client._request("GET", path)  # noqa: SLF001
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="토스증권 Open API — 계좌조회·종목검색")
    p.add_argument("--account-seq", type=int, default=None, help="accountSeq (미지정 시 .env 또는 첫 계좌)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("accounts", help="계좌 목록")
    sub.add_parser("account", help="계좌 목록 (accounts 별칭)")

    h = sub.add_parser("holdings", help="보유 종목")
    h.add_argument("--symbol", default=None, help="특정 종목만 (예: 005930)")

    bp = sub.add_parser("buying-power", help="매수 가능 금액")
    bp.add_argument(
        "--currency",
        choices=["KRW", "USD", "krw", "usd"],
        default=None,
        help="통화 (미지정 시 KRW·USD 모두 조회)",
    )

    s = sub.add_parser("search", help="종목 검색 (심볼 또는 한글명)")
    s.add_argument("query", help="예: 005930, 삼성전자, AAPL")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    account_seq = args.account_seq
    if account_seq is None:
        env_seq = os.getenv("TOSSINVEST_ACCOUNT_SEQ", "").strip()
        if env_seq:
            account_seq = int(env_seq)

    try:
        client = TossInvestClient.from_env()
        if account_seq is not None:
            client.account_seq = account_seq

        if args.command in ("accounts", "account"):
            cmd_accounts(client)
        elif args.command == "holdings":
            cmd_holdings(client, account_seq, args.symbol)
        elif args.command == "buying-power":
            cmd_buying_power(client, account_seq, args.currency)
        elif args.command == "search":
            cmd_search(client, args.query)
        else:
            parser.print_help()
            return 1
    except TossInvestError as e:
        print(f"오류: {e}", file=sys.stderr)
        if e.status_code == 401:
            print("→ client_id / client_secret 이 맞는지, WTS Open API 승인 상태를 확인하세요.", file=sys.stderr)
        if e.status_code == 403:
            print("→ WTS Open API 설정에서 허용 IP 를 확인하세요.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
