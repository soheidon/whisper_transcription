#!/usr/bin/env python3
"""Whisper 文字起こし CLI ツール。"""

import argparse
import os
import sys

from whisper_transcription import WhisperTranscriber

SOURCE_DIR = "./source"
MEDIA_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac", ".opus",
    ".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv",
}


def resolve_input(path: str | None) -> str:
    """入力パスを解決する。

    - 指定なし → source/ 内の最初の音声ファイルを返す
    - パス区切りを含む → そのまま返す
    - ファイル名のみ → source/ 内のそのファイルを返す
    """
    if path is None:
        return _find_first_audio(SOURCE_DIR)

    if os.sep in path or os.altsep in path:
        return path

    candidate = os.path.join(SOURCE_DIR, path)
    if os.path.isfile(candidate):
        return candidate
    return path


def _find_first_audio(directory: str) -> str:
    """ディレクトリ内の最初の音声ファイルを返す。"""
    try:
        for name in os.listdir(directory):
            if os.path.splitext(name)[1].lower() in MEDIA_EXTENSIONS:
                return os.path.join(directory, name)
    except FileNotFoundError:
        pass
    raise FileNotFoundError(
        f"source/ ディレクトリに音声/動画ファイルが見つかりません。"
        f" --input でファイルを指定してください。"
    )


def main():
    parser = argparse.ArgumentParser(
        description="OpenAI Whisper で音声ファイルを文字起こしし、TXT/SRT を出力します。"
    )
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="文字起こしする音声ファイル。省略時は source/ 内のファイルを自動検出。"
             "ファイル名のみの指定でも source/ 内を検索します。",
    )
    parser.add_argument(
        "--language", "-l",
        default="auto",
        choices=["auto", "ja", "en", "zh", "fr",
                 "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs",
                 "ca", "cs", "cy", "da", "de", "el", "es", "et", "eu", "fa", "fi", "fo",
                 "gl", "gu", "ha", "haw", "he", "hi", "hr", "ht", "hu", "hy", "id", "is",
                 "it", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb", "ln", "lo", "lt",
                 "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", "ne", "nl",
                 "nn", "no", "oc", "pa", "pl", "ps", "pt", "ro", "ru", "sa", "sd", "si",
                 "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw", "ta", "te", "tg",
                 "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "yue"],
        help="言語指定 (default: auto = 自動検出)",
    )
    parser.add_argument(
        "--model", "-m",
        default="large",
        choices=["tiny", "small", "medium", "large"],
        help="Whisperモデルサイズ (default: large)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="./outputs",
        help="出力ディレクトリ (default: ./outputs)",
    )
    parser.add_argument(
        "--device", "-d",
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="実行デバイス (default: auto = CUDA優先)",
    )

    args = parser.parse_args()

    try:
        input_path = resolve_input(args.input)
    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)

    language = None if args.language == "auto" else args.language

    transcriber = WhisperTranscriber(model_name=args.model, device=args.device)
    if args.device == "cuda" and transcriber.device == "cpu":
        print("CUDAが利用できないためCPUにフォールバックします")
    print(f"実行デバイス: {transcriber.device}")
    print(f"モデル '{args.model}' をロード中...")
    transcriber.load_model()

    try:
        print(f"文字起こし中: {input_path}")
        result = transcriber.transcribe_and_save(
            audio_path=input_path,
            output_dir=args.output_dir,
            language=language,
        )
        print(f"検出言語: {result['detected_language']}")
        print(f"SRT:  {result['srt']}")
        print(f"TXT:  {result['txt']}")
        print(f"TXT (タイムスタンプ付き): {result['timestamped_txt']}")
        print("完了しました。")
    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"エラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
