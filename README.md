# WhisperGUI

OpenAI Whisper を使った音声/動画ファイル文字起こし CLI／GUI ツール。
A speech-to-text transcription tool using OpenAI Whisper with CLI and GUI.

[日本語](#日本語) | [English](#english)

## 日本語

### 必要条件

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) (動画ファイルを処理する場合)

## インストール

```bash
# CPU版（最小構成）
pip install -r requirements.txt

# CUDA 12.4 版（GPU使用時）
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install openai-whisper
```

> **注意**: `requirements.txt` の `torch` は CPU 版です。GPU を使う場合は上記の CUDA 版インストール手順に置き換えてください。ランチャーの Setup 機能からも環境構築できます。

## 使い方

`source/` フォルダに音声ファイルを置いてください。

```bash
# source/ 内のファイルを自動検出
python transcribe.py

# source/ 内の特定ファイルをファイル名で指定
python transcribe.py --input audio.mp3

# 他ディレクトリのファイルをパスで指定
python transcribe.py --input C:/music/speech.mp3

# 日本語指定 + medium モデル
python transcribe.py --input audio.mp3 --language ja --model medium
```

## オプション

| オプション | デフォルト | 説明 |
|---|---|---|
| `--input`, `-i` | (自動) | 音声ファイル。省略時は `source/` 内を自動検出。ファイル名のみだと `source/` 内を検索 |
| `--language`, `-l` | `auto` | 言語指定（全99言語対応。`auto`=自動検出、優先: `ja` `en` `zh` `fr` + アルファベット順で95言語） |
| `--model`, `-m` | `large` | モデルサイズ (`tiny`, `small`, `medium`, `large`) |
| `--output-dir`, `-o` | `./outputs` | 出力ディレクトリ |
| `--device`, `-d` | `auto` | 実行デバイス (`auto`, `cpu`, `cuda`)。auto は CUDA 優先 |

## 出力ファイル

`outputs/` ディレクトリに以下が生成されます：

- `{ファイル名}.srt` — SRT 字幕形式
- `{ファイル名}.txt` — プレーンテキスト
- `{ファイル名}_with_timestamp.txt` — タイムスタンプ付きテキスト

## デバイス

`--device` オプションで実行デバイスを指定できます。

- `auto` (デフォルト): CUDA が利用可能なら GPU、なければ CPU
- `cuda`: GPU を強制。CUDA 非利用時は CPU にフォールバック
- `cpu`: CPU を強制

```bash
python transcribe.py --input audio.mp3 --device cuda
```

## GUI

### WhisperGUI.exe（推奨）

`WhisperGUI.exe` は、既存の Conda 環境 `whisper-transcription` を使って `gui.py` を起動する軽量ランチャーです。

**重要**: `WhisperGUI.exe` は **Python / Whisper / PyTorch 本体を同梱していません**。ランチャー単体では動作せず、PC に Conda 環境 `whisper-transcription` が構築済みである必要があります。

**起動方法**:
- デスクトップに `WhisperGUI.exe` のショートカットを作成し、ダブルクリックで起動してください。
- `.bat` と異なり、コマンドプロンプトや PowerShell のウィンドウは表示されません。

**ランチャーの機能**:
- 起動時に Conda 環境・pythonw.exe・ffmpeg・CUDA の利用可否を自動チェック
- 一度すべて OK になると、7日間はチェックをスキップ（「Recheck」で再確認可能）
- 不足コンポーネントがある場合のみ Setup パネルを表示
- チェック結果やエラーはランチャー画面内のログエリアに表示
- 「GUI起動後にランチャーを閉じる」オプションあり（既定: オフ）

**ビルド方法**:
```bash
dotnet build WhisperGUILauncher/WhisperGUILauncher.csproj -c Release
# 出力: WhisperGUILauncher/bin/Release/net8.0-windows/WhisperGUI.exe
```

### WhisperGUI.bat（補助）

Conda 環境が未構築の場合や、トラブルシューティング用に `.bat` も利用できます。
`WhisperGUI.bat` をダブルクリックで起動します。conda 環境の有効化から GUI 起動まで自動実行されます。

### コマンドライン

```bash
conda activate whisper-transcription
python gui.py
```

GUI では以下が設定できます：

- ファイル選択ダイアログで音声/動画ファイルを選択
- 出力先フォルダを選択
- 言語: auto / ja / en (デフォルト: en)
- モデル: tiny / small / medium / large (デフォルト: small)
- デバイス: auto / cpu / cuda (デフォルト: auto)
- 文字起こしは別スレッドで実行され、UI は固まりません
- 不定進捗バー＋ステータス表示（モデルロード中 → 文字起こし中 → 保存中 → 完了）
- 音声長を処理開始時に表示（ffprobe で自動取得）
- 入力ファイル・出力フォルダの「開く」ボタンでエクスプローラ表示
- 出力先未指定の場合は入力ファイルと同じフォルダに出力するか確認
- ログと結果は画面上に表示されます
- キャンセルボタンはモデルロード前後および保存処理の中止に対応しています
- 「環境状態」ボタンで Python / Whisper / PyTorch / CUDA / FFmpeg の状態を確認可能
- 設定は `user_settings.json` に自動保存（汎用デフォルトは `gui_settings.json`）
- ランチャー・GUI 両方に `assets/app.ico` のアプリアイコンを表示（exe 本体 + ウィンドウ左上）

## 設定ファイル

| ファイル | 用途 | Git |
|---|---|---|
| `gui_settings.json` | 汎用デフォルト値（モデル、デバイス、言語） | 管理対象 |
| `user_settings.json` | ユーザー固有設定（パス、最終設定、環境検証状態） | 管理対象外 |
| `launcher_settings.json` | ランチャー設定（環境検証状態、スキップ期間） | 管理対象外 |

> **移行について**: 以前のバージョンで使われていた `.gui_settings.json`（先頭ドット付き）は、初回起動時に自動的に `user_settings.json` へ移行され、削除されます。

## Git 管理対象

```
gui_settings.json     汎用デフォルト設定
README.md
requirements.txt
gui.py
transcribe.py
whisper_transcription/   コアライブラリ
WhisperGUILauncher/      C# ランチャー ソースコード
assets/                  アプリアイコン
```

## Git 管理対象外

```
user_settings.json      ユーザー固有設定（自動作成）
launcher_settings.json  ランチャー設定（自動作成）
.gui_settings.json      旧設定ファイル（移行後削除）
outputs/                文字起こし出力
source/                 入力メディアファイル
notebooks/              参考元コード（本プロジェクトのソースではない）
__pycache__/
*.pyc
*.srt
*.txt (出力ファイル)
*.mp3 / *.mp4 / *.wav / etc.
WhisperGUILauncher/bin/
WhisperGUILauncher/obj/
```

## GPU版 PyTorch について

`requirements.txt` の `torch` は CPU 版がインストールされます。
CUDA 版 PyTorch を使う場合は以下のいずれかで導入してください：

- **ランチャーの Setup 機能**: 「Create Conda Env」から環境を作成後、「Install pip deps」で依存関係をインストール
- **手動インストール**:
  ```bash
  conda create -n whisper-transcription python=3.11 -y
  conda activate whisper-transcription
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
  pip install openai-whisper
  ```

---

## English

OpenAI Whisper transcription tool with CLI and GUI.

### Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) (for processing video files)

### Installation

```bash
# CPU version (minimal)
pip install -r requirements.txt

# CUDA 12.4 (for GPU)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install openai-whisper
```

> **Note**: `torch` in `requirements.txt` installs the CPU version. Use the CUDA install steps above for GPU support. The launcher's Setup feature can also set up the environment.

### Usage

Place audio files in the `source/` directory.

```bash
# Auto-detect files in source/
python transcribe.py

# Specify a file in source/ by name
python transcribe.py --input audio.mp3

# Specify a file by full path
python transcribe.py --input C:/music/speech.mp3

# Japanese + medium model
python transcribe.py --input audio.mp3 --language ja --model medium
```

### Options

| Option | Default | Description |
|---|---|---|
| `--input`, `-i` | (auto) | Audio file. Auto-detects in `source/` if omitted |
| `--language`, `-l` | `auto` | Language (99 languages supported. `auto`=detect, priority: `ja` `en` `zh` `fr` + 95 more alphabetical) |
| `--model`, `-m` | `large` | Model size (`tiny`, `small`, `medium`, `large`) |
| `--output-dir`, `-o` | `./outputs` | Output directory |
| `--device`, `-d` | `auto` | Device (`auto`, `cpu`, `cuda`). auto prefers CUDA |

### Output Files

Generated in the `outputs/` directory:

- `{filename}.srt` — SubRip subtitle format
- `{filename}.txt` — Plain text
- `{filename}_with_timestamp.txt` — Timestamped text

### GUI

#### WhisperGUI.exe (Recommended)

`WhisperGUI.exe` is a lightweight launcher that starts `gui.py` using your existing `whisper-transcription` Conda environment.

**Important**: `WhisperGUI.exe` does **NOT bundle Python / Whisper / PyTorch**. The Conda environment `whisper-transcription` must already exist on the PC.

**How to launch**:
- Create a shortcut to `WhisperGUI.exe` on your desktop and double-click.
- Unlike `.bat`, no command prompt or PowerShell window appears.

**Launcher features**:
- Auto-checks Conda environment, pythonw.exe, ffmpeg, and CUDA on startup
- Skips checks for 7 days once everything passes (Recheck available anytime)
- Setup panel appears only when components are missing
- Check results and errors shown in the launcher's log area
- Option to auto-close launcher after GUI starts (off by default)

**Build**:
```bash
dotnet build WhisperGUILauncher/WhisperGUILauncher.csproj -c Release
# Output: WhisperGUILauncher/bin/Release/net8.0-windows/WhisperGUI.exe
```

#### WhisperGUI.bat (Auxiliary)

Use `.bat` for troubleshooting or if the Conda environment hasn't been set up yet.

#### Command Line

```bash
conda activate whisper-transcription
python gui.py
```

The GUI provides:

- File dialog for audio/video selection with "Open" button for Explorer
- Output folder selection with "Open" button
- Confirmation dialog if output directory is not specified (uses input file's folder)
- Language: auto / ja / en (default: en)
- Model: tiny / small / medium / large (default: small)
- Device: auto / cpu / cuda (default: auto)
- Background thread processing (non-blocking UI)
- Indeterminate progress bar + status display (loading → transcribing → saving → done)
- Audio duration display (via ffprobe)
- Cancel button (before/during model load, during save)
- "Environment" button to check Python / Whisper / PyTorch / CUDA / FFmpeg status
- Settings auto-saved to `user_settings.json` (general defaults in `gui_settings.json`)
- App icon (`assets/app.ico`) shown on both launcher EXE and GUI window title bar

### Settings Files

| File | Purpose | Git |
|---|---|---|
| `gui_settings.json` | General defaults (model, device, language) | Tracked |
| `user_settings.json` | User-specific settings (paths, last used) | Ignored |
| `launcher_settings.json` | Launcher settings (verification state) | Ignored |

> **Migration**: Old `.gui_settings.json` (with leading dot) is automatically migrated to `user_settings.json` on first launch.

### Git Tracked Files

```
gui_settings.json     General default settings
README.md
requirements.txt
gui.py
transcribe.py
whisper_transcription/   Core library
WhisperGUILauncher/      C# launcher source code
assets/                  App icon
```

### Git Ignored Files

```
user_settings.json      User-specific settings (auto-created)
launcher_settings.json  Launcher settings (auto-created)
.gui_settings.json      Legacy settings (migrated & deleted)
outputs/                Transcription output
source/                 Input media files
notebooks/              Reference code (not project source)
__pycache__/
*.pyc
*.srt
*.txt (output files)
*.mp3 / *.mp4 / *.wav / etc.
WhisperGUILauncher/bin/
WhisperGUILauncher/obj/
```

### GPU PyTorch

`torch` in `requirements.txt` installs the CPU version.
For CUDA-enabled PyTorch:

- **Launcher Setup**: Create the environment via "Create Conda Env", then "Install pip deps"
- **Manual install**:
  ```bash
  conda create -n whisper-transcription python=3.11 -y
  conda activate whisper-transcription
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
  pip install openai-whisper
  ```
