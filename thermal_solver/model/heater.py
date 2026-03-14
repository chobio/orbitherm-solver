"""SINDA/FLUINT 風ヒータ制御のデータモデル。

HEADER HEATER DATA で定義されるヒータの静的定義（設計値）を保持する。
ON/OFF 実行状態は HeaterRuntimeState（runtime パッケージ）で管理する。

設計方針:
  - HeaterData は純粋なデータコンテナ（パース結果の直接表現）
  - バリデーションは __post_init__ で即時実施
  - ランタイム状態（ON/OFF）は分離
  - 将来: 比例制御 (proportional_band)、デューティ比 (duty_ratio) フィールド追加可能
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HeaterData:
    """サーモスタット付きヒータの定義データ。

    Attributes
    ----------
    name: ヒータ識別名（一意であること）
    sense_node: 温度監視ノード番号（整数 node id）
    apply_node: 熱入力を加えるノード番号（整数 node id）
    on_temp: ON 切り替え温度 [K]。温度がこの値以下になると ON
    off_temp: OFF 切り替え温度 [K]。温度がこの値以上になると OFF
    heater_power: ON 時に apply_node へ加算する熱量 [W]（正値）
    initial_state: 初期 ON/OFF 状態（True=ON, False=OFF）
    enabled: False にすると制御ループで完全スキップ（一時無効化用）
    submodel_path: サブモデルスコープ（ノードラベル解決に使用）
    metadata: 拡張用任意辞書（コメント、ユニット等）

    制御仕様 (ヒステリシス付き2点制御):
      T <= on_temp  → ON
      T >= off_temp → OFF
      on_temp < T < off_temp → 前状態維持

    将来拡張:
      - proportional_band: float = 0.0  比例帯 [K]（0=純ON/OFF）
      - duty_ratio: float = 1.0         デューティ比（0〜1, 1=常時全電力）
      - power_limit: float              電力バス制限
      - priority: int = 0               複数ヒータ競合時の優先順位
    """

    name: str
    sense_node: int
    apply_node: int
    on_temp: float
    off_temp: float
    heater_power: float
    initial_state: bool = False
    enabled: bool = True
    submodel_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """生成直後にデータ整合性を検証する。"""
        if not self.name or not self.name.strip():
            raise ValueError("HeaterData.name は空にできません。")
        if not isinstance(self.sense_node, int):
            raise TypeError(
                f"HeaterData.sense_node は整数でなければなりません。"
                f"渡された型: {type(self.sense_node).__name__!r}"
            )
        if not isinstance(self.apply_node, int):
            raise TypeError(
                f"HeaterData.apply_node は整数でなければなりません。"
                f"渡された型: {type(self.apply_node).__name__!r}"
            )
        if self.heater_power < 0.0:
            raise ValueError(
                f"HeaterData {self.name!r}: heater_power は 0 以上でなければなりません。"
                f"渡された値: {self.heater_power}"
            )
        if self.off_temp < self.on_temp:
            raise ValueError(
                f"HeaterData {self.name!r}: off_temp ({self.off_temp}) は "
                f"on_temp ({self.on_temp}) 以上でなければなりません。"
            )

    def __repr__(self) -> str:
        state = "ON" if self.initial_state else "OFF"
        enabled_str = "" if self.enabled else ", disabled"
        return (
            f"HeaterData({self.name!r}, "
            f"sense={self.sense_node}, apply={self.apply_node}, "
            f"on={self.on_temp}, off={self.off_temp}, "
            f"power={self.heater_power}W, init={state}{enabled_str})"
        )
