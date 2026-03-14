"""Variables0Executor のテスト。

実行方法:
    cd E:\\Themal_Analysis\\Solver_Ver1.1
    python -m pytest tests/test_variables0_executor.py -v
    # または:
    python tests/test_variables0_executor.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from thermal_solver.model.array_data import ArrayData
from thermal_solver.model.variables0 import Variables0Assignment
from thermal_solver.runtime.array_registry import ArrayRegistry
from thermal_solver.runtime.variables0_executor import (
    Variables0Executor,
    Variables0Runtime,
    _validate_ast_safety,
    _eval_node,
)
from thermal_solver.runtime.variables0_functions import Variables0Functions
import ast


def _make_registry() -> ArrayRegistry:
    """テスト用の共通 ArrayRegistry を生成する。"""
    reg = ArrayRegistry()
    reg.add(ArrayData.from_singlet(
        name="POWER_MODE",
        values=[10.0, 20.0, 15.0, 5.0],
        submodel_path="MAIN",
    ))
    reg.add(ArrayData.from_flat_doublet(
        name="SOLAR_HEAT",
        flat_values=[0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0],
        submodel_path="MAIN",
    ))
    return reg


# ══════════════════════════════════════════════════════════════════════════════
# Variables0Runtime
# ══════════════════════════════════════════════════════════════════════════════

class TestVariables0Runtime:
    """Variables0Runtime の基本テスト。"""

    def test_empty_by_default(self):
        rt = Variables0Runtime()
        assert rt.values == {}

    def test_initial_values(self):
        rt = Variables0Runtime(values={"A": 1.0, "B": 2.0})
        assert rt.values["A"] == 1.0
        assert rt.values["B"] == 2.0


# ══════════════════════════════════════════════════════════════════════════════
# 仕様書サンプルの完全実行テスト
# ══════════════════════════════════════════════════════════════════════════════

class TestFullSpecExample:
    """仕様書のサンプルコードをそのまま検証する。"""

    def test_spec_example(self):
        """仕様書の期待値: QEXT≈10.25, MODE_PWR=10.0, QTOTAL≈20.25。

        POWER_MODE は submodel_path="MAIN" 付きで登録されているが、
        executor も submodel_path="MAIN" なので解決できる。
        SOLAR_HEAT も同様。
        """
        registry = _make_registry()

        assignments = [
            Variables0Assignment(
                target="QEXT",
                expression='ARR("SOLAR_HEAT", TIME)',
                submodel_path="MAIN",
            ),
            Variables0Assignment(
                target="MODE_PWR",
                expression='ARRI("POWER_MODE", 1)',
                submodel_path="MAIN",
            ),
            Variables0Assignment(
                target="QTOTAL",
                expression="QEXT + MODE_PWR",
                submodel_path="MAIN",
            ),
        ]

        executor = Variables0Executor(registry, submodel_path="MAIN")
        runtime = executor.execute(assignments, time_value=750.0)

        # SOLAR_HEAT: x=[0,1000,2000], y=[5,12,3]
        # TIME=750 → [0,1000] セグメント: y = 5 + 7 * 0.75 = 10.25
        assert abs(runtime.values["QEXT"] - 10.25) < 1e-9, runtime.values["QEXT"]
        # POWER_MODE[1] = 10.0
        assert runtime.values["MODE_PWR"] == 10.0, runtime.values["MODE_PWR"]
        # QTOTAL = 10.25 + 10.0 = 20.25
        assert abs(runtime.values["QTOTAL"] - 20.25) < 1e-9, runtime.values["QTOTAL"]


# ══════════════════════════════════════════════════════════════════════════════
# ARR / ARRI の評価
# ══════════════════════════════════════════════════════════════════════════════

class TestARRAndARRI:
    """ARR() / ARRI() 呼び出しのテスト。"""

    def _executor(self) -> Variables0Executor:
        return Variables0Executor(_make_registry(), submodel_path="MAIN")

    def test_ARR_interpolates(self):
        """ARR() が doublet を補間すること。"""
        ex = self._executor()
        asgn = [Variables0Assignment("Q", 'ARR("SOLAR_HEAT", TIME)', "MAIN")]
        rt = ex.execute(asgn, time_value=500.0)
        # x=[0,1000], y=[5,12]: 500/1000 = 0.5 → y = 5 + 7*0.5 = 8.5
        assert abs(rt.values["Q"] - 8.5) < 1e-9

    def test_ARR_at_exact_point(self):
        """ARR() が既存点で正確な値を返すこと。"""
        ex = self._executor()
        for time_v, expected_y in [(0.0, 5.0), (1000.0, 12.0), (2000.0, 3.0)]:
            asgn = [Variables0Assignment("Q", 'ARR("SOLAR_HEAT", TIME)', "MAIN")]
            rt = ex.execute(asgn, time_value=time_v)
            assert abs(rt.values["Q"] - expected_y) < 1e-9, f"TIME={time_v}: {rt.values['Q']}"

    def test_ARR_clamp_below(self):
        """ARR() clamp: 下限外は先頭値。"""
        ex = self._executor()
        asgn = [Variables0Assignment("Q", 'ARR("SOLAR_HEAT", TIME)', "MAIN")]
        rt = ex.execute(asgn, time_value=-100.0)
        assert rt.values["Q"] == 5.0

    def test_ARR_clamp_above(self):
        """ARR() clamp: 上限外は末尾値。"""
        ex = self._executor()
        asgn = [Variables0Assignment("Q", 'ARR("SOLAR_HEAT", TIME)', "MAIN")]
        rt = ex.execute(asgn, time_value=9999.0)
        assert rt.values["Q"] == 3.0

    def test_ARRI_index1(self):
        """ARRI() が 1-based インデックスで正しい値を返すこと。"""
        ex = self._executor()
        for idx, expected in [(1, 10.0), (2, 20.0), (3, 15.0), (4, 5.0)]:
            asgn = [Variables0Assignment("M", f'ARRI("POWER_MODE", {idx})', "MAIN")]
            rt = ex.execute(asgn, time_value=0.0)
            assert rt.values["M"] == expected, f"index={idx}: {rt.values['M']}"

    def test_ARRI_out_of_range_raises(self):
        """ARRI() の範囲外インデックスで IndexError が上がること。"""
        ex = self._executor()
        asgn = [Variables0Assignment("M", 'ARRI("POWER_MODE", 99)', "MAIN")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except IndexError:
            pass

    def test_ARR_on_singlet_raises_typeerror(self):
        """singlet 配列に ARR() を呼ぶと TypeError。"""
        ex = self._executor()
        asgn = [Variables0Assignment("Q", 'ARR("POWER_MODE", TIME)', "MAIN")]
        try:
            ex.execute(asgn, time_value=1.0)
            assert False, "例外が上がるべき"
        except TypeError:
            pass

    def test_ARRI_on_doublet_raises_typeerror(self):
        """doublet 配列に ARRI() を呼ぶと TypeError。"""
        ex = self._executor()
        asgn = [Variables0Assignment("Q", 'ARRI("SOLAR_HEAT", 1)', "MAIN")]
        try:
            ex.execute(asgn, time_value=1.0)
            assert False, "例外が上がるべき"
        except TypeError:
            pass

    def test_ARR_non_string_literal_raises(self):
        """ARR() の第1引数が変数名だと TypeError。"""
        ex = self._executor()
        # ARR(SOME_VAR, TIME) → first arg is Name, not Constant str
        asgn = [Variables0Assignment("Q", "ARR(SOME_VAR, TIME)", "MAIN")]
        try:
            ex.execute(asgn, time_value=1.0)
            assert False, "例外が上がるべき"
        except (TypeError, NameError):
            pass

    def test_ARRI_float_index_raises(self):
        """ARRI() の第2引数が非整数 float だと TypeError。"""
        ex = self._executor()
        asgn = [Variables0Assignment("M", 'ARRI("POWER_MODE", 1.5)', "MAIN")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except TypeError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# TIME の利用
# ══════════════════════════════════════════════════════════════════════════════

class TestTimeVariable:
    """TIME 変数のテスト。"""

    def _executor(self) -> Variables0Executor:
        return Variables0Executor(_make_registry(), submodel_path="MAIN")

    def test_TIME_used_directly(self):
        """TIME をそのまま変数として使えること。"""
        ex = self._executor()
        asgn = [Variables0Assignment("T", "TIME", "")]
        rt = ex.execute(asgn, time_value=123.456)
        assert abs(rt.values["T"] - 123.456) < 1e-9

    def test_TIME_in_arithmetic(self):
        """TIME を算術式で使えること。"""
        ex = self._executor()
        asgn = [Variables0Assignment("T2", "TIME * 2.0 + 1.0", "")]
        rt = ex.execute(asgn, time_value=10.0)
        assert abs(rt.values["T2"] - 21.0) < 1e-9

    def test_TIME_as_ARR_argument(self):
        """TIME を ARR() の第2引数として使えること。"""
        ex = self._executor()
        asgn = [Variables0Assignment("Q", 'ARR("SOLAR_HEAT", TIME)', "MAIN")]
        rt = ex.execute(asgn, time_value=1000.0)
        assert rt.values["Q"] == 12.0


# ══════════════════════════════════════════════════════════════════════════════
# 四則演算
# ══════════════════════════════════════════════════════════════════════════════

class TestArithmetic:
    """四則演算のテスト。"""

    def _executor(self) -> Variables0Executor:
        return Variables0Executor(_make_registry(), submodel_path="MAIN")

    def test_addition(self):
        ex = self._executor()
        asgn = [Variables0Assignment("R", "1.0 + 2.0", "")]
        assert abs(ex.execute(asgn, 0.0).values["R"] - 3.0) < 1e-9

    def test_subtraction(self):
        ex = self._executor()
        asgn = [Variables0Assignment("R", "10.0 - 3.0", "")]
        assert abs(ex.execute(asgn, 0.0).values["R"] - 7.0) < 1e-9

    def test_multiplication(self):
        ex = self._executor()
        asgn = [Variables0Assignment("R", "4.0 * 5.0", "")]
        assert abs(ex.execute(asgn, 0.0).values["R"] - 20.0) < 1e-9

    def test_division(self):
        ex = self._executor()
        asgn = [Variables0Assignment("R", "10.0 / 4.0", "")]
        assert abs(ex.execute(asgn, 0.0).values["R"] - 2.5) < 1e-9

    def test_unary_minus(self):
        ex = self._executor()
        asgn = [Variables0Assignment("R", "-5.0", "")]
        assert abs(ex.execute(asgn, 0.0).values["R"] - (-5.0)) < 1e-9

    def test_unary_plus(self):
        ex = self._executor()
        asgn = [Variables0Assignment("R", "+3.0", "")]
        assert abs(ex.execute(asgn, 0.0).values["R"] - 3.0) < 1e-9

    def test_parentheses(self):
        ex = self._executor()
        asgn = [Variables0Assignment("R", "(2.0 + 3.0) * 4.0", "")]
        assert abs(ex.execute(asgn, 0.0).values["R"] - 20.0) < 1e-9

    def test_division_by_zero(self):
        ex = self._executor()
        asgn = [Variables0Assignment("R", "1.0 / 0.0", "")]
        try:
            ex.execute(asgn, 0.0)
            assert False, "例外が上がるべき"
        except ZeroDivisionError:
            pass

    def test_complex_expression(self):
        """複合演算式のテスト。"""
        ex = self._executor()
        asgn = [Variables0Assignment("R", "2.0 * 3.0 + 4.0 / 2.0 - 1.0", "")]
        # 2*3 + 4/2 - 1 = 6 + 2 - 1 = 7
        assert abs(ex.execute(asgn, 0.0).values["R"] - 7.0) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# 既存変数の参照（逐次代入）
# ══════════════════════════════════════════════════════════════════════════════

class TestSequentialAssignment:
    """変数が上から順に評価され、後続の式で前の結果を参照できること。"""

    def _executor(self) -> Variables0Executor:
        return Variables0Executor(_make_registry(), submodel_path="MAIN")

    def test_sequential_evaluation(self):
        ex = self._executor()
        asgn = [
            Variables0Assignment("A", "10.0", ""),
            Variables0Assignment("B", "A * 2.0", ""),
            Variables0Assignment("C", "A + B", ""),
        ]
        rt = ex.execute(asgn, time_value=0.0)
        assert rt.values["A"] == 10.0
        assert rt.values["B"] == 20.0
        assert rt.values["C"] == 30.0

    def test_undefined_variable_raises(self):
        """未定義変数を参照すると NameError。"""
        ex = self._executor()
        asgn = [Variables0Assignment("R", "UNDEFINED_VAR * 2.0", "")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except NameError as e:
            assert "UNDEFINED_VAR" in str(e)

    def test_runtime_accumulates_across_assignments(self):
        """runtime.values が代入ごとに蓄積されること。"""
        ex = self._executor()
        asgn = [
            Variables0Assignment("X", "1.0", ""),
            Variables0Assignment("Y", "2.0", ""),
        ]
        rt = ex.execute(asgn, time_value=0.0)
        assert len(rt.values) == 2

    def test_existing_runtime_is_reused(self):
        """既存の runtime を渡すと変数が引き継がれること。"""
        ex = self._executor()
        rt = Variables0Runtime(values={"PRE": 5.0})
        asgn = [Variables0Assignment("R", "PRE + 10.0", "")]
        rt = ex.execute(asgn, time_value=0.0, runtime=rt)
        assert rt.values["R"] == 15.0
        assert rt.values["PRE"] == 5.0


# ══════════════════════════════════════════════════════════════════════════════
# AST 安全検証
# ══════════════════════════════════════════════════════════════════════════════

class TestASTSafety:
    """禁止 AST ノードの検出テスト。"""

    def _reject_expr(self, expr: str) -> None:
        """式が TypeError を上げることを確認するヘルパー。"""
        tree = ast.parse(expr, mode="eval")
        try:
            _validate_ast_safety(tree)
            assert False, f"式 {expr!r} は拒否されるべきでした"
        except TypeError:
            pass

    def test_attribute_access_rejected(self):
        """属性アクセス (obj.attr) は拒否されること。"""
        self._reject_expr("os.getcwd()")

    def test_list_comprehension_rejected(self):
        """リスト内包表記は拒否されること。"""
        self._reject_expr("[x for x in range(10)]")

    def test_dict_rejected(self):
        """辞書リテラルは拒否されること。"""
        self._reject_expr("{'a': 1}")

    def test_subscript_rejected(self):
        """添字アクセスは拒否されること。"""
        self._reject_expr("arr[0]")

    def test_lambda_rejected(self):
        """lambda は拒否されること（SyntaxError または TypeError）。"""
        try:
            tree = ast.parse("lambda x: x", mode="eval")
            _validate_ast_safety(tree)
            assert False, "lambda は拒否されるべきでした"
        except (TypeError, SyntaxError):
            pass

    def test_allowed_expression_passes(self):
        """許可式は検証を通過すること。"""
        for expr in [
            "1.0 + 2.0",
            "TIME * 3.0",
            "-5.0",
            "(A + B) / 2.0",
            'ARR("X", TIME)',
            'ARRI("Y", 1)',
        ]:
            tree = ast.parse(expr, mode="eval")
            _validate_ast_safety(tree)  # 例外が上がらないこと


class TestForbiddenFunctions:
    """禁止関数の検出テスト。"""

    def _executor(self) -> Variables0Executor:
        return Variables0Executor(_make_registry(), submodel_path="MAIN")

    def test_builtin_print_rejected(self):
        """print() は拒否されること。"""
        ex = self._executor()
        asgn = [Variables0Assignment("R", "print(1.0)", "")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except (NameError, TypeError):
            pass

    def test_arbitrary_function_rejected(self):
        """未登録の任意関数は拒否されること。"""
        ex = self._executor()
        asgn = [Variables0Assignment("R", "SIN(1.0)", "")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except (NameError, TypeError):
            pass

    def test_getattr_rejected(self):
        """getattr() は拒否されること。"""
        ex = self._executor()
        asgn = [Variables0Assignment("R", "getattr(os, 'system')", "")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except (NameError, TypeError):
            pass

    def test_ARR_without_enough_args_raises(self):
        """ARR() 引数不足は TypeError。"""
        ex = self._executor()
        asgn = [Variables0Assignment("R", 'ARR("SOLAR_HEAT")', "MAIN")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except TypeError:
            pass

    def test_ARRI_without_enough_args_raises(self):
        """ARRI() 引数不足は TypeError。"""
        ex = self._executor()
        asgn = [Variables0Assignment("R", 'ARRI("POWER_MODE")', "MAIN")]
        try:
            ex.execute(asgn, time_value=0.0)
            assert False, "例外が上がるべき"
        except TypeError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# submodel_path 付きの解決
# ══════════════════════════════════════════════════════════════════════════════

class TestSubmodelPathResolution:
    """submodel_path を使った名前解決のテスト。"""

    def test_submodel_path_from_executor(self):
        """executor の submodel_path で配列を解決できること。"""
        reg = ArrayRegistry()
        reg.add(ArrayData.from_singlet("PM", [100.0, 200.0], submodel_path="SUB1"))
        ex = Variables0Executor(reg, submodel_path="SUB1")
        asgn = [Variables0Assignment("R", 'ARRI("PM", 1)', "SUB1")]
        rt = ex.execute(asgn, time_value=0.0)
        assert rt.values["R"] == 100.0

    def test_submodel_path_fallback(self):
        """サブモデルパスなしで登録した配列はどのパスからでも解決できること。"""
        reg = ArrayRegistry()
        reg.add(ArrayData.from_singlet("GLOBAL", [42.0]))  # submodel_path=""
        ex = Variables0Executor(reg, submodel_path="ANY_SUB")
        asgn = [Variables0Assignment("R", 'ARRI("GLOBAL", 1)', "ANY_SUB")]
        rt = ex.execute(asgn, time_value=0.0)
        assert rt.values["R"] == 42.0

    def test_assignment_submodel_overrides_executor_default(self):
        """assignment の submodel_path が executor のデフォルトより優先されること。"""
        reg = ArrayRegistry()
        reg.add(ArrayData.from_singlet("LOCAL", [99.0], submodel_path="LOCAL_SUB"))
        # executor は "MAIN" で初期化、assignment は "LOCAL_SUB" を指定
        ex = Variables0Executor(reg, submodel_path="MAIN")
        asgn = [Variables0Assignment("R", 'ARRI("LOCAL", 1)', submodel_path="LOCAL_SUB")]
        rt = ex.execute(asgn, time_value=0.0)
        assert rt.values["R"] == 99.0


# ══════════════════════════════════════════════════════════════════════════════
# スタンドアロン実行
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_classes = [
        TestVariables0Runtime,
        TestFullSpecExample,
        TestARRAndARRI,
        TestTimeVariable,
        TestArithmetic,
        TestSequentialAssignment,
        TestASTSafety,
        TestForbiddenFunctions,
        TestSubmodelPathResolution,
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
