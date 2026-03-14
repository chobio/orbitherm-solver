"""SINDA/FLUINT 風の補間サブルーチン。

doublet 配列 (ArrayData) に対する線形補間を提供する。
既存の solvers/common.py の interpolate_array() とは独立した実装で、
ArrayData 型を直接受け取り、extrapolation モードを尊重する。

設計方針:
  - singlet/doublet の型混同を防ぐため、doublet 専用 API とする
  - 補間ロジックは小さな補助関数に分割して単体テストしやすくする
  - 例外メッセージは問題箇所と原因を具体的に示す
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..model.array_data import ArrayData


def _linear_segment(x0: float, y0: float, x1: float, y1: float, x: float) -> float:
    """2点 (x0,y0)-(x1,y1) の線形補間（または外挿）を返す。

    x0 == x1 の場合は y0 を返す（ゼロ除算回避）。
    """
    if x0 == x1:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def interp_linear(array_data: "ArrayData", x: float) -> float:
    """doublet 配列を線形補間して y 値を返す。

    Parameters
    ----------
    array_data: doublet 型の ArrayData
    x: 補間したい独立変数の値

    Returns
    -------
    float: 線形補間された y 値

    Raises
    ------
    TypeError: singlet 配列が渡された場合
    ValueError: extrapolation="error" かつ x が範囲外の場合
    """
    if array_data.array_type != "doublet":
        raise TypeError(
            f"interp_linear() は doublet 配列専用です。"
            f"配列 {array_data.name!r} は {array_data.array_type!r} 型です。"
            f"singlet 配列には get_singlet_value() または ARRI() を使ってください。"
        )

    xs = array_data.x_values
    ys = array_data.y_values
    extrap = array_data.extrapolation

    # ── 範囲内の一致点 ────────────────────────────────────────────────────
    # バリデーション済みなので xs は厳密単調増加・長さ ≥ 2 が保証されている

    # 下限以下
    if x <= xs[0]:
        if x == xs[0]:
            return ys[0]
        return _handle_lower_extrapolation(array_data.name, xs, ys, x, extrap)

    # 上限以上
    if x >= xs[-1]:
        if x == xs[-1]:
            return ys[-1]
        return _handle_upper_extrapolation(array_data.name, xs, ys, x, extrap)

    # ── 範囲内: 該当セグメントを二分探索で特定 ─────────────────────────
    lo, hi = 0, len(xs) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    return _linear_segment(xs[lo], ys[lo], xs[hi], ys[hi], x)


def _handle_lower_extrapolation(
    name: str,
    xs: list[float],
    ys: list[float],
    x: float,
    extrap: str,
) -> float:
    """下限外の外挿処理。"""
    if extrap == "clamp":
        return ys[0]
    if extrap == "linear":
        return _linear_segment(xs[0], ys[0], xs[1], ys[1], x)
    # extrap == "error"
    raise ValueError(
        f"配列 {name!r}: x={x} は範囲外です (下限: {xs[0]})。"
        f"extrapolation='error' が設定されています。"
    )


def _handle_upper_extrapolation(
    name: str,
    xs: list[float],
    ys: list[float],
    x: float,
    extrap: str,
) -> float:
    """上限外の外挿処理。"""
    if extrap == "clamp":
        return ys[-1]
    if extrap == "linear":
        return _linear_segment(xs[-2], ys[-2], xs[-1], ys[-1], x)
    # extrap == "error"
    raise ValueError(
        f"配列 {name!r}: x={x} は範囲外です (上限: {xs[-1]})。"
        f"extrapolation='error' が設定されています。"
    )
