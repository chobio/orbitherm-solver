"""定常解析ソルバー。

PICARD 法（輻射線形化反復）と CNFRW 法（ニュートン法）の2種類を提供する。
"""
from __future__ import annotations

import numpy as np

from .common import get_node_qsrc


def run_steady_analysis(
    nodes: dict,
    boundary_nodes: set[str],
    conductance: dict[tuple, float],
    radiation_conductors: set[tuple],
    heat_input: dict[str, float],
    heat_input_func: dict[str, tuple],
    sigma: float,
    tol: float = 1e-6,
    max_iter: int = 200,
) -> dict:
    """定常解析: PICARD 法。

    輻射を線形化して K*T=RHS を反復求解し、収束するまで繰り返す。
    収束しない場合は max_iter 回で打ち切り。

    Returns
    -------
    dict: 節点温度を更新した nodes
    """
    unknown_list = sorted([n for n in nodes if n not in boundary_nodes])
    if not unknown_list:
        return nodes

    n_unk = len(unknown_list)
    node_to_idx = {n: i for i, n in enumerate(unknown_list)}
    T_MAX_RAD, T_MIN_RAD = 5000.0, 1.0

    def _get_G_rad_lin(n1: str, n2: str, r: float) -> float | None:
        if (n1, n2) not in radiation_conductors:
            return None
        t1 = max(T_MIN_RAD, min(T_MAX_RAD, float(nodes[n1]["T"])))
        t2 = max(T_MIN_RAD, min(T_MAX_RAD, float(nodes[n2]["T"])))
        t_ref = max(T_MIN_RAD, min(T_MAX_RAD, (t1 + t2) / 2.0))
        return r * sigma * 4.0 * (t_ref**3)

    for _ in range(max_iter):
        K = np.zeros((n_unk, n_unk))
        RHS = np.zeros(n_unk)

        for i, ni in enumerate(unknown_list):
            q_src = get_node_qsrc(ni, heat_input, heat_input_func, 0.0)
            RHS[i] = q_src
            for (n1, n2), r in conductance.items():
                G = _get_G_rad_lin(n1, n2, r) if (n1, n2) in radiation_conductors else r
                if n1 == ni:
                    other = n2
                elif n2 == ni:
                    other = n1
                else:
                    continue
                if other in node_to_idx:
                    j = node_to_idx[other]
                    K[i, i] += G
                    K[i, j] -= G
                else:
                    K[i, i] += G
                    RHS[i] += G * nodes[other]["T"]

        try:
            T_new = np.linalg.solve(K, RHS)
        except np.linalg.LinAlgError:
            break

        T_old = np.array([nodes[unknown_list[i]]["T"] for i in range(n_unk)])
        err = np.max(np.abs(T_new - T_old))
        for i, n in enumerate(unknown_list):
            nodes[n] = {"T": float(T_new[i]), "C": nodes[n]["C"]}
        if err < tol:
            return nodes

    return nodes


def run_steady_cnfrw(
    nodes: dict,
    boundary_nodes: set[str],
    conductance: dict[tuple, float],
    radiation_conductors: set[tuple],
    heat_input: dict[str, float],
    heat_input_func: dict[str, tuple],
    sigma: float,
    tol: float = 1e-6,
    max_iter: int = 50,
) -> dict:
    """定常解析: CNFRW 法（Conjugate Newton Forward）。

    ニュートン法で残差 R(T)=0 を反復求解する。
    PICARD 法より収束が速いが、初期値依存に注意。

    Returns
    -------
    dict: 節点温度を更新した nodes
    """
    unknown_list = sorted([n for n in nodes if n not in boundary_nodes])
    if not unknown_list:
        return nodes

    n_unk = len(unknown_list)
    node_to_idx = {n: i for i, n in enumerate(unknown_list)}
    T_MAX_RAD, T_MIN_RAD = 5000.0, 1.0

    def _residual_and_jacobian(T_vec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        for i, n in enumerate(unknown_list):
            nodes[n] = {"T": float(T_vec[i]), "C": nodes[n]["C"]}
        R = np.zeros(n_unk)
        J = np.zeros((n_unk, n_unk))

        for i, ni in enumerate(unknown_list):
            q_src = get_node_qsrc(ni, heat_input, heat_input_func, 0.0)
            R[i] = q_src
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
                    R[i] += sign * q
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
                    R[i] += sign * q
                    J[i, i] += -r
                    if other in node_to_idx:
                        J[i, node_to_idx[other]] += r
        return R, J

    T_vec = np.array([nodes[n]["T"] for n in unknown_list])
    for _ in range(max_iter):
        R, J = _residual_and_jacobian(T_vec)
        err_abs = np.max(np.abs(R))
        try:
            dx = np.linalg.solve(J, -R)
        except np.linalg.LinAlgError:
            break
        T_vec = T_vec + dx
        T_vec = np.clip(T_vec, T_MIN_RAD, T_MAX_RAD)
        if np.max(np.abs(dx)) < tol or err_abs < tol:
            break

    for i, n in enumerate(unknown_list):
        nodes[n] = {"T": float(T_vec[i]), "C": nodes[n]["C"]}
    return nodes
