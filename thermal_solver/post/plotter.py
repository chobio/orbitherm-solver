"""温度履歴グラフ描画モジュール。"""
from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt

from ..solvers.common import _node_display_name


def make_temperature_plot(
    record_times: list[float],
    results: dict[str, list[float]],
    output_png: str,
    title: str = "Temperature Evolution",
    interactive: bool = False,
) -> None:
    """温度履歴グラフを PNG に保存する。

    Parameters
    ----------
    record_times: 時刻リスト [s]
    results: 節点名 → 温度リスト [°C]
    output_png: 保存先 PNG パス
    title: グラフタイトル
    interactive: True の場合、表示後に Enter 待ちを行う
    """
    plt.figure(figsize=(10, 5))
    for node, temps in results.items():
        plt.plot(record_times, temps, label=_node_display_name(node))
    plt.xlabel("Time (s)")
    plt.ylabel("Temperature (°C)")
    plt.legend()
    plt.title(f"{title} (°C)")
    plt.grid()
    plt.savefig(output_png)
    plt.show(block=False)
    if interactive:
        input("グラフを確認したらEnterを押してください：")
    plt.close()
