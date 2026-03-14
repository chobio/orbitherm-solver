"""パーサー回帰テスト。

parse_header_input() と build_model() の単体テスト。
ソルバーは実行しない。数値ロジックには触れず、入力解釈のみを確認する。

実行方法:
    cd E:\\Themal_Analysis\\orbitherm-solver
    python -m pytest tests/test_parser.py -v
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_DATA = os.path.join(_ROOT, "tests", "data")

from thermal_solver.io.input_parser import parse_header_input
from thermal_solver.io.model_builder import build_model
from thermal_solver.model.config import AnalysisConfig


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def _inp(case: str, filename: str) -> str:
    return os.path.join(_DATA, case, filename)


# ── case_steady ───────────────────────────────────────────────────────────────

class TestSteadyParser:
    """case_steady: 最小定常ケースのパーサーテスト。"""

    def setup_method(self):
        path = _inp("case_steady", "steady.inp")
        self.sections = parse_header_input(path)
        self.config, self.model = build_model(self.sections, path)

    def test_analysis_type_is_steady(self):
        assert self.config.analysis_type == "STEADY"

    def test_steady_solver_is_picard(self):
        assert self.config.steady_solver == "PICARD"

    def test_output_graph_false(self):
        assert self.config.output_graph is False

    def test_node_count(self):
        assert len(self.model.nodes) == 2

    def test_boundary_node_exists(self):
        assert "MAIN.2" in self.model.boundary_nodes

    def test_regular_node_exists(self):
        assert "MAIN.1" not in self.model.boundary_nodes
        assert "MAIN.1" in self.model.nodes

    def test_regular_node_initial_temperature(self):
        # 初期温度 100℃ → 373.15 K として格納されるが、273.0 加算で 373 K
        t = self.model.nodes["MAIN.1"]["T"]
        assert abs(t - 373.0) < 1.0, f"T_MAIN.1初期値が想定外: {t} K"

    def test_boundary_node_temperature(self):
        # 境界ノード MAIN.2 = 0℃ → 273 K
        t = self.model.nodes["MAIN.2"]["T"]
        assert abs(t - 273.0) < 1.0, f"T_MAIN.2境界温度が想定外: {t} K"

    def test_conductor_count(self):
        assert len(self.model.conductance) == 1

    def test_conductor_value(self):
        assert ("MAIN.1", "MAIN.2") in self.model.conductance
        g = self.model.conductance[("MAIN.1", "MAIN.2")]
        assert abs(g - 2.0) < 1e-9

    def test_no_radiation_conductors(self):
        assert len(self.model.radiation_conductors) == 0

    def test_no_arithmetic_nodes(self):
        assert len(self.model.arithmetic_nodes) == 0

    def test_heat_source_on_node1(self):
        assert "MAIN.1" in self.model.heat_input
        assert abs(self.model.heat_input["MAIN.1"] - 10.0) < 1e-9


# ── case_transient ────────────────────────────────────────────────────────────

class TestTransientParser:
    """case_transient: 最小過渡ケースのパーサーテスト。"""

    def setup_method(self):
        path = _inp("case_transient", "transient.inp")
        self.sections = parse_header_input(path)
        self.config, self.model = build_model(self.sections, path)

    def test_analysis_type_is_transient(self):
        assert self.config.analysis_type == "TRANSIENT"

    def test_transient_method_is_backward(self):
        assert self.config.transient_method == "BACKWARD"

    def test_time_range(self):
        assert abs(self.config.time_start - 0.0) < 1e-9
        assert abs(self.config.time_end - 10.0) < 1e-9

    def test_output_interval(self):
        assert abs(self.config.dt - 5.0) < 1e-9

    def test_timestep(self):
        assert abs(self.config.delta_t - 1.0) < 1e-9

    def test_node_count(self):
        assert len(self.model.nodes) == 2

    def test_boundary_node(self):
        assert "MAIN.2" in self.model.boundary_nodes

    def test_heat_capacity(self):
        c = self.model.nodes["MAIN.1"]["C"]
        assert c is not None
        assert abs(c - 1.0) < 1e-9

    def test_conductor_conductance(self):
        assert ("MAIN.1", "MAIN.2") in self.model.conductance
        assert abs(self.model.conductance[("MAIN.1", "MAIN.2")] - 0.5) < 1e-9

    def test_no_heat_source(self):
        assert "MAIN.1" not in self.model.heat_input
        assert "MAIN.1" not in self.model.heat_input_func


# ── case_radiation ────────────────────────────────────────────────────────────

class TestRadiationParser:
    """case_radiation: 輻射コンダクタのパーサーテスト。"""

    def setup_method(self):
        path = _inp("case_radiation", "radiation.inp")
        self.sections = parse_header_input(path)
        self.config, self.model = build_model(self.sections, path)

    def test_analysis_type_is_steady(self):
        assert self.config.analysis_type == "STEADY"

    def test_sigma_value(self):
        assert abs(self.config.sigma - 5.67e-8) < 1e-15

    def test_radiation_conductor_registered(self):
        """負のコンダクタ番号 → radiation_conductors に登録されること。"""
        assert len(self.model.radiation_conductors) == 1

    def test_radiation_conductor_nodes(self):
        assert ("MAIN.1", "MAIN.2") in self.model.radiation_conductors

    def test_radiation_conductor_value(self):
        r = self.model.conductance.get(("MAIN.1", "MAIN.2"))
        assert r is not None
        assert abs(r - 1.0) < 1e-9

    def test_node_count(self):
        assert len(self.model.nodes) == 2

    def test_boundary_node(self):
        assert "MAIN.2" in self.model.boundary_nodes

    def test_heat_source(self):
        assert "MAIN.1" in self.model.heat_input
        assert abs(self.model.heat_input["MAIN.1"] - 10.0) < 1e-9

    def test_no_conductive_conductors(self):
        """全コンダクタが輻射であること（このケースは輻射のみ）。"""
        assert set(self.model.conductance.keys()) == self.model.radiation_conductors


# ── case_arithmetic ───────────────────────────────────────────────────────────

class TestArithmeticParser:
    """case_arithmetic: 算術節点のパーサーテスト。"""

    def setup_method(self):
        path = _inp("case_arithmetic", "arithmetic.inp")
        self.sections = parse_header_input(path)
        self.config, self.model = build_model(self.sections, path)

    def test_analysis_type_is_steady(self):
        assert self.config.analysis_type == "STEADY"

    def test_arithmetic_node_identified(self):
        """C < 0 のノード MAIN.2 が算術節点として登録されること。"""
        assert "MAIN.2" in self.model.arithmetic_nodes

    def test_arithmetic_node_capacity_is_zero(self):
        """算術節点の内部 C は 0.0 に設定されること。"""
        c = self.model.nodes["MAIN.2"]["C"]
        assert c == 0.0

    def test_boundary_nodes(self):
        assert "MAIN.3" in self.model.boundary_nodes
        assert "MAIN.4" in self.model.boundary_nodes

    def test_regular_node_not_arithmetic(self):
        assert "MAIN.1" not in self.model.arithmetic_nodes
        assert "MAIN.1" not in self.model.boundary_nodes

    def test_node_count(self):
        # MAIN.1, MAIN.2, MAIN.3, MAIN.4
        assert len(self.model.nodes) == 4

    def test_conductor_count(self):
        # 41: MAIN.4↔MAIN.1, 12: MAIN.1↔MAIN.2, 23: MAIN.2↔MAIN.3
        assert len(self.model.conductance) == 3

    def test_all_conductances_are_conductive(self):
        assert len(self.model.radiation_conductors) == 0

    def test_boundary_temperatures(self):
        t3 = self.model.nodes["MAIN.3"]["T"]
        t4 = self.model.nodes["MAIN.4"]["T"]
        assert abs(t3 - 373.0) < 1.0, f"MAIN.3(100°C境界): {t3} K"
        assert abs(t4 - 273.0) < 1.0, f"MAIN.4(0°C境界): {t4} K"

    def test_no_heat_source(self):
        for node in ["MAIN.1", "MAIN.2"]:
            assert node not in self.model.heat_input
            assert node not in self.model.heat_input_func
