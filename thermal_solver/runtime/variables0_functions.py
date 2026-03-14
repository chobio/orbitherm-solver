"""SINDA/FLUINT の HEADER VARIABLES 0 相当の配列参照関数・モデル書き込み関数。

配列読み取り (ARR / ARRI) に加えて、ノード熱入力への書き込み (set_qi) を提供する。

設計方針:
  - ARR() / ARRI() → 配列読み取り専用（既存設計を維持）
  - set_qi()       → ThermalModel.dynamic_heat_input への書き込み窓口
  - _resolve_node_label() → node id → 節点ラベルの解決ロジックを分離
  - QI() は左辺ターゲット専用のため as_eval_namespace() には含めない

将来拡張ポイント:
  - set_t(node_id, value): ThermalModel.nodes のT値を書き込む
  - set_qr(node_id, value): 輻射熱源の書き込み
  - 文字列ラベル QI("BATTERY") への対応は _resolve_node_label() に追記
"""
from __future__ import annotations

from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..model.thermal_model import ThermalModel

from .array_registry import ArrayRegistry


class Variables0Functions:
    """HEADER VARIABLES 0 スコープで使用できる配列参照・モデル書き込み関数群。

    Parameters
    ----------
    array_registry: 参照元の ArrayRegistry
    submodel_path: デフォルトのサブモデルパス（省略可）
    model: ThermalModel への参照（QI 等のモデル書き込みに必要、省略可）

    Examples
    --------
    >>> v0 = Variables0Functions(registry, model=model)
    >>> q_solar = v0.ARR("SOLAR_HEAT", 750.0)
    >>> mode_1  = v0.ARRI("POWER_MODE", 1)
    >>> v0.set_qi(20, 100.0, submodel_path="MAIN")  # MAIN.20 に 100W 書き込み
    """

    def __init__(
        self,
        array_registry: ArrayRegistry,
        submodel_path: str = "",
        model: Optional["ThermalModel"] = None,
    ) -> None:
        if not isinstance(array_registry, ArrayRegistry):
            raise TypeError(
                f"Variables0Functions には ArrayRegistry を渡してください。"
                f"渡された型: {type(array_registry).__name__!r}"
            )
        self._registry = array_registry
        self._submodel_path = submodel_path
        self._model = model

    # ── 配列読み取り API ─────────────────────────────────────────────────────

    def ARR(self, name: str, x: float, submodel_path: str = "") -> float:
        """doublet 配列を線形補間して値を返す。

        SINDA/FLUINT の ARR(配列名, 独立変数) に相当。

        Parameters
        ----------
        name: doublet 配列名
        x: 補間する独立変数の値（時刻・温度など）
        submodel_path: サブモデルパス（省略可）

        Returns
        -------
        float: 補間結果

        Raises
        ------
        KeyError: 配列が見つからない場合
        TypeError: singlet 配列に ARR() を呼んだ場合
        ValueError: extrapolation="error" かつ範囲外の場合
        """
        return self._registry.get_value(name, float(x), submodel_path)

    def ARRI(self, name: str, index: int, submodel_path: str = "") -> float:
        """singlet 配列から index 番目の値を返す（1-based）。

        SINDA/FLUINT の ARRI(配列名, インデックス) に相当。

        Parameters
        ----------
        name: singlet 配列名
        index: 1-based インデックス（1 が先頭）
        submodel_path: サブモデルパス（省略可）

        Returns
        -------
        float: values[index - 1]

        Raises
        ------
        KeyError: 配列が見つからない場合
        TypeError: doublet 配列に ARRI() を呼んだ場合
        IndexError: index が範囲外の場合
        """
        return self._registry.get_singlet_value(name, int(index), submodel_path)

    # ── モデル書き込み API ───────────────────────────────────────────────────

    def set_qi(
        self,
        node_id: Union[int, str],
        value: float,
        submodel_path: str = "",
    ) -> None:
        """ノードの動的外部熱入力 [W] を ThermalModel.dynamic_heat_input に書き込む。

        VARIABLES 0 の左辺 QI(node)=value に対応する書き込み窓口。

        Parameters
        ----------
        node_id: 節点番号 (int) または 将来の文字列ラベル
        value: 設定する熱入力 [W]
        submodel_path: 節点が属するサブモデルパス（ラベル解決に使用）

        Raises
        ------
        RuntimeError: model が設定されていない場合
        KeyError: node_id に対応する節点が model.nodes に見つからない場合

        将来拡張:
          node_id が文字列の場合は直接ラベルとして照合する処理を追加可能。
          QR(node)=... の set_qr() も同じパターンで追加できる。
        """
        if self._model is None:
            raise RuntimeError(
                "QI target requires a model instance. "
                "Pass model= to Variables0Functions() or Variables0Executor()."
            )
        label = self._resolve_node_label(node_id, submodel_path)
        self._model.dynamic_heat_input[label] = float(value)

    def _resolve_node_label(
        self,
        node_id: Union[int, str],
        submodel_path: str = "",
    ) -> str:
        """node_id を ThermalModel.nodes のフルラベルに解決する。

        解決優先順位:
          1. "{submodel_path}.{node_id}" が model.nodes に存在する
          2. いずれかのグループの ".{node_id}" サフィックスで唯一一致
          3. 見つからない / 複数候補がある → 例外

        Parameters
        ----------
        node_id: 整数ノード番号（将来: 文字列ラベルにも対応可能）
        submodel_path: サブモデルパス（名前解決の優先ヒント）

        Returns
        -------
        str: model.nodes のフルラベル（例: "MAIN.20"）

        将来拡張:
          node_id が文字列の場合: まず完全一致 (model.nodes に直接存在するか) を試す。
          例: "MAIN.BATTERY" を直接許可する場合は先頭に完全一致チェックを追加。
        """
        model = self._model
        node_id_str = str(node_id)
        suffix = f".{node_id_str}"

        # 1. submodel_path 指定がある場合は修飾キーを優先
        if submodel_path:
            label = f"{submodel_path}{suffix}"
            if label in model.nodes:
                return label

        # 2. 全ノードから suffix 一致を検索
        candidates = [n for n in model.nodes if n.endswith(suffix)]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise ValueError(
                f"Ambiguous node id {node_id!r}: "
                f"multiple matches found: {candidates}. "
                f"Specify submodel_path to disambiguate."
            )

        # 3. 見つからない
        raise KeyError(
            f"Node {node_id!r} not found in model.nodes. "
            f"Searched for label ending with {suffix!r}. "
            f"Available nodes: {sorted(model.nodes.keys())}"
        )

    # ── eval 環境公開 ─────────────────────────────────────────────────────────

    def as_eval_namespace(self) -> dict[str, object]:
        """eval() コンテキストに渡せる名前空間辞書を返す。

        ARR / ARRI のみを公開する。
        QI は左辺ターゲット専用のため eval 環境には含めない。

        Returns
        -------
        dict: {"ARR": self.ARR, "ARRI": self.ARRI}

        将来拡張:
          数学関数 SIN/COS/EXP を追加する場合はここに追記する。
          例: {"ARR": self.ARR, "ARRI": self.ARRI, "SIN": math.sin}
        """
        return {
            "ARR": self.ARR,
            "ARRI": self.ARRI,
        }

    def __repr__(self) -> str:
        model_info = "model=<set>" if self._model is not None else "model=None"
        return f"Variables0Functions(registry={self._registry!r}, {model_info})"
