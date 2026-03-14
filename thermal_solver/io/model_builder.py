"""パース済みセクション辞書から AnalysisConfig + ThermalModel を構築する。

orbitherm_main.py（旧: thermal_main_mp.py）の main() 内にあったセクション解析ブロックを抽出。
入力エラーは ValueError を送出する（呼び出し元で catch して適切に処理すること）。
"""
from __future__ import annotations

import re
import sys
from typing import Any

import numpy as np

from ..model.config import AnalysisConfig
from ..model.thermal_model import ThermalModel
from .input_parser import (
    parse_array_section,
    parse_heater_section,
    parse_variables0_section,
    safe_eval,
)

# 輻射計算用空間ノード名（common.py と同じ定数）
_SPACE_NODE_NUMBER = 9999
_SPACE_NODE_NAME = "SPACE.9999"


def _line_iter(section_lines: list) -> Any:
    """section_lines の各要素を (行番号, 行文字列) のタプルに正規化して yield する。"""
    for item in section_lines:
        if isinstance(item, tuple) and len(item) == 2:
            yield item[0], item[1]
        else:
            yield 0, item if isinstance(item, str) else str(item)


def build_model(
    sections: dict,
    input_filename: str,
) -> tuple[AnalysisConfig, ThermalModel]:
    """パース済みセクション辞書から AnalysisConfig と ThermalModel を構築して返す。

    Parameters
    ----------
    sections: parse_header_input() の戻り値
    input_filename: エラーメッセージ用の入力ファイルパス

    Returns
    -------
    (AnalysisConfig, ThermalModel)

    Raises
    ------
    ValueError: 入力データに不正がある場合
    SystemExit: 互換のため致命的エラーでは sys.exit(1) を呼ぶ場合あり
    """
    config = AnalysisConfig()
    model = ThermalModel()

    # ── OPTIONS DATA / CONTROL DATA ───────────────────────────────────────────
    for key, lines in sections.items():
        if key.startswith("OPTIONS DATA"):
            for _ln, l in _line_iter(lines):
                if l.upper().startswith("OUTPUT.DQ"):
                    config.output_dq = "TRUE" in l.upper()
                elif l.upper().startswith("OUTPUT.GRAPH"):
                    config.output_graph = "TRUE" in l.upper()

        if key.startswith("CONTROL DATA"):
            for _ln, l in _line_iter(lines):
                lu = l.upper()
                if "TIMESTART" in lu:
                    config.time_start = safe_eval(l.split("=")[1])
                elif "TIMEND" in lu:
                    config.time_end = safe_eval(l.split("=")[1])
                elif re.search(r"(^|,)\s*DT\s*=", lu):
                    config.dt = safe_eval(l.split("DT")[1].split("=")[1].split(",")[0])
                elif "TIME_STEP" in lu:
                    config.delta_t = safe_eval(l.split("=")[1])
                elif "STEFAN_BOLTZMANN" in lu:
                    config.sigma = safe_eval(l.split("=")[1])
                elif "ANALYSIS" in lu:
                    val = l.split("=")[1].strip().upper()
                    if val in ("STEADY", "STEADY-STATE", "定常"):
                        config.analysis_type = "STEADY"
                    elif val in ("STEADY_THEN_TRANSIENT", "STEADY_TRANSIENT", "定常のち過渡"):
                        config.analysis_type = "STEADY_THEN_TRANSIENT"
                    else:
                        config.analysis_type = "TRANSIENT"
                elif "STEADY_SOLVER" in lu:
                    val = l.split("=")[1].strip().upper()
                    config.steady_solver = "CNFRW" if val == "CNFRW" else "PICARD"
                elif "TRANSIENT_METHOD" in lu:
                    val = l.split("=")[1].strip().upper()
                    if val in ("CRANK_NICOLSON", "CRANK", "CN"):
                        config.transient_method = "CRANK_NICOLSON"
                    elif val in ("BACKWARD", "BACKWARD_DIFFERENCING", "IMPLICIT"):
                        config.transient_method = "BACKWARD"
                    else:
                        config.transient_method = "EXPLICIT"
                elif "SAVE_FINAL_TEMPERATURE" in lu:
                    val = l.split("=", 1)[1].strip()
                    if val.upper() == "TRUE":
                        config.save_final_temperature = True
                    elif val:
                        config.save_final_temperature = val
                elif "INITIAL_TEMPERATURE_FILE" in lu:
                    val = l.split("=", 1)[1].strip()
                    if val:
                        config.initial_temperature_file = val

    # ── NODE DATA ──────────────────────────────────────────────────────────────
    for key, lines in sections.items():
        if not key.startswith("NODE DATA"):
            continue
        group = key.split(":")[1] if ":" in key else "GLOBAL"
        for line_no, l in _line_iter(lines):
            parts = [x.strip() for x in l.split(",")]
            if len(parts) < 3:
                continue
            raw_num = parts[0].strip()
            temp_val = safe_eval(parts[1])
            if temp_val is None:
                print(
                    f"エラー: ノードデータの温度が数値ではありません。"
                    f"入力ファイル {input_filename} の {line_no} 行目: {l}"
                )
                sys.exit(1)
            c_val = parts[2].strip().lower()

            # 境界節点判定:
            #   1列目が負の数値 → 絶対値をノード番号として使う
            #   3列目に "bound" を含む文字列 → キーワード指定
            is_boundary_by_sign = raw_num.startswith("-") and raw_num.lstrip("-").isdigit()
            is_boundary_by_keyword = "bound" in c_val
            node_id_str = raw_num.lstrip("-") if is_boundary_by_sign else raw_num
            label = f"{group}.{node_id_str}"

            if is_boundary_by_sign or is_boundary_by_keyword:
                model.nodes[label] = {"T": temp_val + 273.0, "C": None}
                model.boundary_nodes.add(label)
            else:
                cap = safe_eval(parts[2])
                if cap is None:
                    print(
                        f"エラー: ノードデータの熱容量が数値ではありません。"
                        f"入力ファイル {input_filename} の {line_no} 行目: {l}"
                    )
                    sys.exit(1)
                if cap < 0:
                    model.arithmetic_nodes.add(label)
                    model.nodes[label] = {"T": temp_val + 273.0, "C": 0.0}
                else:
                    model.nodes[label] = {"T": temp_val + 273.0, "C": cap}
            model.node_groups[label] = group

    # ── CONDUCTOR DATA ─────────────────────────────────────────────────────────
    cond_line_no: dict[tuple, int] = {}
    for key, lines in sections.items():
        if not key.startswith("CONDUCTOR DATA"):
            continue
        group = key.split(":")[1] if ":" in key else "GLOBAL"
        for line_no, l in _line_iter(lines):
            parts = [x.strip() for x in l.split(",")]
            if group == "GLOBAL":
                n1 = parts[1].strip()
                n2 = parts[2].strip()
            else:
                n1 = parts[1].strip() if "." in parts[1].strip() else f"{group}.{parts[1]}"
                n2 = parts[2].strip() if "." in parts[2].strip() else f"{group}.{parts[2]}"
            r_val = safe_eval(parts[3])
            if r_val is None:
                print(
                    f"エラー: コンダクタンス値が数値ではありません。"
                    f"入力ファイル {input_filename} の {line_no} 行目: {l}"
                )
                sys.exit(1)
            model.conductance[(n1, n2)] = r_val
            cond_line_no[(n1, n2)] = line_no
            if parts[0].strip().startswith("-"):
                model.radiation_conductors.add((n1, n2))

    # 空間ノード "9999" → "SPACE.9999" に統一
    _cond_new: dict = {}
    _rad_new: set = set()
    _cond_line_no_new: dict = {}
    for (n1, n2), r in model.conductance.items():
        n1n = _SPACE_NODE_NAME if (n1 == "9999" or n1 == str(_SPACE_NODE_NUMBER)) else n1
        n2n = _SPACE_NODE_NAME if (n2 == "9999" or n2 == str(_SPACE_NODE_NUMBER)) else n2
        _cond_new[(n1n, n2n)] = r
        _cond_line_no_new[(n1n, n2n)] = cond_line_no.get((n1, n2), 0)
        if (n1, n2) in model.radiation_conductors:
            _rad_new.add((n1n, n2n))
    model.conductance = _cond_new
    cond_line_no = _cond_line_no_new
    model.radiation_conductors = _rad_new

    # SPACE ノードが conductance に使われているが nodes に未定義なら追加
    if _SPACE_NODE_NAME not in model.nodes and any(
        _SPACE_NODE_NAME in (n1, n2) for n1, n2 in model.conductance
    ):
        model.nodes[_SPACE_NODE_NAME] = {"T": 3.0, "C": 0.0}
        model.node_groups[_SPACE_NODE_NAME] = "SPACE"

    # ── SOURCE DATA ────────────────────────────────────────────────────────────
    for key, lines in sections.items():
        if not key.startswith("SOURCE DATA"):
            continue
        group = key.split(":")[1] if ":" in key else "GLOBAL"
        for line_no, l in _line_iter(lines):
            parts = [x.strip() for x in l.split(",")]
            node_num = parts[0]
            label = f"{group}.{node_num}"
            if len(parts) > 2 and parts[1].upper() == "ARRAY":
                method = "LINEAR"
                if len(parts) > 3 and parts[2].upper() in ("LINEAR", "STEP"):
                    method = parts[2].upper()
                pairs = re.findall(r"\(([^,]+),\s*([^)]+)\)", l)
                arr = []
                for t, v in pairs:
                    arr.append((safe_eval(t), safe_eval(v)))
                if not arr:
                    print(
                        f"エラー: ARRAY定義で(時刻,値)ペアが見つかりません。"
                        f"入力ファイル {input_filename} の {line_no} 行目: {l}"
                    )
                    sys.exit(1)
                arr.sort()
                times, values = zip(*arr)
                model.heat_input_func[label] = (np.array(times), np.array(values), method)
            else:
                val = safe_eval(parts[1])
                if val is None:
                    print(
                        f"エラー: 熱源値が数値ではありません。"
                        f"入力ファイル {input_filename} の {line_no} 行目: {l}"
                    )
                    sys.exit(1)
                model.heat_input[label] = val

    # ── ノード参照エラーチェック ────────────────────────────────────────────────
    all_nodes = set(model.nodes.keys())
    for (n1, n2) in model.conductance.keys():
        if n1 not in all_nodes or n2 not in all_nodes:
            line_no = cond_line_no.get((n1, n2), 0)
            loc = f" 入力ファイル {input_filename} の {line_no} 行目付近。" if line_no else ""
            print(f"エラー: コンダクタンスノード {n1} または {n2} が未定義。{loc}")
            sys.exit(1)

    # ── ARRAY DATA ─────────────────────────────────────────────────────────────
    # HEADER ARRAY DATA セクション → ArrayData リストとして model.arrays に格納
    # ArrayRegistry の構築は ThermalModel.build_array_registry() または
    # run_case() 側で行う（build_model はデータ構築のみ担当）
    for key, lines in sections.items():
        if not key.startswith("ARRAY DATA"):
            continue
        submodel = key.split(":")[1] if ":" in key else ""
        try:
            arrays = parse_array_section(lines, submodel_path=submodel)
        except ValueError as e:
            print(
                f"エラー: ARRAY DATA パースに失敗しました。"
                f"入力ファイル {input_filename}: {e}"
            )
            sys.exit(1)
        model.arrays.extend(arrays)

    # ── VARIABLES 0 ────────────────────────────────────────────────────────────
    # HEADER VARIABLES 0 セクション → Variables0Assignment リストとして格納
    # 実行は run_case() または solvers 側で Variables0Executor.execute() を呼ぶ
    # 将来: サブモデルごとに分けた変数スコープを実装する場合は submodel を使う
    for key, lines in sections.items():
        if not key.startswith("VARIABLES 0"):
            continue
        submodel = key.split(":")[1] if ":" in key else ""
        try:
            assignments = parse_variables0_section(lines, submodel_path=submodel)
        except ValueError as e:
            print(
                f"エラー: VARIABLES 0 パースに失敗しました。"
                f"入力ファイル {input_filename}: {e}"
            )
            sys.exit(1)
        model.variables0_assignments.extend(assignments)

    # ── HEATER DATA ────────────────────────────────────────────────────────────
    # HEADER HEATER DATA セクション → HeaterData リストとして model.heaters に格納
    # ON/OFF 制御の実行は HeaterController（runtime パッケージ）が担当する
    for key, lines in sections.items():
        if not key.startswith("HEATER DATA"):
            continue
        submodel = key.split(":")[1] if ":" in key else ""
        try:
            heaters = parse_heater_section(lines, submodel_path=submodel)
        except ValueError as e:
            print(
                f"エラー: HEATER DATA パースに失敗しました。"
                f"入力ファイル {input_filename}: {e}"
            )
            sys.exit(1)
        model.heaters.extend(heaters)

    return config, model
