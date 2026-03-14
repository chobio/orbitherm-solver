"""Orbitherm Solver CLI エントリポイント。

Orbitherm Solver（thermal_solver パッケージ）を直接 CLI から実行するためのモジュール。
orbitherm_main.py との互換を維持しつつ、将来は pyproject.toml の
[project.scripts] エントリポイントとして `orbitherm-solver` コマンド名で登録可能。

使用例:
    python -m thermal_solver.cli.main input.inp [--output basename] [--no-input]
    orbitherm-solver input.inp  (pyproject.toml 登録後)
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    """CLI メイン関数。argparse で引数を処理して run_case() を呼ぶ。"""
    # thermal_solver パッケージが見つからない場合に備えてパスを調整
    _here = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from thermal_solver.app.run_case import run_case

    parser = argparse.ArgumentParser(
        prog="orbitherm-solver",
        description=(
            "Orbitherm Solver — SINDA-like thermal network solver "
            "for steady-state and transient analysis."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_file", nargs="?", help="入力ファイル (.inp)")
    parser.add_argument(
        "--output", "-o",
        metavar="BASENAME",
        help="出力ファイルのベース名（拡張子なし）。省略時は入力ファイル名から自動",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="グラフ表示後のEnter待ちをしない（UI/バッチ用）",
    )
    args = parser.parse_args()

    if not args.input_file:
        parser.print_help()
        sys.exit(1)

    run_case(
        input_path=args.input_file,
        output_base=args.output,
        no_input=args.no_input,
    )


if __name__ == "__main__":
    main()
