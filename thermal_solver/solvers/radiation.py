"""輻射関連の計算ヘルパー。

輻射の基礎的な計算ロジックはコアソルバー（steady/transient/implicit）に組み込まれているが、
将来的に輻射ビューファクタ計算や材料依存処理を追加する際はここに集約する。
"""
from __future__ import annotations

# 輻射計算で用いる温度クリップ範囲
T_MAX_RAD: float = 5000.0  # [K]
T_MIN_RAD: float = 1.0     # [K]


def linearize_radiation_conductance(
    r: float,
    t1: float,
    t2: float,
    sigma: float = 5.67e-8,
) -> float:
    """輻射コンダクタンスを参照温度まわりで線形化して等価熱伝導率を返す。

    Q ≈ R×σ×4×T_ref^3×(T1−T2) の近似。

    Parameters
    ----------
    r: 輻射係数 [m^2]
    t1, t2: 両端温度 [K]
    sigma: Stefan-Boltzmann 定数

    Returns
    -------
    float: 等価線形コンダクタンス [W/K]
    """
    t1s = max(T_MIN_RAD, min(T_MAX_RAD, float(t1)))
    t2s = max(T_MIN_RAD, min(T_MAX_RAD, float(t2)))
    t_ref = max(T_MIN_RAD, min(T_MAX_RAD, (t1s + t2s) / 2.0))
    return r * sigma * 4.0 * (t_ref**3)


def radiation_heat_flux(
    r: float,
    t1: float,
    t2: float,
    sigma: float = 5.67e-8,
) -> float:
    """輻射熱流量 Q = R×σ×(T1^4−T2^4) [W] を返す。

    Parameters
    ----------
    r: 輻射係数 [m^2]
    t1, t2: 温度 [K]
    sigma: Stefan-Boltzmann 定数
    """
    t1s = max(T_MIN_RAD, min(T_MAX_RAD, float(t1)))
    t2s = max(T_MIN_RAD, min(T_MAX_RAD, float(t2)))
    return r * sigma * (t1s**4 - t2s**4)
