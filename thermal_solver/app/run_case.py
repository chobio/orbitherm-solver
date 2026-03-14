"""Orbitherm Solver — 共通実行入口モジュール。

UI（orbitherm_ui.py）・CLI（orbitherm_main.py）・将来の Orbitherm Studio（FreeCAD アダプタ）
すべてから呼び出せる統一エントリポイントを提供する。
"""
from __future__ import annotations

import os
import re
import time
from typing import Callable, Optional

from ..io.input_parser import load_initial_temperature_file, parse_header_input
from ..io.model_builder import build_model
from ..io.result_writer import save_final_temperature_file, write_csv, write_out
from ..model.config import AnalysisConfig
from ..model.result import SolverResult
from ..model.thermal_model import ThermalModel
from ..post.plotter import make_temperature_plot
from ..solvers.common import _node_display_name, record_snapshot
from ..solvers.steady import run_steady_analysis, run_steady_cnfrw
from ..solvers.transient import run_transient_analysis


def run_case(
    input_path: str,
    output_base: Optional[str] = None,
    no_input: bool = True,
    logger: Optional[Callable[[str], None]] = None,
    make_plot: bool = True,
    **kwargs,
) -> SolverResult:
    """熱解析を実行して結果を返す。

    Parameters
    ----------
    input_path: 入力ファイル (.inp) のパス
    output_base: 出力ファイルのベース名（省略時は入力ファイル名から自動生成）
    no_input: True の場合グラフ表示後の Enter 待ちをしない（UI/バッチ用）
    logger: ログ出力 callable（None の場合は print を使用）
    make_plot: True の場合 PNG グラフを出力する
    **kwargs: 将来の拡張用

    Returns
    -------
    SolverResult: 解析結果オブジェクト
    """
    _log = logger or print
    result = SolverResult()

    try:
        result = _run_case_impl(
            input_path=input_path,
            output_base=output_base,
            interactive=not no_input,
            logger=_log,
            make_plot=make_plot,
        )
    except SystemExit:
        raise
    except Exception as exc:
        result.success = False
        result.error_message = str(exc)
        _log(f"[ERROR] run_case 例外: {exc}")
        raise

    return result


def _run_case_impl(
    input_path: str,
    output_base: Optional[str],
    interactive: bool,
    logger: Callable[[str], None],
    make_plot: bool,
) -> SolverResult:
    """run_case の実処理本体。"""

    # ── 入力パース ──────────────────────────────────────────────────────────────
    logger("=== プリプロセス開始 ===")
    sections = parse_header_input(input_path)
    logger("  入力ファイル解析 ... 完了")

    logger("  オプション・コントロールデータ解析 ...", )
    config, model = build_model(sections, input_path)
    logger("  ノード・コンダクタンス・熱源データ解析 ... 完了")

    # ── 出力パス決定 ────────────────────────────────────────────────────────────
    input_dir = os.path.dirname(os.path.abspath(input_path))
    if output_base is None:
        base = re.sub(r"\.inp$", "", os.path.basename(input_path), flags=re.IGNORECASE)
        out_base = os.path.join(input_dir, base)
    elif os.path.isabs(output_base):
        out_base = output_base
    else:
        out_base = os.path.join(input_dir, output_base)

    log_path = f"{out_base}.log"
    result = SolverResult(log_path=log_path)

    # ── ログファイル初期化 ─────────────────────────────────────────────────────
    from ..io.log_writer import LogWriter
    log_writer = LogWriter(log_path)
    log_writer.log(f"# 入力ファイル: {input_path}")
    log_writer.log("")

    def log(msg: str) -> None:
        log_writer.log(msg)

    logger("=== プリプロセス完了 ===\n")
    log("プリプロセス完了")

    if model.arithmetic_nodes:
        logger(f"  算術節点: {len(model.arithmetic_nodes)} 節点\n")
        log(f"算術節点: {len(model.arithmetic_nodes)} 節点")
    logger(f"  解析種別: {config.analysis_type}\n")
    log(f"解析種別: {config.analysis_type}")

    # ── 初期温度ファイル読み込み ────────────────────────────────────────────────
    nodes = model.nodes
    if config.analysis_type == "TRANSIENT" and config.initial_temperature_file:
        n_loaded = load_initial_temperature_file(config.initial_temperature_file, nodes)
        if n_loaded is not None and n_loaded > 0:
            logger(f"  初期温度ファイルを読み込みました: {config.initial_temperature_file} ({n_loaded} 節点)\n")
            log(f"初期温度ファイル: {config.initial_temperature_file} ({n_loaded} 節点)")
        elif n_loaded == 0:
            logger(f"  警告: 初期温度ファイルに有効な節点がありません: {config.initial_temperature_file}\n")
            log(f"警告: 初期温度ファイルに有効な節点がありません: {config.initial_temperature_file}")
        else:
            logger(f"  エラー: 初期温度ファイルを読み込めません: {config.initial_temperature_file}\n")
            log(f"エラー: 初期温度ファイルを読み込めません: {config.initial_temperature_file}")
            import sys
            sys.exit(1)

    # ── 結果バッファ初期化 ─────────────────────────────────────────────────────
    record_times: list[float] = []
    results: dict[str, list[float]] = {node: [] for node in nodes}
    results_qsrc: dict[str, list[float]] = {node: [] for node in nodes}
    results_qnet: dict[str, list[float]] = {node: [] for node in nodes}
    results_cond_flow: dict[tuple, list[float]] = {(n1, n2): [] for (n1, n2) in model.conductance}

    def _snap(n: dict, t: float) -> None:
        record_snapshot(
            n, t,
            model.conductance, model.heat_input, model.heat_input_func,
            model.radiation_conductors, config.sigma,
            record_times, results, results_qsrc, results_qnet, results_cond_flow,
            dynamic_heat_input=model.dynamic_heat_input or None,
        )

    # ── 解析実行 ────────────────────────────────────────────────────────────────
    if config.analysis_type == "STEADY":
        logger("=== 定常解析開始 ===\n")
        log(f"定常解析開始 (ソルバ: {config.steady_solver})")
        t0 = time.time()
        nodes = _run_steady(nodes, model, config)
        elapsed = time.time() - t0
        _snap(nodes, 0.0)
        logger(f"\n=== 定常解析終了 ===  (計算経過時間: {elapsed:.2f} 秒)\n")
        log(f"定常解析終了 経過時間: {elapsed:.2f} 秒")

    elif config.analysis_type == "STEADY_THEN_TRANSIENT":
        # 定常解析フェーズ
        logger("=== 定常解析開始 ===\n")
        log(f"定常解析開始 (ソルバ: {config.steady_solver}) [定常のち過渡]")
        t0 = time.time()
        nodes = _run_steady(nodes, model, config)
        elapsed_steady = time.time() - t0
        logger(f"\n=== 定常解析終了 ===  (計算経過時間: {elapsed_steady:.2f} 秒)\n")
        log(f"定常解析終了 経過時間: {elapsed_steady:.2f} 秒")
        # 定常終了時温度を保存
        steady_temp_path = f"{out_base}_steady_final_temperature.csv"
        save_final_temperature_file(steady_temp_path, nodes)
        logger(f"  定常終了時温度を保存しました: {steady_temp_path}\n")
        log(f"定常終了時温度保存: {steady_temp_path}")
        # 過渡初期値として定常結果を記録
        _snap(nodes, config.time_start)
        # 過渡解析フェーズ
        nodes, elapsed_trans = run_transient_analysis(
            nodes, model, config, on_output=_snap, logger=logger
        )
        log(f"過渡解析終了 経過時間: {elapsed_trans:.2f} 秒")
        # 過渡終了時温度を保存
        transient_temp_path = f"{out_base}_final_temperature.csv"
        save_final_temperature_file(transient_temp_path, nodes)
        logger(f"  過渡終了時温度を保存しました: {transient_temp_path}\n")
        log(f"過渡終了時温度保存: {transient_temp_path}")

    else:
        # 純粋な過渡解析
        _snap(nodes, config.time_start)
        nodes, elapsed_trans = run_transient_analysis(
            nodes, model, config, on_output=_snap, logger=logger
        )
        log(f"過渡解析終了 経過時間: {elapsed_trans:.2f} 秒")

    # ── save_final_temperature 処理 ───────────────────────────────────────────
    if config.save_final_temperature and config.analysis_type != "STEADY_THEN_TRANSIENT":
        if config.save_final_temperature is True:
            final_temp_path = f"{out_base}_final_temperature.csv"
        else:
            final_temp_path = str(config.save_final_temperature)
        save_final_temperature_file(final_temp_path, nodes)
        logger(f"  終了時温度を保存しました: {final_temp_path}\n")
        log(f"終了時温度保存: {final_temp_path}")

    # ── 定常収束判定 ───────────────────────────────────────────────────────────
    STEADY_STATE_ABS_TOL = 0.01
    converged_steady = False
    if len(record_times) >= 2:
        i_last = len(record_times) - 1
        max_dt = max(
            abs(results[node][i_last] - results[node][i_last - 1]) for node in results
        )
        converged_steady = max_dt < STEADY_STATE_ABS_TOL
        t_last, t_prev = record_times[i_last], record_times[i_last - 1]
        if converged_steady:
            logger(
                f"定常収束: 判定済 (最後の出力間 {t_prev}s→{t_last}s の"
                f"最大温度変化 {max_dt:.6f}℃ < {STEADY_STATE_ABS_TOL}℃)\n"
            )
            log(f"定常収束: 判定済 max|dT|={max_dt:.6f}℃ (閾値 {STEADY_STATE_ABS_TOL}℃)")
        else:
            logger(
                f"定常未達: 最後の出力間 {t_prev}s→{t_last}s の"
                f"最大温度変化 {max_dt:.6f}℃ (閾値 {STEADY_STATE_ABS_TOL}℃)\n"
            )
            log(f"定常未達: max|dT|={max_dt:.6f}℃ (閾値 {STEADY_STATE_ABS_TOL}℃)")
    else:
        log("定常収束: 出力時刻が2未満のため判定省略")

    # ── 結果ファイル書き出し ────────────────────────────────────────────────────
    output_csv = f"{out_base}_mp.csv"
    output_out = f"{out_base}.out"
    output_png = f"{out_base}_mp.png" if (make_plot and config.output_graph) else None

    write_csv(output_csv, record_times, results)
    log(f"出力: {output_csv}")

    write_out(
        output_out, input_path, record_times,
        results, results_qsrc, results_qnet, results_cond_flow,
    )
    log(f"出力: {output_out}")

    if output_png:
        title = f"Temperature Evolution ({os.path.basename(out_base)})"
        make_temperature_plot(
            record_times, results, output_png,
            title=title, interactive=interactive,
        )
        log(f"出力: {output_png}")

    logger(f"解析完了（マルチプロセス版）！結果は {output_csv} に保存されました。")
    logger(f"計算出力: {output_out}  ログ: {log_path}")
    if output_png:
        logger(f"グラフは {output_png} に出力されました。\n")
    log("解析完了")
    log_writer.close()

    result.record_times = record_times
    result.results = results
    result.results_qsrc = results_qsrc
    result.results_qnet = results_qnet
    result.results_cond_flow = results_cond_flow
    result.converged_steady = converged_steady
    result.output_csv = output_csv
    result.output_out = output_out
    result.output_png = output_png
    result.log_path = log_path
    result.success = True
    return result


def _run_steady(nodes: dict, model: ThermalModel, config: AnalysisConfig) -> dict:
    """設定に応じた定常ソルバーを選択して実行する。"""
    if config.steady_solver == "CNFRW":
        return run_steady_cnfrw(
            nodes, model.boundary_nodes, model.conductance,
            model.radiation_conductors, model.heat_input, model.heat_input_func,
            config.sigma,
        )
    return run_steady_analysis(
        nodes, model.boundary_nodes, model.conductance,
        model.radiation_conductors, model.heat_input, model.heat_input_func,
        config.sigma,
    )
