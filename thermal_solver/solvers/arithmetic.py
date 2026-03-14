"""算術節点（熱容量=0）の温度を熱収支方程式で求解するモジュール。"""
from __future__ import annotations

import numpy as np

from .common import get_node_qsrc


def solve_arithmetic_nodes(
    nodes: dict,
    arithmetic_nodes: set[str],
    conductance: dict[tuple, float],
    radiation_conductors: set[tuple] | None,
    heat_input: dict[str, float],
    heat_input_func: dict[str, tuple],
    current_time: float,
    sigma: float = 5.67e-8,
    dynamic_heat_input: dict[str, float] | None = None,
) -> dict:
    """算術節点の温度を熱収支=0 から連立方程式で求解する。

    輻射コンダクタンスは現在温度で線形化して計算する。
    算術節点がなければ nodes をそのまま返す。

    Returns
    -------
    dict: 算術節点温度を更新した nodes の新しい辞書
    """
    radiation_conductors = radiation_conductors or set()
    if not arithmetic_nodes:
        return nodes

    arith_list = sorted(arithmetic_nodes)
    n_arith = len(arith_list)
    node_to_idx = {n: i for i, n in enumerate(arith_list)}
    T_MAX_RAD, T_MIN_RAD = 5000.0, 1.0

    def _get_G(n1: str, n2: str, r: float) -> float:
        """輻射コンダクタンスを線形化して等価コンダクタンスを返す。"""
        if (n1, n2) in radiation_conductors:
            t1 = max(T_MIN_RAD, min(T_MAX_RAD, float(nodes[n1]["T"])))
            t2 = max(T_MIN_RAD, min(T_MAX_RAD, float(nodes[n2]["T"])))
            t_ref = max(T_MIN_RAD, min(T_MAX_RAD, (t1 + t2) / 2.0))
            return r * sigma * 4.0 * (t_ref**3)
        return r

    A = np.zeros((n_arith, n_arith))
    b = np.zeros(n_arith)

    for i, ni in enumerate(arith_list):
        q_src = get_node_qsrc(ni, heat_input, heat_input_func, current_time, dynamic_heat_input)
        b[i] = q_src
        for (n1, n2), r in conductance.items():
            G = _get_G(n1, n2, r)
            if ni == n1:
                other = n2
            elif ni == n2:
                other = n1
            else:
                continue
            if other in node_to_idx:
                j = node_to_idx[other]
                A[i, i] += G
                A[i, j] -= G
            else:
                A[i, i] += G
                b[i] += G * nodes[other]["T"]
        if A[i, i] <= 0:
            A[i, i] = 1.0

    try:
        T_arith = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return nodes

    new_nodes = dict(nodes)
    for i, n in enumerate(arith_list):
        new_nodes[n] = {"T": float(T_arith[i]), "C": nodes[n]["C"]}
    return new_nodes
