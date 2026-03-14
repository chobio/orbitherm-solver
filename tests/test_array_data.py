"""ArrayData / interpolation / ArrayRegistry / Variables0Functions のテスト。

実行方法:
    cd E:\\Themal_Analysis\\orbitherm-solver
    python -m pytest tests/test_array_data.py -v
    # または pytest なしの場合:
    python tests/test_array_data.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from thermal_solver.model.array_data import ArrayData
from thermal_solver.runtime.array_registry import ArrayRegistry
from thermal_solver.runtime.variables0_functions import Variables0Functions
from thermal_solver.subroutines.interpolation import interp_linear


# ══════════════════════════════════════════════════════════════════════════════
# ArrayData: doublet
# ══════════════════════════════════════════════════════════════════════════════

class TestDoubletArrayData:
    """doublet 配列の生成・バリデーション・アクセステスト。"""

    def test_from_doublet_basic(self):
        """正常な doublet 配列を生成できること。"""
        arr = ArrayData.from_doublet(
            name="SOLAR_HEAT",
            x_values=[0.0, 1000.0, 2000.0],
            y_values=[5.0, 12.0, 3.0],
        )
        assert arr.name == "SOLAR_HEAT"
        assert arr.array_type == "doublet"
        assert arr.x_values == [0.0, 1000.0, 2000.0]
        assert arr.y_values == [5.0, 12.0, 3.0]
        assert arr.extrapolation == "clamp"

    def test_from_flat_doublet(self):
        """フラットリストから doublet を正しく展開できること。"""
        arr = ArrayData.from_flat_doublet(
            name="SOLAR_HEAT",
            flat_values=[0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0],
        )
        assert arr.x_values == [0.0, 1000.0, 2000.0]
        assert arr.y_values == [5.0, 12.0, 3.0]

    def test_from_flat_doublet_odd_count_raises(self):
        """奇数個の flat_values で ValueError が上がること。"""
        try:
            ArrayData.from_flat_doublet("X", [0.0, 1.0, 2.0])
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "奇数" not in str(e) or "偶数" in str(e) or "3" in str(e)

    def test_non_monotonic_x_raises(self):
        """x が厳密単調増加でない場合に ValueError が上がること。"""
        try:
            ArrayData.from_doublet("X", [0.0, 2.0, 1.0], [1.0, 2.0, 3.0])
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "単調増加" in str(e)

    def test_duplicate_x_raises(self):
        """x に重複値がある場合に ValueError が上がること。"""
        try:
            ArrayData.from_doublet("X", [0.0, 1.0, 1.0], [1.0, 2.0, 3.0])
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "単調増加" in str(e)

    def test_xy_length_mismatch_raises(self):
        """x と y の長さ不一致で ValueError が上がること。"""
        try:
            ArrayData.from_doublet("X", [0.0, 1.0], [1.0, 2.0, 3.0])
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "長さ" in str(e)

    def test_single_point_raises(self):
        """1点のみでは補間できないため ValueError が上がること。"""
        try:
            ArrayData.from_doublet("X", [0.0], [1.0])
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "2点" in str(e)

    def test_empty_raises(self):
        """空の x/y で ValueError が上がること。"""
        try:
            ArrayData.from_doublet("X", [], [])
            assert False, "例外が上がるべき"
        except ValueError:
            pass

    def test_values_field_must_be_empty_for_doublet(self):
        """doublet なのに values が入っていれば ValueError が上がること。"""
        try:
            ArrayData(
                name="X",
                array_type="doublet",
                x_values=[0.0, 1.0],
                y_values=[0.0, 1.0],
                values=[99.0],
            )
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "values" in str(e)

    def test_get_singlet_value_on_doublet_raises_typeerror(self):
        """doublet に get_singlet_value() を呼んだら TypeError が上がること。"""
        arr = ArrayData.from_doublet("X", [0.0, 1.0], [0.0, 1.0])
        try:
            arr.get_singlet_value(1)
            assert False, "例外が上がるべき"
        except TypeError as e:
            assert "singlet" in str(e)


# ══════════════════════════════════════════════════════════════════════════════
# ArrayData: singlet
# ══════════════════════════════════════════════════════════════════════════════

class TestSingletArrayData:
    """singlet 配列の生成・アクセステスト。"""

    def test_from_singlet_basic(self):
        """正常な singlet 配列を生成できること。"""
        arr = ArrayData.from_singlet("POWER_MODE", [10.0, 20.0, 15.0, 5.0])
        assert arr.name == "POWER_MODE"
        assert arr.array_type == "singlet"
        assert arr.values == [10.0, 20.0, 15.0, 5.0]

    def test_get_singlet_value_1based(self):
        """1-based インデックスで正しい値を返すこと。"""
        arr = ArrayData.from_singlet("PM", [10.0, 20.0, 15.0, 5.0])
        assert arr.get_singlet_value(1) == 10.0
        assert arr.get_singlet_value(2) == 20.0
        assert arr.get_singlet_value(3) == 15.0
        assert arr.get_singlet_value(4) == 5.0

    def test_get_singlet_value_out_of_range_raises(self):
        """範囲外インデックスで IndexError が上がること。"""
        arr = ArrayData.from_singlet("PM", [10.0, 20.0])
        try:
            arr.get_singlet_value(0)
            assert False, "例外が上がるべき"
        except IndexError:
            pass
        try:
            arr.get_singlet_value(3)
            assert False, "例外が上がるべき"
        except IndexError:
            pass

    def test_singlet_empty_raises(self):
        """空の values で ValueError が上がること。"""
        try:
            ArrayData.from_singlet("PM", [])
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "1個以上" in str(e)

    def test_singlet_with_x_values_raises(self):
        """singlet なのに x_values が入っていれば ValueError が上がること。"""
        try:
            ArrayData(
                name="X",
                array_type="singlet",
                values=[1.0],
                x_values=[0.0],
            )
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "x_values" in str(e)

    def test_invalid_array_type_raises(self):
        """無効な array_type で ValueError が上がること。"""
        try:
            ArrayData(name="X", array_type="triplet")  # type: ignore
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "triplet" in str(e)

    def test_empty_name_raises(self):
        """空の name で ValueError が上がること。"""
        try:
            ArrayData.from_singlet("", [1.0])
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "name" in str(e)


# ══════════════════════════════════════════════════════════════════════════════
# interp_linear
# ══════════════════════════════════════════════════════════════════════════════

class TestInterpLinear:
    """interp_linear() の補間・外挿テスト。"""

    def _solar(self, extrap="clamp") -> ArrayData:
        return ArrayData.from_flat_doublet(
            "SOLAR_HEAT",
            [0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0],
            extrapolation=extrap,
        )

    # ── 範囲内 ──────────────────────────────────────────────────────────

    def test_exact_lower_bound(self):
        assert interp_linear(self._solar(), 0.0) == 5.0

    def test_exact_upper_bound(self):
        assert interp_linear(self._solar(), 2000.0) == 3.0

    def test_exact_midpoint(self):
        assert interp_linear(self._solar(), 1000.0) == 12.0

    def test_interpolate_first_segment(self):
        """x=500: x=[0,1000] y=[5,12] → y=8.5"""
        result = interp_linear(self._solar(), 500.0)
        assert abs(result - 8.5) < 1e-9, f"期待値 8.5, 実際 {result}"

    def test_interpolate_second_segment(self):
        """x=750: x=[0,1000] y=[5,12] → y=5 + 7*0.75 = 10.25"""
        result = interp_linear(self._solar(), 750.0)
        assert abs(result - 10.25) < 1e-9, f"期待値 10.25, 実際 {result}"

    def test_interpolate_request_value(self):
        """ユーザーが期待した q_solar at 750.0 のテスト。"""
        arr = ArrayData.from_flat_doublet(
            "SOLAR_HEAT",
            [0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0],
        )
        result = interp_linear(arr, 750.0)
        # x=[0,1000], y=[5,12]: 750/1000 = 0.75 → y = 5 + 7*0.75 = 10.25
        assert abs(result - 10.25) < 1e-9

    # ── clamp ────────────────────────────────────────────────────────────

    def test_clamp_below(self):
        """clamp: 下限以下は先頭値を返す。"""
        result = interp_linear(self._solar("clamp"), -100.0)
        assert result == 5.0

    def test_clamp_above(self):
        """clamp: 上限以上は末尾値を返す。"""
        result = interp_linear(self._solar("clamp"), 9999.0)
        assert result == 3.0

    # ── linear (外挿) ────────────────────────────────────────────────────

    def test_linear_extrap_below(self):
        """linear: 下限外は最初の2点の傾きで外挿。"""
        # x=[0,1000], y=[5,12]: slope = 7/1000 = 0.007
        # x=-100: y = 5 + 0.007 * (-100 - 0) = 5 - 0.7 = 4.3
        result = interp_linear(self._solar("linear"), -100.0)
        assert abs(result - 4.3) < 1e-9, f"期待値 4.3, 実際 {result}"

    def test_linear_extrap_above(self):
        """linear: 上限外は最後の2点の傾きで外挿。"""
        # x=[1000,2000], y=[12,3]: slope = -9/1000 = -0.009
        # x=2500: y = 3 + (-0.009) * (2500 - 2000) = 3 - 4.5 = -1.5
        result = interp_linear(self._solar("linear"), 2500.0)
        assert abs(result - (-1.5)) < 1e-9, f"期待値 -1.5, 実際 {result}"

    # ── error ────────────────────────────────────────────────────────────

    def test_error_extrap_below_raises(self):
        """error: 下限外で ValueError が上がること。"""
        try:
            interp_linear(self._solar("error"), -1.0)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "範囲外" in str(e)

    def test_error_extrap_above_raises(self):
        """error: 上限外で ValueError が上がること。"""
        try:
            interp_linear(self._solar("error"), 2001.0)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "範囲外" in str(e)

    def test_error_extrap_in_range_does_not_raise(self):
        """error: 範囲内では例外が上がらないこと。"""
        result = interp_linear(self._solar("error"), 500.0)
        assert abs(result - 8.5) < 1e-9

    # ── singlet への呼び出しは TypeError ────────────────────────────────

    def test_singlet_raises_typeerror(self):
        """singlet 配列に interp_linear() を呼んだら TypeError。"""
        arr = ArrayData.from_singlet("PM", [10.0, 20.0])
        try:
            interp_linear(arr, 1.0)
            assert False, "例外が上がるべき"
        except TypeError as e:
            assert "doublet" in str(e)


# ══════════════════════════════════════════════════════════════════════════════
# ArrayRegistry
# ══════════════════════════════════════════════════════════════════════════════

class TestArrayRegistry:
    """ArrayRegistry の登録・取得・名前解決テスト。"""

    def _make_registry(self) -> ArrayRegistry:
        reg = ArrayRegistry()
        reg.add(ArrayData.from_singlet("POWER_MODE", [10.0, 20.0, 15.0, 5.0]))
        reg.add(ArrayData.from_flat_doublet(
            "SOLAR_HEAT",
            [0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0],
        ))
        return reg

    def test_add_and_get(self):
        reg = self._make_registry()
        arr = reg.get("SOLAR_HEAT")
        assert arr.name == "SOLAR_HEAT"
        assert arr.array_type == "doublet"

    def test_get_case_insensitive(self):
        """名前解決は大文字小文字を区別しないこと。"""
        reg = self._make_registry()
        assert reg.get("solar_heat").name == "SOLAR_HEAT"
        assert reg.get("Solar_Heat").name == "SOLAR_HEAT"
        assert reg.get("SOLAR_HEAT").name == "SOLAR_HEAT"

    def test_get_missing_raises_keyerror(self):
        reg = self._make_registry()
        try:
            reg.get("NONEXISTENT")
            assert False, "例外が上がるべき"
        except KeyError:
            pass

    def test_len(self):
        reg = self._make_registry()
        assert len(reg) == 2

    def test_contains(self):
        reg = self._make_registry()
        assert "SOLAR_HEAT" in reg
        assert "MISSING" not in reg

    def test_get_value_doublet(self):
        """doublet の get_value() が正しく補間すること。"""
        reg = self._make_registry()
        result = reg.get_value("SOLAR_HEAT", 500.0)
        assert abs(result - 8.5) < 1e-9

    def test_get_singlet_value(self):
        """singlet の get_singlet_value() が正しい値を返すこと。"""
        reg = self._make_registry()
        assert reg.get_singlet_value("POWER_MODE", 1) == 10.0
        assert reg.get_singlet_value("POWER_MODE", 2) == 20.0

    def test_submodel_path_resolution(self):
        """submodel_path 付きで登録した配列をパスなしでも取得できること。"""
        reg = ArrayRegistry()
        arr = ArrayData.from_singlet(
            name="LOCAL_ARRAY",
            values=[1.0, 2.0],
            submodel_path="SUB1",
        )
        reg.add(arr)
        # 完全修飾で取得
        found = reg.get("LOCAL_ARRAY", submodel_path="SUB1")
        assert found.name == "LOCAL_ARRAY"

    def test_submodel_path_fallback_to_bare_name(self):
        """submodel_path なしで登録された配列は、パス指定でも fallback で取得できること。"""
        reg = ArrayRegistry()
        reg.add(ArrayData.from_singlet("GLOBAL_ARR", [5.0]))
        # パス付きで検索しても bare key でフォールバック
        found = reg.get("GLOBAL_ARR", submodel_path="ANYSUB")
        assert found.name == "GLOBAL_ARR"

    def test_add_non_arraydata_raises(self):
        """ArrayData 以外を add() すると TypeError。"""
        reg = ArrayRegistry()
        try:
            reg.add({"name": "X"})  # type: ignore
            assert False, "例外が上がるべき"
        except TypeError:
            pass

    def test_overwrite_same_name(self):
        """同名配列を add() すると上書きされること。"""
        reg = ArrayRegistry()
        reg.add(ArrayData.from_singlet("A", [1.0]))
        reg.add(ArrayData.from_singlet("A", [99.0]))
        assert reg.get_singlet_value("A", 1) == 99.0


# ══════════════════════════════════════════════════════════════════════════════
# Variables0Functions
# ══════════════════════════════════════════════════════════════════════════════

class TestVariables0Functions:
    """Variables0Functions (ARR / ARRI) のテスト。"""

    def _make_v0(self) -> Variables0Functions:
        reg = ArrayRegistry()
        reg.add(ArrayData.from_singlet("POWER_MODE", [10.0, 20.0, 15.0, 5.0]))
        reg.add(ArrayData.from_flat_doublet(
            "SOLAR_HEAT",
            [0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0],
            extrapolation="clamp",
        ))
        return Variables0Functions(reg)

    def test_ARR_interpolates(self):
        """ARR() が doublet 配列を正しく補間すること。"""
        v0 = self._make_v0()
        result = v0.ARR("SOLAR_HEAT", 750.0)
        # x=[0,1000], y=[5,12]: 750/1000 * 7 + 5 = 10.25
        assert abs(result - 10.25) < 1e-9, f"期待値 10.25, 実際 {result}"

    def test_ARR_at_exact_point(self):
        """ARR() が既存点で正確な値を返すこと。"""
        v0 = self._make_v0()
        assert v0.ARR("SOLAR_HEAT", 0.0) == 5.0
        assert v0.ARR("SOLAR_HEAT", 1000.0) == 12.0
        assert v0.ARR("SOLAR_HEAT", 2000.0) == 3.0

    def test_ARR_clamp_below(self):
        """ARR() の clamp: 下限外は先頭値。"""
        v0 = self._make_v0()
        assert v0.ARR("SOLAR_HEAT", -500.0) == 5.0

    def test_ARR_clamp_above(self):
        """ARR() の clamp: 上限外は末尾値。"""
        v0 = self._make_v0()
        assert v0.ARR("SOLAR_HEAT", 5000.0) == 3.0

    def test_ARRI_returns_correct_value(self):
        """ARRI() が singlet 配列から正しいインデックス値を返すこと。"""
        v0 = self._make_v0()
        assert v0.ARRI("POWER_MODE", 1) == 10.0
        assert v0.ARRI("POWER_MODE", 2) == 20.0
        assert v0.ARRI("POWER_MODE", 3) == 15.0
        assert v0.ARRI("POWER_MODE", 4) == 5.0

    def test_ARRI_out_of_range_raises(self):
        """ARRI() の範囲外インデックスで IndexError。"""
        v0 = self._make_v0()
        try:
            v0.ARRI("POWER_MODE", 5)
            assert False, "例外が上がるべき"
        except IndexError:
            pass

    def test_ARR_on_singlet_raises_typeerror(self):
        """singlet 配列に ARR() を呼ぶと TypeError。"""
        v0 = self._make_v0()
        try:
            v0.ARR("POWER_MODE", 1.0)
            assert False, "例外が上がるべき"
        except TypeError as e:
            assert "doublet" in str(e)

    def test_ARRI_on_doublet_raises_typeerror(self):
        """doublet 配列に ARRI() を呼ぶと TypeError。"""
        v0 = self._make_v0()
        try:
            v0.ARRI("SOLAR_HEAT", 1)
            assert False, "例外が上がるべき"
        except TypeError as e:
            assert "singlet" in str(e)

    def test_ARR_missing_key_raises_keyerror(self):
        """存在しない配列に ARR() を呼ぶと KeyError。"""
        v0 = self._make_v0()
        try:
            v0.ARR("NONEXISTENT", 1.0)
            assert False, "例外が上がるべき"
        except KeyError:
            pass

    def test_as_eval_namespace(self):
        """as_eval_namespace() が ARR/ARRI を含む辞書を返すこと。"""
        v0 = self._make_v0()
        ns = v0.as_eval_namespace()
        assert "ARR" in ns
        assert "ARRI" in ns
        assert callable(ns["ARR"])
        assert callable(ns["ARRI"])

    def test_eval_namespace_usage(self):
        """eval() コンテキストで ARR() が動作すること（将来の parser のテスト）。"""
        v0 = self._make_v0()
        ns = {**v0.as_eval_namespace(), "TIME": 750.0}
        result = eval("ARR('SOLAR_HEAT', TIME)", {"__builtins__": {}}, ns)
        assert abs(result - 10.25) < 1e-9

    def test_full_example_from_spec(self):
        """仕様書のサンプルコードが期待通りに動作すること。

        registry → Variables0Functions → ARR / ARRI の一通りのフロー確認。
        """
        registry = ArrayRegistry()
        registry.add(
            ArrayData.from_singlet(
                name="POWER_MODE",
                values=[10.0, 20.0, 15.0, 5.0],
            )
        )
        registry.add(
            ArrayData.from_flat_doublet(
                name="SOLAR_HEAT",
                flat_values=[0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0],
                extrapolation="clamp",
            )
        )
        v0 = Variables0Functions(registry)

        q_solar = v0.ARR("SOLAR_HEAT", 750.0)
        mode_1 = v0.ARRI("POWER_MODE", 1)

        # 750 は [0,1000] セグメントの 75% → y = 5 + 7*0.75 = 10.25
        assert abs(q_solar - 10.25) < 1e-9, f"q_solar = {q_solar}"
        # POWER_MODE[1] = 10.0
        assert mode_1 == 10.0, f"mode_1 = {mode_1}"


# ══════════════════════════════════════════════════════════════════════════════
# スタンドアロン実行用エントリポイント
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_classes = [
        TestDoubletArrayData,
        TestSingletArrayData,
        TestInterpLinear,
        TestArrayRegistry,
        TestVariables0Functions,
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
