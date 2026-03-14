"""parse_array_section / parse_variables0_section のテスト。

実行方法:
    cd E:\\Themal_Analysis\\orbitherm-solver
    python -m pytest tests/test_input_parser_arrays.py -v
    # または:
    python tests/test_input_parser_arrays.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from thermal_solver.io.input_parser import parse_array_section, parse_variables0_section
from thermal_solver.model.array_data import ArrayData
from thermal_solver.model.variables0 import Variables0Assignment


# ══════════════════════════════════════════════════════════════════════════════
# parse_array_section: doublet
# ══════════════════════════════════════════════════════════════════════════════

class TestParseArraySectionDoublet:
    """doublet 配列の parse テスト。"""

    def test_basic_doublet(self):
        """最小構成の doublet を正しくパースできること。"""
        lines = [(10, "SOLAR_HEAT, 0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0")]
        result = parse_array_section(lines)
        assert len(result) == 1
        arr = result[0]
        assert arr.name == "SOLAR_HEAT"
        assert arr.array_type == "doublet"
        assert arr.x_values == [0.0, 1000.0, 2000.0]
        assert arr.y_values == [5.0, 12.0, 3.0]
        assert arr.extrapolation == "clamp"

    def test_doublet_extrap_linear(self):
        """EXTRAP=LINEAR を正しく認識できること。"""
        lines = [(11, "HEAT_PROFILE, EXTRAP=LINEAR, 0.0, 100.0, 3600.0, 200.0, 7200.0, 50.0")]
        result = parse_array_section(lines)
        assert result[0].extrapolation == "linear"
        assert result[0].x_values == [0.0, 3600.0, 7200.0]
        assert result[0].y_values == [100.0, 200.0, 50.0]

    def test_doublet_extrap_clamp_explicit(self):
        """EXTRAP=CLAMP を明示的に指定できること。"""
        lines = [(12, "ARR_X, EXTRAP=CLAMP, 0.0, 1.0, 10.0, 2.0")]
        result = parse_array_section(lines)
        assert result[0].extrapolation == "clamp"

    def test_doublet_extrap_error(self):
        """EXTRAP=ERROR を指定できること。"""
        lines = [(13, "ARR_Y, EXTRAP=ERROR, 0.0, 5.0, 100.0, 10.0")]
        result = parse_array_section(lines)
        assert result[0].extrapolation == "error"

    def test_doublet_extrap_case_insensitive(self):
        """EXTRAP= のモードは大文字小文字を区別しないこと。"""
        lines = [(14, "ARR_Z, extrap=linear, 0.0, 1.0, 5.0, 2.0")]
        result = parse_array_section(lines)
        assert result[0].extrapolation == "linear"

    def test_multiple_doublets(self):
        """複数行の doublet を正しくパースできること。"""
        lines = [
            (10, "SOLAR_HEAT, 0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0"),
            (11, "HEAT_PROFILE, EXTRAP=LINEAR, 0.0, 100.0, 3600.0, 200.0"),
        ]
        result = parse_array_section(lines)
        assert len(result) == 2
        assert result[0].name == "SOLAR_HEAT"
        assert result[1].name == "HEAT_PROFILE"

    def test_doublet_odd_count_raises(self):
        """奇数個の数値で ValueError が上がること。"""
        lines = [(15, "BAD_ARR, 0.0, 5.0, 1000.0")]
        try:
            parse_array_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "15" in str(e)
            assert "BAD_ARR" in str(e)

    def test_doublet_single_point_raises(self):
        """1点のみは ArrayData バリデーションで弾かれること。"""
        lines = [(16, "ONE_POINT, 0.0, 5.0")]
        try:
            parse_array_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "16" in str(e)

    def test_doublet_non_monotonic_raises(self):
        """x が単調増加でない場合に ValueError が上がること。"""
        lines = [(17, "BAD_X, 0.0, 1.0, 5.0, 2.0, 3.0, 3.0")]
        try:
            parse_array_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "17" in str(e)

    def test_empty_lines_skipped(self):
        """空行はスキップされること。"""
        lines = [(10, ""), (11, "   "), (12, "SOLAR_HEAT, 0.0, 5.0, 1000.0, 12.0")]
        result = parse_array_section(lines)
        assert len(result) == 1

    def test_submodel_path_propagated(self):
        """submodel_path が各 ArrayData に設定されること。"""
        lines = [(10, "SOLAR, 0.0, 1.0, 100.0, 2.0")]
        result = parse_array_section(lines, submodel_path="SUB1")
        assert result[0].submodel_path == "SUB1"


# ══════════════════════════════════════════════════════════════════════════════
# parse_array_section: singlet
# ══════════════════════════════════════════════════════════════════════════════

class TestParseArraySectionSinglet:
    """singlet 配列の parse テスト。"""

    def test_basic_singlet(self):
        """最小構成の singlet を正しくパースできること。"""
        lines = [(20, "POWER_MODE, S, 10.0, 20.0, 15.0, 5.0")]
        result = parse_array_section(lines)
        assert len(result) == 1
        arr = result[0]
        assert arr.name == "POWER_MODE"
        assert arr.array_type == "singlet"
        assert arr.values == [10.0, 20.0, 15.0, 5.0]

    def test_singlet_s_lowercase(self):
        """'s' の小文字でも singlet と認識されること。"""
        lines = [(21, "PM, s, 1.0, 2.0")]
        result = parse_array_section(lines)
        assert result[0].array_type == "singlet"

    def test_singlet_single_value(self):
        """1個の値でも singlet を生成できること。"""
        lines = [(22, "SINGLE, S, 42.0")]
        result = parse_array_section(lines)
        assert result[0].values == [42.0]

    def test_singlet_empty_raises(self):
        """S の後に値がない場合は ValueError が上がること。"""
        lines = [(23, "EMPTY, S")]
        try:
            parse_array_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "23" in str(e)
            assert "EMPTY" in str(e)

    def test_mixed_singlet_and_doublet(self):
        """singlet と doublet が混在しても正しくパースできること。"""
        lines = [
            (10, "SOLAR, 0.0, 5.0, 1000.0, 12.0"),
            (11, "POWER_MODE, S, 10.0, 20.0"),
        ]
        result = parse_array_section(lines)
        assert len(result) == 2
        assert result[0].array_type == "doublet"
        assert result[1].array_type == "singlet"


# ══════════════════════════════════════════════════════════════════════════════
# parse_array_section: エラーケース
# ══════════════════════════════════════════════════════════════════════════════

class TestParseArraySectionErrors:
    """エラーケースのテスト。"""

    def test_no_name_raises(self):
        """先頭が空なら ValueError（行番号付き）。"""
        lines = [(5, ", 0.0, 1.0, 2.0, 3.0")]
        try:
            parse_array_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "5" in str(e)
            assert "name" in str(e)

    def test_non_numeric_in_doublet_raises(self):
        """doublet に非数値が混じると ValueError。"""
        lines = [(6, "ARR, 0.0, abc, 1.0, 2.0")]
        try:
            parse_array_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "6" in str(e)


# ══════════════════════════════════════════════════════════════════════════════
# parse_variables0_section
# ══════════════════════════════════════════════════════════════════════════════

class TestParseVariables0Section:
    """parse_variables0_section() のテスト。"""

    def test_basic_assignment(self):
        """単純な代入文をパースできること。"""
        lines = [(30, 'QEXT = ARR("SOLAR_HEAT", TIME)')]
        result = parse_variables0_section(lines)
        assert len(result) == 1
        assert result[0].target == "QEXT"
        assert result[0].expression == 'ARR("SOLAR_HEAT", TIME)'

    def test_multiple_assignments(self):
        """複数の代入文を順序保持でパースできること。"""
        lines = [
            (30, 'QEXT = ARR("SOLAR_HEAT", TIME)'),
            (31, 'MODE_PWR = ARRI("POWER_MODE", 1)'),
            (32, "QTOTAL = QEXT + MODE_PWR"),
        ]
        result = parse_variables0_section(lines)
        assert len(result) == 3
        assert result[0].target == "QEXT"
        assert result[1].target == "MODE_PWR"
        assert result[2].target == "QTOTAL"
        assert result[2].expression == "QEXT + MODE_PWR"

    def test_empty_lines_skipped(self):
        """空行はスキップされること。"""
        lines = [(30, ""), (31, "   "), (32, "QEXT = 100.0")]
        result = parse_variables0_section(lines)
        assert len(result) == 1

    def test_arithmetic_expression(self):
        """四則演算を含む式を正しくパースできること。"""
        lines = [(40, "QTOTAL = QEXT + MODE_PWR * 2.0 - 5.0")]
        result = parse_variables0_section(lines)
        assert result[0].expression == "QTOTAL = QEXT + MODE_PWR * 2.0 - 5.0".split("=", 1)[1].strip()

    def test_submodel_path_set(self):
        """submodel_path が各 assignment に設定されること。"""
        lines = [(50, "QEXT = 100.0")]
        result = parse_variables0_section(lines, submodel_path="MAIN")
        assert result[0].submodel_path == "MAIN"

    def test_invalid_no_equals_raises(self):
        """'=' がない行は ValueError（行番号付き）。"""
        lines = [(60, "QEXT 100.0")]
        try:
            parse_variables0_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "60" in str(e)

    def test_invalid_target_starts_with_digit_raises(self):
        """先頭が数字の変数名は ValueError。"""
        lines = [(61, "1QEXT = 100.0")]
        try:
            parse_variables0_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "61" in str(e)

    def test_expression_with_parens(self):
        """括弧を含む式を正しくパースできること。"""
        lines = [(70, "Q = (QEXT + 10.0) * 2.0")]
        result = parse_variables0_section(lines)
        assert result[0].expression == "(QEXT + 10.0) * 2.0"

    def test_numeric_literal_only(self):
        """右辺が数値リテラルのみでも動作すること。"""
        lines = [(80, "CONST = 273.15")]
        result = parse_variables0_section(lines)
        assert result[0].target == "CONST"
        assert result[0].expression == "273.15"

    def test_target_with_underscore(self):
        """アンダースコアを含む変数名をパースできること。"""
        lines = [(90, "SOLAR_FLUX = 1361.0")]
        result = parse_variables0_section(lines)
        assert result[0].target == "SOLAR_FLUX"


# ══════════════════════════════════════════════════════════════════════════════
# スタンドアロン実行
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_classes = [
        TestParseArraySectionDoublet,
        TestParseArraySectionSinglet,
        TestParseArraySectionErrors,
        TestParseVariables0Section,
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
