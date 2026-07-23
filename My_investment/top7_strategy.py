# -*- coding: utf-8 -*-
"""코스피 TOP30 → 신호 랭킹 TOP7 분산 매매 전략 (+10% 익절 익일 / -10% 손절)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import yfinance as yf

from signal_rules import check_buy_signals, check_sell_signals

COMM_RATE = 0.00015
TAX_RATE = 0.002
STOP_LOSS = -0.10
TAKE_PROFIT = 0.10
TOP_N = 7
MIN_CASH_TO_DEPLOY = 200_000

FALLBACK_TOP30 = [
    ("005930", "삼성전자"), ("000660", "SK하이닉스"), ("373220", "LG에너지솔루션"),
    ("207940", "삼성바이오로직스"), ("005380", "현대차"), ("000270", "기아"),
    ("068270", "셀트리온"), ("105560", "KB금융"), ("055550", "신한지주"),
    ("035420", "NAVER"), ("005490", "POSCO홀딩스"), ("086790", "하나금융지주"),
    ("006400", "삼성SDI"), ("051910", "LG화학"), ("035720", "카카오"),
    ("012330", "현대모비스"), ("032830", "삼성생명"), ("138040", "메리츠금융지주"),
    ("033780", "KT&G"), ("003550", "LG"), ("009150", "삼성전기"),
    ("034730", "SK"), ("096770", "SK이노베이션"), ("015760", "한국전력"),
    ("316140", "우리금융지주"), ("010130", "고려아연"), ("024110", "기업은행"),
    ("011200", "HMM"), ("017670", "SK텔레콤"), ("028260", "삼성물산"),
]


@dataclass
class StrategyConfig:
    top_n: int = TOP_N
    take_profit: float = TAKE_PROFIT
    stop_loss: float = STOP_LOSS
    min_cash: float = MIN_CASH_TO_DEPLOY
    comm_rate: float = COMM_RATE
    tax_rate: float = TAX_RATE


def get_kospi_top30() -> list[dict]:
    """코스피 시총 상위 30종."""
    try:
        import FinanceDataReader as fdr

        listing = fdr.StockListing("KRX")
        kospi = listing[listing["Market"] == "KOSPI"].copy()
        kospi = kospi.sort_values("Marcap", ascending=False).head(30)
        return [
            {"tic": str(row.Code).zfill(6), "name": str(row.Name)}
            for _, row in kospi.iterrows()
        ]
    except Exception:
        return [{"tic": t, "name": n} for t, n in FALLBACK_TOP30]


def load_hist_map(
    tickers: list[dict],
    start: str = "2023-01-01",
    extra_symbols: list[str] | None = None,
) -> dict:
    """yfinance OHLCV 로드."""
    symbols = {item["tic"] for item in tickers}
    if extra_symbols:
        symbols.update(extra_symbols)
    name_map = {item["tic"]: item["name"] for item in tickers}
    hist_map: dict = {}

    for tic in sorted(symbols):
        try:
            h = yf.Ticker(f"{str(tic).zfill(6)}.KS").history(
                start=start, end=datetime.now().strftime("%Y-%m-%d")
            )
            if h.empty or len(h) < 60:
                continue
            h.index = h.index.tz_localize(None) if h.index.tz else h.index
            hist_map[tic] = {"name": name_map.get(tic, tic), "hist": h}
        except Exception:
            continue
    return hist_map


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
            "tic": tic,
            "name": info["name"],
            "buy_hit": buy["hit"],
            "sell_hit": s_hit,
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


def check_tp_reached(bar, avg_cost: float, take_profit: float = TAKE_PROFIT) -> bool:
    tp = avg_cost * (1 + take_profit)
    if open_px(bar) >= tp:
        return True
    return bar["High"] >= tp


def buy_shares(cash: float, price: float, comm_rate: float = COMM_RATE) -> tuple[int, float]:
    cost = price * (1 + comm_rate)
    qty = int(cash // cost)
    if qty <= 0:
        return 0, cash
    spent = qty * cost
    return qty, cash - spent


def latest_signal_date(hist_map: dict) -> pd.Timestamp | None:
  dates = sorted(set().union(*[set(v["hist"].index) for v in hist_map.values()]))
  if len(dates) < 2:
      return None
  return dates[-2]


def latest_trade_date(hist_map: dict) -> pd.Timestamp | None:
  dates = sorted(set().union(*[set(v["hist"].index) for v in hist_map.values()]))
  return dates[-1] if dates else None
