# -*- coding: utf-8 -*-
"""
TOP7 자동매매 — 코스피 TOP30 신호 랭킹 상위 7종 분산 매수
익절 +10% (익일 시가) / 손절 -10% (당일)

사용 예
-------
  python top7_trader.py scan
  python top7_trader.py status
  python top7_trader.py run                  # dry-run (기본)
  python top7_trader.py run --execute        # 실제 주문
  python top7_trader.py run --execute --budget 5000000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from toss_client import TossInvestClient, TossInvestError
from top7_strategy import (
    StrategyConfig,
    buy_shares,
    check_sl,
    check_tp_reached,
    get_bar,
    get_kospi_top30,
    latest_signal_date,
    latest_trade_date,
    load_hist_map,
    open_px,
    rank_stocks,
)

warnings.filterwarnings("ignore")

_PROJECT_DIR = Path(__file__).resolve().parent
_STATE_FILE = _PROJECT_DIR / "top7_state.json"
load_dotenv(_PROJECT_DIR / ".env")
sys.stdout.reconfigure(encoding="utf-8")


@dataclass
class Action:
    side: str
    symbol: str
    name: str
    qty: int
    price: float | None
    reason: str
    executed: bool = False
    order_id: str | None = None


def _load_config() -> StrategyConfig:
    return StrategyConfig(
        top_n=int(os.getenv("TOP7_TOP_N", "7")),
        take_profit=float(os.getenv("TOP7_TAKE_PROFIT", "0.10")),
        stop_loss=float(os.getenv("TOP7_STOP_LOSS", "-0.10")),
        min_cash=float(os.getenv("TOP7_MIN_CASH", "200000")),
    )


def _budget_limit() -> float | None:
    raw = os.getenv("TOP7_BUDGET", "").strip()
    if not raw:
        return None
    return float(raw)


def _load_state() -> dict:
    if not _STATE_FILE.exists():
        return {"version": 1, "positions": {}, "last_run_date": None}
    with _STATE_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _save_state(state: dict) -> None:
    with _STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _fmt_money(v) -> str:
    try:
        return f"{float(v):,.0f}원"
    except (TypeError, ValueError):
        return str(v)


def _holding_map(client: TossInvestClient, account_seq: int | None) -> dict[str, dict]:
    data = client.get_holdings(account_seq=account_seq)
    out = {}
    for it in data.get("items", []):
        sym = str(it.get("symbol", "")).zfill(6)
        out[sym] = it
    return out


def _sync_positions(state: dict, holdings: dict[str, dict]) -> None:
    """전략 포지션을 API 보유와 동기화."""
    for sym in list(state["positions"].keys()):
        if sym not in holdings:
            del state["positions"][sym]


def _client_order_id(side: str, symbol: str, date_str: str) -> str:
    return f"top7-{side[:1]}-{symbol}-{date_str}"[:36]


def cmd_scan(cfg: StrategyConfig) -> int:
    print("데이터 로드 중...")
    top30 = get_kospi_top30()
    hist_map = load_hist_map(top30)
    if not hist_map:
        print("OHLCV 데이터를 불러오지 못했습니다.")
        return 1

    sig_date = latest_signal_date(hist_map)
    trade_date = latest_trade_date(hist_map)
    if sig_date is None:
        print("신호 계산용 거래일이 부족합니다.")
        return 1

    ranking = rank_stocks(hist_map, sig_date)
    print(f"\n=== TOP{cfg.top_n} 매수 후보 (신호일: {sig_date.date()}, 기준가: {trade_date.date()}) ===")
    if ranking.empty:
        print("매수 신호 종목 없음")
        return 0

    print(f"{'순위':>4} {'심볼':<8} {'종목명':<14} {'매수신호':>6} {'매도신호':>6} {'순점수':>6}  신호")
    print("-" * 80)
    for i, row in ranking.head(cfg.top_n).iterrows():
        print(
            f"{i+1:>4} {row['tic']:<8} {str(row['name'])[:12]:<14} "
            f"{row['buy_hit']:>6} {row['sell_hit']:>6} {row['net']:>6}  {row['signals']}"
        )
    return 0


def cmd_status(client: TossInvestClient, account_seq: int | None, cfg: StrategyConfig) -> int:
    state = _load_state()
    holdings = _holding_map(client, account_seq)
    _sync_positions(state, holdings)

    print("=== TOP7 전략 상태 ===")
    print(f"  상태파일: {_STATE_FILE}")
    print(f"  마지막 실행: {state.get('last_run_date') or '-'}")
    print(f"  익절/손절: +{cfg.take_profit*100:.0f}% / {cfg.stop_loss*100:.0f}%")
    print()

    if not state["positions"]:
        print("전략 보유 종목 없음")
    else:
        print(f"{'심볼':<8} {'종목명':<14} {'수량':>6} {'평단':>10} {'익절대기':>8} {'보유일':>6}")
        print("-" * 60)
        for sym, pos in state["positions"].items():
            h = holdings.get(sym, {})
            qty = h.get("quantity", "-")
            avg = h.get("averagePurchasePrice", "-")
            tp = "예" if pos.get("tp_pending") else "-"
            print(
                f"{sym:<8} {str(pos.get('name', ''))[:12]:<14} {str(qty):>6} "
                f"{str(avg):>10} {tp:>8} {pos.get('hold_days', 0):>6}"
            )

    try:
        bp = client.get_buying_power(account_seq=account_seq, currency="KRW")
        cash = float(bp.get("cashBuyingPower", 0))
        print(f"\n매수 가능(KRW): {_fmt_money(cash)}")
        budget = _budget_limit()
        if budget:
            print(f"전략 예산 한도: {_fmt_money(min(cash, budget))}")
    except TossInvestError as e:
        print(f"\n매수가능 조회 실패: {e}")

    _save_state(state)
    return 0


def _plan_actions(
    client: TossInvestClient,
    account_seq: int | None,
    cfg: StrategyConfig,
    budget: float | None,
    execute: bool,
) -> tuple[list[Action], dict]:
    state = _load_state()
    holdings = _holding_map(client, account_seq)
    _sync_positions(state, holdings)

    top30 = get_kospi_top30()
    extra = list(state["positions"].keys())
    hist_map = load_hist_map(top30, extra_symbols=extra)
    if not hist_map:
        raise TossInvestError("OHLCV 데이터를 불러오지 못했습니다.")

    sig_date = latest_signal_date(hist_map)
    trade_date = latest_trade_date(hist_map)
    if sig_date is None or trade_date is None:
        raise TossInvestError("거래일 데이터가 부족합니다.")

    actions: list[Action] = []
    day_sells = 0
    today_str = trade_date.strftime("%Y%m%d")

    # 1) 익절 대기 → 익일 시가 매도
    for sym in list(state["positions"].keys()):
        pos = state["positions"][sym]
        if not pos.get("tp_pending"):
            continue
        h = holdings.get(sym)
        if not h:
            continue
        qty = int(float(h.get("quantity", 0)))
        if qty <= 0:
            continue
        price = float(h.get("lastPrice") or 0)
        actions.append(Action(
            side="SELL", symbol=sym, name=pos.get("name", sym),
            qty=qty, price=price,
            reason=f"익절+{cfg.take_profit*100:.0f}%(익일시가)",
        ))
        day_sells += 1

    # 2) 손절 / 익절 도달 체크
    for sym in list(state["positions"].keys()):
        pos = state["positions"][sym]
        if pos.get("tp_pending"):
            continue
        if any(a.symbol == sym and a.side == "SELL" for a in actions):
            continue
        h = holdings.get(sym)
        if not h:
            continue
        bar = get_bar(hist_map, sym, trade_date)
        if bar is None:
            continue
        avg_cost = float(h.get("averagePurchasePrice") or 0)
        if avg_cost <= 0:
            continue
        pos["hold_days"] = int(pos.get("hold_days", 0)) + 1

        hit, sell_px, reason = check_sl(bar, avg_cost, cfg.stop_loss)
        qty = int(float(h.get("quantity", 0)))
        if qty <= 0:
            continue
        if hit:
            actions.append(Action(
                side="SELL", symbol=sym, name=pos.get("name", sym),
                qty=qty, price=float(sell_px), reason=reason,
            ))
            day_sells += 1
        elif check_tp_reached(bar, avg_cost, cfg.take_profit):
            pos["tp_pending"] = True
            actions.append(Action(
                side="HOLD", symbol=sym, name=pos.get("name", sym),
                qty=0, price=None, reason=f"익절+{cfg.take_profit*100:.0f}% 도달 → 익일 매도 예약",
            ))

    # 3) 재매수 조건
    ranking = rank_stocks(hist_map, sig_date)
    bp = client.get_buying_power(account_seq=account_seq, currency="KRW")
    cash = float(bp.get("cashBuyingPower", 0))
    if budget is not None:
        cash = min(cash, budget) if cash > 0 else budget

    simulated_cash = False
    effective_cash = cash
    if not execute and effective_cash < cfg.min_cash:
        effective_cash = budget or _budget_limit() or 10_000_000
        simulated_cash = True

    strategy_count = len(state["positions"])
    pending_sell_syms = {a.symbol for a in actions if a.side == "SELL"}
    strategy_count_after_sells = strategy_count - len(
        [s for s in pending_sell_syms if s in state["positions"]]
    )

    if effective_cash >= cfg.min_cash and (day_sells > 0 or strategy_count_after_sells == 0) and not ranking.empty:
        n = min(cfg.top_n, len(ranking))
        per = effective_cash / n
        picks = ranking.head(n)
        for _, row in picks.iterrows():
            sym = row["tic"]
            bar = get_bar(hist_map, sym, trade_date)
            if bar is None:
                continue
            buy_px = open_px(bar)
            qty, _ = buy_shares(per, buy_px, cfg.comm_rate)
            if qty <= 0:
                continue
            reason = f"TOP{cfg.top_n} 1/{n} (신호 {row['buy_hit']}개)"
            if simulated_cash:
                reason += f" [시뮬: {_fmt_money(effective_cash)} 가정]"
            actions.append(Action(
                side="BUY", symbol=sym, name=row["name"],
                qty=qty, price=buy_px, reason=reason,
            ))

    if execute:
        for act in actions:
            if act.side not in ("BUY", "SELL"):
                continue
            cid = _client_order_id(act.side, act.symbol, today_str)
            try:
                if act.side == "SELL":
                    sellable = client.get_sellable_quantity(act.symbol, account_seq=account_seq)
                    max_qty = int(float(sellable.get("sellableQuantity", act.qty)))
                    act.qty = min(act.qty, max_qty)
                    if act.qty <= 0:
                        continue
                result = client.create_order(
                    act.symbol,
                    act.side,
                    act.qty,
                    order_type="MARKET",
                    client_order_id=cid,
                    account_seq=account_seq,
                )
                act.executed = True
                act.order_id = result.get("orderId")
            except TossInvestError as e:
                act.reason = f"{act.reason} [실패: {e}]"

        for act in actions:
            sym = act.symbol
            if act.side == "SELL" and act.executed:
                state["positions"].pop(sym, None)
            elif act.side == "BUY" and act.executed:
                pos = state["positions"].get(sym, {
                    "name": act.name, "tp_pending": False, "hold_days": 0,
                })
                pos["name"] = act.name
                pos["tp_pending"] = False
                pos["hold_days"] = 0
                state["positions"][sym] = pos
            elif act.side == "HOLD":
                state["positions"][sym] = state["positions"].get(sym, {
                    "name": act.name, "hold_days": 0,
                })
                state["positions"][sym]["tp_pending"] = True

        state["last_run_date"] = datetime.now().strftime("%Y-%m-%d")
        _save_state(state)

    return actions, state


def cmd_run(
    client: TossInvestClient,
    account_seq: int | None,
    cfg: StrategyConfig,
    budget: float | None,
    execute: bool,
) -> int:
    mode = "실행" if execute else "DRY-RUN"
    print(f"=== TOP7 자동매매 [{mode}] ===")
    print(f"  익절 +{cfg.take_profit*100:.0f}% (익일) / 손절 {cfg.stop_loss*100:.0f}%")
    if budget:
        print(f"  예산 한도: {_fmt_money(budget)}")
    print()

    try:
        actions, _ = _plan_actions(client, account_seq, cfg, budget, execute)
    except TossInvestError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    if not actions:
        print("오늘 실행할 매매 없음")
        return 0

    for act in actions:
        if act.side == "HOLD":
            print(f"  [예약] {act.symbol} {act.name} — {act.reason}")
            continue
        px = f" @ {act.price:,.0f}" if act.price else ""
        mark = " ✓" if act.executed else ""
        oid = f" (orderId={act.order_id})" if act.order_id else ""
        print(f"  [{act.side}] {act.symbol} {act.name} {act.qty}주{px} — {act.reason}{mark}{oid}")

    if not execute:
        print("\n→ 실제 주문은 --execute 옵션을 붙여 실행하세요.")
    else:
        print(f"\n상태 저장: {_STATE_FILE}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="TOP7 자동매매 (코스피 TOP30 신호 랭킹)")
    p.add_argument("--account-seq", type=int, default=None)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="TOP7 매수 후보 조회")
    sub.add_parser("status", help="전략 보유·상태 조회")

    run = sub.add_parser("run", help="매매 로직 실행")
    run.add_argument("--execute", action="store_true", help="실제 주문 (기본: dry-run)")
    run.add_argument("--budget", type=float, default=None, help="투입 예산 상한 (원)")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    cfg = _load_config()

    account_seq = args.account_seq
    if account_seq is None:
        env_seq = os.getenv("TOSSINVEST_ACCOUNT_SEQ", "").strip()
        if env_seq:
            account_seq = int(env_seq)

    if args.command == "scan":
        return cmd_scan(cfg)

    try:
        client = TossInvestClient.from_env()
        if account_seq is not None:
            client.account_seq = account_seq
    except TossInvestError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    if args.command == "status":
        return cmd_status(client, account_seq, cfg)
    if args.command == "run":
        budget = args.budget if args.budget is not None else _budget_limit()
        return cmd_run(client, account_seq, cfg, budget, args.execute)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
