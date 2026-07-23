# -*- coding: utf-8 -*-
"""워크북 전체 틀 고정 해제 (Excel COM)."""
import sys
from pathlib import Path

from excel_sheet_utils import postprocess_workbook_via_excel

if __name__ == "__main__":
    p = Path(sys.argv[1] if len(sys.argv) > 1 else "investment_0719_W.xlsx")
    if not p.is_absolute():
        p = Path(__file__).resolve().parent / p
    ok = postprocess_workbook_via_excel(p)
    print("OK" if ok else "FAIL", p)
