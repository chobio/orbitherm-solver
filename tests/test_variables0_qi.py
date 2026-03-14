"""Variables0Executor の QI(node)=... 機能テスト。

実行方法:
    cd E:\\Themal_Analysis\\Solver_Ver1.1
    python -m pytest tests/test_variables0_qi.py -v
    # または:
    python tests/test_variables0_qi.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from thermal_solver.model.array_data import ArrayData
from thermal_solver.model.thermal_model import ThermalModel
from thermal_solver.model.variables0 import Variables0Assignment
from thermal_solver.runtime.array_registry import ArrayRegistry
from thermal_solver.runtime.variables0_executor import Variables0Executor, Variables0Runtime
from thermal_solver.runtime.variables0_functions import Variables0Functions
from thermal_solver.solvers.common import get_node_qsrc


# ── テスト用フィクスチャヘルパー ─────────────────────────────────────────────

def _make_model() -> ThermalModel:
    """最小構成の ThermalModel を生成する。"""
    model = ThermalModel()
    # MAIN グループのノード
    model.nodes["MAIN.20"] = {"T": 300.0, "C": 100.0}
    model.nodes["MAIN.21"] = {"T": 300.0, "C": 100.0}
    model.nodes["MAIN.30"] = {"T": 300.0, "C": 50.0}
    model.node_groups["MAIN.20"] = "MAIN"
    model.node_groups["MAIN.21"] = "MAIN"
    model.node_groups["MAIN.30"] = "MAIN"
    return model


def _make_registry() -> ArrayRegistry:
    """SOLAR_HEAT (doublet) と POWER_MODE (singlet) を登録した ArrayRegistry。"""
    reg = ArrayRegistry()
    reg.add(ArrayData.from_flat_doublet(
        "SOLAR_HEAT",
        [0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0],
        submodel_path="MAIN",
    ))
    reg.add(ArrayData.from_singlet(
        "POWER_MODE",
        [10.0, 20.0, 15.0, 5.0],
        submodel_path="MAIN",
    ))
    return reg


def _make_executor(model=None) -> Variables0Executor:
    """executor を生成するヘルパー。"""
    return Variables0Executor(_make_registry(), submodel_path="MAIN", model=model)


# ══════════════════════════════════════════════════════════════════════════════
# 1. QI 代入が dynamic_heat_input に入る
# ══════════════════════════════════════════════════════════════════════════════

class TestQIWritesToDynamicHeatInput:
    """QI(node)=value が model.dynamic_heat_input に書き込まれることを確認。"""

    def test_qi_literal_value(self):
        """QI(20) = 5.0 → model.dynamic_heat_input["MAIN.20"] == 5.0"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(20)", "5.0", "MAIN")]
        ex.execute(asgn, time_value=0.0)
        assert "MAIN.20" in model.dynamic_heat_input
        assert abs(model.dynamic_heat_input["MAIN.20"] - 5.0) < 1e-9

    def test_qi_does_not_go_into_runtime_values(self):
        """QI 代入は runtime.values には入らないこと。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(20)", "100.0", "MAIN")]
        rt = ex.execute(asgn, time_value=0.0)
        assert "QI(20)" not in rt.values
        assert len(rt.values) == 0

    def test_qi_multiple_nodes(self):
        """複数ノードへの QI 代入が正しく書き込まれること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [
            Variables0Assignment("QI(20)", "100.0", "MAIN"),
            Variables0Assignment("QI(21)", "200.0", "MAIN"),
        ]
        ex.execute(asgn, time_value=0.0)
        assert abs(model.dynamic_heat_input["MAIN.20"] - 100.0) < 1e-9
        assert abs(model.dynamic_heat_input["MAIN.21"] - 200.0) < 1e-9

    def test_qi_negative_value(self):
        """負の熱入力も正しく書き込まれること（吸熱）。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(20)", "-50.0", "MAIN")]
        ex.execute(asgn, time_value=0.0)
        assert abs(model.dynamic_heat_input["MAIN.20"] - (-50.0)) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# 2. ARR を使って QI 代入できる
# ══════════════════════════════════════════════════════════════════════════════

class TestQIWithARR:
    """QI(node) = ARR("SOLAR_HEAT", TIME) の組み合わせテスト。"""

    def test_qi_with_arr_at_750(self):
        """TIME=750 で ARR の補間値が QI に入ること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(20)", 'ARR("SOLAR_HEAT", TIME)', "MAIN")]
        ex.execute(asgn, time_value=750.0)
        # SOLAR_HEAT: x=[0,1000,2000], y=[5,12,3]
        # TIME=750: [0,1000]セグメント: y = 5 + 7*0.75 = 10.25
        assert abs(model.dynamic_heat_input["MAIN.20"] - 10.25) < 1e-9

    def test_qi_with_arr_at_exact_point(self):
        """既存の補間点と一致する TIME では正確な値が入ること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(20)", 'ARR("SOLAR_HEAT", TIME)', "MAIN")]
        ex.execute(asgn, time_value=0.0)
        assert abs(model.dynamic_heat_input["MAIN.20"] - 5.0) < 1e-9

        ex.execute(asgn, time_value=1000.0)
        assert abs(model.dynamic_heat_input["MAIN.20"] - 12.0) < 1e-9

    def test_qi_with_arri(self):
        """QI(20) = ARRI("POWER_MODE", 2) → 20.0 が入ること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(20)", 'ARRI("POWER_MODE", 2)', "MAIN")]
        ex.execute(asgn, time_value=0.0)
        assert abs(model.dynamic_heat_input["MAIN.20"] - 20.0) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# 3. 通常変数と QI の組み合わせ
# ══════════════════════════════════════════════════════════════════════════════

class TestQIWithRegisterVariable:
    """QEXT = ARR(...); QI(20) = QEXT + 2.0 の組み合わせテスト。"""

    def test_qi_using_intermediate_variable(self):
        """中間変数を経由した QI 代入が正しく動作すること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [
            Variables0Assignment("QEXT", 'ARR("SOLAR_HEAT", TIME)', "MAIN"),
            Variables0Assignment("QI(20)", "QEXT + 2.0", "MAIN"),
        ]
        rt = ex.execute(asgn, time_value=750.0)
        # QEXT = 10.25, QI(20) = 12.25
        assert abs(rt.values["QEXT"] - 10.25) < 1e-9
        assert abs(model.dynamic_heat_input["MAIN.20"] - 12.25) < 1e-9

    def test_qi_and_register_side_by_side(self):
        """通常変数と QI が同一ブロック内で共存できること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [
            Variables0Assignment("FACTOR", "2.0", ""),
            Variables0Assignment("QI(20)", "FACTOR * 10.0", "MAIN"),
            Variables0Assignment("RESULT", "FACTOR + 1.0", ""),
        ]
        rt = ex.execute(asgn, time_value=0.0)
        assert abs(rt.values["FACTOR"] - 2.0) < 1e-9
        assert abs(rt.values["RESULT"] - 3.0) < 1e-9
        assert abs(model.dynamic_heat_input["MAIN.20"] - 20.0) < 1e-9

    def test_qi_arithmetic_expression(self):
        """QI の右辺に四則演算が使えること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(20)", "(100.0 + 50.0) / 2.0", "MAIN")]
        ex.execute(asgn, time_value=0.0)
        assert abs(model.dynamic_heat_input["MAIN.20"] - 75.0) < 1e-9

    def test_qi_with_time(self):
        """QI の右辺で TIME を直接使えること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(20)", "TIME * 0.1", "MAIN")]
        ex.execute(asgn, time_value=500.0)
        assert abs(model.dynamic_heat_input["MAIN.20"] - 50.0) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# 4. model なしで QI を使うとエラー
# ══════════════════════════════════════════════════════════════════════════════

class TestQIWithoutModel:
    """model が設定されていない Executor で QI を使うとエラーになること。"""

    def test_qi_without_model_raises_runtime_error(self):
        """model=None で QI を実行すると RuntimeError が上がること。"""
        ex = Variables0Executor(_make_registry(), submodel_path="MAIN", model=None)
        asgn = [Variables0Assignment("QI(20)", "100.0", "MAIN")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except RuntimeError as e:
            assert "model" in str(e).lower() or "QI" in str(e)

    def test_set_qi_without_model_raises(self):
        """Variables0Functions.set_qi() は model=None のとき RuntimeError。"""
        v0 = Variables0Functions(_make_registry(), model=None)
        try:
            v0.set_qi(20, 100.0)
            assert False, "例外が上がるべき"
        except RuntimeError as e:
            assert "model" in str(e).lower()


# ══════════════════════════════════════════════════════════════════════════════
# 5. 不正な QI ターゲットでエラー
# ══════════════════════════════════════════════════════════════════════════════

class TestQIInvalidTarget:
    """不正な QI ターゲット書式のエラーテスト。"""

    def test_qi_empty_raises(self):
        """QI() （中身なし）は ValueError が上がること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI()", "100.0", "MAIN")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "QI()" in str(e) or "node id" in str(e)

    def test_qi_string_label_not_supported_yet(self):
        """QI(ABC) は整数のみ対応なので TypeError が上がること。"""
        model = _make_model()
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(BATTERY)", "100.0", "MAIN")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except TypeError as e:
            assert "integer" in str(e).lower() or "BATTERY" in str(e)

    def test_qi_node_not_in_model_raises(self):
        """モデルに存在しないノード番号は KeyError が上がること。"""
        model = _make_model()  # nodes: MAIN.20, MAIN.21, MAIN.30
        ex = _make_executor(model)
        asgn = [Variables0Assignment("QI(999)", "100.0", "MAIN")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except KeyError as e:
            assert "999" in str(e)


# ══════════════════════════════════════════════════════════════════════════════
# 6. dynamic_heat_input のクリア振る舞い
# ══════════════════════════════════════════════════════════════════════════════

class TestDynamicHeatInputClear:
    """execute() 呼び出しごとに dynamic_heat_input がクリアされることを確認。"""

    def test_clear_on_each_execute(self):
        """前の execute() の QI 値が次の execute() でクリアされること。"""
        model = _make_model()
        ex = _make_executor(model)

        # 第1回: QI(20) と QI(21) を書き込む
        asgn1 = [
            Variables0Assignment("QI(20)", "100.0", "MAIN"),
            Variables0Assignment("QI(21)", "200.0", "MAIN"),
        ]
        ex.execute(asgn1, time_value=0.0)
        assert "MAIN.20" in model.dynamic_heat_input
        assert "MAIN.21" in model.dynamic_heat_input

        # 第2回: QI(20) のみ書き込む → QI(21) はクリアされるはず
        asgn2 = [Variables0Assignment("QI(20)", "50.0", "MAIN")]
        ex.execute(asgn2, time_value=1.0)

        assert abs(model.dynamic_heat_input["MAIN.20"] - 50.0) < 1e-9
        assert "MAIN.21" not in model.dynamic_heat_input, \
            "QI(21) は前ステップの値が残ってはいけない"

    def test_empty_assignments_clears_all(self):
        """QI なしの execute() では dynamic_heat_input が空になること。"""
        model = _make_model()
        ex = _make_executor(model)

        # 先に QI を書き込む
        ex.execute(
            [Variables0Assignment("QI(20)", "100.0", "MAIN")],
            time_value=0.0,
        )
        assert "MAIN.20" in model.dynamic_heat_input

        # QI なしの execute() → クリアされる
        ex.execute(
            [Variables0Assignment("QEXT", "200.0", "")],
            time_value=1.0,
        )
        assert "MAIN.20" not in model.dynamic_heat_input
        assert len(model.dynamic_heat_input) == 0


# ══════════════════════════════════════════════════════════════════════════════
# 7. get_node_qsrc の優先順位テスト
# ══════════════════════════════════════════════════════════════════════════════

class TestGetNodeQsrcPriority:
    """dynamic_heat_input が静的 heat_input より優先されることを確認。"""

    def test_dynamic_overrides_static(self):
        """dynamic_heat_input が設定されているとき静的値より優先されること。"""
        heat_input = {"MAIN.20": 10.0}
        heat_input_func = {}
        dynamic = {"MAIN.20": 99.0}

        result = get_node_qsrc("MAIN.20", heat_input, heat_input_func, 0.0, dynamic)
        assert result == 99.0

    def test_static_used_when_no_dynamic(self):
        """dynamic_heat_input が空のとき静的値が使われること。"""
        heat_input = {"MAIN.20": 10.0}
        result = get_node_qsrc("MAIN.20", heat_input, {}, 0.0, {})
        assert result == 10.0

    def test_dynamic_none_falls_through_to_static(self):
        """dynamic_heat_input=None のとき静的値が使われること。"""
        heat_input = {"MAIN.20": 10.0}
        result = get_node_qsrc("MAIN.20", heat_input, {}, 0.0, None)
        assert result == 10.0

    def test_default_zero_when_none_set(self):
        """どちらも設定されていないとき 0.0 が返ること。"""
        result = get_node_qsrc("MAIN.99", {}, {}, 0.0, {})
        assert result == 0.0

    def test_dynamic_only_affects_specified_node(self):
        """dynamic は指定ノードのみに影響し、他ノードは静的値を使うこと。"""
        heat_input = {"MAIN.20": 10.0, "MAIN.21": 20.0}
        dynamic = {"MAIN.20": 99.0}  # MAIN.21 は指定なし

        q20 = get_node_qsrc("MAIN.20", heat_input, {}, 0.0, dynamic)
        q21 = get_node_qsrc("MAIN.21", heat_input, {}, 0.0, dynamic)

        assert q20 == 99.0   # dynamic 優先
        assert q21 == 20.0   # 静的値


# ══════════════════════════════════════════════════════════════════════════════
# 8. _resolve_node_label のテスト
# ══════════════════════════════════════════════════════════════════════════════

class TestResolveNodeLabel:
    """Variables0Functions._resolve_node_label() のテスト。"""

    def test_resolve_with_submodel_path(self):
        """submodel_path + node_id でラベルを解決できること。"""
        model = _make_model()
        v0 = Variables0Functions(_make_registry(), model=model)
        label = v0._resolve_node_label(20, submodel_path="MAIN")
        assert label == "MAIN.20"

    def test_resolve_by_suffix_search(self):
        """submodel_path なしでも唯一一致ならラベルを解決できること。"""
        model = _make_model()
        v0 = Variables0Functions(_make_registry(), model=model)
        # MAIN.30 は1つしかない
        label = v0._resolve_node_label(30, submodel_path="")
        assert label == "MAIN.30"

    def test_resolve_ambiguous_raises(self):
        """複数グループに同じ番号があると ValueError が上がること。"""
        model = _make_model()
        model.nodes["SUB.20"] = {"T": 300.0, "C": 100.0}  # 重複する .20
        v0 = Variables0Functions(_make_registry(), model=model)
        try:
            v0._resolve_node_label(20, submodel_path="")
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "Ambiguous" in str(e)

    def test_resolve_missing_raises(self):
        """存在しない node_id で KeyError が上がること。"""
        model = _make_model()
        v0 = Variables0Functions(_make_registry(), model=model)
        try:
            v0._resolve_node_label(999, submodel_path="MAIN")
            assert False, "例外が上がるべき"
        except KeyError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# 9. ThermalModel.dynamic_heat_input フィールドのテスト
# ══════════════════════════════════════════════════════════════════════════════

class TestDynamicHeatInputField:
    """ThermalModel に dynamic_heat_input フィールドが存在することを確認。"""

    def test_field_exists_and_defaults_empty(self):
        """新規モデルでは dynamic_heat_input は空辞書であること。"""
        model = ThermalModel()
        assert hasattr(model, "dynamic_heat_input")
        assert model.dynamic_heat_input == {}

    def test_independent_from_heat_input(self):
        """heat_input と dynamic_heat_input は独立したフィールドであること。"""
        model = ThermalModel()
        model.heat_input["A.1"] = 10.0
        model.dynamic_heat_input["A.1"] = 99.0
        assert model.heat_input["A.1"] == 10.0
        assert model.dynamic_heat_input["A.1"] == 99.0


# ══════════════════════════════════════════════════════════════════════════════
# スタンドアロン実行
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_classes = [
        TestQIWritesToDynamicHeatInput,
        TestQIWithARR,
        TestQIWithRegisterVariable,
        TestQIWithoutModel,
        TestQIInvalidTarget,
        TestDynamicHeatInputClear,
        TestGetNodeQsrcPriority,
        TestResolveNodeLabel,
        TestDynamicHeatInputField,
    ]

    passed = 0
    failed = 0

    for cls in test_classes:
        methods = sorted(m for m in dir(cls) if m.startswith("test_"))
        for m in methods:
            obj = cls()
            try:
                getattr(obj, m)()
                print(f"  PASS  {cls.__name__}.{m}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {cls.__name__}.{m}: {e}")
                failed += 1

    print(f"\n{'='*60}")
    print(f"  合計: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    if failed:
        sys.exit(1)
