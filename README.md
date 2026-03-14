# Orbitherm Solver v1.1

**Orbitherm Solver** — SINDA-like thermal network solver for steady-state and transient analysis.

SINDA/FLUINT ライクな有限差分法熱解析ソルバー（Python 実装）。  
定常解析・過渡解析・配列参照・サブルーチン実行・ヒータ制御・時間依存熱入力に対応した計算エンジン。

---

## 主な機能とデータフォーマット

### 入力ファイル（.inp）のセクション

| セクション | 説明 |
|---|---|
| `HEADER NODE DATA` | 節点定義（熱容量・境界節点・算術節点） |
| `HEADER CONDUCTOR DATA` | 熱コンダクタンス（導体・輻射） |
| `HEADER SOURCE DATA` | 節点への熱源（定数・時変 ARRAY 補間） |
| `HEADER ARRAY DATA` | 配列定義（doublet / singlet） |
| `HEADER VARIABLES 0` | 時変制御式（QI() による動的熱入力） |
| `HEADER HEATER DATA` | サーモスタット付きヒータ制御 |
| `HEADER CONTROL DATA` | 解析設定（時間範囲・解法・ANALYSIS） |
| `HEADER OPTIONS DATA` | 出力オプション（DQ・グラフ等） |

### 配列データ（ARRAY DATA）

- **doublet**: `ARR("配列名", x)` で線形補間して参照
- **singlet**: `ARRI("配列名", i)` でインデックス参照

```
HEADER ARRAY DATA
    SOLAR_HEAT,  0.0, 0.0,  500.0, 120.0,  1000.0, 0.0
    POWER_MODE,  S,   5.0, 10.0, 15.0
```

### 時変制御式（VARIABLES 0）

各タイムステップで `QI(ノード番号) = 式` により動的熱入力を設定。`TIME`・`ARR()`・`ARRI()` が利用可能。

```
HEADER VARIABLES 0
    QSOLAR = ARR("SOLAR_HEAT", TIME)
    QI(20) = QSOLAR
```

### ヒータ制御（HEATER DATA）

ヒステリシス付き ON/OFF 制御。`SENSE` ノードの温度で ON/OFF を判定し、`APPLY` ノードに `POWER` [W] を加算。

```
HEADER HEATER DATA
    BATT_HTR, SENSE=20, APPLY=20, ON=268.15, OFF=273.15, POWER=8.0
```

| キー | 説明 |
|---|---|
| SENSE | 温度監視ノード |
| APPLY | 熱入力加算ノード |
| ON | OFF→ON 閾値 [K]（この温度以下で ON） |
| OFF | ON→OFF 閾値 [K]（この温度以上で OFF） |
| POWER | ON 時の電力 [W] |
| INIT | 初期状態（ON/OFF、省略時 OFF） |
| ENABLED | 有効フラグ（YES/NO、省略時 YES） |

> 詳細は `MANUAL.md` を参照。

---

## GUI（orbitherm_ui.py）

- **起動**: `launch_ui.lnk` をダブルクリック、または `python orbitherm_ui.py`
- **操作**: 入力ファイル（.inp）を選択、出力ベース名を任意で入力し「解析を実行」
- **プログレスバー**: 過渡解析の計算進行状況をリアルタイムで表示（パーセント・ステップ数）

---

> **ブランド体系**
> - 親ブランド: **Orbitherm**
> - 本パッケージ: **Orbitherm Solver** （Python パッケージ名: `orbitherm_solver`、現行互換名: `thermal_solver`）
> - FreeCAD ワークベンチ（将来予定）: **Orbitherm Studio**

---

## ディレクトリ構成

```
orbitherm-solver/
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
│  │  ├─ heater.py           # HeaterData dataclass（HEATER DATA 定義）
│  │  └─ result.py           # SolverResult dataclass
│  ├─ runtime/
│  │  └─ heater_controller.py # HeaterController（ON/OFF 制御実行）
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
cd E:\Themal_Analysis\orbitherm-solver
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
