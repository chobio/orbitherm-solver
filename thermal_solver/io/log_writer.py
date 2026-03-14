"""ログ出力ユーティリティ。

ファイルへの書き出しと print 互換 callable をまとめたシンプルなクラス。
"""
from __future__ import annotations

import time
from typing import Callable, Optional


class LogWriter:
    """ファイルと標準出力への同時ログ出力。

    Parameters
    ----------
    filepath: ログファイルパス
    printer: print 互換 callable（None の場合は標準出力）
    """

    def __init__(
        self,
        filepath: str,
        printer: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._filepath = filepath
        self._printer = printer or print
        self._file = open(filepath, "w", encoding="utf-8")
        self._file.write(f"# 熱解析ログ {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._file.flush()

    def log(self, msg: str) -> None:
        """ファイルのみに書き出す（標準出力には出さない）。"""
        self._file.write(msg + "\n")
        self._file.flush()

    def print_and_log(self, msg: str) -> None:
        """標準出力とファイル両方に書き出す。"""
        self._printer(msg)
        self.log(msg)

    def close(self) -> None:
        self._file.close()

    @property
    def filepath(self) -> str:
        return self._filepath

    def __enter__(self) -> "LogWriter":
        return self

    def __exit__(self, *_) -> None:
        self.close()
