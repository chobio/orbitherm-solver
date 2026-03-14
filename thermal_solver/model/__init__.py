"""Orbitherm Solver モデル層。

解析設定・熱モデル・結果コンテナのデータクラス群。

将来の移行方針:
    AnalysisConfig  → OrbithermSolverConfig（エイリアスで段階移行）
    ThermalModel    → ThermalModel（維持）
    SolverResult    → OrbithermResult（エイリアスで段階移行）
"""
from .config import AnalysisConfig
from .thermal_model import ThermalModel
from .result import SolverResult

__all__ = ["AnalysisConfig", "ThermalModel", "SolverResult"]
