# -*- coding: utf-8 -*-
"""Finviz 스타일 트리맵 PNG 생성 및 엑셀 시트 삽입."""
from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import squarify

from matplotlib import font_manager

for _fam in ("Malgun Gothic", "NanumGothic", "AppleGothic"):
    if any(_fam.lower() in (f.name or "").lower() for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = _fam
        break
plt.rcParams["axes.unicode_minus"] = False


def _hex_to_mpl(hex6: str):
    h = hex6.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


ACCT_COLORS = {
    "DC": "2E7D32",
    "개인연금1": "1565C0",
    "개인연금2": "0277BD",
    "ISA": "F9A825",
    "일반계좌": "C2185B",
    "CMA": "EF6C00",
    "IRP": "6A1B9A",
    "은행예금": "558B2F",
}
DEFAULT_COLOR = "78909C"


def short_label(name: str, tic: str, max_len: int = 14) -> str:
    n = str(name or "").strip()
    if len(n) > max_len:
        n = n[: max_len - 1] + "…"
    t = str(tic or "").strip()
    if t and t not in n:
        return f"{n}\n({t})" if n else t
    return n or t


def generate_treemap_png(
    items: list[dict],
    out_path: Path,
    title: str = "포트폴리오 (평가액 비율)",
    max_slices: int = 36,
) -> bool:
    """
    items: [{name, ticker, val, acct}, ...] val > 0
    """
    rows = [x for x in items if float(x.get("val") or 0) > 0]
    if not rows:
        return False
    rows.sort(key=lambda x: -float(x["val"]))
    total = sum(float(x["val"]) for x in rows)
    if total <= 0:
        return False

    if len(rows) > max_slices:
        head = rows[: max_slices - 1]
        tail_val = sum(float(x["val"]) for x in rows[max_slices - 1 :])
        head.append(
            {"name": "기타", "ticker": "", "val": tail_val, "acct": ""}
        )
        rows = head

    sizes = [float(x["val"]) for x in rows]
    colors = []
    labels = []
    for x in rows:
        acct = x.get("acct") or ""
        hex_c = ACCT_COLORS.get(acct, DEFAULT_COLOR)
        colors.append(_hex_to_mpl(hex_c))
        pct = float(x["val"]) / total * 100
        lab = short_label(x.get("name", ""), x.get("ticker", ""))
        if pct >= 4:
            labels.append(f"{lab}\n{pct:.1f}%")
        elif pct >= 1.5:
            labels.append(f"{pct:.1f}%")
        else:
            labels.append("")

    fig, ax = plt.subplots(figsize=(12, 7), dpi=120)
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")
    squarify.plot(
        sizes=sizes,
        label=labels,
        color=colors,
        alpha=0.92,
        ax=ax,
        text_kwargs={"fontsize": 8, "color": "white", "weight": "bold"},
        pad=True,
    )
    ax.axis("off")
    ax.set_title(title, color="white", fontsize=14, pad=12, weight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return True


def embed_treemap_on_sheet(ws, png_path: Path, anchor: str = "K5", width_px: int = 720, height_px: int = 420):
    from openpyxl.drawing.image import Image

    img = Image(str(png_path))
    img.width = width_px
    img.height = height_px
    img.anchor = anchor
    ws.add_image(img)


def treemap_from_holdings(ws_title: str, holdings: list[dict], ws, anchor: str, tmp_dir: Path | None = None) -> bool:
    td = tmp_dir or Path(tempfile.gettempdir())
    png = td / f"treemap_{abs(hash(ws_title)) % 10**8}.png"
    ok = generate_treemap_png(holdings, png, title=ws_title)
    if ok:
        embed_treemap_on_sheet(ws, png, anchor=anchor)
    return ok
