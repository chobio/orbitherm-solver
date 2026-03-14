"""解析結果を格納するデータクラス。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SolverResult:
    """熱解析の実行結果コンテナ。

    Attributes
    ----------
    record_times: 出力時刻リスト [s]
    results: 節点名 → 温度履歴リスト [°C]
    results_qsrc: 節点名 → 熱源履歴リスト [W]
    results_qnet: 節点名 → 正味熱流入履歴リスト [W]
    results_cond_flow: (節点1, 節点2) → コンダクタ熱流量履歴 [W]
    converged_steady: 定常収束判定結果
    output_csv: 出力CSV パス
    output_out: 出力OUTファイルパス
    output_png: 出力グラフ PNG パス（グラフ出力なし時は None）
    log_path: ログファイルパス
    success: 正常終了フラグ
    error_message: エラー時のメッセージ
    """

    record_times: list[float] = field(default_factory=list)
    results: dict[str, list[float]] = field(default_factory=dict)
    results_qsrc: dict[str, list[float]] = field(default_factory=dict)
    results_qnet: dict[str, list[float]] = field(default_factory=dict)
    results_cond_flow: dict[tuple, list[float]] = field(default_factory=dict)

    converged_steady: bool = False
    output_csv: str = ""
    output_out: str = ""
    output_png: Optional[str] = None
    log_path: str = ""
    success: bool = True
    error_message: str = ""
