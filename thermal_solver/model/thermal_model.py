"""熱モデル全体を格納するデータクラス。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .array_data import ArrayData
    from .heater import HeaterData
    from .variables0 import Variables0Assignment


@dataclass
class ThermalModel:
    """パース済みの熱モデル構成要素をまとめたコンテナ。

    nodes の各値は {"T": float, "C": float|None} 形式の辞書。
    既存ソルバーコードとの互換を維持するため、段階的に NodeData dataclass へ移行可能。
    """

    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    """節点名 → {"T": 温度[K], "C": 熱容量[J/K] or None}"""

    conductance: dict[tuple[str, str], float] = field(default_factory=dict)
    """(節点1, 節点2) → コンダクタンス値 [W/K] または 輻射係数 [m^2]"""

    heat_input: dict[str, float] = field(default_factory=dict)
    """節点名 → 定数熱源 [W]"""

    heat_input_func: dict[str, tuple] = field(default_factory=dict)
    """節点名 → (times_array, values_array, method_str) の補間テーブル"""

    boundary_nodes: set[str] = field(default_factory=set)
    """境界節点名セット（温度固定）"""

    arithmetic_nodes: set[str] = field(default_factory=set)
    """算術節点名セット（熱容量ゼロ、熱収支=0 で温度決定）"""

    radiation_conductors: set[tuple[str, str]] = field(default_factory=set)
    """輻射コンダクタンスの (節点1, 節点2) セット"""

    node_groups: dict[str, str] = field(default_factory=dict)
    """節点名 → 所属グループ名"""

    # ── ARRAY / VARIABLES 0 拡張フィールド ────────────────────────────────

    arrays: list["ArrayData"] = field(default_factory=list)
    """HEADER ARRAY DATA で定義された配列リスト（singlet / doublet）。
    ArrayRegistry の構築は build_array_registry() または run_case 時に行う。"""

    variables0_assignments: list["Variables0Assignment"] = field(default_factory=list)
    """HEADER VARIABLES 0 で定義された代入文リスト（記述順）。
    タイムステップごとに Variables0Executor.execute() で評価する。"""

    heaters: list["HeaterData"] = field(default_factory=list)
    """HEADER HEATER DATA で定義されたヒータリスト。

    ON/OFF 実行状態は HeaterRuntimeState（runtime/heater_controller.py）で管理する。
    ここには静的定義（設計値）のみを保持する。

    将来拡張:
      - 比例制御ヒータ、電力バス制限、デューティ比ヒータ等を同リストに追加可能。
      - VARIABLES 1/2 に統合する場合は別フィールドで管理することを推奨。
    """

    dynamic_heat_input: dict[str, float] = field(default_factory=dict)
    """VARIABLES 0 の QI(node)=... で書き込まれた動的熱入力 [W]。

    キーは heat_input と同じ節点ラベル文字列（例: "MAIN.20"）。
    各タイムステップの Variables0Executor.execute() 実行時にクリア・更新される。
    get_node_qsrc() での優先順位: dynamic_heat_input > heat_input > heat_input_func

    将来拡張:
      - 文字列ラベル QI("BATTERY") に対応する場合は、
        resolve_node_label() で文字列照合を追加する
      - QR(node)=... (輻射熱源) は別フィールドで管理することを推奨
    """

    def build_array_registry(self, submodel_path: str = "") -> "ArrayRegistry":
        """model.arrays から ArrayRegistry を構築して返す。

        Parameters
        ----------
        submodel_path: フォールバックのサブモデルパス（省略可）

        Returns
        -------
        ArrayRegistry: 全配列が登録済みのレジストリ

        Notes
        -----
        このメソッドは run_case() や Variables0Executor を初期化する前に
        呼び出すことを想定している。
        """
        from ..runtime.array_registry import ArrayRegistry
        registry = ArrayRegistry()
        for arr in self.arrays:
            registry.add(arr)
        return registry
