"""HEADER VARIABLES 0 の内部表現データモデル。

SINDA/FLUINT の VARIABLES 0 ブロックは、タイムステップごとに評価される
代入式の列として表現される。このモジュールはその構造を保持するデータクラスを定義する。

設計方針:
  - Variables0Assignment: 1行の代入文「target = expression」を表現
  - Variables0Block: ブロック全体（複数 assignment のリスト）を表現
  - 将来 QI(node)=... や T(node)=... に対応するための拡張ポイントを target に持つ

将来拡張ポイント:
  - target に "QI(20)" のような文字列を格納し、executor がパースして
    ノード書き込みと register 変数代入を区別する
  - submodel_path でサブモデルスコープごとの評価をサポート
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Variables0Assignment:
    """VARIABLES 0 内の1行の代入文を表現する。

    Attributes
    ----------
    target: 代入先の変数名（例: "QEXT"）
        将来: "QI(20)" のようなノード書き込み指定も格納可能にする想定
    expression: 右辺の式文字列（例: 'ARR("SOLAR_HEAT", TIME)'）
    submodel_path: サブモデルパス（将来の名前空間スコープ用）

    Examples
    --------
    >>> asgn = Variables0Assignment(
    ...     target="QEXT",
    ...     expression='ARR("SOLAR_HEAT", TIME)',
    ...     submodel_path="MAIN",
    ... )
    """

    target: str
    expression: str
    submodel_path: str = ""

    def __post_init__(self) -> None:
        if not self.target or not self.target.strip():
            raise ValueError("Variables0Assignment.target は空にできません。")
        if not self.expression or not self.expression.strip():
            raise ValueError(
                f"Variables0Assignment: target {self.target!r} の expression が空です。"
            )

    def __repr__(self) -> str:
        path = f", submodel={self.submodel_path!r}" if self.submodel_path else ""
        return f"Variables0Assignment({self.target!r} = {self.expression!r}{path})"


@dataclass
class Variables0Block:
    """HEADER VARIABLES 0 ブロック全体を表現するコンテナ。

    Attributes
    ----------
    assignments: Variables0Assignment のリスト（記述順を保持）
    submodel_path: このブロック全体のサブモデルパス（省略可）

    Notes
    -----
    assignments は記述順に評価される（上から下へ逐次代入）。
    """

    assignments: list[Variables0Assignment] = field(default_factory=list)
    submodel_path: str = ""

    def __len__(self) -> int:
        return len(self.assignments)

    def __repr__(self) -> str:
        return (
            f"Variables0Block("
            f"{len(self.assignments)} assignments, "
            f"submodel={self.submodel_path!r})"
        )
