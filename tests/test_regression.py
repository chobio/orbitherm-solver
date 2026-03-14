"""回帰テスト: run_case() による全ケースの統合テスト。

ソルバーを実際に実行し、代表節点温度・出力ファイル生成・
収束判定・時刻点を確認する。

数値の期待値は各 INP ファイルのコメントに記載した解析解に基づく。
許容誤差は数値解法の近似誤差・反復収束誤差を考慮して設定する。

実行方法:
    cd E:\\Themal_Analysis\\orbitherm-solver
    python -m pytest tests/test_regression.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_DATA = os.path.join(_ROOT, "tests", "data")

from thermal_solver.app.run_case import run_case
from thermal_solver.model.result import SolverResult


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def _inp(case: str, filename: str) -> str:
    return os.path.join(_DATA, case, filename)


def _run(case: str, filename: str, tmpdir: str) -> SolverResult:
    """指定ケースを tmpdir に出力して run_case() を実行する。"""
    out_base = str(Path(tmpdir) / Path(filename).stem)
    return run_case(
        input_path=_inp(case, filename),
        output_base=out_base,
        no_input=True,
        make_plot=False,
    )


# ── case_steady ───────────────────────────────────────────────────────────────

class TestSteadyRegression:
    """case_steady の回帰テスト。

    解析解: T_MAIN.1 = 10 / 2.0 = 5.0 ℃
    """

    def test_run_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_steady", "steady.inp", tmpdir)
            assert result.success, f"実行失敗: {result.error_message}"

    def test_csv_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_steady", "steady.inp", tmpdir)
            assert os.path.isfile(result.output_csv), f"CSV が生成されていない: {result.output_csv}"

    def test_out_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_steady", "steady.inp", tmpdir)
            assert os.path.isfile(result.output_out), f"OUT が生成されていない: {result.output_out}"

    def test_log_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_steady", "steady.inp", tmpdir)
            assert os.path.isfile(result.log_path), f"ログが生成されていない: {result.log_path}"

    def test_steady_temperature_main1(self):
        """MAIN.1 の定常温度 ≈ 5.0 ℃。許容誤差 ±0.1 ℃。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_steady", "steady.inp", tmpdir)
            t = result.results["MAIN.1"][-1]
            assert abs(t - 5.0) < 0.1, f"T_MAIN.1 = {t} ℃ (期待値 5.0 ℃)"

    def test_record_has_one_timepoint(self):
        """定常解析は時刻点が1点のみ。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_steady", "steady.inp", tmpdir)
            assert len(result.record_times) == 1
            assert result.record_times[0] == 0.0

    def test_no_png_generated(self):
        """OUTPUT.GRAPH = FALSE かつ make_plot=False → PNG は生成されない。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_steady", "steady.inp", tmpdir)
            assert result.output_png is None or not os.path.isfile(str(result.output_png))


# ── case_transient ────────────────────────────────────────────────────────────

class TestTransientRegression:
    """case_transient の回帰テスト。

    BACKWARD 陰解法 dt=1s:
        T(n+1) = T(n) / 1.5  (境界 0℃、G=0.5、C=1)
        T(5s)  ≈ 13.17 ℃
        T(10s) ≈ 1.73 ℃
    """

    def test_run_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_transient", "transient.inp", tmpdir)
            assert result.success

    def test_csv_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_transient", "transient.inp", tmpdir)
            assert os.path.isfile(result.output_csv)

    def test_record_times_are_correct(self):
        """t=0, 5, 10 の3点が記録されること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_transient", "transient.inp", tmpdir)
            times = result.record_times
            assert len(times) == 3, f"record_times = {times}"
            assert abs(times[0] - 0.0) < 0.01
            assert abs(times[1] - 5.0) < 0.01
            assert abs(times[2] - 10.0) < 0.01

    def test_initial_temperature(self):
        """t=0 の MAIN.1 温度 ≈ 100 ℃。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_transient", "transient.inp", tmpdir)
            t0 = result.results["MAIN.1"][0]
            assert abs(t0 - 100.0) < 1.0, f"T(t=0) = {t0} ℃"

    def test_temperature_monotonically_decreasing(self):
        """熱源なし・境界0℃ → 温度は単調に減少すること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_transient", "transient.inp", tmpdir)
            temps = result.results["MAIN.1"]
            assert temps[0] > temps[1] > temps[2], (
                f"単調減少でない: {temps}"
            )

    def test_final_temperature_range(self):
        """T(10s) は 0 〜 50 ℃ の範囲内（BACKWARD 近似値 ≈ 1.73 ℃）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_transient", "transient.inp", tmpdir)
            t_final = result.results["MAIN.1"][-1]
            assert 0.0 < t_final < 50.0, f"T(10s) = {t_final} ℃"

    def test_final_temperature_approximate(self):
        """BACKWARD 陰解法の近似値 ≈ 1.73 ℃。許容誤差 ±1.0 ℃。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_transient", "transient.inp", tmpdir)
            t_final = result.results["MAIN.1"][-1]
            assert abs(t_final - 1.73) < 1.0, f"T(10s) = {t_final} ℃ (期待値 ≈ 1.73 ℃)"

    def test_boundary_node_stays_fixed(self):
        """境界ノード MAIN.2 の温度は 0 ℃ に固定されること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_transient", "transient.inp", tmpdir)
            for t in result.results["MAIN.2"]:
                assert abs(t - 0.0) < 0.1, f"MAIN.2 境界温度が変化: {t} ℃"


# ── case_radiation ────────────────────────────────────────────────────────────

class TestRadiationRegression:
    """case_radiation の回帰テスト。

    解析解（厳密）:
        T1^4 = 293^4 + 10 / 5.67e-8 = 7.546e9
        T1 ≈ 294.7 K ≈ 21.7 ℃
    PICARD 法の収束誤差: ±0.2 ℃ 程度
    """

    def test_run_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_radiation", "radiation.inp", tmpdir)
            assert result.success

    def test_csv_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_radiation", "radiation.inp", tmpdir)
            assert os.path.isfile(result.output_csv)

    def test_radiation_node_above_boundary(self):
        """熱源あり → MAIN.1 の温度は境界 MAIN.2 (20℃) より高いこと。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_radiation", "radiation.inp", tmpdir)
            t1 = result.results["MAIN.1"][-1]
            t2 = result.results["MAIN.2"][-1]
            assert t1 > t2, f"T_MAIN.1({t1}) > T_MAIN.2({t2}) でない"

    def test_radiation_temperature_approximate(self):
        """T_MAIN.1 ≈ 21.7 ℃。PICARD 収束許容誤差を含め ±1.0 ℃。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_radiation", "radiation.inp", tmpdir)
            t1 = result.results["MAIN.1"][-1]
            assert abs(t1 - 21.7) < 1.0, (
                f"T_MAIN.1 = {t1} ℃ (期待値 ≈ 21.7 ℃)"
            )

    def test_radiation_temperature_upper_bound(self):
        """輻射のみ・Q=10W → 極端に高温にはならないこと (< 100℃)。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_radiation", "radiation.inp", tmpdir)
            t1 = result.results["MAIN.1"][-1]
            assert t1 < 100.0, f"T_MAIN.1 = {t1} ℃ (上限 100 ℃)"

    def test_boundary_node_fixed(self):
        """境界ノード MAIN.2 = 20 ℃ 固定。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_radiation", "radiation.inp", tmpdir)
            t2 = result.results["MAIN.2"][-1]
            assert abs(t2 - 20.0) < 0.1, f"MAIN.2 = {t2} ℃"


# ── case_arithmetic ───────────────────────────────────────────────────────────

class TestArithmeticRegression:
    """case_arithmetic の回帰テスト。

    解析解（厳密）:
        T_MAIN.1 = 100/3 ≈ 33.333 ℃
        T_MAIN.2 = 200/3 ≈ 66.667 ℃
    PICARD 法の収束許容誤差: ±0.01 ℃ 以内
    """

    def test_run_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_arithmetic", "arithmetic.inp", tmpdir)
            assert result.success

    def test_csv_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_arithmetic", "arithmetic.inp", tmpdir)
            assert os.path.isfile(result.output_csv)

    def test_main1_temperature(self):
        """MAIN.1 の定常温度 = 100/3 ≈ 33.33 ℃。許容誤差 ±0.5 ℃。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_arithmetic", "arithmetic.inp", tmpdir)
            t1 = result.results["MAIN.1"][-1]
            assert abs(t1 - 100.0 / 3.0) < 0.5, (
                f"T_MAIN.1 = {t1} ℃ (期待値 {100/3:.3f} ℃)"
            )

    def test_main2_temperature(self):
        """MAIN.2(算術節点)の定常温度 = 200/3 ≈ 66.67 ℃。許容誤差 ±0.5 ℃。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_arithmetic", "arithmetic.inp", tmpdir)
            t2 = result.results["MAIN.2"][-1]
            assert abs(t2 - 200.0 / 3.0) < 0.5, (
                f"T_MAIN.2 = {t2} ℃ (期待値 {200/3:.3f} ℃)"
            )

    def test_temperature_ordering(self):
        """物理的に T_MAIN.4(0℃) < T_MAIN.1 < T_MAIN.2 < T_MAIN.3(100℃)。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_arithmetic", "arithmetic.inp", tmpdir)
            t1 = result.results["MAIN.1"][-1]
            t2 = result.results["MAIN.2"][-1]
            t3 = result.results["MAIN.3"][-1]
            t4 = result.results["MAIN.4"][-1]
            assert t4 < t1 < t2 < t3, (
                f"温度順序が不正: T4={t4}, T1={t1}, T2={t2}, T3={t3}"
            )

    def test_boundary_nodes_fixed(self):
        """境界ノードの温度は固定されること。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_arithmetic", "arithmetic.inp", tmpdir)
            t3 = result.results["MAIN.3"][-1]
            t4 = result.results["MAIN.4"][-1]
            assert abs(t3 - 100.0) < 0.1, f"MAIN.3(100℃境界) = {t3}"
            assert abs(t4 - 0.0) < 0.1, f"MAIN.4(0℃境界) = {t4}"

    def test_arithmetic_node_heat_balance(self):
        """算術節点の熱収支が≈0であること（定常収束後）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run("case_arithmetic", "arithmetic.inp", tmpdir)
            qnet_main2 = result.results_qnet["MAIN.2"][-1]
            assert abs(qnet_main2) < 0.01, (
                f"MAIN.2 正味熱流入 = {qnet_main2} W (ゼロ期待)"
            )
