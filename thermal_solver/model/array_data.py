"""SINDA/FLUINT 風の配列データクラス。

HEADER ARRAY DATA セクションで定義される singlet / doublet 配列を表現する。

singlet: 1次元インデックスアクセス用の値リスト (ARRI で参照)
doublet: (x, y) ペアの補間テーブル (ARR で線形補間参照)

設計方針:
  - dataclass + __post_init__ バリデーション
  - 便利コンストラクタ (from_singlet / from_doublet / from_flat_doublet)
  - 範囲外処理は extrapolation フィールドで明示的に指定
  - 型と責務の混同を防ぐため singlet/doublet は完全に分離
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


# 有効な配列タイプ
ArrayType = Literal["singlet", "doublet"]

# 範囲外処理モード
ExtrapolationMode = Literal["clamp", "linear", "error"]

_VALID_ARRAY_TYPES: frozenset[str] = frozenset({"singlet", "doublet"})
_VALID_EXTRAP_MODES: frozenset[str] = frozenset({"clamp", "linear", "error"})


@dataclass
class ArrayData:
    """SINDA/FLUINT 風配列データ。

    Attributes
    ----------
    name: 配列名（大文字小文字を区別しない名前解決のため保存は任意）
    array_type: "singlet" または "doublet"
    values: singlet 用の値リスト（doublet 時は空リスト）
    x_values: doublet 用の独立変数リスト（singlet 時は空リスト）
    y_values: doublet 用の従属変数リスト（singlet 時は空リスト）
    extrapolation: 範囲外処理 ("clamp" | "linear" | "error")。doublet 専用。
    submodel_path: サブモデルパス（名前空間スコープ用。省略可）
    metadata: 任意の付加情報（コメント・単位など）
    """

    name: str
    array_type: ArrayType

    values: list[float] = field(default_factory=list)
    x_values: list[float] = field(default_factory=list)
    y_values: list[float] = field(default_factory=list)

    extrapolation: ExtrapolationMode = "clamp"
    submodel_path: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate()

    # ── バリデーション ────────────────────────────────────────────────────────

    def _validate(self) -> None:
        """構造的整合性を検証する。不正な場合は ValueError / TypeError を送出。"""
        if not self.name or not self.name.strip():
            raise ValueError("ArrayData.name は空にできません。")

        if self.array_type not in _VALID_ARRAY_TYPES:
            raise ValueError(
                f"無効な array_type: {self.array_type!r}。"
                f"有効値: {sorted(_VALID_ARRAY_TYPES)}"
            )

        if self.extrapolation not in _VALID_EXTRAP_MODES:
            raise ValueError(
                f"無効な extrapolation モード: {self.extrapolation!r}。"
                f"有効値: {sorted(_VALID_EXTRAP_MODES)}"
            )

        if self.array_type == "singlet":
            self._validate_singlet()
        else:
            self._validate_doublet()

    def _validate_singlet(self) -> None:
        if len(self.values) < 1:
            raise ValueError(
                f"singlet 配列 {self.name!r}: values は1個以上必要です。"
            )
        if self.x_values:
            raise ValueError(
                f"singlet 配列 {self.name!r}: x_values は空でなければなりません。"
            )
        if self.y_values:
            raise ValueError(
                f"singlet 配列 {self.name!r}: y_values は空でなければなりません。"
            )

    def _validate_doublet(self) -> None:
        if not self.x_values or not self.y_values:
            raise ValueError(
                f"doublet 配列 {self.name!r}: x_values と y_values は必須です。"
            )
        if len(self.x_values) != len(self.y_values):
            raise ValueError(
                f"doublet 配列 {self.name!r}: "
                f"x_values ({len(self.x_values)}点) と "
                f"y_values ({len(self.y_values)}点) の長さが一致しません。"
            )
        if len(self.x_values) < 2:
            raise ValueError(
                f"doublet 配列 {self.name!r}: 補間には2点以上必要です "
                f"(現在 {len(self.x_values)}点)。"
            )
        # 厳密単調増加チェック
        for i in range(1, len(self.x_values)):
            if self.x_values[i] <= self.x_values[i - 1]:
                raise ValueError(
                    f"doublet 配列 {self.name!r}: "
                    f"x_values は厳密単調増加でなければなりません。"
                    f"インデックス {i-1}→{i}: "
                    f"{self.x_values[i-1]} >= {self.x_values[i]}"
                )
        if self.values:
            raise ValueError(
                f"doublet 配列 {self.name!r}: values は空でなければなりません "
                f"(doublet は x_values / y_values を使います)。"
            )

    # ── 便利コンストラクタ ──────────────────────────────────────────────────

    @classmethod
    def from_singlet(
        cls,
        name: str,
        values: list[float],
        submodel_path: str = "",
        metadata: Optional[dict] = None,
    ) -> "ArrayData":
        """singlet 配列を生成する。

        Parameters
        ----------
        name: 配列名
        values: 値リスト（1個以上）
        submodel_path: サブモデルパス（省略可）
        metadata: 付加情報（省略可）
        """
        return cls(
            name=name,
            array_type="singlet",
            values=list(values),
            submodel_path=submodel_path,
            metadata=dict(metadata) if metadata else {},
        )

    @classmethod
    def from_doublet(
        cls,
        name: str,
        x_values: list[float],
        y_values: list[float],
        extrapolation: ExtrapolationMode = "clamp",
        submodel_path: str = "",
        metadata: Optional[dict] = None,
    ) -> "ArrayData":
        """doublet 配列を生成する。

        Parameters
        ----------
        name: 配列名
        x_values: 独立変数リスト（厳密単調増加、2点以上）
        y_values: 従属変数リスト（x_values と同じ長さ）
        extrapolation: 範囲外処理モード
        submodel_path: サブモデルパス（省略可）
        metadata: 付加情報（省略可）
        """
        return cls(
            name=name,
            array_type="doublet",
            x_values=list(x_values),
            y_values=list(y_values),
            extrapolation=extrapolation,
            submodel_path=submodel_path,
            metadata=dict(metadata) if metadata else {},
        )

    @classmethod
    def from_flat_doublet(
        cls,
        name: str,
        flat_values: list[float],
        extrapolation: ExtrapolationMode = "clamp",
        submodel_path: str = "",
        metadata: Optional[dict] = None,
    ) -> "ArrayData":
        """フラットな (x0, y0, x1, y1, ...) 形式から doublet 配列を生成する。

        SINDA/FLUINT の ARRAY DATA セクションで一般的な記述形式に対応。

        Parameters
        ----------
        name: 配列名
        flat_values: [x0, y0, x1, y1, ...] 形式の値リスト（偶数個必須）
        extrapolation: 範囲外処理モード
        submodel_path: サブモデルパス（省略可）
        metadata: 付加情報（省略可）

        Examples
        --------
        >>> ArrayData.from_flat_doublet("SOLAR", [0.0, 5.0, 1000.0, 12.0, 2000.0, 3.0])
        # → x=[0.0, 1000.0, 2000.0], y=[5.0, 12.0, 3.0]
        """
        if len(flat_values) % 2 != 0:
            raise ValueError(
                f"from_flat_doublet({name!r}): flat_values の要素数は偶数でなければなりません "
                f"(現在 {len(flat_values)}個)。"
            )
        x_values = flat_values[0::2]
        y_values = flat_values[1::2]
        return cls.from_doublet(
            name=name,
            x_values=x_values,
            y_values=y_values,
            extrapolation=extrapolation,
            submodel_path=submodel_path,
            metadata=dict(metadata) if metadata else {},
        )

    # ── アクセサ ─────────────────────────────────────────────────────────────

    def get_singlet_value(self, index: int) -> float:
        """singlet 配列の index 番目の値を返す（1-based または 0-based）。

        SINDA/FLUINT では 1-based インデックスが一般的だが、
        この実装は 1-based (index=1 が先頭) を採用する。

        Parameters
        ----------
        index: 1-based インデックス（1 以上）

        Returns
        -------
        float: values[index - 1]

        Raises
        ------
        TypeError: singlet 以外の配列に対して呼ばれた場合
        IndexError: index が範囲外の場合
        """
        if self.array_type != "singlet":
            raise TypeError(
                f"get_singlet_value() は singlet 配列専用です。"
                f"配列 {self.name!r} は {self.array_type!r} 型です。"
            )
        if index < 1 or index > len(self.values):
            raise IndexError(
                f"singlet 配列 {self.name!r}: "
                f"インデックス {index} は範囲外です "
                f"(有効範囲: 1 〜 {len(self.values)})。"
            )
        return self.values[index - 1]

    def __repr__(self) -> str:
        if self.array_type == "singlet":
            detail = f"values={self.values}"
        else:
            detail = f"x={self.x_values}, y={self.y_values}, extrap={self.extrapolation!r}"
        return f"ArrayData(name={self.name!r}, type={self.array_type!r}, {detail})"
