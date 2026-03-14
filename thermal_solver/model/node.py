"""節点データのデータクラス定義。

現在の nodes 辞書 {"T": float, "C": float|None} との互換ヘルパーを提供する。
段階的な移行のため、既存コードは dict 形式のまま動作させてよい。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class NodeData:
    """熱節点データ。

    Attributes
    ----------
    T: 温度 [K]
    C: 熱容量 [J/K]。None の場合は境界節点。
    """

    T: float
    C: Optional[float]

    def to_dict(self) -> dict[str, Any]:
        return {"T": self.T, "C": self.C}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NodeData":
        return cls(T=float(d["T"]), C=d.get("C"))
