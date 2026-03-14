"""陰解法ステップ計算モジュール。

BACKWARD 差分法と CRANK-NICOLSON 法の1ステップ更新を提供する。
"""
from __future__ import annotations

import numpy as np

from .common import get_node_qsrc


def build_Qnet_and_J(
    nodes: dict,
    unknown_list: list[str],
    node_to_idx: dict[str, int],
    boundary_nodes: set[str],
    conductance: dict[tuple, float],
    radiation_conductors: set[tuple],
    heat_input: dict[str, float],
    heat_input_func: dict[str, tuple],
    current_time: float,
    sigma: float,
    dynamic_heat_input: dict[str, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """未知節点の熱収支ベクトル Q と ヤコビアン J を構築する。

    Q_net_i = 節点 i への正味熱流入 [W]

    Returns
    -------
    (Q, J): 各サイズ n_unk の ndarray
    """
    n_unk = len(unknown_list)
    T_MAX_RAD, T_MIN_RAD = 5000.0, 1.0
    Q = np.zeros(n_unk)
    J = np.zeros((n_unk, n_unk))

    for i, ni in enumerate(unknown_list):
        q_src = get_node_qsrc(ni, heat_input, heat_input_func, current_time, dynamic_heat_input)
        Q[i] = q_src
        for (n1, n2), r in conductance.items():
            t1 = max(T_MIN_RAD, min(T_MAX_RAD, float(nodes[n1]["T"])))
            t2 = max(T_MIN_RAD, min(T_MAX_RAD, float(nodes[n2]["T"])))
            if n1 == ni:
                other = n2
                sign = -1
            elif n2 == ni:
                other = n1
                sign = 1
            else:
                continue
            if (n1, n2) in radiation_conductors:
                q = r * sigma * (t1**4 - t2**4)
                Q[i] += sign * q
                dq_dt1 = r * sigma * 4.0 * (t1**3)
                dq_dt2 = -r * sigma * 4.0 * (t2**3)
                if ni == n1:
                    J[i, i] += -dq_dt1
                    if other in node_to_idx:
                        J[i, node_to_idx[other]] += dq_dt2
                else:
                    if other in node_to_idx:
                        J[i, node_to_idx[other]] += dq_dt1
                    J[i, i] += -dq_dt2
            else:
                q = r * (t1 - t2)
                Q[i] += sign * q
                J[i, i] += -r
                if other in node_to_idx:
                    J[i, node_to_idx[other]] += r

    return Q, J


def step_implicit(
    nodes: dict,
    unknown_list: list[str],
    node_to_idx: dict[str, int],
    boundary_nodes: set[str],
    conductance: dict[tuple, float],
    radiation_conductors: set[tuple],
    heat_input: dict[str, float],
    heat_input_func: dict[str, tuple],
    current_time: float,
    delta_t: float,
    sigma: float,
    method: str = "BACKWARD",
    dynamic_heat_input: dict[str, float] | None = None,
) -> dict:
    """陰解法で1タイムステップ更新する。

    BACKWARD（後退差分）または CRANK_NICOLSON を指定可能。

    線形システム: M*T^{n+1} = RHS
      通常節点: M = (C/dt)*I - theta*J,  RHS = (C/dt)*T^n + Q - theta*J*T^n
      算術節点(C=0): M = J,               RHS = J*T^n - Q

    Returns
    -------
    dict: 節点温度を更新した nodes（失敗時は変更なし）
    """
    n_unk = len(unknown_list)
    C_diag = np.array(
        [nodes[n]["C"] if nodes[n]["C"] and nodes[n]["C"] > 0 else 0.0 for n in unknown_list]
    )
    Q, J = build_Qnet_and_J(
        nodes, unknown_list, node_to_idx, boundary_nodes,
        conductance, radiation_conductors,
        heat_input, heat_input_func, current_time, sigma,
        dynamic_heat_input=dynamic_heat_input,
    )
    T_vec = np.array([nodes[n]["T"] for n in unknown_list])
    theta = 1.0 if method == "BACKWARD" else 0.5

    M = np.diag(np.maximum(C_diag, 0.0) / delta_t) - theta * J
    RHS = np.zeros(n_unk)
    for i in range(n_unk):
        if C_diag[i] > 0:
            RHS[i] = (C_diag[i] / delta_t) * T_vec[i] + Q[i] - theta * np.dot(J[i, :], T_vec)
        else:
            M[i, :] = J[i, :]
            RHS[i] = np.dot(J[i, :], T_vec) - Q[i]

    try:
        T_new = np.linalg.solve(M, RHS)
    except np.linalg.LinAlgError:
        return nodes

    T_new = np.clip(T_new, 1.0, 5000.0)
    for i, n in enumerate(unknown_list):
        nodes[n] = {"T": float(T_new[i]), "C": nodes[n]["C"]}
    return nodes
