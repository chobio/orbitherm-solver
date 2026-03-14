"""解析設定を保持するデータクラス。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class AnalysisConfig:
    """熱解析実行パラメータ一式。

    Attributes
    ----------
    time_start: 開始時刻 [s]
    time_end: 終了時刻 [s]
    dt: 出力間隔 [s]
    delta_t: 計算タイムステップ [s]
    sigma: Stefan-Boltzmann 定数 [W/(m^2 K^4)]
    analysis_type: 解析種別 ("TRANSIENT" | "STEADY" | "STEADY_THEN_TRANSIENT")
    steady_solver: 定常ソルバー種別 ("PICARD" | "CNFRW")
    transient_method: 過渡解法 ("EXPLICIT" | "CRANK_NICOLSON" | "BACKWARD")
    save_final_temperature: 終了時温度保存設定 (None=保存なし, True=自動命名, str=ファイルパス)
    initial_temperature_file: 過渡解析初期温度CSVパス
    output_dq: 熱流量差分出力フラグ
    output_graph: グラフ出力フラグ
    """

    time_start: float = 0.0
    time_end: float = 100.0
    dt: float = 5.0
    delta_t: float = 0.01
    sigma: float = 5.67e-8

    analysis_type: str = "TRANSIENT"
    steady_solver: str = "PICARD"
    transient_method: str = "EXPLICIT"

    save_final_temperature: Optional[Union[bool, str]] = None
    initial_temperature_file: Optional[str] = None

    output_dq: bool = False
    output_graph: bool = True
