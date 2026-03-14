"""過渡解析ループモジュール。

陽解法（マルチプロセス並列）と陰解法（BACKWARD / CRANK_NICOLSON）の
タイムステップ実行を管理する。

Windows での multiprocessing.Pool 使用時は、このモジュールがトップレベルで
インポート可能であることが必要。node_update_task はモジュールレベルに定義する。
"""
from __future__ import annotations

import time
from multiprocessing import Pool, cpu_count
from typing import Callable

from ..model.config import AnalysisConfig
from ..model.thermal_model import ThermalModel
from .arithmetic import solve_arithmetic_nodes
from .common import interpolate_array, print_progress_bar
from .implicit import step_implicit


def node_update_task(args: tuple) -> tuple[str, float]:
    """陽解法の1節点・1ステップ温度更新タスク（Pool.map 用）。

    Pool.map から呼ばれるため、グローバルスコープに定義する必要がある。

    args の構成 (13要素):
      node, data, nodes, boundary_nodes, arithmetic_nodes,
      conductance, heat_input, heat_input_func,
      current_time, delta_t, radiation_conductors, sigma,
      dynamic_heat_input  ← VARIABLES 0 動的熱源 (dict or None)
    """
    (
        node, data, nodes, boundary_nodes, arithmetic_nodes,
        conductance, heat_input, heat_input_func,
        current_time, delta_t, radiation_conductors, sigma,
        dynamic_heat_input,
    ) = args

    radiation_conductors = radiation_conductors or set()
    arithmetic_nodes = arithmetic_nodes or set()
    T_new = data["T"]

    if node in boundary_nodes or node in arithmetic_nodes:
        return (node, T_new)

    T_MAX_RAD, T_MIN_RAD = 5000.0, 1.0
    dE = 0.0

    for (n1, n2), r in conductance.items():
        T_self = data["T"]
        if node == n1:
            T_other = nodes[n2]["T"]
        elif node == n2:
            T_other = nodes[n1]["T"]
        else:
            continue

        if (n1, n2) in radiation_conductors:
            # 時間積分安定化のため輻射を T_ref まわりで線形化
            # 出力の熱流量は compute_output_snapshot で Q=R×σ×(T1^4−T2^4) を使用
            T1_safe = max(T_MIN_RAD, min(T_MAX_RAD, float(T_self)))
            T2_safe = max(T_MIN_RAD, min(T_MAX_RAD, float(T_other)))
            T_ref = max(T_MIN_RAD, min(T_MAX_RAD, (T1_safe + T2_safe) / 2.0))
            k_lin = r * sigma * 4.0 * (T_ref**3)
            Q = k_lin * (T1_safe - T2_safe) if node == n1 else k_lin * (T2_safe - T1_safe)
        else:
            Q = (T_self - T_other) * r if node == n1 else (T_other - T_self) * r

        if node == n1:
            dE -= Q * delta_t
        else:
            dE += Q * delta_t

    # 熱源取得: dynamic_heat_input を静的値より優先する
    Qsrc = 0.0
    if dynamic_heat_input is not None and node in dynamic_heat_input:
        Qsrc = dynamic_heat_input[node]
    elif node in heat_input:
        Qsrc = heat_input[node]
    elif node in heat_input_func:
        times, values, method = heat_input_func[node]
        Qsrc = interpolate_array(times, values, current_time, method)
    dE += Qsrc * delta_t

    if data["C"] and data["C"] > 0:
        T_new = data["T"] + dE / data["C"]
    return (node, T_new)


# node_update_task が参照する sigma は args から渡す設計だが、
# 上記関数内で sigma を args から取り出せるよう、
# 実際の呼び出しでは args タプルの末尾に sigma を含める
# （orbitherm_main.py 互換のシグネチャを維持）

# ── ただし args に sigma が含まれない旧形式との互換のため、
# ── モジュールレベルで _sigma をキャッシュする仕組みは使わない。
# ── orbitherm_main.py の args_list 構築側で sigma を必ず渡すこと。


def run_transient_analysis(
    nodes: dict,
    model: ThermalModel,
    config: AnalysisConfig,
    on_output: Callable[[dict, float], None] | None = None,
    logger: Callable[[str], None] = print,
) -> tuple[dict, float]:
    """過渡解析ループを実行する。

    Parameters
    ----------
    nodes: 初期節点辞書（in-place 更新される）
    model: ThermalModel（conductance, boundary_nodes 等を参照）
    config: AnalysisConfig（時刻設定・解法を参照）
    on_output: 出力間隔ごとに呼ばれるコールバック (nodes, current_time) -> None
    logger: ログ出力 callable

    Returns
    -------
    (final_nodes, elapsed_seconds)
    """
    time_start = config.time_start
    time_end = config.time_end
    delta_t = config.delta_t
    dt = config.dt
    sigma = config.sigma
    transient_method = config.transient_method

    use_implicit = transient_method in ("CRANK_NICOLSON", "BACKWARD")
    total_steps = int((time_end - time_start) / delta_t)
    output_interval_steps = int(round(dt / delta_t))
    step_counter = 0
    current_time = time_start

    unknown_list = sorted([n for n in nodes if n not in model.boundary_nodes])
    node_to_idx = {n: i for i, n in enumerate(unknown_list)} if use_implicit else {}

    # ── VARIABLES 0 エクゼキュータの初期化 ───────────────────────────────────
    # model.variables0_assignments が空でない場合のみ Executor を作成する。
    # 各タイムステップの先頭で execute() を呼ぶことで dynamic_heat_input を更新する。
    # Executor は run_transient_analysis() 内で完結し、外部 API は変更しない（方式A）。
    _v0_executor = None
    if model.variables0_assignments:
        from ..runtime.variables0_executor import Variables0Executor
        _v0_registry = model.build_array_registry()
        _v0_executor = Variables0Executor(
            _v0_registry, submodel_path="", model=model
        )

    # ── ヒータコントローラの初期化 ───────────────────────────────────────────
    # model.heaters が空でない場合のみ HeaterController を作成する。
    # VARIABLES 0 の直後に apply() を呼ぶことで QI 値への加算を保証する。
    # コントローラはこの関数内で完結し、外部 API は変更しない（方式A と同様）。
    _heater_controller = None
    _heater_runtime = None
    if model.heaters:
        from ..runtime.heater_controller import HeaterController
        _heater_controller = HeaterController(model)
        _heater_runtime = _heater_controller.initialize_states()

    if use_implicit:
        logger(f"=== 過渡解析開始 ===  (全{total_steps}ステップ, 陰解法: {transient_method})\n")
        pool = None
    else:
        ncpu = cpu_count()
        pool = Pool(processes=ncpu)
        logger(f"=== 過渡解析開始 ===  (全{total_steps}ステップ, {ncpu}コア並列)\n")

    start_time = time.time()
    last_print = -1

    try:
        while current_time < time_end - 1e-8:
            # ── 動的熱入力フック（VARIABLES 0 → ヒータ制御）────────────────
            # 実行順序:
            #   1. dynamic_heat_input をクリア（VARIABLES 0 が担当、または明示的に）
            #   2. VARIABLES 0 で QI 値を設定
            #   3. ヒータ制御で上記 QI 値に電力を加算
            # この順序により: 最終値 = QI(node) + ヒータ電力 となる
            if _v0_executor is not None:
                # execute() の先頭で dynamic_heat_input.clear() が呼ばれる
                _v0_executor.execute(
                    model.variables0_assignments,
                    time_value=current_time,
                )
            elif _heater_controller is not None:
                # VARIABLES 0 なしでヒータのみの場合は明示的にクリア
                model.dynamic_heat_input.clear()

            if _heater_controller is not None:
                # QI 値（あれば）の上にヒータ電力を加算する
                _heater_runtime = _heater_controller.apply(
                    nodes, model.dynamic_heat_input, _heater_runtime
                )
            # ─────────────────────────────────────────────────────────────

            if use_implicit:
                nodes = step_implicit(
                    nodes, unknown_list, node_to_idx, model.boundary_nodes,
                    model.conductance, model.radiation_conductors,
                    model.heat_input, model.heat_input_func,
                    current_time, delta_t, sigma, method=transient_method,
                    dynamic_heat_input=model.dynamic_heat_input or None,
                )
            else:
                _dhi = model.dynamic_heat_input if model.dynamic_heat_input else None
                args_list = [
                    (
                        node, data, nodes,
                        model.boundary_nodes, model.arithmetic_nodes,
                        model.conductance, model.heat_input, model.heat_input_func,
                        current_time, delta_t, model.radiation_conductors, sigma,
                        _dhi,
                    )
                    for node, data in nodes.items()
                ]
                outlist = pool.map(node_update_task, args_list)
                new_nodes = {k: {"T": v, "C": nodes[k]["C"]} for k, v in outlist}
                new_nodes = solve_arithmetic_nodes(
                    new_nodes, model.arithmetic_nodes,
                    model.conductance, model.radiation_conductors,
                    model.heat_input, model.heat_input_func,
                    current_time, sigma,
                    dynamic_heat_input=_dhi,
                )
                nodes = new_nodes

            current_time += delta_t
            step_counter += 1
            now = int(100 * step_counter / total_steps)
            elapsed = time.time() - start_time
            if now != last_print and (now % 1 == 0 or current_time >= time_end - 1e-8):
                print_progress_bar(step_counter, total_steps, elapsed)
                last_print = now

            if (
                step_counter % output_interval_steps == 0
                or current_time >= time_end - 1e-8
            ):
                if on_output is not None:
                    on_output(nodes, current_time)
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    print()
    elapsed_total = time.time() - start_time
    logger(f"\n=== 過渡解析終了 ===  (計算経過時間: {elapsed_total:.2f} 秒)\n")
    return nodes, elapsed_total
