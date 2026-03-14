# Orbitherm Solver — メインエントリポイント
# orbitherm_main.py  v1.1
# Orbitherm Solver (thermal_solver パッケージ) の CLI 実行ラッパー
#
# [役割]
# コアロジックは thermal_solver/ パッケージ（将来: orbitherm_solver/）に集約済み。
# このファイルは orbitherm_ui.py (Orbitherm Solver UI) が subprocess で起動する
# 直接実行ターゲット。
#
# 後方互換のため、各関数は thermal_solver 配下からの再エクスポートとして
# このモジュールからも import 可能にしてある。
#
# Windows の multiprocessing（spawn モード）では
# if __name__ == "__main__" ガードが必須。

from __future__ import annotations

import os
import sys

# ── パス解決: __file__ 基準でプロジェクトルートを sys.path に追加 ────────────
# launch_ui.lnk 経由で起動した場合などカレントディレクトリが変わっても
# thermal_solver パッケージが見つかるようにする。
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── thermal_solver からコア機能を再エクスポート ──────────────────────────────
# 既存コードで `from orbitherm_main import parse_header_input` のような
# 直接インポートをしていた場合も壊れないようにする。

from thermal_solver.io.input_parser import (       # noqa: F401
    parse_header_input,
    safe_eval,
    load_initial_temperature_file,
)
from thermal_solver.io.result_writer import (      # noqa: F401
    save_final_temperature_file,
)
from thermal_solver.solvers.common import (        # noqa: F401
    SPACE_NODE_NUMBER,
    SPACE_NODE_NAME,
    _node_display_name,
    interpolate_array,
    get_node_qsrc,
    compute_output_snapshot,
    print_progress_bar,
)
from thermal_solver.solvers.steady import (        # noqa: F401
    run_steady_analysis,
    run_steady_cnfrw,
)
from thermal_solver.solvers.transient import (     # noqa: F401
    node_update_task,
)
from thermal_solver.solvers.implicit import (      # noqa: F401
    build_Qnet_and_J,
    step_implicit,
)
from thermal_solver.solvers.arithmetic import (    # noqa: F401
    solve_arithmetic_nodes,
)


def main(input_filename: str, output_base: str | None = None, interactive: bool = True) -> None:
    """Orbitherm Solver メイン処理。

    thermal_solver.app.run_case.run_case() に処理を委譲する薄いラッパー。
    引数シグネチャは従来の main(input_filename, output_base, interactive) を維持する。
    """
    from thermal_solver.app.run_case import run_case

    run_case(
        input_path=input_filename,
        output_base=output_base,
        no_input=not interactive,
        make_plot=True,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="orbitherm-solver",
        description="Orbitherm Solver — SINDA-like thermal network solver for steady-state and transient analysis.",
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

    main(
        args.input_file,
        output_base=args.output,
        interactive=not args.no_input,
    )
