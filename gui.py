"""Whisper 文字起こし GUI (Tkinter)。"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from tkinter import filedialog, messagebox, ttk

from whisper_transcription import WhisperTranscriber

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERAL_SETTINGS_FILE = os.path.join(BASE_DIR, "gui_settings.json")
USER_SETTINGS_FILE = os.path.join(BASE_DIR, "user_settings.json")
OLD_SETTINGS_FILE = os.path.join(BASE_DIR, ".gui_settings.json")

GENERAL_DEFAULTS = {
    "default_model": "small",
    "default_device": "auto",
    "default_language": "en",
}

USER_DEFAULTS = {
    "last_input_dir": "",
    "last_output_dir": "",
    "last_language": "en",
    "last_model": "small",
    "last_device": "auto",
    "setup_verified": False,
    "setup_verified_at": None,
    "setup_skip_days": 7,
}


def _migrate_old_settings():
    """古い .gui_settings.json から user_settings.json へ移行する。"""
    if not os.path.isfile(OLD_SETTINGS_FILE):
        return
    try:
        with open(OLD_SETTINGS_FILE, "r", encoding="utf-8") as f:
            old = json.load(f)
        user = _load_json(USER_SETTINGS_FILE, USER_DEFAULTS)
        if old.get("last_input_dir"):
            user["last_input_dir"] = old["last_input_dir"]
        if old.get("output_dir") and old["output_dir"] != "./outputs":
            user["last_output_dir"] = old["output_dir"]
        for key in ("language", "model", "device"):
            if key in old:
                user[f"last_{key}"] = old[key]
        _save_json(USER_SETTINGS_FILE, user)
        os.remove(OLD_SETTINGS_FILE)
    except (OSError, json.JSONDecodeError):
        pass


def _load_json(path: str, defaults: dict) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(defaults)


def _save_json(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


class TranscribeGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Whisper Transcription")
        self.root.geometry("700x560")
        self.root.resizable(True, True)
        self.root.minsize(600, 480)

        self.transcriber: WhisperTranscriber | None = None
        self._running = False
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._log_queue = queue.Queue()

        # load settings
        _migrate_old_settings()
        self._general = _load_json(GENERAL_SETTINGS_FILE, GENERAL_DEFAULTS)
        self._user = _load_json(USER_SETTINGS_FILE, USER_DEFAULTS)

        self._build_ui()
        self._load_settings()
        self._poll_log_queue()

    # ------------------------------------------------------------------ UI 構築

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # --- 入力ファイル ---
        file_frame = ttk.LabelFrame(main, text="入力ファイル", padding=8)
        file_frame.pack(fill=tk.X, pady=(0, 6))

        self.input_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.input_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6)
        )
        ttk.Button(file_frame, text="参照...", command=self._browse_input).pack(side=tk.RIGHT, padx=(0, 4))
        ttk.Button(file_frame, text="開く", command=self._open_input_location).pack(side=tk.RIGHT)

        # --- 出力先 ---
        out_frame = ttk.LabelFrame(main, text="出力先フォルダ", padding=8)
        out_frame.pack(fill=tk.X, pady=(0, 6))

        self.output_var = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6)
        )
        ttk.Button(out_frame, text="参照...", command=self._browse_output).pack(side=tk.RIGHT, padx=(0, 4))
        ttk.Button(out_frame, text="開く", command=self._open_output_location).pack(side=tk.RIGHT)

        # --- 設定行 ---
        settings = ttk.Frame(main)
        settings.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(settings, text="言語:").pack(side=tk.LEFT, padx=(0, 4))
        self.lang_var = tk.StringVar(value="en")
        lang_cb = ttk.Combobox(
            settings, textvariable=self.lang_var, values=["auto", "ja", "en"],
            state="readonly", width=6,
        )
        lang_cb.pack(side=tk.LEFT, padx=(0, 16))

        ttk.Label(settings, text="モデル:").pack(side=tk.LEFT, padx=(0, 4))
        self.model_var = tk.StringVar(value="small")
        model_cb = ttk.Combobox(
            settings, textvariable=self.model_var,
            values=["tiny", "small", "medium", "large"],
            state="readonly", width=7,
        )
        model_cb.pack(side=tk.LEFT, padx=(0, 16))

        ttk.Label(settings, text="デバイス:").pack(side=tk.LEFT, padx=(0, 4))
        self.device_var = tk.StringVar(value="auto")
        device_cb = ttk.Combobox(
            settings, textvariable=self.device_var,
            values=["auto", "cpu", "cuda"],
            state="readonly", width=5,
        )
        device_cb.pack(side=tk.LEFT, padx=(0, 16))

        self.run_btn = ttk.Button(settings, text="文字起こし実行", command=self._on_run)
        self.run_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.cancel_btn = ttk.Button(settings, text="キャンセル", command=self._on_cancel)

        # --- 進捗バー ---
        self.progress = ttk.Progressbar(main, mode="indeterminate")

        # --- ステータスラベル ---
        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(main, textvariable=self.status_var, font=("", 9))

        # --- ログ出力エリア ---
        log_frame = ttk.LabelFrame(main, text="ログ", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 6))

        self.log_text = tk.Text(
            log_frame, wrap=tk.WORD, state=tk.DISABLED,
            font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
            relief=tk.FLAT, borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- 下部ボタン ---
        bottom = ttk.Frame(main)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="環境状態", command=self._show_environment).pack(side=tk.LEFT)

    # ------------------------------------------------------------------ ログ出力

    def _log(self, msg: str):
        self._log_queue.put(msg)

    def _poll_log_queue(self):
        while True:
            try:
                msg = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self._write_log(msg)
        self.root.after(100, self._poll_log_queue)

    def _write_log(self, msg: str):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------ ファイル選択

    def _browse_input(self):
        initial_dir = self._user.get("last_input_dir", "")
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = ""
        path = filedialog.askopenfilename(
            title="音声/動画ファイルを選択",
            filetypes=[
                ("メディアファイル", "*.mp3;*.wav;*.m4a;*.flac;*.ogg;*.mp4;*.avi;*.mov;*.mkv;*.webm"),
                ("すべてのファイル", "*.*"),
            ],
            initialdir=initial_dir if initial_dir else None,
        )
        if path:
            self.input_var.set(path)
            self._user["last_input_dir"] = os.path.dirname(path)
            _save_json(USER_SETTINGS_FILE, self._user)

    def _browse_output(self):
        initial_dir = self.output_var.get() or self._user.get("last_output_dir", "")
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = ""
        path = filedialog.askdirectory(
            title="出力先フォルダを選択",
            initialdir=initial_dir if initial_dir else None,
        )
        if path:
            self.output_var.set(path)
            self._user["last_output_dir"] = path
            _save_json(USER_SETTINGS_FILE, self._user)

    def _open_input_location(self):
        path = self.input_var.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("エラー", "ファイルが存在しません。")
            return
        subprocess.Popen(["explorer", "/select,", os.path.abspath(path)])

    def _open_output_location(self):
        path = self.output_var.get().strip()
        if not path:
            messagebox.showwarning("エラー", "出力先フォルダが指定されていません。")
            return
        if not os.path.isdir(path):
            if messagebox.askyesno("確認", f"フォルダが存在しません。作成しますか？\n\n{path}"):
                os.makedirs(path, exist_ok=True)
            else:
                return
        os.startfile(path)

    # ------------------------------------------------------------------ 設定の永続化

    def _load_settings(self):
        self.lang_var.set(self._user.get("last_language", self._general.get("default_language", "en")))
        self.model_var.set(self._user.get("last_model", self._general.get("default_model", "small")))
        self.device_var.set(self._user.get("last_device", self._general.get("default_device", "auto")))
        saved_output = self._user.get("last_output_dir", "")
        self.output_var.set(saved_output if saved_output else "")

    def _save_settings(self):
        self._user["last_language"] = self.lang_var.get()
        self._user["last_model"] = self.model_var.get()
        self._user["last_device"] = self.device_var.get()
        self._user["last_output_dir"] = self.output_var.get()
        if self.input_var.get():
            self._user["last_input_dir"] = os.path.dirname(self.input_var.get())
        _save_json(USER_SETTINGS_FILE, self._user)

    # ------------------------------------------------------------------ 進捗表示

    def _set_status(self, text: str):
        self.root.after(0, lambda: self.status_var.set(text))

    def _show_progress(self):
        self.root.after(0, lambda: self.progress.pack(fill=tk.X, pady=(0, 2)))
        self.root.after(0, self.progress.start)

    def _hide_progress(self):
        self.root.after(0, self.progress.stop)
        self.root.after(0, self.progress.pack_forget)
        self.root.after(0, lambda: self.status_var.set(""))

    # ------------------------------------------------------------------ 実行制御

    def _on_run(self):
        if self._running:
            if self._thread and self._thread.is_alive():
                messagebox.showwarning("実行中", "現在文字起こしを実行中です。")
            return

        input_path = self.input_var.get().strip()
        if not input_path:
            messagebox.showwarning("入力エラー", "音声/動画ファイルを選択してください。")
            return

        output_dir = self.output_var.get().strip()
        if not output_dir:
            default_out = os.path.dirname(input_path)
            if messagebox.askyesno("出力先未指定", f"出力先が指定されていません。\n入力ファイルと同じフォルダに出力しますか？\n\n{default_out}"):
                output_dir = default_out
                self.output_var.set(output_dir)
            else:
                return

        language = self.lang_var.get()
        model_name = self.model_var.get()
        device = self.device_var.get()

        self._save_settings()

        self._running = True
        self._cancel_event.clear()
        self.run_btn.pack_forget()
        self.cancel_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._clear_log()
        self._show_progress()

        self._thread = threading.Thread(
            target=self._transcribe_thread,
            args=(input_path, output_dir, language, model_name, device),
            daemon=True,
        )
        self._thread.start()

    def _on_cancel(self):
        if not self._running:
            return
        self._cancel_event.set()
        self._log("")
        self._log("=== キャンセルされました ===")
        self._thread = None
        self._running = False
        self._hide_progress()
        self.cancel_btn.pack_forget()
        self.run_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._save_settings()

    def _is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _transcribe_thread(self, input_path, output_dir, language, model_name, device):
        try:
            lang_label = "(自動検出)" if language == "auto" else language
            self._log(f"入力ファイル: {input_path}")
            self._log(f"出力先: {output_dir}")
            self._log(f"言語: {lang_label}  モデル: {model_name}  デバイス: {device}")

            # 音声長の取得
            duration = WhisperTranscriber.get_audio_duration(input_path)
            if duration is not None:
                dur_str = WhisperTranscriber.format_duration(duration)
                self._log(f"音声長: {dur_str}")

            self.transcriber = WhisperTranscriber(model_name=model_name, device=device)

            resolved_device = self.transcriber.device
            if device == "cuda" and resolved_device == "cpu":
                self._log("CUDAが利用できないためCPUにフォールバックします")

            self._log(f"実行デバイス: {resolved_device}")

            # モデルロード
            self._set_status("モデルをロード中...")
            self._log(f"モデル '{model_name}' をロード中...")

            self.transcriber.load_model()

            if self._is_cancelled():
                return
            self._log("モデルロード完了。")

            # 文字起こし
            dur_hint = f" (音声長: {WhisperTranscriber.format_duration(duration)})" if duration else ""
            self._set_status(f"文字起こし中... しばらくお待ちください{dur_hint}")
            self._log("文字起こしを開始します...")

            language_arg = None if language == "auto" else language
            result = self.transcriber.transcribe_and_save(
                audio_path=input_path,
                output_dir=output_dir,
                language=language_arg,
            )

            if self._is_cancelled():
                return

            # 保存完了
            self._set_status("保存中...")
            self._log("")
            self._log("=== 完了 ===")
            self._log(f"検出言語: {result['detected_language']}")
            self._log(f"SRT:  {result['srt']}")
            self._log(f"TXT:  {result['txt']}")
            self._log(f"TXT (タイムスタンプ付き): {result['timestamped_txt']}")
            self._set_status("完了しました")

        except Exception as e:
            if self._is_cancelled():
                return
            self._log("")
            self._log(f"=== エラー ===")
            self._log(f"{e}")
            self._set_status("エラーが発生しました")
        finally:
            if not self._is_cancelled():
                self._running = False
                self.root.after(0, self._restore_run_button)
                self.root.after(3000, self._hide_progress)

    def _restore_run_button(self):
        self.cancel_btn.pack_forget()
        self.run_btn.pack(side=tk.LEFT, padx=(0, 6))

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------ 環境状態

    def _show_environment(self):
        win = tk.Toplevel(self.root)
        win.title("環境状態")
        win.geometry("420x280")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        frame = ttk.Frame(win, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Environment Status", font=("", 12, "bold")).pack(anchor=tk.W, pady=(0, 12))

        checks = self._run_env_checks()

        text = tk.Text(frame, font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
                       relief=tk.FLAT, borderwidth=0, height=9, wrap=tk.WORD)
        text.pack(fill=tk.X)

        for label, ok, detail in checks:
            icon = "OK" if ok else "NG"
            text.insert(tk.END, f"  {icon}   {label}: {detail}\n")

        text.configure(state=tk.DISABLED)

        # verification timestamp
        verified_at = self._user.get("setup_verified_at")
        if verified_at:
            ttk.Label(frame, text=f"最終確認: {verified_at[:19].replace('T', ' ')}",
                      font=("", 8)).pack(anchor=tk.W, pady=(8, 8))
        else:
            ttk.Label(frame, text="最終確認: 未確認", font=("", 8)).pack(anchor=tk.W, pady=(8, 8))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="再チェック",
                   command=lambda: self._refresh_env_window(win)).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="閉じる", command=win.destroy).pack(side=tk.RIGHT)

    def _refresh_env_window(self, win):
        win.destroy()
        self._user["setup_verified"] = True
        self._user["setup_verified_at"] = datetime.now(timezone.utc).isoformat()
        _save_json(USER_SETTINGS_FILE, self._user)
        self._show_environment()

    def _run_env_checks(self) -> list[tuple[str, bool, str]]:
        results = []

        # Python
        results.append(("Python", True, sys.version.split()[0]))

        # Conda env (check if we're running inside the expected env)
        conda_prefix = os.environ.get("CONDA_PREFIX", "")
        conda_env = os.path.basename(conda_prefix) if conda_prefix else ""
        if conda_env:
            results.append(("Conda env", True, conda_env))
        else:
            results.append(("Conda env", False, "not in conda env"))

        # Whisper
        try:
            import whisper
            results.append(("Whisper", True, whisper.__version__ if hasattr(whisper, '__version__') else "installed"))
        except ImportError:
            results.append(("Whisper", False, "not installed"))

        # PyTorch + CUDA
        try:
            import torch
            torch_ver = torch.__version__
            cuda_ok = torch.cuda.is_available()
            cuda_info = f"{torch_ver} (CUDA: {'yes' if cuda_ok else 'no'})"
            results.append(("PyTorch", True, cuda_info))
        except ImportError:
            results.append(("PyTorch", False, "not installed"))

        # FFmpeg
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            results.append(("FFmpeg", True, "available"))
        except (FileNotFoundError, subprocess.CalledProcessError):
            results.append(("FFmpeg", False, "not found in PATH"))

        return results


def main():
    root = tk.Tk()
    app = TranscribeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
