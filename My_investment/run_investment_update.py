# -*- coding: utf-8 -*-
"""
investment_dividend.xlsx 일괄 갱신
  1) 계좌현황 현재가(I/J) · 환율 · K~N 수식
  2) 마지막 탭 '월별배당' — 연·월 배당 실적 + yfinance 예측

사용:
  investment_update.exe              → GUI에서 입력 xlsx 선택
  python run_investment_update.py    → 동일 GUI
  python run_investment_update.py file.xlsx [--dividend-only] [--year 2026]
"""
import argparse
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app_paths import app_dir, resolve_workbook, safe_reconfigure_stdio

safe_reconfigure_stdio()

DEFAULT_XLSX = app_dir() / "investment_dividend.xlsx"


def process_workbook(path: Path, dividend_only: bool, year: int, log=print):
    from add_monthly_dividend_tab import run_dividend_tab
    from update_prices import update_workbook

    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {path}")

    class _Stream:
        def write(self, s):
            if s and s.strip():
                log(s.rstrip("\n"))

        def flush(self):
            pass

    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = _Stream()
    try:
        log(f"대상: {path}")
        if not dividend_only:
            update_workbook(path)
            from update_amount_auto import update_amount_sheet

            update_amount_sheet(path)
        run_dividend_tab(path, year=year)
        log("\n완료. 엑셀을 다시 열어 확인하세요.")
    finally:
        sys.stdout, sys.stderr = old_out, old_err


class App(tk.Tk):
    def __init__(self, initial: Path | None = None):
        super().__init__()
        self.title("포트폴리오 시세·배당 갱신")
        self.geometry("560x420")
        self.minsize(480, 360)
        self.resizable(True, True)

        default = initial if initial and initial.exists() else (
            DEFAULT_XLSX if DEFAULT_XLSX.exists() else None
        )
        self.file_var = tk.StringVar(value=str(default) if default else "")
        self.div_only = tk.BooleanVar(value=False)
        self.year_var = tk.StringVar(value="2026")
        self._busy = False

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="입력 엑셀 파일 (.xlsx)", font=("", 10, "bold")).pack(
            anchor=tk.W
        )
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, pady=(4, 8))
        ttk.Entry(row, textvariable=self.file_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6)
        )
        ttk.Button(row, text="찾아보기…", command=self.browse).pack(side=tk.RIGHT)

        opt = ttk.Frame(frm)
        opt.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(
            opt, text="배당 탭만 갱신 (현재가 생략)", variable=self.div_only
        ).pack(side=tk.LEFT)
        ttk.Label(opt, text="배당 연도").pack(side=tk.LEFT, padx=(16, 4))
        ttk.Entry(opt, textvariable=self.year_var, width=6).pack(side=tk.LEFT)

        ttk.Label(
            frm,
            text="※ 선택한 엑셀 파일을 반드시 닫은 뒤 실행하세요.",
            foreground="#666",
        ).pack(anchor=tk.W, pady=(0, 6))

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill=tk.X, pady=(0, 8))
        self.run_btn = ttk.Button(btn_row, text="실행", command=self.start)
        self.run_btn.pack(side=tk.LEFT)
        ttk.Button(btn_row, text="종료", command=self.destroy).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        ttk.Label(frm, text="진행 로그", font=("", 10, "bold")).pack(anchor=tk.W)
        log_frm = ttk.Frame(frm)
        log_frm.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.log = tk.Text(log_frm, height=12, wrap=tk.WORD, state=tk.DISABLED)
        scroll = ttk.Scrollbar(log_frm, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def browse(self):
        init_dir = app_dir()
        cur = self.file_var.get().strip()
        if cur:
            p = Path(cur)
            if p.parent.is_dir():
                init_dir = p.parent
        path = filedialog.askopenfilename(
            parent=self,
            title="입력 엑셀 파일 선택",
            initialdir=str(init_dir),
            filetypes=[
                ("Excel 파일", "*.xlsx"),
                ("모든 파일", "*.*"),
            ],
        )
        if path:
            self.file_var.set(path)

    def append_log(self, msg: str):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + ("\n" if not msg.endswith("\n") else ""))
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def start(self):
        if self._busy:
            return
        raw = self.file_var.get().strip()
        if not raw:
            messagebox.showwarning("확인", "엑셀 파일을 선택하세요.", parent=self)
            return
        path = resolve_workbook(Path(raw))
        if not path.exists():
            messagebox.showerror("오류", f"파일이 없습니다.\n{path}", parent=self)
            return
        if path.suffix.lower() != ".xlsx":
            messagebox.showwarning(
                "확인", "xlsx 파일을 선택하세요.", parent=self
            )
            return
        try:
            year = int(self.year_var.get().strip())
        except ValueError:
            messagebox.showwarning("확인", "배당 연도를 숫자로 입력하세요.", parent=self)
            return

        self._busy = True
        self.run_btn.configure(state=tk.DISABLED)
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
        self.append_log(f"시작: {path.name}")
        self.append_log("(엑셀이 열려 있으면 저장에 실패할 수 있습니다)\n")

        def worker():
            try:
                process_workbook(
                    path,
                    self.div_only.get(),
                    year,
                    log=lambda m: self.after(0, self.append_log, str(m)),
                )
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "완료",
                        f"갱신 완료\n{path.name}\n\n엑셀을 다시 열어 확인하세요.",
                        parent=self,
                    ),
                )
            except Exception as e:
                err = "".join(traceback.format_exception(e))
                self.after(0, self.append_log, err)
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "오류",
                        f"{e}\n\n엑셀 파일이 열려 있으면 닫고 다시 시도하세요.",
                        parent=self,
                    ),
                )
            finally:
                self.after(0, self._done)

        threading.Thread(target=worker, daemon=True).start()

    def _done(self):
        self._busy = False
        self.run_btn.configure(state=tk.NORMAL)


def main():
    ap = argparse.ArgumentParser(description="포트폴리오: 시세 + 연·월 배당 탭")
    ap.add_argument(
        "file",
        nargs="?",
        default=None,
        help="대상 xlsx (미지정 시 GUI)",
    )
    ap.add_argument(
        "--dividend-only",
        action="store_true",
        help="현재가 갱신 없이 월별배당 탭만 재생성",
    )
    ap.add_argument("--year", type=int, default=2026, help="배당 집계 연도")
    ap.add_argument(
        "--no-gui",
        action="store_true",
        help="GUI 없이 콘솔만 (파일 인자 필수)",
    )
    args = ap.parse_args()

    # exe: 항상 GUI / python: 파일 미지정 시 GUI / --no-gui: 콘솔만
    if args.no_gui:
        use_gui = False
    elif getattr(sys, "frozen", False):
        use_gui = True
    else:
        use_gui = args.file is None

    if use_gui:
        initial = resolve_workbook(Path(args.file)) if args.file else None
        app = App(initial=initial)
        app.mainloop()
        return

    if not args.file:
        print("파일 경로가 필요합니다. (또는 GUI 실행)")
        sys.exit(1)
    path = resolve_workbook(Path(args.file))
    try:
        process_workbook(path, args.dividend_only, args.year)
    except Exception as e:
        print(f"오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
