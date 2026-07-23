# -*- coding: utf-8 -*-
import json
from pathlib import Path

d = json.loads(
    Path(r"c:\Users\seaho\My project\My_investment\_portfolio_analysis.json").read_text(
        encoding="utf-8"
    )
)
perf = d["perf"]
w1 = w3 = tw = 0.0
for t, p in perf.items():
    if p["r1m"] is None:
        continue
    w = p["val"]
    tw += w
    w1 += w * p["r1m"]
    w3 += w * p["r3m"]

compact = {
    "asof": d["asof"],
    "total": round(d["total"]),
    "main": round(d["main_total"]),
    "w": round(d["w_total"]),
    "n_main": d["n_main"],
    "n_w": d["n_w"],
    "n_tickers": d["n_tickers"],
    "hhi": round(d["hhi_tic"], 4),
    "top1": round(d["top1_share"] * 100, 1),
    "top5": round(d["top5_share"] * 100, 1),
    "cc": round(d["cc_share"] * 100, 1),
    "us": round(d["us_eq_share"] * 100, 1),
    "cash": round(d["cash_share"] * 100, 1),
    "bond": round(d["bond_share"] * 100, 1),
    "w1m": round(w1 / tw, 2),
    "w3m": round(w3 / tw, 2),
    "theme": [
        {"name": t["name"], "pct": round(t["pct"], 1), "val": round(t["val"])}
        for t in d["theme"]
    ],
    "acct": [
        {
            "label": f"{a['src']}/{a['acct']}",
            "pct": round(a["pct"], 1),
            "val": round(a["val"]),
        }
        for a in d["acct"]
    ],
    "top": [
        {
            "tic": t["tic"],
            "name": t["name"][:28],
            "pct": round(t["pct"], 1),
            "val": round(t["val"]),
            "pnl": round(t["pnl_pct"], 1) if t["pnl_pct"] is not None else None,
            "srcs": t["srcs"],
            "theme": t["theme"],
        }
        for t in d["top_tickers"][:15]
    ],
    "perf": [
        {
            "tic": t,
            "name": p["name"][:24],
            "pct": round(p["val"] / d["total"] * 100, 1),
            "r1w": round(p["r1w"], 1),
            "r1m": round(p["r1m"], 1),
            "r3m": round(p["r3m"], 1),
            "series": p["series"],
        }
        for t, p in sorted(perf.items(), key=lambda z: -z[1]["val"])[:10]
    ],
}
Path(r"c:\Users\seaho\My project\My_investment\_canvas_data.json").write_text(
    json.dumps(compact, ensure_ascii=False), encoding="utf-8"
)
print("w1m", compact["w1m"], "w3m", compact["w3m"])
print("themes", compact["theme"][:6])
