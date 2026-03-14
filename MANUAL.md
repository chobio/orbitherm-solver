# Orbitherm Solver — 解説・マニュアル

## 1. 概要

**Orbitherm Solver** は**熱伝導ネットワーク（ノード法）**による SINDAライク熱解析ソルバです。  
節点（ノード）と熱コンダクタンスでネットワークを定義し、**定常解析**または**過渡解析**で温度・熱流量を計算します。

### 主な機能

- **定常解析**: 収束した温度分布（PICARD 線形化反復 / CNFRW ニュートン法）
- **過渡解析**: 時間積分（陽解法 / Crank–Nicolson / 後退差分）
- **定常のち過渡**: 1回の実行で「定常→終了温度保存→過渡→終了温度保存」
- **輻射**: コンダクタンスを輻射として扱い \(Q = R\sigma(T_1^4 - T_2^4)\) で計算
- **算術節点**: 熱容量が負の節点を熱収支=0 の代数節点として扱う
- **境界節点**: 固定温度（BOUNDARY）
- **終了温度の保存・読み込み**: 解析終了温度を CSV で保存し、過渡解析の初期温度として再利用可能
- **配列データ（ARRAY DATA）**: singlet / doublet 配列を定義し、時刻などに応じた補間参照が可能
- **時変制御式（VARIABLES 0）**: 各タイムステップで評価される代入式。配列補間 ARR/ARRI を用いた時変熱入力 QI() 設定が可能
- **ヒータ制御（HEATER DATA）**: サーモスタット付きヒステリシス ON/OFF 制御ヒータ
- **GUI**: 入力ファイル選択・出力ベース名指定で実行する UI（`orbitherm_ui.py`）

---

## 2. 必要な環境

- **Python 3.10 以上**
- **ライブラリ**: numpy, pandas, matplotlib  
  - 定常 CNFRW・過渡陰解法では内部で線形ソルバを使用（NumPy）

```bash
pip install numpy pandas matplotlib
```

---

## 3. 起動方法

### 3.1 コマンドライン

```bash
python orbitherm_main.py 入力ファイル.inp [--output 出力ベース名] [--no-input]
```

- `--output`, `-o`: 出力ファイルのベース名（省略時は入力ファイル名から自動）
- `--no-input`: グラフ表示後の Enter 待ちをしない（UI・バッチ用）

### 3.2 GUI

- **起動**: `launch_ui.lnk` をダブルクリック、または `python orbitherm_ui.py`
- **操作**: 入力ファイル（.inp）を選択、出力ベース名を任意で入力し「解析を実行」

### 3.3 Python パッケージとして呼び出す

```python
from thermal_solver.app.run_case import run_case

result = run_case(
    input_path="examples/test1.inp",
    output_base="results/test1",
    no_input=True,
)
print(result.success, result.output_csv)
```

```python
from thermal_solver.app.service import OrbithermSolver

solver = OrbithermSolver()
result = solver.run("examples/test1.inp", no_input=True)
```

---

## 4. 入力ファイル形式（.inp）

UTF-8 で記述し、`END OF DATA` で終端します。

### 4.1 コメント規則

- **コメント行**: 行の先頭（空白のみ可）が `#` の行は無視
- **行中コメント**: `#` 以降は無視され、その前だけが有効

### 4.2 セクション構造

`HEADER セクション名 [, サブ名]` の次の行から、次の HEADER または `END OF DATA` までがそのセクションのデータ行です。

---

### 4.3 OPTIONS DATA

| キー | 値 | 説明 |
|------|-----|------|
| OUTPUT.DQ | TRUE / FALSE | TRUE のとき、CSV に各ノードの熱流出入量（熱入出力 [W]）を列 `{ノード名}_Q` で追加 |
| OUTPUT.GRAPH | TRUE / FALSE | 温度推移グラフの描画・保存 |

---

### 4.4 CONTROL DATA

| キー | 既定値 | 説明 |
|------|--------|------|
| TIMESTART | 0.0 | 計算開始時刻 [s] |
| TIMEND | 100.0 | 計算終了時刻 [s] |
| DT | 5.0 | 結果出力間隔 [s] |
| TIME_STEP | 0.01 | 時間積分のステップ [s] |
| STEFAN_BOLTZMANN | 5.67e-8 | ステファン・ボルツマン定数 |
| ANALYSIS | TRANSIENT | 下記「解析種別」 |
| STEADY_SOLVER | PICARD | 定常: PICARD / CNFRW |
| TRANSIENT_METHOD | EXPLICIT | 過渡: EXPLICIT / CRANK_NICOLSON / BACKWARD |
| SAVE_FINAL_TEMPERATURE | （なし） | TRUE またはファイルパスで終了温度を保存 |
| INITIAL_TEMPERATURE_FILE | （なし） | 過渡解析の初期温度 CSV パス |

**解析種別（ANALYSIS）**

- **TRANSIENT**: 過渡解析のみ
- **STEADY**: 定常解析のみ
- **STEADY_THEN_TRANSIENT**（別名: STEADY_TRANSIENT, 定常のち過渡）  
  定常→終了温度保存→過渡→終了温度保存を 1 回の実行で実施

---

### 4.5 NODE DATA [, グループ名]

1行: `ノード番号, 初期温度[℃], 熱容量またはBOUNDARY`

- **熱容量**: 正の数 [J/K]。内部では温度は [K] で保持。
- **BOUNDARY**: 境界節点（固定温度）。熱容量は持たない。
- **熱容量が負**（例: -1.0）: **算術節点**。熱容量 0 として熱収支=0 の式で温度を求める。
- **ノード番号が負**（例: -3）: 境界節点として扱う（数値の符号で BOUNDARY を指定する書式）。

グループがある場合、節点ラベルは `グループ名.ノード番号`（例: SUB1.10）。  
CONDUCTOR で他グループを参照するときは `SUB1.15` のように書く。

```
HEADER NODE DATA, MAIN
    1,  25.0,  500.0    # 通常節点: 初期温度25℃, 熱容量500 J/K
    2,  25.0,   -1.0    # 算術節点: 熱容量<0
    -3, 20.0,    1.0    # 境界節点: ノード番号を負にして指定
```

---

### 4.6 CONDUCTOR DATA [, グループ名]

1行: `導体番号, ノード1, ノード2, コンダクタンス[W/K]`

- **導体番号が正**: 通常の熱コンダクタンス。熱流量 \(Q = G(T_1 - T_2)\)。
- **導体番号がマイナス**（例: -2099）: **輻射**として扱う。  
  \(Q = R \sigma (T_1^4 - T_2^4)\)。時間積分時は線形化で安定化、T は 1～5000 K にクランプ。

グループが GLOBAL のときはノード名をそのまま（例: GLOBAL.1, SUB1.10）。  
他グループの CONDUCTOR では `グループ.番号` で指定。

```
HEADER CONDUCTOR DATA, MAIN
    12,   1, 2,  5.0    # 通常コンダクタンス 5 W/K
    -10,  1, 3,  1.0    # 輻射コンダクタ R=1.0 m^2（番号が負）
```

---

### 4.7 SOURCE DATA [, グループ名]

1行（定数熱源）: `ノード番号, 熱源 [W]`  

1行（時変・配列補間）: `ノード番号, ARRAY, LINEAR|STEP, (時刻1, 値1), (時刻2, 値2), ...`
- **LINEAR**: 線形補間  
- **STEP**: ステップ補間（変化点まで前の値を維持し、変化点で即時切り替え）

熱源はノードへの正の熱流入 [W] として扱います。

```
HEADER SOURCE DATA, MAIN
    1,  10.0                                    # 定数 10W
    2,  ARRAY, LINEAR, (0.0, 5.0), (100.0, 20.0)  # 時変: 線形補間
    3,  ARRAY, STEP,   (0.0, 0.0), (50.0, 15.0)   # 時変: ステップ
```

---

### 4.8 ARRAY DATA（配列定義）

VARIABLES 0 の ARR/ARRI 関数や SOURCE DATA の補間テーブルとは独立して、  
名前付き配列を定義するセクションです。

**doublet 配列**（線形補間テーブル）:
```
配列名, x0, y0, x1, y1, ...
配列名, EXTRAP=LINEAR, x0, y0, x1, y1, ...   # 範囲外: 線形外挿
```

**singlet 配列**（インデックス参照テーブル）:
```
配列名, S, v1, v2, v3, ...
```

| 配列タイプ | アクセス方法 | 説明 |
|---|---|---|
| doublet | `ARR("配列名", x)` | x を独立変数として線形補間。x は厳密単調増加で2点以上必要 |
| singlet | `ARRI("配列名", i)` | i 番目（1-based）の値を返す |

**EXTRAP オプション**（doublet のみ）:

| 値 | 挙動 |
|---|---|
| `EXTRAP=CLAMP`（既定） | 範囲外は端点の値に固定 |
| `EXTRAP=LINEAR` | 範囲外は端点から線形外挿 |
| `EXTRAP=ERROR` | 範囲外は例外を送出 |

```
HEADER ARRAY DATA
    SOLAR_HEAT,  0.0, 0.0,  500.0, 120.0, 1000.0, 0.0   # doublet: 時刻→太陽熱入力
    POWER_MODE,  S,   5.0, 10.0, 15.0                    # singlet: モード別消費電力
    TIDE_TABLE,  EXTRAP=LINEAR, 0.0, 10.0, 3600.0, 40.0  # doublet: 線形外挿あり
```

---

### 4.9 VARIABLES 0（時変制御式）

各タイムステップの計算前に評価される代入式のブロックです。  
SINDA/FLUINT の VARIABLES 0 に相当します。

**書式**:
```
変数名 = 式
QI(ノード番号) = 式
```

**使用できる要素**:

| 要素 | 説明 |
|---|---|
| `TIME` | 現在の時刻 [s]（組み込み変数） |
| `ARR("配列名", x)` | doublet 配列を x で線形補間して返す |
| `ARRI("配列名", i)` | singlet 配列の i 番目（1-based）を返す |
| `QI(n) = 値` | ノード n に動的外部熱入力 [W] を設定（左辺ターゲット） |
| `変数名` | 同ブロック内で前に定義した変数を参照できる |
| `+ - * /` | 四則演算 |
| 数値リテラル | 整数・浮動小数点数 |

**注意事項**:
- 式の評価は AST 安全検証を経て実行されます。属性アクセス・import・lambda など危険な構文は拒否されます。
- `QI(n) = ...` は左辺専用です。右辺の式では `QI()` は使用できません。
- 代入は記述順に逐次評価されます（上の変数を下の式で参照可能）。
- `QI(n)` で設定した動的熱入力は毎ステップ先頭でクリアされ、そのステップの評価結果だけが有効です。
- ヒータ制御（HEATER DATA）による熱入力は VARIABLES 0 の QI 値への**加算**で処理されます。

```
HEADER VARIABLES 0
    QSOLAR   = ARR("SOLAR_HEAT", TIME)          # 太陽熱入力 [W]
    QMODE    = ARRI("POWER_MODE", 1)            # モード1の消費電力
    QTOTAL   = QSOLAR + QMODE
    QI(20)   = QTOTAL                           # ノード20 に QTOTAL [W] を設定
    QI(30)   = ARR("SOLAR_HEAT", TIME) * 0.5   # ノード30 に太陽熱の半分を設定
```

---

### 4.10 HEATER DATA（サーモスタット付きヒータ）

ヒステリシス付き ON/OFF 制御ヒータを定義するセクションです。  
各タイムステップで感知ノードの温度を監視し、ON/OFF を判定して熱入力を加算します。

**書式**:
```
ヒータ名, SENSE=n, APPLY=n, ON=温度[K], OFF=温度[K], POWER=電力[W] [, INIT=ON|OFF] [, ENABLED=YES|NO]
```

| キー | 必須 | 説明 |
|---|---|---|
| `SENSE=n` | ○ | 温度を監視するノード番号（整数） |
| `APPLY=n` | ○ | 熱入力を加えるノード番号（整数） |
| `ON=t` | ○ | ON になる温度閾値 [K]（この温度以下で ON） |
| `OFF=t` | ○ | OFF になる温度閾値 [K]（この温度以上で OFF） |
| `POWER=w` | ○ | ON 時の電力 [W]（正値） |
| `INIT=ON\|OFF` | − | 初期状態（省略時: OFF） |
| `ENABLED=YES\|NO` | − | ヒータ有効フラグ（省略時: YES） |

**制御仕様（ヒステリシス制御）**:

| 条件 | 状態 |
|---|---|
| 感知ノード温度 ≤ ON 温度 | → ON |
| 感知ノード温度 ≥ OFF 温度 | → OFF |
| ON 温度 < 温度 < OFF 温度 | → 前状態を維持（不感帯） |

> **例**: ON=268.15 K (-5℃), OFF=273.15 K (0℃) の場合、-5℃以下で ON、0℃以上で OFF、-5～0℃の間は前状態維持。

```
HEADER HEATER DATA
    BATT_HTR,     SENSE=20, APPLY=20, ON=268.15, OFF=273.15, POWER=8.0
    AVIONICS_HTR, SENSE=31, APPLY=35, ON=265.15, OFF=270.15, POWER=4.5, INIT=ON
    SPARE_HTR,    SENSE=20, APPLY=20, ON=263.15, OFF=268.15, POWER=2.0, ENABLED=NO
```

---

## 5. 解析の種類とアルゴリズム

### 5.1 定常解析（ANALYSIS = STEADY）

- **PICARD（既定）**: 輻射を T_ref まわりで線形化し、K·T = RHS を反復（最大 200 回、tol=1e-6）。
- **CNFRW**: ニュートン法。残差 R(T) とヤコビアン J を計算し、J·ΔT = −R を解いて T を更新。T は 1～5000 K にクランプ。

### 5.2 過渡解析（ANALYSIS = TRANSIENT）

- **EXPLICIT**: 前進オイラー。並列可能。
- **BACKWARD**: 後退差分。毎ステップ (C/dt)·I − J の線形系を解く。
- **CRANK_NICOLSON**: θ=0.5 の陰解法。算術節点は C=0 の行として同じ線形系に含める。

各タイムステップの処理順序（VARIABLES 0 / HEATER DATA がある場合）:

1. VARIABLES 0 を評価（ARR/ARRI で配列を参照、QI() でノード熱入力を設定）
2. HEATER DATA の制御ループを実行（ON/OFF を判定し dynamic_heat_input に加算）
3. 算術節点の温度を熱収支=0 で更新
4. 全ノードの温度を積分（EXPLICIT / BACKWARD / CRANK_NICOLSON）

### 5.3 定常のち過渡（ANALYSIS = STEADY_THEN_TRANSIENT）

1. 定常解析を実行  
2. 終了温度を `{出力ベース名}_steady_final_temperature.csv` に保存  
3. その温度を初期値として過渡解析を実行（TIMESTART～TIMEND）  
4. 過渡終了温度を `{出力ベース名}_final_temperature.csv` に保存  

CSV・.out・グラフには「定常の 1 時刻 + 過渡の全出力時刻」が含まれます。

---

## 6. 終了温度の保存と再利用

### 6.1 保存

- **SAVE_FINAL_TEMPERATURE = TRUE**: 解析終了時、`{出力ベース名}_final_temperature.csv` に保存。
- **SAVE_FINAL_TEMPERATURE = ファイルパス**: 指定パスに保存。
- **STEADY_THEN_TRANSIENT** のときは、定常用・過渡用の 2 ファイルを自動保存するため、上記オプションは不要。

保存形式: CSV の 1 行目 `node,T_C`、2 行目以降 `節点名, 温度[℃]`。

### 6.2 過渡の初期温度として読み込み

- **INITIAL_TEMPERATURE_FILE = ファイルパス**: 過渡解析の初期温度をその CSV から読み込む。  
  ファイルに存在する節点だけ NODE DATA の初期温度を上書き。節点名は .inp のラベルと一致させる。

---

## 7. 出力ファイル

| ファイル名 | 内容 |
|---|---|
| `{ベース名}_mp.csv` | 時刻ごとの各節点温度 [℃]。OUTPUT.DQ=TRUE のときは `{ノード名}_Q` 列を追加 |
| `{ベース名}.out` | 各出力時刻のノード温度・発熱・熱入出力・コンダクタンス熱流量の詳細テキスト |
| `{ベース名}.log` | 実行ログ |
| `{ベース名}_mp.png` | 温度推移グラフ（OUTPUT.GRAPH=TRUE のとき） |
| `{ベース名}_final_temperature.csv` | 終了温度（SAVE_FINAL_TEMPERATURE または STEADY_THEN_TRANSIENT 時） |
| `{ベース名}_steady_final_temperature.csv` | 定常終了温度（STEADY_THEN_TRANSIENT 時のみ） |

過渡解析では、最後の 2 出力時刻の最大温度変化が 0.01℃ 未満のとき「定常収束」と表示されます。

---

## 8. ファイル構成

```
orbitherm_main.py          # メインソルバ（CLI エントリポイント）
orbitherm_ui.py            # GUI（Orbitherm Solver 実行 UI）
launch_ui.lnk              # Windows ショートカット
Thermal_Ui_Icon.ico        # UI 用アイコン
pyproject.toml             # パッケージ設定（name: orbitherm-solver）
requirements.txt
README.md
MANUAL.md                  # 本マニュアル
thermal_solver/            # Orbitherm Solver コアパッケージ
  app/                     # run_case(), OrbithermSolver サービス
  model/                   # AnalysisConfig, ThermalModel, SolverResult 等
  io/                      # .inp パーサー、結果書き出し
  solvers/                 # 定常・過渡・輻射・算術節点
  runtime/                 # 配列レジストリ・VARIABLES 0 実行エンジン・ヒータ制御
  post/                    # グラフ描画
  cli/                     # orbitherm-solver コマンド
  subroutines/             # 補間ユーティリティ
  freecad/                 # Orbitherm Studio 連携ブリッジ（将来実装）
tests/
  data/
    case_steady/           # 定常解析リグレッションケース
    case_transient/        # 過渡解析リグレッションケース
    case_radiation/        # 輻射コンダクタケース
    case_arithmetic/       # 算術節点ケース
examples/
```

---

## 9. 入力例

### 9.1 基本構成（CONTROL まわり）

```
HEADER OPTIONS DATA
    OUTPUT.DQ    = FALSE
    OUTPUT.GRAPH = TRUE

HEADER CONTROL DATA
    TIMESTART = 0.0
    TIMEND    = 600.0
    DT        = 100.0
    TIME_STEP = 0.1
    STEFAN_BOLTZMANN = 5.67e-8
    ANALYSIS          = STEADY_THEN_TRANSIENT
    STEADY_SOLVER     = CNFRW
    TRANSIENT_METHOD  = BACKWARD
    SAVE_FINAL_TEMPERATURE = TRUE
```

### 9.2 算術節点・輻射コンダクタの組み合わせ

```
HEADER NODE DATA, MAIN
    1,  50.0,  200.0     # 通常節点
    2,  25.0,   -1.0     # 算術節点（熱容量 < 0）
    -3,  0.0,    1.0     # 境界節点（番号が負）

HEADER CONDUCTOR DATA, MAIN
    12,  1, 2,  5.0      # 通常コンダクタンス
    -99, 1, 3,  1.0e-4   # 輻射コンダクタ（番号が負）
```

### 9.3 ARRAY DATA と VARIABLES 0 による時変熱入力

```
HEADER ARRAY DATA
    SOLAR_HEAT,  0.0, 0.0,  1800.0, 120.0,  3600.0, 0.0   # 軌道1周期の太陽熱
    MODE_POWER,  S,   5.0,  10.0,  20.0                    # モード別電力 [W]

HEADER VARIABLES 0
    QSUN     = ARR("SOLAR_HEAT", TIME)       # 時刻 TIME での太陽熱入力
    QELEC    = ARRI("MODE_POWER", 1)         # モード1の電力: 5 W
    QTOTAL   = QSUN + QELEC
    QI(10)   = QTOTAL                        # ノード10 に合計熱入力を設定

HEADER NODE DATA, MAIN
    10, 20.0, 500.0
    -99, -270.0, 1.0

HEADER CONDUCTOR DATA, MAIN
    -1, 10, 99, 2.5e-5
```

### 9.4 HEATER DATA によるサーモスタット制御

```
HEADER NODE DATA, MAIN
    10, 20.0, 1000.0     # 電池ノード（監視+加熱対象）
    20, 20.0,  500.0     # 電装ノード（監視）
    21, 20.0,  300.0     # 電装ノード（加熱対象）
    -99, -270.0, 1.0     # 宇宙空間境界節点

HEADER HEATER DATA
    BATT_HTR,     SENSE=10, APPLY=10, ON=268.15, OFF=273.15, POWER=8.0
    AVIONICS_HTR, SENSE=20, APPLY=21, ON=265.15, OFF=270.15, POWER=4.5, INIT=ON

HEADER CONDUCTOR DATA, MAIN
    -1, 10, 99, 1.0e-5
    -2, 20, 99, 8.0e-6
    23, 20, 21, 2.0
```

---

## 10. セクション一覧（対応状況）

| セクション | 対応 | 説明 |
|---|---|---|
| `HEADER OPTIONS DATA` | ✓ | OUTPUT.DQ / OUTPUT.GRAPH |
| `HEADER CONTROL DATA` | ✓ | 解析設定・時間設定 |
| `HEADER NODE DATA [, グループ]` | ✓ | 節点定義 |
| `HEADER CONDUCTOR DATA [, グループ]` | ✓ | コンダクタンス・輻射定義 |
| `HEADER SOURCE DATA [, グループ]` | ✓ | 定数・時変熱源 |
| `HEADER ARRAY DATA` | ✓ | singlet / doublet 配列定義 |
| `HEADER VARIABLES 0` | ✓ | タイムステップ毎の制御式（ARR/ARRI/QI） |
| `HEADER HEATER DATA` | ✓ | サーモスタット付きヒータ制御 |

---

## 11. 注意事項・制限

- **温度単位**: 入力・出力ともに **℃**。内部計算は **K** で行います（273.15 を加算）。
- **HEATER DATA の ON/OFF 温度**: 内部は **K** で比較します。入力値もすべて **K** で指定してください。
- **VARIABLES 0 の QI**: ステップ毎にクリアされるため、値を持続させたい場合は毎ステップ再設定が必要です。
- **複数ヒータが同一ノードに向いている場合**: dynamic_heat_input に加算（上書きではない）されます。
- **算術節点（C < 0）**: 定常・過渡ともに熱収支=0 で温度を代数的に決定します。熱容量を持たないため、過渡解析での時間積分ステップには参加しません。
- **輻射コンダクタ**: 温度は 1～5000 K にクランプして計算します。
- **EXPLICIT 法**: タイムステップが大きすぎると発散することがあります。`TIME_STEP` を小さくするか、`BACKWARD` / `CRANK_NICOLSON` に切り替えてください。
