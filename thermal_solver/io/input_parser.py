"""入力ファイル（.inp）のパース処理。

orbitherm_main.py（旧: thermal_main_mp.py）から抽出した parse_header_input / safe_eval /
load_initial_temperature_file をここに集約する。

追加機能:
  - parse_array_section()     : HEADER ARRAY DATA → list[ArrayData]
  - parse_variables0_section(): HEADER VARIABLES 0 → list[Variables0Assignment]
  - parse_heater_section()    : HEADER HEATER DATA → list[HeaterData]
"""
from __future__ import annotations

import ast
import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..model.array_data import ArrayData
    from ..model.heater import HeaterData
    from ..model.variables0 import Variables0Assignment

# VARIABLES 0 代入文の正規表現: 先頭が識別子、"=" で左右分割
_VARS0_ASSIGN_RE = re.compile(r"^([A-Za-z_]\w*)\s*=\s*(.+)$")


def parse_header_input(filename: str) -> dict[str, list[tuple[int, str]]]:
    """HEADER セクション単位で .inp ファイルを解析し辞書として返す。

    Returns
    -------
    dict: キーは "SECTION NAME" または "SECTION NAME:SUBNAME"、
          値は (行番号, 行文字列) のリスト。
    """
    sections: dict[str, list] = {}
    section: Optional[str] = None
    subname: Optional[str] = None

    with open(filename, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.rstrip()
            if not line:
                continue
            if line.lstrip().startswith("#"):
                continue
            line = line.split("#")[0].strip()
            if not line:
                continue
            if line.upper().startswith("END OF DATA"):
                break
            if line.upper().startswith("HEADER"):
                m = re.match(r"HEADER\s+(.+?)(?:,|$)", line, re.IGNORECASE)
                section = m.group(1).strip().upper() if m else None
                sub_match = re.search(r",\s*(\S+)", line)
                subname = sub_match.group(1).strip() if sub_match else None
                key = section if not subname else f"{section}:{subname}"
                if key not in sections:
                    sections[key] = []
                continue
            key = section if not subname else f"{section}:{subname}"
            if key:
                sections.setdefault(key, []).append((line_no, line))

    return sections


def safe_eval(expr: str) -> float:
    """文字列式を安全に float へ変換する。

    ast.literal_eval を試み、失敗時は組み込みなし eval にフォールバック。
    """
    try:
        return float(ast.literal_eval(expr))
    except Exception:
        try:
            return float(eval(expr, {"__builtins__": {}}, {}))
        except Exception:
            return float(expr)


def parse_array_section(
    lines: list[tuple[int, str]],
    submodel_path: str = "",
) -> list["ArrayData"]:
    """HEADER ARRAY DATA セクションの (line_no, text) リストを ArrayData リストに変換する。

    対応書式:
        doublet: NAME, x0, y0, x1, y1, ...
        doublet (外挿指定): NAME, EXTRAP=LINEAR, x0, y0, x1, y1, ...
        singlet: NAME, S, v0, v1, v2, ...

    Parameters
    ----------
    lines: parse_header_input() が返す (行番号, 行文字列) のリスト
    submodel_path: 登録時のサブモデルパス（省略可）

    Returns
    -------
    list[ArrayData]

    Raises
    ------
    ValueError: 構文エラーや数値変換エラー時（行番号付きメッセージ）
    """
    from ..model.array_data import ArrayData

    result: list[ArrayData] = []

    for line_no, text in lines:
        text = text.strip()
        if not text:
            continue

        parts = [p.strip() for p in text.split(",")]

        # 配列名の取得
        name = parts[0].strip()
        if not name:
            raise ValueError(f"Line {line_no}: ARRAY DATA entry has no name")

        remaining = parts[1:]

        # ── singlet 判定 ─────────────────────────────────────────────────
        if remaining and remaining[0].upper() == "S":
            value_strs = remaining[1:]
            if not value_strs:
                raise ValueError(
                    f"Line {line_no}: invalid singlet array {name!r}: "
                    f"値が1つも指定されていません。"
                )
            try:
                values = [safe_eval(v) for v in value_strs]
            except Exception as e:
                raise ValueError(
                    f"Line {line_no}: invalid singlet array {name!r}: "
                    f"数値変換エラー: {e}"
                ) from e
            try:
                arr = ArrayData.from_singlet(
                    name=name,
                    values=values,
                    submodel_path=submodel_path,
                )
            except ValueError as e:
                raise ValueError(
                    f"Line {line_no}: invalid singlet array {name!r}: {e}"
                ) from e
            result.append(arr)
            continue

        # ── doublet 解析 ─────────────────────────────────────────────────
        extrap = "clamp"
        flat_values: list[float] = []

        for part in remaining:
            pu = part.strip().upper()
            if pu.startswith("EXTRAP="):
                extrap = part.strip().split("=", 1)[1].strip().lower()
            elif part.strip():
                try:
                    flat_values.append(safe_eval(part.strip()))
                except Exception as e:
                    raise ValueError(
                        f"Line {line_no}: invalid doublet array {name!r}: "
                        f"非数値トークン {part.strip()!r}: {e}"
                    ) from e

        if len(flat_values) % 2 != 0:
            raise ValueError(
                f"Line {line_no}: invalid doublet array {name!r}: "
                f"odd number of values ({len(flat_values)}個)。"
                f"(x,y) ペアは偶数個必要です。"
            )

        try:
            arr = ArrayData.from_flat_doublet(
                name=name,
                flat_values=flat_values,
                extrapolation=extrap,
                submodel_path=submodel_path,
            )
        except ValueError as e:
            raise ValueError(
                f"Line {line_no}: invalid doublet array {name!r}: {e}"
            ) from e

        result.append(arr)

    return result


def parse_variables0_section(
    lines: list[tuple[int, str]],
    submodel_path: str = "",
) -> list["Variables0Assignment"]:
    """HEADER VARIABLES 0 セクションの (line_no, text) リストを
    Variables0Assignment リストに変換する。

    対応書式:
        VARNAME = 式
        例: QEXT = ARR("SOLAR_HEAT", TIME)
            MODE_PWR = ARRI("POWER_MODE", 1)
            QTOTAL = QEXT + MODE_PWR

    処理仕様:
        - 空行・コメント行を無視
        - 最初の "=" で左右を分割
        - lhs は識別子（[A-Za-z_][\\w]*）
        - rhs は任意の式文字列

    Parameters
    ----------
    lines: parse_header_input() が返す (行番号, 行文字列) のリスト
    submodel_path: 各 assignment のサブモデルパス（省略可）

    Returns
    -------
    list[Variables0Assignment]

    Raises
    ------
    ValueError: 構文エラー時（行番号付きメッセージ）
    """
    from ..model.variables0 import Variables0Assignment

    result: list[Variables0Assignment] = []

    for line_no, text in lines:
        text = text.strip()
        if not text:
            continue

        m = _VARS0_ASSIGN_RE.match(text)
        if not m:
            raise ValueError(
                f"Line {line_no}: invalid VARIABLES 0 assignment: {text!r}\n"
                f"  期待形式: VARNAME = 式"
            )

        target = m.group(1).strip()
        expression = m.group(2).strip()

        if not target:
            raise ValueError(
                f"Line {line_no}: missing target in VARIABLES 0 assignment"
            )
        if not expression:
            raise ValueError(
                f"Line {line_no}: missing expression in VARIABLES 0 assignment"
            )

        result.append(
            Variables0Assignment(
                target=target,
                expression=expression,
                submodel_path=submodel_path,
            )
        )

    return result


def parse_heater_section(
    lines: list[tuple[int, str]],
    submodel_path: str = "",
) -> list["HeaterData"]:
    """HEADER HEATER DATA セクションの (line_no, text) リストを HeaterData リストに変換する。

    対応書式:
        NAME, SENSE=n, APPLY=n, ON=t, OFF=t, POWER=w [, INIT=ON|OFF] [, ENABLED=YES|NO]

    例:
        BATT_HTR, SENSE=20, APPLY=20, ON=273.15, OFF=278.15, POWER=8.0
        AVIONICS_HTR, SENSE=31, APPLY=35, ON=268.15, OFF=272.15, POWER=4.5, INIT=ON

    フィールド仕様:
        必須: SENSE (int), APPLY (int), ON (float), OFF (float), POWER (float)
        任意: INIT=ON|OFF (デフォルト OFF), ENABLED=YES|NO (デフォルト YES)

    Parameters
    ----------
    lines: parse_header_input() が返す (行番号, 行文字列) のリスト
    submodel_path: 各 HeaterData のサブモデルパス（省略可）

    Returns
    -------
    list[HeaterData]

    Raises
    ------
    ValueError: 構文エラー・必須キー不足・数値変換エラー・off_temp < on_temp 等
                いずれも行番号付きメッセージ

    将来拡張:
        PROPORTIONAL_BAND=, DUTY_RATIO= などのキーを追加する場合は
        _HEATER_OPTIONAL_KEYS に追加し、HeaterData のフィールドに対応させる。
    """
    from ..model.heater import HeaterData

    _REQUIRED_KEYS = frozenset({"SENSE", "APPLY", "ON", "OFF", "POWER"})

    result: list[HeaterData] = []

    for line_no, raw in lines:
        text = raw.strip()
        if not text:
            continue

        parts = [p.strip() for p in text.split(",")]

        # ── ヒータ名の取得 ───────────────────────────────────────────────────
        name = parts[0].strip()
        if not name:
            raise ValueError(
                f"Line {line_no}: HEATER DATA entry has no name"
            )

        # ── key=value 辞書を構築 ─────────────────────────────────────────────
        kv: dict[str, str] = {}
        for part in parts[1:]:
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                k, v = part.split("=", 1)
                kv[k.strip().upper()] = v.strip()
            else:
                raise ValueError(
                    f"Line {line_no}: heater {name!r} has unexpected token {part!r}. "
                    f"Expected KEY=VALUE format."
                )

        # ── 必須キーチェック ─────────────────────────────────────────────────
        missing = _REQUIRED_KEYS - kv.keys()
        if missing:
            first_missing = sorted(missing)[0]
            raise ValueError(
                f"Line {line_no}: heater {name!r} missing required key {first_missing!r}. "
                f"Required keys: {sorted(_REQUIRED_KEYS)}"
            )

        # ── SENSE / APPLY: 整数 ──────────────────────────────────────────────
        try:
            sense_node = int(kv["SENSE"])
        except ValueError:
            raise ValueError(
                f"Line {line_no}: heater {name!r} has invalid SENSE value: {kv['SENSE']!r}. "
                f"Expected integer node id."
            )
        try:
            apply_node = int(kv["APPLY"])
        except ValueError:
            raise ValueError(
                f"Line {line_no}: heater {name!r} has invalid APPLY value: {kv['APPLY']!r}. "
                f"Expected integer node id."
            )

        # ── ON / OFF / POWER: 浮動小数点数 ──────────────────────────────────
        try:
            on_temp = float(kv["ON"])
        except ValueError:
            raise ValueError(
                f"Line {line_no}: heater {name!r} has invalid ON value: {kv['ON']!r}."
            )
        try:
            off_temp = float(kv["OFF"])
        except ValueError:
            raise ValueError(
                f"Line {line_no}: heater {name!r} has invalid OFF value: {kv['OFF']!r}."
            )
        try:
            heater_power = float(kv["POWER"])
        except ValueError:
            raise ValueError(
                f"Line {line_no}: heater {name!r} has invalid POWER value: {kv['POWER']!r}."
            )

        # off_temp >= on_temp の事前チェック（HeaterData でも検証されるが行番号付きで出す）
        if off_temp < on_temp:
            raise ValueError(
                f"Line {line_no}: heater {name!r} requires OFF >= ON. "
                f"Got ON={on_temp}, OFF={off_temp}."
            )

        # ── オプションキー ───────────────────────────────────────────────────
        initial_state = False
        if "INIT" in kv:
            val_up = kv["INIT"].upper()
            if val_up == "ON":
                initial_state = True
            elif val_up == "OFF":
                initial_state = False
            else:
                raise ValueError(
                    f"Line {line_no}: heater {name!r} has invalid INIT value: {kv['INIT']!r}. "
                    f"Expected ON or OFF."
                )

        enabled = True
        if "ENABLED" in kv:
            val_up = kv["ENABLED"].upper()
            if val_up in ("YES", "TRUE", "ON", "1"):
                enabled = True
            elif val_up in ("NO", "FALSE", "OFF", "0"):
                enabled = False
            else:
                raise ValueError(
                    f"Line {line_no}: heater {name!r} has invalid ENABLED value: {kv['ENABLED']!r}. "
                    f"Expected YES or NO."
                )

        result.append(HeaterData(
            name=name,
            sense_node=sense_node,
            apply_node=apply_node,
            on_temp=on_temp,
            off_temp=off_temp,
            heater_power=heater_power,
            initial_state=initial_state,
            enabled=enabled,
            submodel_path=submodel_path,
        ))

    return result


def load_initial_temperature_file(
    filepath: str,
    nodes: dict,
) -> Optional[int]:
    """初期温度 CSV（node,T_C）を読み込み、nodes の温度を上書きする。

    Parameters
    ----------
    filepath: CSV ファイルパス
    nodes: {"T": float, "C": float|None} 形式の節点辞書（in-place 更新）

    Returns
    -------
    int: 読み込んだ節点数。ファイルが空または失敗時は None。
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if not lines:
            return None
        count = 0
        start = 1 if (lines[0].upper().startswith("NODE") and "," in lines[0]) else 0
        for ln in lines[start:]:
            parts = [p.strip() for p in ln.split(",", 1)]
            if len(parts) < 2:
                continue
            node_name, t_str = parts[0], parts[1]
            if node_name not in nodes:
                continue
            try:
                t_c = float(t_str)
            except ValueError:
                continue
            nodes[node_name]["T"] = t_c + 273.0
            count += 1
        return count
    except Exception:
        return None
