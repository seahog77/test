# -*- coding: utf-8 -*-
"""워크북 틀 고정 해제 · 금액순 차트 제거 (Excel COM)."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook


def clear_all_freeze_panes(wb: Workbook) -> None:
    for ws in wb.worksheets:
        ws.freeze_panes = None
        try:
            ws.sheet_view.pane = None
        except Exception:
            pass
        try:
            for view in ws.views.sheetView:
                view.pane = None
                view.topLeftCell = "A1"
                view.xSplit = 0
                view.ySplit = 0
        except Exception:
            pass


def postprocess_workbook_via_excel(path: Path) -> bool:
    """모든 시트 틀 고정 해제 + 금액순 기존 차트(원그래프) 삭제."""
    try:
        import win32com.client as win32
    except ImportError:
        return False

    path = path.resolve()
    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = None
    try:
        wb = xl.Workbooks.Open(str(path))
        for i in range(1, wb.Sheets.Count + 1):
            ws = wb.Sheets(i)
            ws.Activate()
            win = xl.ActiveWindow
            if win.FreezePanes:
                win.FreezePanes = False
            win.SplitRow = 0
            win.SplitColumn = 0
        try:
            ws_amt = wb.Sheets("금액순")
            while ws_amt.ChartObjects().Count > 0:
                ws_amt.ChartObjects(1).Delete()
        except Exception:
            pass
        wb.Save()
        return True
    except Exception:
        return False
    finally:
        if wb is not None:
            wb.Close(SaveChanges=False)
        xl.Quit()


def finalize_workbook(path: Path, wb: Workbook | None = None) -> None:
    if wb is not None:
        clear_all_freeze_panes(wb)
        wb.save(path)
    postprocess_workbook_via_excel(path)
