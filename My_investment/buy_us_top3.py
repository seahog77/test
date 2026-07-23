# -*- coding: utf-8 -*-
"""미국 TOP3 1주씩 시장가 매수."""
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from toss_client import TossInvestClient, TossInvestError

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).resolve().parent / ".env")

SYMBOLS = [
    ("XOM", "Exxon"),
    ("CVX", "Chevron"),
    ("WMT", "Walmart"),
]


def main() -> int:
    client = TossInvestClient.from_env()
    bp = client.get_buying_power(currency="USD")
    cash = float(bp.get("cashBuyingPower") or 0)
    print(f"매수가능 USD: ${cash:,.2f}")

    syms = [s for s, _ in SYMBOLS]
    prices = {p.get("symbol"): p for p in client.get_prices(syms)}
    est = 0.0
    for sym, name in SYMBOLS:
        px = prices.get(sym, {}).get("lastPrice")
        px_f = float(px) if px not in (None, "") else 0.0
        est += px_f
        print(f"  {sym} {name}: ${px_f:,.2f} x 1주")
    print(f"예상 합계(단순): ${est:,.2f}")

    if cash < est * 0.95:
        print("오류: USD 매수가능금액이 부족합니다. 주문을 실행하지 않습니다.")
        return 1

    print("\n=== 시장가 매수 실행 ===")
    day = datetime.now().strftime("%Y%m%d")
    ok = 0
    for sym, name in SYMBOLS:
        cid = f"us3-{sym}-{day}"[:36]
        try:
            result = client.create_order(
                sym,
                "BUY",
                1,
                order_type="MARKET",
                client_order_id=cid,
            )
            oid = result.get("orderId") if isinstance(result, dict) else result
            print(f"  [OK] {sym} {name} 1주  BUY MARKET  orderId={oid}")
            ok += 1
        except TossInvestError as e:
            print(f"  [FAIL] {sym} {name}: {e}")
    print(f"\n완료: {ok}/{len(SYMBOLS)}")
    return 0 if ok == len(SYMBOLS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
