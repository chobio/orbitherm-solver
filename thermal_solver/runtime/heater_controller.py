"""サーモスタット付きヒータ制御ランタイム。

HEADER HEATER DATA で定義された HeaterData リストを実行時に評価し、
各タイムステップで ON/OFF 状態を更新して dynamic_heat_input へ電力を加算する。

アーキテクチャ上の責務分離:
  HeaterData           → 静的定義（パース結果、モデル保持）
  HeaterRuntimeState   → 実行時 ON/OFF 状態（ランタイム保持）
  HeaterController     → 制御ロジックの実行（サービス層）

制御仕様（ヒステリシス付き2点制御）:
  T <= on_temp  → ON
  T >= off_temp → OFF
  on_temp < T < off_temp → 前状態維持

加算ルール:
  dynamic_heat_input[apply_label] += heater_power
  - 上書きではなく加算（QI(node)=... で設定済みの値に積み上げ）
  - 同一ノードに複数ヒータが向いている場合は合算される

将来拡張ポイント:
  比例制御 (P制御):
    _controller_type: str = "hysteresis" | "proportional"
    proportional_power = min(heater.heater_power, kp * (heater.on_temp - T))
    → HeaterData に proportional_band フィールドを追加して分岐するだけ

  デューティ比制御:
    duty_ratio: float を HeaterData に追加
    dynamic_heat_input[...] += heater.heater_power * heater.duty_ratio

  VARIABLES 1/2 統合:
    HeaterRuntimeState をより汎用的な RuntimeContext に統合可能
    状態フィールドを分けておくことで混在を防ぐ

  電力バス制限:
    apply() に bus_limit=None 引数を追加し、合算電力を上限でクリップ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..model.heater import HeaterData
    from ..model.thermal_model import ThermalModel


# ══════════════════════════════════════════════════════════════════════════════
# ランタイム状態コンテナ
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class HeaterRuntimeState:
    """各ヒータの ON/OFF 実行状態を保持するコンテナ。

    Variables0Runtime と責務を分離することで、
    ヒータ状態 / register 変数 / dynamic_heat_input の 3層が明確になる。

    Attributes
    ----------
    states: ヒータ名 → 現在の ON/OFF 状態 (True=ON, False=OFF)

    将来拡張:
      - accumulated_energy: dict[str, float]  積算エネルギー [J]
      - cycle_count: dict[str, int]           ON/OFF サイクル数
      - last_switch_time: dict[str, float]    最後に ON/OFF が切り替わった時刻
    """

    states: dict[str, bool] = field(default_factory=dict)

    def is_on(self, heater_name: str, default: bool = False) -> bool:
        """ヒータが ON かどうかを返す。未登録の場合は default を返す。"""
        return self.states.get(heater_name, default)

    def set_state(self, heater_name: str, state: bool) -> None:
        """ヒータ状態を更新する。"""
        self.states[heater_name] = state

    def __repr__(self) -> str:
        on_list = [k for k, v in self.states.items() if v]
        off_list = [k for k, v in self.states.items() if not v]
        return f"HeaterRuntimeState(ON={on_list}, OFF={off_list})"


# ══════════════════════════════════════════════════════════════════════════════
# ヒータ制御エンジン
# ══════════════════════════════════════════════════════════════════════════════

class HeaterController:
    """サーモスタット付きヒータ制御を実行するコントローラ。

    使用例:
        controller = HeaterController(model)
        heater_runtime = controller.initialize_states()

        # タイムステップループ内
        heater_runtime = controller.apply(nodes, model.dynamic_heat_input, heater_runtime)

    Parameters
    ----------
    model: ThermalModel（heaters リストとノード情報を参照）

    Raises
    ------
    ValueError: モデル内にヒータが定義されていないか、ノード解決に失敗した場合
    """

    def __init__(self, model: "ThermalModel") -> None:
        if not hasattr(model, "heaters"):
            raise TypeError("model には heaters 属性が必要です。")
        self._heaters: list["HeaterData"] = model.heaters
        self._model = model

        # ノードラベルのキャッシュ（初期化時に解決）
        # {heater_name: full_label_string} e.g. "BATT_HTR" → "MAIN.20"
        self._sense_labels: dict[str, str] = {}
        self._apply_labels: dict[str, str] = {}

        self._precompute_labels()

    def _precompute_labels(self) -> None:
        """各ヒータの sense_node / apply_node をノードラベルに変換してキャッシュする。

        enabled=False のヒータはスキップする（後でラベル解決が必要になれば
        enabled 状態を変更する前に再初期化すること）。
        """
        for heater in self._heaters:
            try:
                self._sense_labels[heater.name] = self._resolve_node_label(
                    heater.sense_node, heater.submodel_path
                )
                self._apply_labels[heater.name] = self._resolve_node_label(
                    heater.apply_node, heater.submodel_path
                )
            except (KeyError, ValueError) as e:
                raise ValueError(
                    f"Heater {heater.name!r}: ノード解決に失敗しました: {e}"
                ) from e

    def _resolve_node_label(self, node_id: int, submodel_path: str = "") -> str:
        """整数ノード番号を model.nodes のフルラベルに解決する。

        解決優先順位:
          1. "{submodel_path}.{node_id}" が model.nodes に存在する
          2. 全ノードで ".{node_id}" サフィックス一致が唯一
          3. 見つからない / 複数 → 例外

        将来拡張:
          文字列ラベル（"BATTERY"）への対応は、node_id が str のとき
          直接 model.nodes での完全一致検索を先に試みるよう分岐を追加する。
        """
        suffix = f".{node_id}"

        if submodel_path:
            label = f"{submodel_path}{suffix}"
            if label in self._model.nodes:
                return label

        candidates = [n for n in self._model.nodes if n.endswith(suffix)]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise ValueError(
                f"Ambiguous node id {node_id!r}: "
                f"multiple matches found: {candidates}. "
                f"Specify HeaterData.submodel_path to disambiguate."
            )
        raise KeyError(
            f"Node {node_id!r} not found in model.nodes. "
            f"Searched for label ending with {suffix!r}. "
            f"Available nodes: {sorted(self._model.nodes.keys())}"
        )

    def initialize_states(
        self,
        runtime_state: Optional[HeaterRuntimeState] = None,
    ) -> HeaterRuntimeState:
        """各ヒータの initial_state を使って HeaterRuntimeState を初期化する。

        既存の runtime_state が渡された場合は、未登録のヒータのみ初期化する
        （既に登録済みの状態は維持される）。

        Parameters
        ----------
        runtime_state: 既存の状態コンテナ（省略時は新規作成）

        Returns
        -------
        HeaterRuntimeState: 初期化済みの状態コンテナ
        """
        if runtime_state is None:
            runtime_state = HeaterRuntimeState()
        for heater in self._heaters:
            if heater.name not in runtime_state.states:
                runtime_state.states[heater.name] = heater.initial_state
        return runtime_state

    def apply(
        self,
        nodes: dict,
        dynamic_heat_input: dict[str, float],
        runtime_state: Optional[HeaterRuntimeState] = None,
    ) -> HeaterRuntimeState:
        """現在のノード温度に基づいてヒータ ON/OFF を判定し、熱入力を加算する。

        処理フロー（各ヒータについて）:
          1. enabled=False なら無視
          2. sense_node のラベルを取得し、nodes から現在温度 T を読む
          3. ヒステリシス制御で新しい ON/OFF 状態を決定:
             T <= on_temp  → ON
             T >= off_temp → OFF
             それ以外      → 前状態を維持
          4. ON のとき: dynamic_heat_input[apply_label] += heater_power
             （上書きではなく加算）

        Parameters
        ----------
        nodes: 現在のノード辞書 {label: {"T": float, "C": float}}
               過渡解析では前ステップ終了時点の温度を使用する
        dynamic_heat_input: 今ステップの動的熱入力辞書（in-place 更新）
               VARIABLES 0 の QI 値が既にある場合はその上に加算する
        runtime_state: ヒータ状態コンテナ（省略時は initialize_states() で生成）

        Returns
        -------
        HeaterRuntimeState: 更新済み状態コンテナ

        Notes
        -----
        temperatures パラメータ仕様（将来拡張用コメント）:
          現在は nodes（フルラベル辞書）を直接受け取る。
          将来 {node_id: temperature} 形式の薄いラッパーが必要になった場合は
          nodes.items() を走査して {id: T} に変換するアダプタを追加する。
        """
        if runtime_state is None:
            runtime_state = self.initialize_states()

        for heater in self._heaters:
            if not heater.enabled:
                continue

            sense_label = self._sense_labels.get(heater.name)
            apply_label = self._apply_labels.get(heater.name)
            if sense_label is None or apply_label is None:
                # enabled=True だがラベル未解決の場合は安全にスキップ
                continue

            if sense_label not in nodes:
                continue

            T = nodes[sense_label]["T"]
            current_state = runtime_state.is_on(heater.name, default=heater.initial_state)

            # ── ヒステリシス制御 ────────────────────────────────────────────
            if T <= heater.on_temp:
                new_state = True
            elif T >= heater.off_temp:
                new_state = False
            else:
                new_state = current_state  # 不感帯: 前状態維持

            runtime_state.set_state(heater.name, new_state)

            # ── 電力加算（ON のとき） ────────────────────────────────────────
            if new_state:
                current = dynamic_heat_input.get(apply_label, 0.0)
                dynamic_heat_input[apply_label] = current + heater.heater_power
                # 将来拡張: 比例制御の場合はここで power を可変にする
                # power = _calc_proportional_power(heater, T)
                # dynamic_heat_input[apply_label] = current + power

        return runtime_state
