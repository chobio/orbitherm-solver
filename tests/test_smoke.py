"""スモークテスト: パッケージの基本インポートと入口関数の存在を確認する。

実行方法:
    cd E:\\Themal_Analysis\\orbitherm-solver
    python -m pytest tests/test_smoke.py -v
"""
from __future__ import annotations

import importlib
import os
import sys
import types

# プロジェクトルートをパスに追加
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class TestPackageImport:
    """thermal_solver パッケージの基本 import テスト。"""

    def test_thermal_solver_importable(self):
        """thermal_solver パッケージが import できること。"""
        import thermal_solver
        assert hasattr(thermal_solver, "__version__")

    def test_run_case_importable(self):
        """run_case 関数が import できること。"""
        from thermal_solver.app.run_case import run_case
        assert callable(run_case)

    def test_model_classes_importable(self):
        """主要データクラスが import できること。"""
        from thermal_solver.model import AnalysisConfig, SolverResult, ThermalModel
        cfg = AnalysisConfig()
        assert cfg.analysis_type == "TRANSIENT"
        assert cfg.steady_solver == "PICARD"
        result = SolverResult()
        assert result.success is True
        model = ThermalModel()
        assert isinstance(model.nodes, dict)

    def test_io_modules_importable(self):
        """io モジュール群が import できること。"""
        from thermal_solver.io.input_parser import parse_header_input, safe_eval
        from thermal_solver.io.model_builder import build_model
        from thermal_solver.io.result_writer import save_final_temperature_file, write_csv
        assert callable(parse_header_input)
        assert callable(safe_eval)
        assert callable(build_model)

    def test_solver_modules_importable(self):
        """solver モジュール群が import できること。"""
        from thermal_solver.solvers.arithmetic import solve_arithmetic_nodes
        from thermal_solver.solvers.common import (
            SPACE_NODE_NAME,
            compute_output_snapshot,
            interpolate_array,
        )
        from thermal_solver.solvers.implicit import step_implicit
        from thermal_solver.solvers.steady import run_steady_analysis, run_steady_cnfrw
        from thermal_solver.solvers.transient import node_update_task, run_transient_analysis
        assert callable(run_steady_analysis)
        assert callable(step_implicit)
        assert callable(node_update_task)
        assert SPACE_NODE_NAME == "SPACE.9999"

    def test_post_plotter_importable(self):
        """plotter モジュールが import できること。"""
        from thermal_solver.post.plotter import make_temperature_plot
        assert callable(make_temperature_plot)


class TestOrbithermMain:
    """orbitherm_main.py のラッパーとしての基本テスト。"""

    def test_main_importable(self):
        """orbitherm_main が import できること。"""
        import orbitherm_main
        assert hasattr(orbitherm_main, "main")

    def test_main_has_entry(self):
        """orbitherm_main.main が callable であること。"""
        import orbitherm_main
        assert callable(orbitherm_main.main)

    def test_main_reexports_functions(self):
        """orbitherm_main が主要関数を再エクスポートしていること（互換テスト）。"""
        import orbitherm_main
        for name in [
            "parse_header_input",
            "safe_eval",
            "interpolate_array",
            "run_steady_analysis",
            "node_update_task",
            "solve_arithmetic_nodes",
            "step_implicit",
        ]:
            assert hasattr(orbitherm_main, name), f"orbitherm_main に {name} がない"
            assert callable(getattr(orbitherm_main, name))


class TestSafeEval:
    """safe_eval の基本動作テスト。"""

    def test_integer(self):
        from thermal_solver.io.input_parser import safe_eval
        assert safe_eval("42") == 42.0

    def test_float(self):
        from thermal_solver.io.input_parser import safe_eval
        assert abs(safe_eval("3.14") - 3.14) < 1e-9

    def test_negative(self):
        from thermal_solver.io.input_parser import safe_eval
        assert safe_eval("-273") == -273.0


class TestInterpolate:
    """interpolate_array の基本動作テスト。"""

    def test_linear_midpoint(self):
        import numpy as np
        from thermal_solver.solvers.common import interpolate_array

        times = np.array([0.0, 10.0])
        values = np.array([0.0, 100.0])
        result = interpolate_array(times, values, 5.0, "LINEAR")
        assert abs(result - 50.0) < 1e-9

    def test_step(self):
        import numpy as np
        from thermal_solver.solvers.common import interpolate_array

        times = np.array([0.0, 10.0])
        values = np.array([0.0, 100.0])
        result = interpolate_array(times, values, 5.0, "STEP")
        assert result == 0.0

    def test_clamp_lower(self):
        import numpy as np
        from thermal_solver.solvers.common import interpolate_array

        times = np.array([5.0, 10.0])
        values = np.array([10.0, 20.0])
        assert interpolate_array(times, values, 0.0) == 10.0

    def test_clamp_upper(self):
        import numpy as np
        from thermal_solver.solvers.common import interpolate_array

        times = np.array([5.0, 10.0])
        values = np.array([10.0, 20.0])
        assert interpolate_array(times, values, 99.0) == 20.0
