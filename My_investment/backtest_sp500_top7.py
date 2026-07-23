# -*- coding: utf-8 -*-
"""S&P500 시총 TOP30 — TOP7 분산, 익절 +10%/-10% (최근 1년) 백테스트"""
import sys
import warnings
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from signal_rules import check_buy_signals, check_sell_signals

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

INITIAL = 10_000.0          # USD
COMM_RATE = 0.001           # 해외주식 수수료 ~0.1%
TAX_RATE = 0.0              # 미국주식 매도세 (증권사 기준 단순화)
STOP_LOSS = -0.10
TOP_N = 7
MIN_DEPLOY_CASH = 200.0
# (label, take_profit, stop_loss)
SCENARIOS = [
    ("TP10_SL10", 0.10, -0.10),
    ("TP20_SL10", 0.20, -0.10),
    ("TP30_SL10", 0.30, -0.10),
    ("TP20_SL5", 0.20, -0.05),
]

END = pd.Timestamp(datetime.now().date())
START = END - pd.DateOffset(years=1)
HIST_START = START - pd.DateOffset(months=14)  # 신호용 여유 OHLCV

FALLBACK_TOP30 = [
    ("NVDA", "NVIDIA"), ("AAPL", "Apple"), ("MSFT", "Microsoft"),
    ("AMZN", "Amazon"), ("GOOGL", "Alphabet A"), ("META", "Meta"),
    ("AVGO", "Broadcom"), ("TSLA", "Tesla"), ("BRK-B", "Berkshire B"),
    ("JPM", "JPMorgan"), ("LLY", "Eli Lilly"), ("V", "Visa"),
    ("UNH", "UnitedHealth"), ("XOM", "Exxon"), ("MA", "Mastercard"),
    ("COST", "Costco"), ("HD", "Home Depot"), ("PG", "P&G"),
    ("JNJ", "Johnson&Johnson"), ("ABBV", "AbbVie"), ("WMT", "Walmart"),
    ("NFLX", "Netflix"), ("BAC", "Bank of America"), ("CRM", "Salesforce"),
    ("KO", "Coca-Cola"), ("AMD", "AMD"), ("MRK", "Merck"), ("ORCL", "Oracle"),
    ("PEP", "PepsiCo"), ("CVX", "Chevron"),
]


def get_sp500_top30() -> list[dict]:
    """S&P500 시가총액 상위 30종 (고정 유니버스 — 백테스트 속도 우선)."""
    name_map = {t: n for t, n in FALLBACK_TOP30}
    try:
        import FinanceDataReader as fdr

        sp = fdr.StockListing("S&P500")
        for sym, nm in zip(sp.Symbol.astype(str), sp.Name.astype(str)):
            name_map.setdefault(sym, nm)
    except Exception:
        pass
    return [{"tic": t, "name": name_map.get(t, t)} for t, _ in FALLBACK_TOP30]


def buy_shares(cash: float, price: float) -> tuple[int, float]:
    cost = price * (1 + COMM_RATE)
    qty = int(cash // cost)
    if qty <= 0:
        return 0, cash
    spent = qty * cost
    return qty, cash - spent


def sell_proceeds(qty: int, price: float) -> float:
    return qty * price * (1 - COMM_RATE - TAX_RATE)


def rank_stocks(hist_map: dict, date: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for tic, info in hist_map.items():
        h = info["hist"]
        if date not in h.index:
            continue
        loc = h.index.get_loc(date)
        buy = check_buy_signals(h.iloc[: loc + 1])
        sell = check_sell_signals(h.iloc[: loc + 1])
        if buy is None:
            continue
        s_hit = sell["hit"] if sell else 99
        rows.append({
            "tic": tic, "name": info["name"],
            "buy_hit": buy["hit"], "sell_hit": s_hit,
            "net": buy["hit"] - s_hit,
            "signals": ",".join(buy["signals"]),
            "ma_up": buy["ma5_gt_20"],
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["buy_hit", "net", "sell_hit", "ma_up"],
        ascending=[False, False, True, False],
    ).reset_index(drop=True)


def get_bar(hist_map: dict, tic: str, date: pd.Timestamp):
    h = hist_map[tic]["hist"]
    if date not in h.index:
        return None
    return h.loc[date]


def open_px(bar) -> float:
    o = bar["Open"]
    return float(o if pd.notna(o) and o > 0 else bar["Close"])


def check_sl(bar, avg_cost: float, stop_loss: float = STOP_LOSS):
    sl = avg_cost * (1 + stop_loss)
    o = open_px(bar)
    if o <= sl:
        return True, o, f"손절(갭){(o / avg_cost - 1) * 100:.1f}%"
    if bar["Low"] <= sl:
        return True, sl, f"손절{stop_loss * 100:.0f}%"
    return False, None, ""


def check_tp_reached(bar, avg_cost: float, take_profit: float) -> bool:
    tp = avg_cost * (1 + take_profit)
    if open_px(bar) >= tp:
        return True
    return bar["High"] >= tp


def deploy_cash(cash, picks, hist_map, today, positions, trades, pick_counts, top_n):
    if cash <= 0 or picks.empty:
        return cash
    n = min(top_n, len(picks))
    picks = picks.head(n)
    per = cash / n
    for _, row in picks.iterrows():
        tic = row["tic"]
        bar = get_bar(hist_map, tic, today)
        if bar is None:
            continue
        buy_px = open_px(bar)
        qty, leftover = buy_shares(per, buy_px)
        if qty <= 0:
            continue
        spent = per - leftover
        cash -= spent
        if tic in positions:
            pos = positions[tic]
            total_qty = pos["qty"] + qty
            pos["avg_cost"] = (pos["avg_cost"] * pos["qty"] + buy_px * qty) / total_qty
            pos["qty"] = total_qty
        else:
            positions[tic] = {
                "qty": qty, "avg_cost": buy_px, "hold_days": 0,
                "tp_pending": False, "name": row["name"],
            }
        pick_counts[tic] = pick_counts.get(tic, 0) + 1
        trades.append({
            "date": today, "side": "BUY", "tic": tic, "name": row["name"],
            "qty": qty, "price": buy_px, "buy_hit": row["buy_hit"],
            "reason": f"TOP{n} 1/{n}",
        })
    return cash


def run_backtest(
    hist_map: dict, trade_dates: list, take_profit: float, stop_loss: float = STOP_LOSS
):
    cash = INITIAL
    positions: dict = {}
    trades, daily_log, pick_counts = [], [], {}
    n_deploy = 0
    end_date = trade_dates[-1]

    for di in range(1, len(trade_dates)):
        prev_date = trade_dates[di - 1]
        today = trade_dates[di]
        day_sells = 0

        for tic in list(positions.keys()):
            pos = positions[tic]
            if not pos["tp_pending"]:
                continue
            bar = get_bar(hist_map, tic, today)
            if bar is None:
                continue
            sell_px = open_px(bar)
            pnl = (sell_px / pos["avg_cost"] - 1) * 100
            cash += sell_proceeds(pos["qty"], sell_px)
            trades.append({
                "date": today, "side": "SELL", "tic": tic, "name": pos["name"],
                "qty": pos["qty"], "price": sell_px, "pnl_pct": pnl,
                "hold_days": pos["hold_days"],
                "reason": f"익절+{take_profit * 100:.0f}%(익일시가)",
            })
            del positions[tic]
            day_sells += 1

        for tic in list(positions.keys()):
            pos = positions[tic]
            if pos["tp_pending"]:
                continue
            bar = get_bar(hist_map, tic, today)
            if bar is None:
                continue
            pos["hold_days"] += 1
            hit, sell_px, sell_reason = check_sl(bar, pos["avg_cost"], stop_loss)
            if hit:
                pnl = (sell_px / pos["avg_cost"] - 1) * 100
                cash += sell_proceeds(pos["qty"], sell_px)
                trades.append({
                    "date": today, "side": "SELL", "tic": tic, "name": pos["name"],
                    "qty": pos["qty"], "price": sell_px, "pnl_pct": pnl,
                    "hold_days": pos["hold_days"], "reason": sell_reason,
                })
                del positions[tic]
                day_sells += 1
            elif check_tp_reached(bar, pos["avg_cost"], take_profit):
                pos["tp_pending"] = True

        ranking = rank_stocks(hist_map, prev_date)
        if cash >= MIN_DEPLOY_CASH and (day_sells > 0 or len(positions) == 0) and not ranking.empty:
            before = cash
            cash = deploy_cash(
                cash, ranking, hist_map, today, positions, trades, pick_counts, TOP_N
            )
            if cash < before:
                n_deploy += 1

        port = cash
        for tic, pos in positions.items():
            bar = get_bar(hist_map, tic, today)
            if bar is not None:
                port += pos["qty"] * bar["Close"]
        daily_log.append({"date": today, "portfolio": port, "n_pos": len(positions), "cash": cash})

    last_val = cash
    for tic, pos in positions.items():
        bar = get_bar(hist_map, tic, end_date)
        if bar is not None:
            last_val += pos["qty"] * bar["Close"]

    sells = [t for t in trades if t["side"] == "SELL"]
    wins = sum(1 for t in sells if t["pnl_pct"] > 0)
    return {
        "final": last_val,
        "return_pct": (last_val / INITIAL - 1) * 100,
        "buys": sum(1 for t in trades if t["side"] == "BUY"),
        "sells": len(sells),
        "wins": wins,
        "win_rate": wins / len(sells) * 100 if sells else 0,
        "tp_cnt": sum(1 for t in sells if "익절" in t["reason"]),
        "sl_cnt": sum(1 for t in sells if "손절" in t["reason"]),
        "avg_hold": sum(t["hold_days"] for t in sells) / len(sells) if sells else 0,
        "n_deploy": n_deploy,
        "n_positions": len(positions),
        "trades": trades,
        "daily": pd.DataFrame(daily_log),
        "pick_counts": pick_counts,
    }


def main():
    base = r"c:\Users\seaho\My project\My_investment"

    print("S&P500 시총 TOP30 조회 중...", flush=True)
    top30 = get_sp500_top30()
    print(f"  유니버스: {', '.join(t['tic'] for t in top30[:8])} ... ({len(top30)}종)")

    print("OHLCV 로드 중...", flush=True)
    hist_map = {}
    hist_start = HIST_START.strftime("%Y-%m-%d")
    hist_end = (END + timedelta(days=1)).strftime("%Y-%m-%d")
    tickers = [item["tic"] for item in top30]
    try:
        raw = yf.download(
            tickers, start=hist_start, end=hist_end,
            auto_adjust=True, group_by="ticker", threads=True, progress=False,
        )
        if raw.empty:
            raise ValueError("empty download")
        for item in top30:
            tic = item["tic"]
            try:
                if len(tickers) == 1:
                    h = raw.copy()
                else:
                    h = raw[tic].copy()
                h = h.dropna(how="all")
                if h.empty or len(h) < 60:
                    continue
                h.index = h.index.tz_localize(None) if h.index.tz else h.index
                hist_map[tic] = {"name": item["name"], "hist": h}
            except Exception:
                continue
    except Exception:
        for item in top30:
            tic = item["tic"]
            try:
                h = yf.Ticker(tic).history(start=hist_start, end=hist_end, auto_adjust=True)
                if h.empty or len(h) < 60:
                    continue
                h.index = h.index.tz_localize(None) if h.index.tz else h.index
                hist_map[tic] = {"name": item["name"], "hist": h}
            except Exception:
                pass

    all_dates = sorted(set().union(*[set(v["hist"].index) for v in hist_map.values()]))
    trade_dates = [d for d in all_dates if START <= d <= END]
    if len(trade_dates) < 20:
        print("거래일 부족"); sys.exit(1)

    spy = yf.Ticker("SPY").history(start=trade_dates[0], end=trade_dates[-1] + pd.Timedelta(days=1))
    spy.index = spy.index.tz_localize(None) if spy.index.tz else spy.index
    spy_bh = INITIAL * spy["Close"].iloc[-1] / spy["Close"].iloc[0]
    spy_ret = (spy_bh / INITIAL - 1) * 100

    print("=" * 88)
    print("  S&P500 TOP30 — TOP7 분산 / 익절·손절 시나리오 비교")
    print(f"  기간: {trade_dates[0].strftime('%Y-%m-%d')} ~ {trade_dates[-1].strftime('%Y-%m-%d')}  (최근 1년)")
    print(f"  초기자금: ${INITIAL:,.0f}  |  수수료: {COMM_RATE*100:.2f}%")
    print("=" * 88)

    results = []
    for label, tp, sl in SCENARIOS:
        print(
            f"\n  ▶ {label} (+{tp*100:.0f}%/{sl*100:.0f}%) 실행 중...",
            flush=True,
        )
        r = run_backtest(hist_map, trade_dates, take_profit=tp, stop_loss=sl)
        r["label"] = label
        r["tp"] = tp
        r["sl"] = sl
        results.append(r)
        pd.DataFrame(r["trades"]).to_csv(
            f"{base}\\sp500_top7_{label}_trades.csv", index=False, encoding="utf-8-sig"
        )
        r["daily"].to_csv(
            f"{base}\\sp500_top7_{label}_daily.csv", index=False, encoding="utf-8-sig"
        )

    print("\n" + "=" * 88)
    print("  시나리오 비교 요약")
    print("=" * 88)
    print(
        f"\n  {'시나리오':<12} {'최종평가':>12} {'수익률':>8} "
        f"{'매수/매도':>10} {'승률':>6} {'익절/손절':>10} {'평균보유':>8} {'보유중':>5}"
    )
    print("  " + "-" * 78)
    for r in results:
        print(
            f"  +{r['tp']*100:.0f}%/{r['sl']*100:.0f}%  ${r['final']:>10,.2f} {r['return_pct']:>+7.1f}% "
            f"{r['buys']:>4}/{r['sells']:<4} {r['win_rate']:>5.0f}% "
            f"{r['tp_cnt']:>4}/{r['sl_cnt']:<4} {r['avg_hold']:>6.1f}일 {r['n_positions']:>4}종"
        )

    print(f"\n  [비교] SPY 단순보유 : ${spy_bh:,.2f} ({spy_ret:+.1f}%)")
    print(f"         SPY 구간     : ${spy['Close'].iloc[0]:,.2f} → ${spy['Close'].iloc[-1]:,.2f}")

    best = max(results, key=lambda x: x["final"])
    print(
        f"\n  ★ 최고 수익: +{best['tp']*100:.0f}%/{best['sl']*100:.0f}% "
        f"→ ${best['final']:,.2f} ({best['return_pct']:+.1f}%)"
    )

    print("\n  저장: sp500_top7_*_trades.csv, _daily.csv")


if __name__ == "__main__":
    main()
