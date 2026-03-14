"""配列レジストリ: ArrayData を名前で管理する実行時コンテナ。

SINDA/FLUINT の HEADER ARRAY DATA セクションで定義された配列を
実行時に名前解決して参照するための中心クラス。

名前解決の優先順位:
  1. "{submodel_path}:{name}" の完全修飾キー（大文字化）
  2. "{name}" のみのキー（大文字化）

この設計により、サブモデル間で同名配列が定義されても正しく解決できる。
"""
from __future__ import annotations

from typing import Optional

from ..model.array_data import ArrayData
from ..subroutines.interpolation import interp_linear


def _make_key(name: str, submodel_path: str = "") -> str:
    """内部キー文字列を生成する（大文字化・空白除去）。

    ルール:
      submodel_path が空でない場合: "{SUBMODEL}:{NAME}"
      submodel_path が空の場合: "{NAME}"
    """
    n = name.strip().upper()
    s = submodel_path.strip().upper()
    if s:
        return f"{s}:{n}"
    return n


class ArrayRegistry:
    """実行時に参照可能な配列の管理クラス。

    使用例:
        registry = ArrayRegistry()
        registry.add(ArrayData.from_singlet("POWER_MODE", [10.0, 20.0]))
        registry.add(ArrayData.from_flat_doublet("SOLAR", [0.0, 5.0, 1000.0, 12.0]))

        arr = registry.get("SOLAR")
        val = registry.get_value("SOLAR", 500.0)
    """

    def __init__(self) -> None:
        # 内部ストレージ: キーは大文字化済み文字列
        self._arrays: dict[str, ArrayData] = {}

    # ── 登録 ─────────────────────────────────────────────────────────────

    def add(self, array_data: ArrayData) -> None:
        """配列を登録する。同名の配列が既にある場合は上書きする。

        Parameters
        ----------
        array_data: 登録する ArrayData

        Raises
        ------
        TypeError: ArrayData 以外が渡された場合
        """
        if not isinstance(array_data, ArrayData):
            raise TypeError(
                f"ArrayRegistry.add() には ArrayData を渡してください。"
                f"渡された型: {type(array_data).__name__!r}"
            )
        key = _make_key(array_data.name, array_data.submodel_path)
        self._arrays[key] = array_data

    # ── 取得 ─────────────────────────────────────────────────────────────

    def get(self, name: str, submodel_path: str = "") -> ArrayData:
        """配列を名前で取得する。

        名前解決の順序:
          1. submodel_path:name (完全修飾)
          2. name のみ

        Parameters
        ----------
        name: 配列名（大文字小文字不問）
        submodel_path: サブモデルパス（省略時は空文字）

        Returns
        -------
        ArrayData

        Raises
        ------
        KeyError: 配列が見つからない場合
        """
        # 完全修飾キーで探索
        full_key = _make_key(name, submodel_path)
        if full_key in self._arrays:
            return self._arrays[full_key]

        # サブモデルパスなしで探索（フォールバック）
        bare_key = _make_key(name, "")
        if bare_key in self._arrays:
            return self._arrays[bare_key]

        # 見つからない場合
        if submodel_path:
            tried = f"{full_key!r} または {bare_key!r}"
        else:
            tried = f"{bare_key!r}"
        raise KeyError(
            f"配列 {tried} はレジストリに登録されていません。"
            f"登録済み: {sorted(self._arrays.keys())}"
        )

    def get_value(
        self,
        name: str,
        x: float,
        submodel_path: str = "",
    ) -> float:
        """doublet 配列を取得して線形補間した値を返す。

        Parameters
        ----------
        name: doublet 配列名
        x: 補間する独立変数の値
        submodel_path: サブモデルパス（省略可）

        Returns
        -------
        float: 補間結果

        Raises
        ------
        KeyError: 配列が見つからない場合
        TypeError: singlet 配列に対して呼ばれた場合
        ValueError: extrapolation="error" かつ範囲外の場合
        """
        arr = self.get(name, submodel_path)
        return interp_linear(arr, x)

    def get_singlet_value(
        self,
        name: str,
        index: int,
        submodel_path: str = "",
    ) -> float:
        """singlet 配列を取得して index 番目の値を返す（1-based）。

        Parameters
        ----------
        name: singlet 配列名
        index: 1-based インデックス
        submodel_path: サブモデルパス（省略可）

        Returns
        -------
        float: values[index - 1]

        Raises
        ------
        KeyError: 配列が見つからない場合
        TypeError: doublet 配列に対して呼ばれた場合
        IndexError: index が範囲外の場合
        """
        arr = self.get(name, submodel_path)
        return arr.get_singlet_value(index)

    # ── ユーティリティ ────────────────────────────────────────────────────

    def __contains__(self, name: str) -> bool:
        """名前（bare key のみ）でレジストリに存在するか確認する。"""
        return _make_key(name, "") in self._arrays

    def __len__(self) -> int:
        return len(self._arrays)

    def __repr__(self) -> str:
        keys = sorted(self._arrays.keys())
        return f"ArrayRegistry({len(self._arrays)} arrays: {keys})"

    @property
    def names(self) -> list[str]:
        """登録済みの内部キーリストを返す。"""
        return sorted(self._arrays.keys())
