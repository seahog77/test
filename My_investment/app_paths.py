# -*- coding: utf-8 -*-
"""스크립트 / PyInstaller exe 공통 작업 폴더 (exe와 xlsx를 같은 폴더에 둠)."""
import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resolve_workbook(path: Path) -> Path:
    if path.is_absolute():
        return path
    return app_dir() / path


def safe_reconfigure_stdio(encoding: str = "utf-8") -> None:
    """windowed exe에서는 stdout/stderr 가 None 일 수 있음."""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding=encoding)
            except Exception:
                pass
