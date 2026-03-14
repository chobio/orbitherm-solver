# Orbitherm Solver v1.1

**Orbitherm Solver** — SINDA-like thermal network solver for steady-state and transient analysis.

SINDA/FLUINT ライクな有限差分法熱解析ソルバー（Python 実装）。  
定常解析・過渡解析・配列参照・サブルーチン実行・ヒータ制御・時間依存熱入力に対応した計算エンジン。

> **ブランド体系**
> - 親ブランド: **Orbitherm**
> - 本パッケージ: **Orbitherm Solver** （Python パッケージ名: `orbitherm_solver`、現行互換名: `thermal_solver`）
> - FreeCAD ワークベンチ（将来予定）: **Orbitherm Studio**

---

## ディレクトリ構成

```
Solver_Ver1.1/
├─ orbitherm_ui.py           # GUI 起動入口（tkinter）
├─ orbitherm_main.py         # CLI/互換ラッパー入口（subprocess 呼び出しターゲット）
├─ launch_ui.lnk             # Windows ショートカット
├─ Thermal_Ui_Icon.ico       # UI アイコン
├─ README.md
├─ requirements.txt
│
├─ thermal_solver/           # Orbitherm Solver コアパッケージ（将来: orbitherm_solver/）
│  ├─ app/
│  │  ├─ run_case.py         # 解析の共通入口（UI・CLI・FreeCAD から呼ぶ）
│  │  └─ service.py          # 薄いサービス層（OrbithermSolver クラス）
│  ├─ model/
│  │  ├─ config.py           # AnalysisConfig dataclass
│  │  ├─ node.py             # NodeData dataclass
│  │  ├─ thermal_model.py    # ThermalModel dataclass
│  │  └─ result.py           # SolverResult dataclass
│  ├─ io/
│  │  ├─ input_parser.py     # .inp ファイルパーサー
│  │  ├─ model_builder.py    # セクション→モデル変換
│  │  ├─ result_writer.py    # CSV / OUT ファイル書き出し
│  │  └─ log_writer.py       # ログ出力ユーティリティ
│  ├─ solvers/
│  │  ├─ common.py           # 共通ユーティリティ（補間・スナップショット等）
│  │  ├─ steady.py           # 定常解析（PICARD / CNFRW）
│  │  ├─ transient.py        # 過渡解析ループ（陽解法並列 / 陰解法）
│  │  ├─ implicit.py         # 陰解法ステップ（BACKWARD / CRANK_NICOLSON）
│  │  ├─ arithmetic.py       # 算術節点（熱容量=0）処理
│  │  └─ radiation.py        # 輻射ヘルパー
│  ├─ post/
│  │  └─ plotter.py          # 温度履歴グラフ描画
│  ├─ cli/
│  │  └─ main.py             # CLI エントリポイント (orbitherm-solver コマンド)
│  └─ freecad/
│     └─ bridge.py           # Orbitherm Studio 連携ブリッジ（将来実装）
│
└─ tests/
   ├─ test_smoke.py
   └─ data/
      ├─ case_steady/
      ├─ case_transient/
      ├─ case_radiation/
      └─ case_arithmetic/
```

---

## 起動方法

### GUI から実行（通常運用）

```
launch_ui.lnk をダブルクリック
  └─→ orbitherm_ui.py (Orbitherm Solver UI) が起動
        └─→ 解析実行ボタンで orbitherm_main.py を subprocess 呼び出し
```

### CLI から直接実行

```powershell
python orbitherm_main.py examples/test1.inp
python orbitherm_main.py examples/test1.inp --output results/test1 --no-input
```

### パッケージとして import して実行

```python
from thermal_solver.app.run_case import run_case  # 現行 import 名（互換維持）

result = run_case(
    input_path="examples/test1.inp",
    output_base="results/test1",
    no_input=True,
)
print(result.output_csv)
```

### OrbithermSolver サービスクラスを使用

```python
from thermal_solver.app.service import OrbithermSolver

solver = OrbithermSolver()
result = solver.run(input_path="examples/test1.inp", no_input=True)
print(result.success)
```

---

## 解析種別

| CONTROL DATA の ANALYSIS 設定 | 内容 |
|---|---|
| `TRANSIENT` | 過渡解析のみ |
| `STEADY` | 定常解析のみ |
| `STEADY_THEN_TRANSIENT` | 定常解析 → 過渡解析 |

## 過渡解法

| TRANSIENT_METHOD 設定 | 内容 |
|---|---|
| `EXPLICIT` | 陽解法（マルチプロセス並列） |
| `BACKWARD` | 後退差分陰解法 |
| `CRANK_NICOLSON` | クランク・ニコルソン法 |

---

## テスト実行

```powershell
cd E:\Themal_Analysis\Solver_Ver1.1
python -m pytest tests/ -v
```

---

## 依存パッケージのインストール

```powershell
pip install -r requirements.txt
```

---

## Orbitherm Studio 連携（将来予定）

`thermal_solver/freecad/bridge.py` に Orbitherm Studio（FreeCAD ワークベンチ）との
連携アダプタスタブを用意してある。  
Orbitherm Solver コアは pure Python で FreeCAD に依存しないため、
FreeCAD 固有コードはこのブリッジ層のみに限定できる。

---

## 命名体系と将来の移行ロードマップ

| 現在の名称 | 正式ブランド名 | 将来のパッケージ名 |
|---|---|---|
| `thermal_solver` パッケージ | **Orbitherm Solver** | `orbitherm_solver` |
| FreeCAD ワークベンチ（未実装） | **Orbitherm Studio** | `orbitherm_studio` |
| `ThermalService` クラス | **OrbithermSolver** | `OrbithermSolver` |
| `AnalysisConfig` | **OrbithermSolverConfig** | `OrbithermSolverConfig` |
| `SolverResult` | **OrbithermResult** | `OrbithermResult` |

内部パッケージのリネームは段階的に行い、既存の `thermal_solver` import は
互換ラッパーとして維持する予定。
