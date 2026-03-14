"""解析結果のファイル出力処理。

終了時温度 CSV / 温度履歴 CSV / 詳細計算 OUT ファイルの書き出しをここに集約する。
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..solvers.common import _node_display_name


def save_final_temperature_file(filepath: str, nodes: dict) -> str:
    """全節点の最終温度を CSV（node,T_C）で保存する。

    空間ノードは SPACE.9999 表記に統一する。

    Returns
    -------
    str: 保存したファイルパス
    """
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("node,T_C\n")
        for n in sorted(nodes.keys()):
            t_k = nodes[n].get("T")
            if t_k is not None:
                t_c = float(t_k) - 273.0
                f.write(f"{_node_display_name(n)},{t_c:.6f}\n")
    return filepath


def write_csv(
    output_csv: str,
    record_times: list[float],
    results: dict[str, list[float]],
) -> None:
    """温度履歴を CSV で書き出す。"""
    csv_dict: dict[str, Any] = {"Time": record_times}
    for node, temps in results.items():
        csv_dict[_node_display_name(node)] = temps
    df = pd.DataFrame(csv_dict)
    df.to_csv(output_csv, index=False, float_format="%.3f")


def write_out(
    output_out: str,
    input_filename: str,
    record_times: list[float],
    results: dict[str, list[float]],
    results_qsrc: dict[str, list[float]],
    results_qnet: dict[str, list[float]],
    results_cond_flow: dict[tuple, list[float]],
) -> None:
    """詳細計算出力 (.out) ファイルを書き出す。"""
    with open(output_out, "w", encoding="utf-8") as fout:
        fout.write("# 熱解析 計算出力 (.out)\n")
        fout.write(f"# 入力: {input_filename}\n")
        fout.write(f"# 出力時刻数: {len(record_times)}\n\n")
        for i, t in enumerate(record_times):
            fout.write(f"Time = {t}\n")
            fout.write("[NODES]\n")
            fout.write("# ノード名    温度(℃)  発熱(W)  熱入出力(W)\n")
            for node in sorted(results.keys()):
                disp = _node_display_name(node)
                fout.write(
                    f"  {disp}  {results[node][i]:.3f}"
                    f"  {results_qsrc[node][i]:.6f}"
                    f"  {results_qnet[node][i]:.6f}\n"
                )
            fout.write("[CONDUCTORS]\n")
            fout.write("# ノード1    ノード2    熱流量(W) (1→2)\n")
            for (n1, n2) in sorted(results_cond_flow.keys()):
                q = results_cond_flow[(n1, n2)][i]
                fout.write(
                    f"  {_node_display_name(n1)}  {_node_display_name(n2)}  {q:.6f}\n"
                )
            fout.write("\n")
