# Orbitherm Solver — 実行 UI
# 入力ファイル選択・出力ファイル名指定で orbitherm_main.py を実行

import os
import re
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox


def get_script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def run_thermal():
    input_path = inp_var.get().strip()
    output_base = out_var.get().strip()

    if not input_path:
        messagebox.showerror("エラー", "入力ファイルを選択してください。")
        return
    if not os.path.isfile(input_path):
        messagebox.showerror("エラー", f"入力ファイルが見つかりません:\n{input_path}")
        return

    script_dir = get_script_dir()
    script_path = os.path.join(script_dir, "orbitherm_main.py")
    if not os.path.isfile(script_path):
        messagebox.showerror("エラー", f"orbitherm_main.py が見つかりません:\n{script_path}")
        return

    cmd = [sys.executable, script_path, os.path.normpath(input_path), "--no-input"]
    if output_base:
        cmd.extend(["--output", output_base])

    log_area.delete("1.0", tk.END)
    log_area.insert(tk.END, f"実行: {' '.join(cmd)}\n\n")
    log_area.see(tk.END)

    run_btn.config(state=tk.DISABLED)
    progress_var.set(0)
    progress_label_var.set("待機中...")

    def run_subprocess():
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                cmd,
                cwd=script_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=0,
                env=env,
            )

            # \r と \n の両方でバッファを分割して進捗行を検出する
            buf = ""
            _PROGRESS_RE = re.compile(r"計算進行状況.*?(\d+\.\d+)%.*?(\d+)/(\d+)")
            while True:
                ch = proc.stdout.read(1)
                if not ch:
                    break
                if ch in ("\r", "\n"):
                    line = buf
                    buf = ""
                    if not line:
                        continue
                    m = _PROGRESS_RE.search(line)
                    if m:
                        pct = float(m.group(1))
                        cur = int(m.group(2))
                        total = int(m.group(3))
                        def update_progress(p=pct, c=cur, t=total):
                            progress_var.set(p)
                            progress_label_var.set(f"{p:.1f}%  ({c}/{t}ステップ)")
                        root.after(0, update_progress)
                    else:
                        def append(l=line):
                            log_area.insert(tk.END, l + "\n")
                            log_area.see(tk.END)
                            log_area.update_idletasks()
                        root.after(0, append)
                else:
                    buf += ch

            # バッファ残りを出力
            if buf.strip():
                def append_rest(l=buf):
                    log_area.insert(tk.END, l + "\n")
                    log_area.see(tk.END)
                root.after(0, append_rest)

            proc.wait()

            def done():
                run_btn.config(state=tk.NORMAL)
                if proc.returncode == 0:
                    progress_var.set(100)
                    progress_label_var.set("完了  100%")
                    messagebox.showinfo("完了", "解析が正常に完了しました。")
                else:
                    progress_label_var.set("エラー終了")
                    messagebox.showerror("エラー", f"終了コード: {proc.returncode}")
            root.after(0, done)

        except Exception as e:
            def fail():
                run_btn.config(state=tk.NORMAL)
                progress_label_var.set("エラー")
                log_area.insert(tk.END, f"\nエラー: {e}\n")
                messagebox.showerror("エラー", str(e))
            root.after(0, fail)

    threading.Thread(target=run_subprocess, daemon=True).start()


def browse_input():
    path = filedialog.askopenfilename(
        title="入力ファイルを選択",
        initialdir=get_script_dir(),
        filetypes=[("INPファイル", "*.inp"), ("すべてのファイル", "*.*")],
    )
    if path:
        inp_var.set(path)
        if not out_var.get().strip():
            base = os.path.splitext(os.path.basename(path))[0]
            out_var.set(base)


def main():
    global root, inp_var, out_var, log_area, run_btn, progress_var, progress_label_var

    root = tk.Tk()
    root.title("Orbitherm Solver")
    root.minsize(520, 460)
    root.geometry("620x520")

    f = ttk.Frame(root, padding=12)
    f.pack(fill=tk.BOTH, expand=True)

    # 入力ファイル
    ttk.Label(f, text="入力ファイル:").grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
    inp_var = tk.StringVar()
    ttk.Entry(f, textvariable=inp_var, width=50).grid(row=1, column=0, sticky=(tk.W, tk.E), padx=(0, 8), pady=(0, 8))
    ttk.Button(f, text="参照...", command=browse_input).grid(row=1, column=1, pady=(0, 8))
    f.grid_columnconfigure(0, weight=1)

    # 出力ファイル名（ベース名、拡張子なし）
    ttk.Label(f, text="出力ファイル名（拡張子なし）:").grid(row=2, column=0, sticky=tk.W, pady=(8, 4))
    out_var = tk.StringVar()
    ttk.Entry(f, textvariable=out_var, width=50).grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
    ttk.Label(f, text="※ 空欄の場合は入力ファイル名から自動（例: result → result_mp.csv, result_mp.png）", font=("", 8)).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 12))

    # 実行ボタン
    run_btn = ttk.Button(f, text="解析を実行", command=run_thermal)
    run_btn.grid(row=5, column=0, columnspan=2, pady=(0, 8))

    # プログレスバー
    progress_var = tk.DoubleVar(value=0)
    progress_label_var = tk.StringVar(value="待機中...")
    ttk.Progressbar(f, variable=progress_var, maximum=100, length=400).grid(
        row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 2)
    )
    ttk.Label(f, textvariable=progress_label_var, font=("", 8)).grid(
        row=7, column=0, columnspan=2, sticky=tk.W, pady=(0, 8)
    )

    # ログ
    ttk.Label(f, text="ログ:").grid(row=8, column=0, sticky=tk.W, pady=(0, 4))
    log_area = scrolledtext.ScrolledText(f, height=14, width=70, wrap=tk.WORD, state=tk.NORMAL)
    log_area.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
    f.grid_rowconfigure(9, weight=1)

    root.mainloop()


if __name__ == "__main__":
    main()
