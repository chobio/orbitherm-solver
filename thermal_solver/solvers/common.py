"""ソルバー共通ユーティリティ。

ノード表示名変換・補間・熱源取得・出力スナップショット計算・プログレスバーを集約する。
"""
from __future__ import annotations

import sys
from typing import Any, Callable

import numpy as np

# 輻射計算用の空間ノード定数
SPACE_NODE_NUMBER: int = 9999
SPACE_NODE_NAME: str = "SPACE.9999"


def _node_display_name(node_name: str) -> str:
    """出力用ノード表示名。空間ノード "9999" を "SPACE.9999" に統一する。"""
    if node_name == "9999" or node_name == str(SPACE_NODE_NUMBER):
        return SPACE_NODE_NAME
    return node_name


def interpolate_array(
    times: np.ndarray,
    values: np.ndarray,
    t: float,
    method: str = "LINEAR",
) -> float:
    """時系列テーブルを補間して値を返す。

    Parameters
    ----------
    times: 時刻配列（昇順）
    values: 対応する値配列
    t: 補間したい時刻
    method: "LINEAR"（線形補間）または "STEP"（階段補間）
    """
    if t <= times[0]:
        return float(values[0])
    if t >= times[-1]:
        return float(values[-1])
    for i in range(1, len(times)):
        if t < times[i]:
            if method == "STEP":
                return float(values[i - 1])
            t0, t1 = times[i - 1], times[i]
            v0, v1 = values[i - 1], values[i]
            return float(v0 + (v1 - v0) * (t - t0) / (t1 - t0))
    return float(values[-1])


def get_node_qsrc(
    node: str,
    heat_input: dict[str, float],
    heat_input_func: dict[str, tuple],
    current_time: float,
    dynamic_heat_input: dict[str, float] | None = None,
) -> float:
    """ノードの熱源 [W] を取得する（定数または時刻補間）。

    参照優先順位:
      1. dynamic_heat_input[node]  ← VARIABLES 0 の QI(node)=... による動的値
      2. heat_input[node]          ← 静的な定数熱源
      3. heat_input_func[node]     ← 時系列テーブル補間
      4. 0.0                       ← デフォルト（熱源なし）

    Parameters
    ----------
    node: 節点ラベル
    heat_input: 静的定数熱源辞書
    heat_input_func: 時系列補間テーブル辞書
    current_time: 現在時刻 [s]
    dynamic_heat_input: VARIABLES 0 により設定された動的熱源（省略可）

    将来拡張:
      dynamic_heat_input が設定されているとき、heat_input_func より優先するか
      （加算するか）は設計判断が必要。現状は上書き（OR 優先）方式を採用。
    """
    if dynamic_heat_input is not None and node in dynamic_heat_input:
        return dynamic_heat_input[node]
    if node in heat_input:
        return heat_input[node]
    if node in heat_input_func:
        times, values, method = heat_input_func[node]
        return interpolate_array(times, values, current_time, method)
    return 0.0


def compute_output_snapshot(
    nodes: dict[str, dict],
    conductance: dict[tuple, float],
    heat_input: dict[str, float],
    heat_input_func: dict[str, tuple],
    current_time: float,
    radiation_conductors: set | None = None,
    sigma: float = 5.67e-8,
    dynamic_heat_input: dict[str, float] | None = None,
) -> tuple[dict, dict, dict]:
    """現在時刻の各ノード発熱・熱流量スナップショットを計算する。

    輻射は Q = R×σ×(T1^4−T2^4) [T:K]

    Parameters
    ----------
    dynamic_heat_input: VARIABLES 0 の QI(node) による動的熱源（省略可）
        get_node_qsrc() に渡して優先参照させる。

    Returns
    -------
    (qsrc, cond_flow, qnet):
        qsrc: {node: 熱源[W]}
        cond_flow: {(n1,n2): 熱流量[W]}
        qnet: {node: 正味熱流入[W]}
    """
    radiation_conductors = radiation_conductors or set()
    T_MAX_RAD, T_MIN_RAD = 5000.0, 1.0

    qsrc = {
        n: get_node_qsrc(n, heat_input, heat_input_func, current_time, dynamic_heat_input)
        for n in nodes
    }
    cond_flow: dict[tuple, float] = {}

    for (n1, n2), r in conductance.items():
        t1 = nodes[n1]["T"]
        t2 = nodes[n2]["T"]
        if (n1, n2) in radiation_conductors:
            t1s = max(T_MIN_RAD, min(T_MAX_RAD, float(t1)))
            t2s = max(T_MIN_RAD, min(T_MAX_RAD, float(t2)))
            q = r * sigma * (t1s**4 - t2s**4)
        else:
            q = r * (t1 - t2)
        cond_flow[(n1, n2)] = q

    qnet: dict[str, float] = {}
    for node in nodes:
        qnet[node] = qsrc[node]
        for (n1, n2), q in cond_flow.items():
            if node == n1:
                qnet[node] -= q
            elif node == n2:
                qnet[node] += q

    return qsrc, cond_flow, qnet


def record_snapshot(
    nodes: dict,
    current_time: float,
    conductance: dict,
    heat_input: dict,
    heat_input_func: dict,
    radiation_conductors: set,
    sigma: float,
    record_times: list[float],
    results: dict[str, list[float]],
    results_qsrc: dict[str, list[float]],
    results_qnet: dict[str, list[float]],
    results_cond_flow: dict[tuple, list[float]],
    dynamic_heat_input: dict[str, float] | None = None,
) -> None:
    """現在の節点状態を結果リストに追記する（in-place 更新）。

    Parameters
    ----------
    dynamic_heat_input: VARIABLES 0 の QI(node) による動的熱源（省略可）
        出力スナップショットに反映させるために compute_output_snapshot へ渡す。
    """
    record_times.append(round(current_time, 3))
    for node in results:
        results[node].append(round(nodes[node]["T"] - 273.0, 3))
    qsrc, cond_flow, qnet = compute_output_snapshot(
        nodes, conductance, heat_input, heat_input_func,
        current_time, radiation_conductors, sigma,
        dynamic_heat_input=dynamic_heat_input,
    )
    for node in results_qsrc:
        results_qsrc[node].append(round(qsrc[node], 6))
    for node in results_qnet:
        results_qnet[node].append(round(qnet[node], 6))
    for (n1, n2) in results_cond_flow:
        results_cond_flow[(n1, n2)].append(round(cond_flow[(n1, n2)], 6))


def print_progress_bar(
    iteration: int,
    total: int,
    elapsed: float,
    bar_length: int = 40,
) -> None:
    """コンソールにプログレスバーを上書き表示する。"""
    percent = "{0:.1f}".format(100 * (iteration / float(total)))
    filled_length = int(bar_length * iteration // total)
    bar = "#" * filled_length + "-" * (bar_length - filled_length)
    sys.stdout.write(
        f"\r計算進行状況 |{bar}| {percent}% ({iteration}/{total}) 経過時間: {elapsed:.1f}秒"
    )
    sys.stdout.flush()
