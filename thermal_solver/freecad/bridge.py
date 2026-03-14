"""Orbitherm Studio 連携ブリッジ（将来実装用スタブ）。

Orbitherm Studio（FreeCAD ワークベンチ）の熱解析モデルを
ThermalModel / AnalysisConfig に変換するアダプタを実装する予定。
Orbitherm Solver コアは FreeCAD に依存しない pure Python のまま維持する。

TODO:
    - FreeCAD のジオメトリからノード/コンダクタンスを生成する関数
    - FreeCAD の材料データベースから熱物性を読み込む関数
    - SolverResult を FreeCAD の結果オブジェクトへ変換する関数
    - OrbithermWorkbench クラスを orbitherm_studio パッケージに実装する
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..model.config import AnalysisConfig
    from ..model.thermal_model import ThermalModel
    from ..model.result import SolverResult


def freecad_model_to_thermal(freecad_model: object) -> tuple["AnalysisConfig", "ThermalModel"]:
    """FreeCAD モデルオブジェクトから (AnalysisConfig, ThermalModel) を生成する。

    Orbitherm Studio から Orbitherm Solver を呼び出す際のエントリポイント（将来実装）。
    未実装。FreeCAD 環境がインストールされていない場合は ImportError を送出する。
    """
    raise NotImplementedError(
        "Orbitherm Studio ブリッジはまだ実装されていません。"
        "将来の thermal_solver/freecad/bridge.py で実装予定です。"
    )


def result_to_freecad(result: "SolverResult", freecad_doc: object) -> None:
    """SolverResult を FreeCAD ドキュメントに書き出す。

    Orbitherm Solver の解析結果を Orbitherm Studio の可視化に渡す（将来実装）。
    未実装。
    """
    raise NotImplementedError("Orbitherm Studio への結果書き出しはまだ実装されていません。")
