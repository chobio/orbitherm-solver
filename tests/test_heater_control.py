"""HeaterController / HeaterData / parse_heater_section のテスト。

実行方法:
    cd E:\\Themal_Analysis\\orbitherm-solver
    python -m pytest tests/test_heater_control.py -v
    # または:
    python tests/test_heater_control.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from thermal_solver.model.heater import HeaterData
from thermal_solver.model.thermal_model import ThermalModel
from thermal_solver.io.input_parser import parse_heater_section
from thermal_solver.runtime.heater_controller import HeaterController, HeaterRuntimeState
from thermal_solver.solvers.common import get_node_qsrc


# ── テスト用フィクスチャヘルパー ─────────────────────────────────────────────

def _make_model(extra_nodes: dict | None = None) -> ThermalModel:
    """最小構成の ThermalModel を生成する。"""
    model = ThermalModel()
    model.nodes["MAIN.20"] = {"T": 300.0, "C": 100.0}
    model.nodes["MAIN.21"] = {"T": 300.0, "C": 100.0}
    model.nodes["MAIN.30"] = {"T": 300.0, "C": 50.0}
    model.nodes["MAIN.35"] = {"T": 300.0, "C": 50.0}
    model.node_groups.update({
        "MAIN.20": "MAIN", "MAIN.21": "MAIN",
        "MAIN.30": "MAIN", "MAIN.35": "MAIN",
    })
    if extra_nodes:
        model.nodes.update(extra_nodes)
    return model


def _make_heater(
    name="BATT_HTR",
    sense_node=20,
    apply_node=20,
    on_temp=273.15,
    off_temp=278.15,
    heater_power=8.0,
    initial_state=False,
    enabled=True,
    submodel_path="MAIN",
) -> HeaterData:
    return HeaterData(
        name=name,
        sense_node=sense_node,
        apply_node=apply_node,
        on_temp=on_temp,
        off_temp=off_temp,
        heater_power=heater_power,
        initial_state=initial_state,
        enabled=enabled,
        submodel_path=submodel_path,
    )


def _make_controller(heaters: list[HeaterData]) -> tuple[ThermalModel, HeaterController]:
    """ThermalModel + HeaterController を一括生成するヘルパー。"""
    model = _make_model()
    model.heaters = heaters
    controller = HeaterController(model)
    return model, controller


# ══════════════════════════════════════════════════════════════════════════════
# 1. HeaterData バリデーションテスト
# ══════════════════════════════════════════════════════════════════════════════

class TestHeaterDataValidation:
    """HeaterData の生成・バリデーションテスト。"""

    def test_valid_creation(self):
        """正常な HeaterData が生成できること。"""
        h = _make_heater()
        assert h.name == "BATT_HTR"
        assert h.sense_node == 20
        assert h.apply_node == 20
        assert abs(h.on_temp - 273.15) < 1e-9
        assert abs(h.off_temp - 278.15) < 1e-9
        assert abs(h.heater_power - 8.0) < 1e-9
        assert h.initial_state is False
        assert h.enabled is True

    def test_empty_name_raises(self):
        try:
            HeaterData("", 20, 20, 273.15, 278.15, 8.0)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "name" in str(e)

    def test_off_less_than_on_raises(self):
        """off_temp < on_temp で ValueError。"""
        try:
            HeaterData("H", 20, 20, 278.15, 273.15, 8.0)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "OFF" in str(e) or "off_temp" in str(e)

    def test_off_equals_on_is_valid(self):
        """off_temp == on_temp は有効（デッドバンドなし）。"""
        h = HeaterData("H", 20, 20, 273.15, 273.15, 5.0)
        assert abs(h.on_temp - h.off_temp) < 1e-9

    def test_negative_power_raises(self):
        """heater_power < 0 で ValueError。"""
        try:
            HeaterData("H", 20, 20, 273.15, 278.15, -1.0)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "power" in str(e).lower()

    def test_zero_power_is_valid(self):
        """heater_power == 0 は有効（無効ヒータの表現に使える）。"""
        h = HeaterData("H", 20, 20, 273.15, 278.15, 0.0)
        assert h.heater_power == 0.0

    def test_sense_node_must_be_int(self):
        """sense_node が float のとき TypeError。"""
        try:
            HeaterData("H", 20.5, 20, 273.15, 278.15, 8.0)  # type: ignore
            assert False, "例外が上がるべき"
        except TypeError:
            pass

    def test_initial_state_on(self):
        """initial_state=True が反映されること。"""
        h = HeaterData("H", 20, 20, 273.15, 278.15, 8.0, initial_state=True)
        assert h.initial_state is True

    def test_enabled_false(self):
        """enabled=False が反映されること。"""
        h = HeaterData("H", 20, 20, 273.15, 278.15, 8.0, enabled=False)
        assert h.enabled is False


# ══════════════════════════════════════════════════════════════════════════════
# 2. parse_heater_section テスト
# ══════════════════════════════════════════════════════════════════════════════

class TestParseHeaterSection:
    """parse_heater_section() の単体テスト。"""

    def test_basic_parse(self):
        """基本的なヒータ定義をパースできること。"""
        lines = [(10, "BATT_HTR, SENSE=20, APPLY=20, ON=273.15, OFF=278.15, POWER=8.0")]
        heaters = parse_heater_section(lines)
        assert len(heaters) == 1
        h = heaters[0]
        assert h.name == "BATT_HTR"
        assert h.sense_node == 20
        assert h.apply_node == 20
        assert abs(h.on_temp - 273.15) < 1e-9
        assert abs(h.off_temp - 278.15) < 1e-9
        assert abs(h.heater_power - 8.0) < 1e-9
        assert h.initial_state is False
        assert h.enabled is True

    def test_parse_init_on(self):
        """INIT=ON が initial_state=True に変換されること。"""
        lines = [(11, "AVIONICS_HTR, SENSE=31, APPLY=35, ON=268.15, OFF=272.15, POWER=4.5, INIT=ON")]
        heaters = parse_heater_section(lines, submodel_path="MAIN")
        assert heaters[0].initial_state is True
        assert heaters[0].submodel_path == "MAIN"

    def test_parse_init_off_explicit(self):
        """INIT=OFF が初期状態 False に変換されること。"""
        lines = [(12, "H, SENSE=20, APPLY=20, ON=270.0, OFF=275.0, POWER=5.0, INIT=OFF")]
        heaters = parse_heater_section(lines)
        assert heaters[0].initial_state is False

    def test_parse_enabled_no(self):
        """ENABLED=NO が enabled=False に変換されること。"""
        lines = [(13, "H, SENSE=20, APPLY=20, ON=270.0, OFF=275.0, POWER=5.0, ENABLED=NO")]
        heaters = parse_heater_section(lines)
        assert heaters[0].enabled is False

    def test_parse_multiple_heaters(self):
        """複数行を一括パースできること。"""
        lines = [
            (10, "H1, SENSE=20, APPLY=20, ON=273.0, OFF=278.0, POWER=8.0"),
            (11, "H2, SENSE=21, APPLY=21, ON=268.0, OFF=272.0, POWER=4.5"),
        ]
        heaters = parse_heater_section(lines)
        assert len(heaters) == 2
        assert heaters[0].name == "H1"
        assert heaters[1].name == "H2"

    def test_empty_lines_skipped(self):
        """空行が無視されること。"""
        lines = [(9, ""), (10, "H, SENSE=20, APPLY=20, ON=270.0, OFF=275.0, POWER=5.0")]
        heaters = parse_heater_section(lines)
        assert len(heaters) == 1

    def test_missing_required_key_raises(self):
        """必須キー (POWER) が欠落すると ValueError。"""
        lines = [(14, "H, SENSE=20, APPLY=20, ON=270.0, OFF=275.0")]
        try:
            parse_heater_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "POWER" in str(e) or "missing" in str(e).lower()

    def test_invalid_sense_value_raises(self):
        """SENSE が整数でない場合 ValueError。"""
        lines = [(15, "H, SENSE=ABC, APPLY=20, ON=270.0, OFF=275.0, POWER=5.0")]
        try:
            parse_heater_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "SENSE" in str(e)

    def test_invalid_on_value_raises(self):
        """ON が数値でない場合 ValueError。"""
        lines = [(16, "H, SENSE=20, APPLY=20, ON=ABC, OFF=275.0, POWER=5.0")]
        try:
            parse_heater_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "ON" in str(e)

    def test_off_less_than_on_raises(self):
        """OFF < ON のとき ValueError（行番号付き）。"""
        lines = [(17, "H, SENSE=20, APPLY=20, ON=275.0, OFF=270.0, POWER=5.0")]
        try:
            parse_heater_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "17" in str(e) or "OFF" in str(e)

    def test_line_number_in_error_message(self):
        """エラーメッセージに行番号が含まれること。"""
        lines = [(42, "H, SENSE=20, APPLY=20, ON=270.0")]  # missing OFF, POWER
        try:
            parse_heater_section(lines)
            assert False
        except ValueError as e:
            assert "42" in str(e)

    def test_no_name_raises(self):
        """ヒータ名が空のとき ValueError。"""
        lines = [(18, ", SENSE=20, APPLY=20, ON=270.0, OFF=275.0, POWER=5.0")]
        try:
            parse_heater_section(lines)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "name" in str(e).lower()


# ══════════════════════════════════════════════════════════════════════════════
# 3. HeaterController: initialize_states テスト
# ══════════════════════════════════════════════════════════════════════════════

class TestInitializeStates:
    """initialize_states() のテスト。"""

    def test_default_initial_state_off(self):
        """initial_state=False が初期状態として設定されること。"""
        h = _make_heater(initial_state=False)
        model, controller = _make_controller([h])
        rt = controller.initialize_states()
        assert rt.is_on("BATT_HTR") is False

    def test_initial_state_on(self):
        """initial_state=True が初期状態として設定されること。"""
        h = _make_heater(initial_state=True)
        model, controller = _make_controller([h])
        rt = controller.initialize_states()
        assert rt.is_on("BATT_HTR") is True

    def test_existing_state_preserved(self):
        """既存の runtime_state が渡されたとき、既登録の状態は変更されないこと。"""
        h = _make_heater(initial_state=False)
        model, controller = _make_controller([h])
        rt = HeaterRuntimeState()
        rt.set_state("BATT_HTR", True)  # 既に ON
        rt2 = controller.initialize_states(rt)
        assert rt2.is_on("BATT_HTR") is True  # 維持される


# ══════════════════════════════════════════════════════════════════════════════
# 4. HeaterController: ON/OFF 制御テスト
# ══════════════════════════════════════════════════════════════════════════════

class TestHeaterControl:
    """ヒステリシス付き ON/OFF 制御のテスト。"""

    def _run_apply(self, heaters, sense_temp, initial_state=False):
        """apply() を1回実行して返す。"""
        model, controller = _make_controller(heaters)
        model.nodes["MAIN.20"]["T"] = sense_temp
        dhi = {}
        rt = controller.initialize_states()
        rt = controller.apply(model.nodes, dhi, rt)
        return dhi, rt

    def test_turn_on_below_on_temp(self):
        """温度が on_temp 以下のとき OFF → ON に切り替わること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        dhi, rt = self._run_apply([h], sense_temp=270.0)
        assert rt.is_on("BATT_HTR") is True
        assert abs(dhi.get("MAIN.20", 0.0) - 8.0) < 1e-9

    def test_turn_on_at_exact_on_temp(self):
        """温度が on_temp ちょうどのとき ON になること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        dhi, rt = self._run_apply([h], sense_temp=273.15)
        assert rt.is_on("BATT_HTR") is True

    def test_stay_on_in_deadband(self):
        """不感帯温度（on_temp < T < off_temp）で ON 状態を維持すること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 275.0
        dhi = {}
        rt = HeaterRuntimeState()
        rt.set_state("BATT_HTR", True)  # 前状態 ON
        rt = controller.apply(model.nodes, dhi, rt)
        assert rt.is_on("BATT_HTR") is True
        assert abs(dhi.get("MAIN.20", 0.0) - 8.0) < 1e-9

    def test_stay_off_in_deadband(self):
        """不感帯温度で OFF 状態を維持すること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 275.0
        dhi = {}
        rt = HeaterRuntimeState()
        rt.set_state("BATT_HTR", False)  # 前状態 OFF
        rt = controller.apply(model.nodes, dhi, rt)
        assert rt.is_on("BATT_HTR") is False
        assert dhi.get("MAIN.20", 0.0) == 0.0

    def test_turn_off_above_off_temp(self):
        """温度が off_temp 以上のとき ON → OFF に切り替わること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 279.0
        dhi = {}
        rt = HeaterRuntimeState()
        rt.set_state("BATT_HTR", True)  # 前状態 ON
        rt = controller.apply(model.nodes, dhi, rt)
        assert rt.is_on("BATT_HTR") is False
        assert dhi.get("MAIN.20", 0.0) == 0.0

    def test_turn_off_at_exact_off_temp(self):
        """温度が off_temp ちょうどのとき OFF になること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 278.15
        dhi = {}
        rt = HeaterRuntimeState()
        rt.set_state("BATT_HTR", True)
        rt = controller.apply(model.nodes, dhi, rt)
        assert rt.is_on("BATT_HTR") is False


# ══════════════════════════════════════════════════════════════════════════════
# 5. QI(node)=... との加算テスト
# ══════════════════════════════════════════════════════════════════════════════

class TestQIAndHeaterAdditive:
    """既存の QI 値にヒータ電力が加算されることを確認。"""

    def test_heater_adds_to_qi_value(self):
        """dynamic_heat_input に既存値がある場合、ヒータ電力が加算されること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 270.0  # ON 条件
        dhi = {"MAIN.20": 5.0}  # QI(20)=5.0 から設定済みと仮定
        rt = controller.initialize_states()
        controller.apply(model.nodes, dhi, rt)
        assert abs(dhi["MAIN.20"] - 13.0) < 1e-9  # 5.0 + 8.0 = 13.0

    def test_heater_off_does_not_change_qi_value(self):
        """OFF のとき既存 QI 値は変更されないこと。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 279.0  # OFF 条件
        dhi = {"MAIN.20": 5.0}
        rt = HeaterRuntimeState()
        rt.set_state("BATT_HTR", True)  # 前状態 ON だが、温度が off_temp 超え
        controller.apply(model.nodes, dhi, rt)
        assert abs(dhi["MAIN.20"] - 5.0) < 1e-9  # 変化なし


# ══════════════════════════════════════════════════════════════════════════════
# 6. 複数ヒータが同一ノードに加算されるテスト
# ══════════════════════════════════════════════════════════════════════════════

class TestMultipleHeatersOnSameNode:
    """同一 apply_node に複数ヒータが向いている場合の合算テスト。"""

    def test_two_heaters_on_same_node_accumulate(self):
        """2つの ON ヒータの電力が合算されること。"""
        model = _make_model()
        h1 = HeaterData("H1", 20, 20, 273.15, 278.15, 8.0, submodel_path="MAIN")
        h2 = HeaterData("H2", 21, 20, 273.15, 278.15, 5.0, submodel_path="MAIN")
        model.heaters = [h1, h2]

        model.nodes["MAIN.20"]["T"] = 270.0  # sense for H1 → ON
        model.nodes["MAIN.21"]["T"] = 270.0  # sense for H2 → ON

        controller = HeaterController(model)
        rt = controller.initialize_states()
        dhi = {}
        controller.apply(model.nodes, dhi, rt)

        assert abs(dhi.get("MAIN.20", 0.0) - 13.0) < 1e-9  # 8.0 + 5.0

    def test_partial_on_accumulate(self):
        """1つ ON、1つ OFF のとき ON のみが加算されること。"""
        model = _make_model()
        h1 = HeaterData("H1", 20, 20, 273.15, 278.15, 8.0, submodel_path="MAIN")
        h2 = HeaterData("H2", 21, 20, 273.15, 278.15, 5.0, submodel_path="MAIN")
        model.heaters = [h1, h2]

        model.nodes["MAIN.20"]["T"] = 270.0  # H1 → ON
        model.nodes["MAIN.21"]["T"] = 280.0  # H2 → OFF

        controller = HeaterController(model)
        rt = HeaterRuntimeState()
        rt.set_state("H1", False)
        rt.set_state("H2", True)  # 前状態 ON だが、温度が off_temp 超え → OFF
        dhi = {}
        controller.apply(model.nodes, dhi, rt)

        assert abs(dhi.get("MAIN.20", 0.0) - 8.0) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# 7. enabled=False のスキップテスト
# ══════════════════════════════════════════════════════════════════════════════

class TestEnabledFalse:
    """enabled=False のヒータが制御ループでスキップされることを確認。"""

    def test_disabled_heater_not_applied(self):
        """enabled=False のヒータは ON 条件でも電力が加算されないこと。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0, enabled=False)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 270.0  # ON 条件
        dhi = {}
        rt = controller.initialize_states()
        controller.apply(model.nodes, dhi, rt)
        assert dhi.get("MAIN.20", 0.0) == 0.0

    def test_disabled_heater_mixed_with_enabled(self):
        """有効なヒータのみ電力が加算されること。"""
        model = _make_model()
        h_on = HeaterData("H_ON", 20, 20, 273.15, 278.15, 8.0, submodel_path="MAIN")
        h_off = HeaterData("H_DISABLED", 20, 20, 273.15, 278.15, 5.0,
                           enabled=False, submodel_path="MAIN")
        model.heaters = [h_on, h_off]
        model.nodes["MAIN.20"]["T"] = 270.0

        controller = HeaterController(model)
        rt = controller.initialize_states()
        dhi = {}
        controller.apply(model.nodes, dhi, rt)

        assert abs(dhi.get("MAIN.20", 0.0) - 8.0) < 1e-9  # disabled 分は加算されない


# ══════════════════════════════════════════════════════════════════════════════
# 8. HeaterRuntimeState のテスト
# ══════════════════════════════════════════════════════════════════════════════

class TestHeaterRuntimeState:
    """HeaterRuntimeState の基本動作テスト。"""

    def test_default_empty(self):
        """新規作成時は空状態であること。"""
        rt = HeaterRuntimeState()
        assert rt.states == {}

    def test_is_on_default_false(self):
        """未登録ヒータの is_on() はデフォルト False。"""
        rt = HeaterRuntimeState()
        assert rt.is_on("UNKNOWN") is False

    def test_is_on_custom_default(self):
        """is_on() のデフォルト値は指定可能。"""
        rt = HeaterRuntimeState()
        assert rt.is_on("UNKNOWN", default=True) is True

    def test_set_and_get_state(self):
        """set_state / is_on が正しく動作すること。"""
        rt = HeaterRuntimeState()
        rt.set_state("H1", True)
        assert rt.is_on("H1") is True
        rt.set_state("H1", False)
        assert rt.is_on("H1") is False

    def test_multiple_heaters_independent(self):
        """複数ヒータの状態が独立して管理されること。"""
        rt = HeaterRuntimeState()
        rt.set_state("H1", True)
        rt.set_state("H2", False)
        assert rt.is_on("H1") is True
        assert rt.is_on("H2") is False


# ══════════════════════════════════════════════════════════════════════════════
# 9. ノード解決テスト
# ══════════════════════════════════════════════════════════════════════════════

class TestNodeResolution:
    """HeaterController._resolve_node_label() のテスト。"""

    def test_resolve_with_submodel_path(self):
        """submodel_path + node_id でラベルを解決できること。"""
        h = _make_heater(sense_node=20, apply_node=20, submodel_path="MAIN")
        model, controller = _make_controller([h])
        assert controller._sense_labels["BATT_HTR"] == "MAIN.20"
        assert controller._apply_labels["BATT_HTR"] == "MAIN.20"

    def test_resolve_different_sense_and_apply(self):
        """sense_node と apply_node が異なる場合も正しく解決されること。"""
        model = _make_model()
        h = HeaterData("H", 20, 30, 273.15, 278.15, 5.0, submodel_path="MAIN")
        model.heaters = [h]
        controller = HeaterController(model)
        assert controller._sense_labels["H"] == "MAIN.20"
        assert controller._apply_labels["H"] == "MAIN.30"

    def test_resolve_missing_node_raises(self):
        """存在しないノード番号を持つヒータは ValueError。"""
        model = _make_model()
        h = HeaterData("H", 999, 999, 273.15, 278.15, 5.0, submodel_path="MAIN")
        model.heaters = [h]
        try:
            HeaterController(model)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "999" in str(e)

    def test_resolve_ambiguous_node_raises(self):
        """複数グループで同じ番号が存在するとき ValueError（Ambiguous）。"""
        model = _make_model()
        model.nodes["SUB.20"] = {"T": 300.0, "C": 100.0}  # 重複する .20
        h = HeaterData("H", 20, 20, 273.15, 278.15, 5.0, submodel_path="")
        model.heaters = [h]
        try:
            HeaterController(model)
            assert False, "例外が上がるべき"
        except ValueError as e:
            assert "Ambiguous" in str(e)


# ══════════════════════════════════════════════════════════════════════════════
# 10. get_node_qsrc との統合テスト
# ══════════════════════════════════════════════════════════════════════════════

class TestHeaterWithGetNodeQsrc:
    """ヒータ制御後の dynamic_heat_input が get_node_qsrc で優先参照されることを確認。"""

    def test_heater_on_overrides_static(self):
        """ヒータ ON 後の dynamic_heat_input は静的 heat_input より優先されること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 270.0
        model.heat_input["MAIN.20"] = 2.0  # 静的定義

        dhi = {}
        rt = controller.initialize_states()
        controller.apply(model.nodes, dhi, rt)

        q = get_node_qsrc("MAIN.20", model.heat_input, model.heat_input_func, 0.0, dhi)
        assert abs(q - 8.0) < 1e-9  # dynamic が静的より優先

    def test_heater_off_falls_through_to_static(self):
        """ヒータ OFF のとき静的 heat_input が参照されること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 280.0  # OFF 条件
        model.heat_input["MAIN.20"] = 2.0

        rt = HeaterRuntimeState()
        rt.set_state("BATT_HTR", True)  # 前状態 ON
        dhi = {}
        controller.apply(model.nodes, dhi, rt)

        q = get_node_qsrc("MAIN.20", model.heat_input, model.heat_input_func, 0.0, dhi)
        assert abs(q - 2.0) < 1e-9  # 静的値を使用

    def test_qi_plus_heater_via_get_node_qsrc(self):
        """QI + ヒータの合算値が get_node_qsrc で返されること。"""
        h = _make_heater(on_temp=273.15, off_temp=278.15, heater_power=8.0)
        model, controller = _make_controller([h])
        model.nodes["MAIN.20"]["T"] = 270.0

        dhi = {"MAIN.20": 5.0}  # QI(20)=5.0
        rt = controller.initialize_states()
        controller.apply(model.nodes, dhi, rt)  # adds 8.0

        q = get_node_qsrc("MAIN.20", {}, {}, 0.0, dhi)
        assert abs(q - 13.0) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# スタンドアロン実行
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_classes = [
        TestHeaterDataValidation,
        TestParseHeaterSection,
        TestInitializeStates,
        TestHeaterControl,
        TestQIAndHeaterAdditive,
        TestMultipleHeatersOnSameNode,
        TestEnabledFalse,
        TestHeaterRuntimeState,
        TestNodeResolution,
        TestHeaterWithGetNodeQsrc,
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
                import traceback
                traceback.print_exc()
                failed += 1

    print(f"\n{'='*60}")
    print(f"  合計: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    if failed:
        sys.exit(1)
