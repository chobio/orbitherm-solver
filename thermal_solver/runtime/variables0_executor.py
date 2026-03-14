"""VARIABLES 0 評価エンジン。

SINDA/FLUINT の HEADER VARIABLES 0 ブロックを安全に逐次評価する。
各代入文を上から順に評価し、結果を Variables0Runtime または
ThermalModel.dynamic_heat_input に書き込む。

安全設計:
  - ast.parse(mode="eval") で構文木を生成
  - AST の全ノードを許可リストで事前検証
  - eval() は使用しない
  - 許可する AST ノード: 数値・文字列リテラル、変数名、四則演算、ARR/ARRI 呼び出し
  - 禁止: Attribute アクセス、Import、Lambda、ListComp、Dict、Subscript、任意関数呼び出し

左辺ターゲットの種類:
  - 通常変数 (例: QEXT)    → Variables0Runtime.values に格納
  - QI(node) (例: QI(20)) → ThermalModel.dynamic_heat_input に書き込む

将来拡張ポイント:
  - T(node)=value:  _assign_target() に T ターゲット分岐を追加
  - QR(node)=value: 同上、輻射熱源フィールドへの書き込み
  - SIN/COS/EXP:   _ALLOWED_FUNCTIONS に追加し _eval_call() に分岐を追加
  - 条件分岐 (IF):  _eval_node() に ast.IfExp を追加
  - サブモデルスコープ: _eval_expression() の submodel_path を引き回す
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..model.variables0 import Variables0Assignment
    from ..model.thermal_model import ThermalModel

from .array_registry import ArrayRegistry
from .variables0_functions import Variables0Functions

# ── 許可 AST ノード型 ─────────────────────────────────────────────────────────

_ALLOWED_NODE_TYPES: frozenset = frozenset({
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Call,
})

for _legacy_name in ("Num", "Str"):
    _node = getattr(ast, _legacy_name, None)
    if _node is not None:
        _ALLOWED_NODE_TYPES = _ALLOWED_NODE_TYPES | {_node}

# 許可する関数名（大文字で比較）
_ALLOWED_FUNCTIONS: frozenset[str] = frozenset({"ARR", "ARRI"})

# 将来拡張: _ALLOWED_FUNCTIONS |= {"SIN", "COS", "EXP"}

# QI ターゲット正規表現: "QI(20)" / "qi(20)" / "QI( 20 )" / "QI()" にマッチ
# [^)]* で空カッコ QI() も捕捉し、_assign_qi_target で空チェックを行う
_QI_TARGET_RE = re.compile(r"^QI\s*\(([^)]*)\)\s*$", re.IGNORECASE)

# 将来拡張: T(node), QR(node) 等の正規表現をここに追加
# _T_TARGET_RE  = re.compile(r"^T\s*\((.+)\)\s*$", re.IGNORECASE)
# _QR_TARGET_RE = re.compile(r"^QR\s*\((.+)\)\s*$", re.IGNORECASE)


# ══════════════════════════════════════════════════════════════════════════════
# 実行時レジスタ
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Variables0Runtime:
    """VARIABLES 0 の評価結果を保持するレジスタ辞書。

    変数名 → float のシンプルなマッピング。
    VARIABLES 0 内で計算された中間変数はここに蓄積される。
    """

    values: dict[str, float] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Variables0Runtime({dict(self.values)})"


# ══════════════════════════════════════════════════════════════════════════════
# 実行エンジン
# ══════════════════════════════════════════════════════════════════════════════

class Variables0Executor:
    """VARIABLES 0 ブロックを時刻付きで逐次評価するエンジン。

    通常変数への代入と QI(node)=... による動的熱入力設定の両方を処理する。

    Parameters
    ----------
    array_registry: 配列参照元の ArrayRegistry
    submodel_path: デフォルトのサブモデルパス
    model: ThermalModel への参照（QI 代入に必要）

    Notes
    -----
    execute() の先頭で model.dynamic_heat_input.clear() が呼ばれる（model が設定時）。
    これにより前ステップの QI 値が残り続けることを防ぐ。
    """

    def __init__(
        self,
        array_registry: ArrayRegistry,
        submodel_path: str = "",
        model: Optional["ThermalModel"] = None,
    ) -> None:
        if not isinstance(array_registry, ArrayRegistry):
            raise TypeError(
                f"Variables0Executor には ArrayRegistry を渡してください。"
                f"渡された型: {type(array_registry).__name__!r}"
            )
        self._v0_functions = Variables0Functions(
            array_registry,
            submodel_path=submodel_path,
            model=model,
        )
        self._submodel_path = submodel_path
        self._model = model

    def execute(
        self,
        assignments: list["Variables0Assignment"],
        time_value: float,
        runtime: Optional[Variables0Runtime] = None,
    ) -> Variables0Runtime:
        """代入文リストを逐次評価して Variables0Runtime と dynamic_heat_input を更新する。

        実行フロー:
          1. model が設定されていれば dynamic_heat_input.clear()
          2. 各代入文を上から順に rhs 評価 → _assign_target()
          3. runtime を返す

        Parameters
        ----------
        assignments: Variables0Assignment のリスト（記述順に評価）
        time_value: 現在の時刻 [s]（式中の TIME に束縛）
        runtime: 既存レジスタ（省略時は新規作成）

        Returns
        -------
        Variables0Runtime: 評価後のレジスタ

        Notes
        -----
        dynamic_heat_input はこのメソッドの先頭でクリアされる。
        これにより各タイムステップで不要な QI 値が残留しない。
        """
        if runtime is None:
            runtime = Variables0Runtime()

        # 前ステップの動的熱入力を消去（QI 指定があったノードのみ残る）
        if self._model is not None:
            self._model.dynamic_heat_input.clear()

        for asgn in assignments:
            submodel = asgn.submodel_path or self._submodel_path
            try:
                value = self._eval_expression(
                    asgn.expression, runtime, float(time_value), submodel
                )
            except (NameError, TypeError, ValueError, SyntaxError,
                    ZeroDivisionError, KeyError, IndexError) as e:
                raise type(e)(
                    f"VARIABLES 0 評価エラー: {asgn.target!r} = {asgn.expression!r}\n"
                    f"  原因: {e}"
                ) from e

            self._assign_target(asgn.target, value, runtime, submodel_path=submodel)

        return runtime

    def _eval_expression(
        self,
        expr: str,
        runtime: Variables0Runtime,
        time_value: float,
        submodel_path: str = "",
    ) -> float:
        """式文字列を安全に評価して float を返す。"""
        try:
            tree = ast.parse(expr.strip(), mode="eval")
        except SyntaxError as e:
            raise SyntaxError(
                f"VARIABLES 0 式の構文エラー: {expr!r}: {e}"
            ) from e

        _validate_ast_safety(tree)
        return _eval_node(
            tree.body, runtime, time_value, self._v0_functions, submodel_path
        )

    def _assign_target(
        self,
        target: str,
        value: float,
        runtime: Variables0Runtime,
        submodel_path: str = "",
    ) -> None:
        """代入先に value を書き込む。

        ターゲット判定:
          "QI(N)" → QI ターゲット: ThermalModel.dynamic_heat_input に書き込む
          それ以外 → register 変数: runtime.values に書き込む

        将来拡張ポイント:
          "T(N)"  → self._assign_t_target(inner, value, submodel_path)
          "QR(N)" → self._assign_qr_target(inner, value, submodel_path)
          条件: _T_TARGET_RE / _QR_TARGET_RE と同様の正規表現を追加する
        """
        m = _QI_TARGET_RE.match(target.strip())
        if m:
            inner = m.group(1).strip()
            self._assign_qi_target(inner, value, submodel_path)
            return

        # 通常変数代入
        runtime.values[target] = value

    def _assign_qi_target(
        self,
        node_ref_str: str,
        value: float,
        submodel_path: str,
    ) -> None:
        """QI(node) ターゲットを処理して dynamic_heat_input に書き込む。

        現在対応: 整数 node id のみ（例: QI(20)）
        将来対応: 文字列ラベル（例: QI("BATTERY")）

        Raises
        ------
        RuntimeError: model が設定されていない場合
        ValueError: node_ref_str が空の場合
        TypeError: 整数以外の node_ref が指定された場合（現在の制限）
        """
        if self._model is None:
            raise RuntimeError(
                "QI target requires a model instance. "
                "Pass model= to Variables0Executor()."
            )

        if not node_ref_str:
            raise ValueError(
                "Invalid QI target syntax: 'QI()' - node id is required."
            )

        # 将来: 文字列ラベル "BATTERY" に対応する場合は、ここで分岐を追加する
        # if node_ref_str.startswith('"') or node_ref_str.startswith("'"):
        #     label = node_ref_str.strip('"\'')
        #     self._v0_functions.set_qi(label, value, submodel_path)
        #     return

        # 整数 node id として解釈
        try:
            node_id = int(node_ref_str)
        except ValueError:
            raise TypeError(
                f"QI target currently supports integer node ids only. "
                f"Got: 'QI({node_ref_str})'. "
                f"To use string labels like QI(\"BATTERY\"), future extension needed."
            )

        self._v0_functions.set_qi(node_id, value, submodel_path)


# ══════════════════════════════════════════════════════════════════════════════
# AST 安全検証 (プライベート)
# ══════════════════════════════════════════════════════════════════════════════

def _validate_ast_safety(tree: ast.AST) -> None:
    """AST 全ノードを走査し、許可リスト外の型があれば TypeError を送出する。"""
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODE_TYPES:
            raise TypeError(
                f"VARIABLES 0 式に許可されていない要素 {type(node).__name__!r} が含まれています。\n"
                f"使用可能: 数値リテラル, 変数名(TIME を含む), "
                f"四則演算 (+ - * /), ARR(), ARRI()"
            )


# ══════════════════════════════════════════════════════════════════════════════
# AST 評価 (プライベート)
# ══════════════════════════════════════════════════════════════════════════════

def _eval_node(
    node: ast.AST,
    runtime: Variables0Runtime,
    time_value: float,
    v0_functions: Variables0Functions,
    submodel_path: str,
) -> Any:
    """AST ノードを再帰的に評価する。"""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        return float(node.value)

    if hasattr(ast, "Num") and isinstance(node, getattr(ast, "Num")):
        return float(node.n)  # type: ignore[attr-defined]
    if hasattr(ast, "Str") and isinstance(node, getattr(ast, "Str")):
        return node.s  # type: ignore[attr-defined]

    if isinstance(node, ast.Name):
        name = node.id
        if name == "TIME":
            return time_value
        if name in runtime.values:
            return runtime.values[name]
        raise NameError(
            f"Undefined variable '{name}' in VARIABLES 0 expression\n"
            f"  定義済み変数: {sorted(runtime.values.keys())}"
        )

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, runtime, time_value, v0_functions, submodel_path)
        right = _eval_node(node.right, runtime, time_value, v0_functions, submodel_path)
        return _apply_binop(node.op, float(left), float(right))

    if isinstance(node, ast.UnaryOp):
        operand = float(
            _eval_node(node.operand, runtime, time_value, v0_functions, submodel_path)
        )
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return operand
        raise TypeError(f"未サポートの単項演算子: {type(node.op).__name__!r}")

    if isinstance(node, ast.Call):
        return _eval_call(node, runtime, time_value, v0_functions, submodel_path)

    raise TypeError(f"未サポートの AST ノード型: {type(node).__name__!r}")


def _apply_binop(op: ast.operator, left: float, right: float) -> float:
    """二項演算子を適用する。"""
    if isinstance(op, ast.Add):
        return left + right
    if isinstance(op, ast.Sub):
        return left - right
    if isinstance(op, ast.Mult):
        return left * right
    if isinstance(op, ast.Div):
        if right == 0.0:
            raise ZeroDivisionError("VARIABLES 0 式でゼロ除算が発生しました。")
        return left / right
    raise TypeError(f"未サポートの二項演算子: {type(op).__name__!r}")


def _eval_call(
    node: ast.Call,
    runtime: Variables0Runtime,
    time_value: float,
    v0_functions: Variables0Functions,
    submodel_path: str,
) -> float:
    """Call ノードを評価する。ARR/ARRI のみ許可。"""
    if not isinstance(node.func, ast.Name):
        raise TypeError(
            "VARIABLES 0 式では直接の関数名のみ使用できます（属性アクセス不可）。"
        )

    func_name = node.func.id.upper()
    if func_name not in _ALLOWED_FUNCTIONS:
        raise NameError(
            f"Function '{node.func.id}' is not allowed in VARIABLES 0 expression\n"
            f"  使用可能な関数: {sorted(_ALLOWED_FUNCTIONS)}"
        )

    if node.keywords:
        raise TypeError(
            f"VARIABLES 0 の {func_name}() ではキーワード引数は使用できません。"
        )

    if func_name == "ARR":
        if len(node.args) < 2:
            raise TypeError(
                f"ARR() requires 2 arguments: ARR(name, x). "
                f"Got {len(node.args)} argument(s)."
            )
        name = _extract_string_literal(node.args[0], "ARR")
        x = float(
            _eval_node(node.args[1], runtime, time_value, v0_functions, submodel_path)
        )
        return v0_functions.ARR(name, x, submodel_path)

    if func_name == "ARRI":
        if len(node.args) < 2:
            raise TypeError(
                f"ARRI() requires 2 arguments: ARRI(name, index). "
                f"Got {len(node.args)} argument(s)."
            )
        name = _extract_string_literal(node.args[0], "ARRI")
        index_val = _eval_node(
            node.args[1], runtime, time_value, v0_functions, submodel_path
        )
        try:
            index_int = int(float(index_val))
        except (TypeError, ValueError) as e:
            raise TypeError(
                f"ARRI requires second argument to evaluate to an integer. Got: {index_val!r}"
            ) from e
        if float(index_val) != index_int:
            raise TypeError(
                f"ARRI requires second argument to evaluate to an integer. "
                f"Got non-integer: {index_val!r}"
            )
        return v0_functions.ARRI(name, index_int, submodel_path)

    raise NameError(
        f"Function '{func_name}' is not allowed in VARIABLES 0 expression"
    )


def _extract_string_literal(node: ast.AST, func_name: str) -> str:
    """AST ノードから文字列リテラルを抽出する。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if hasattr(ast, "Str") and isinstance(node, getattr(ast, "Str")):
        return node.s  # type: ignore[attr-defined]
    raise TypeError(
        f"{func_name} requires first argument to be a string literal. "
        f"Got: {ast.dump(node)!r}"
    )
