"""Orbitherm Solver サービス層。UI・CLI・Orbitherm Studio から run_case() を呼ぶ共通ラッパー。

現時点では run_case() の薄いプロキシだが、将来ここにキャッシュ・
バリデーション・非同期実行などを追加できる。
"""
from __future__ import annotations

from typing import Callable, Optional

from .run_case import run_case
from ..model.result import SolverResult


class OrbithermSolver:
    """Orbitherm Solver サービスクラス。

    インスタンス化して run() を呼ぶことで解析を実行する。
    将来の Orbitherm Studio（FreeCAD アダプタ）や REST API ラッパーからも利用可能。

    Example
    -------
    >>> from thermal_solver.app.service import OrbithermSolver
    >>> solver = OrbithermSolver()
    >>> result = solver.run("examples/test1.inp", no_input=True)
    >>> print(result.success)
    """

    def run(
        self,
        input_path: str,
        output_base: Optional[str] = None,
        no_input: bool = True,
        logger: Optional[Callable[[str], None]] = None,
        make_plot: bool = True,
    ) -> SolverResult:
        """熱解析を実行する。

        Parameters
        ----------
        input_path: 入力ファイルパス
        output_base: 出力ベース名（省略時は入力ファイル名から自動）
        no_input: True でグラフ表示後の対話プロンプトをスキップ
        logger: ログ出力 callable
        make_plot: True で PNG グラフを出力

        Returns
        -------
        SolverResult
        """
        return run_case(
            input_path=input_path,
            output_base=output_base,
            no_input=no_input,
            logger=logger,
            make_plot=make_plot,
        )


# 後方互換エイリアス: 旧名称 ThermalService は OrbithermSolver の別名として維持する
# TODO: 将来のメジャーバージョンで ThermalService を削除する
ThermalService = OrbithermSolver
