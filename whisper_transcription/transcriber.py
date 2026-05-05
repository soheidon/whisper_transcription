import datetime
import os
import subprocess
import tempfile
import whisper
import torch


class WhisperTranscriber:
    """Whisper 文字起こしの共通処理を提供するクラス。"""

    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"}

    def __init__(self, model_name: str = "large", device: str = "auto"):
        self.model_name = model_name
        self.model = None
        self.device = self._resolve_device(device)

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "cuda":
            return "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cpu":
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def load_model(self):
        self.model = whisper.load_model(self.model_name)
        self.model.to(self.device)

    @staticmethod
    def is_video(file_path: str) -> bool:
        return os.path.splitext(file_path)[1].lower() in WhisperTranscriber.VIDEO_EXTENSIONS

    @staticmethod
    def get_audio_duration(file_path: str) -> float | None:
        """ffprobe で音声/動画ファイルの長さ（秒）を取得する。"""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return float(result.stdout.strip())
        except (ValueError, FileNotFoundError):
            return None

    @staticmethod
    def format_duration(seconds: float) -> str:
        """秒数を 'XX分XX秒' 形式に変換する。"""
        m = int(seconds // 60)
        s = int(seconds % 60)
        if m > 0:
            return f"{m}分{s}秒"
        return f"{s}秒"

    @staticmethod
    def extract_audio(video_path: str, output_dir: str | None = None) -> str:
        base = os.path.splitext(os.path.basename(video_path))[0]
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            audio_path = os.path.join(output_dir, f"{base}_extracted.wav")
        else:
            fd, audio_path = tempfile.mkstemp(suffix=".wav", prefix=f"{base}_")
            os.close(fd)

        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-y", audio_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return audio_path

    @staticmethod
    def format_time(seconds: float) -> str:
        td = str(datetime.timedelta(seconds=seconds))
        if "." in td:
            base, ms = td.split(".")
            ms = ms[:3]
            return f"{base},{ms}"
        return f"{td},000"

    @staticmethod
    def create_srt(segments: list) -> str:
        lines = []
        for i, seg in enumerate(segments, start=1):
            start = WhisperTranscriber.format_time(seg["start"])
            end = WhisperTranscriber.format_time(seg["end"])
            text = seg["text"].strip()
            lines.append(f"{i}\n{start} --> {end}\n{text}\n")
        return "\n".join(lines)

    @staticmethod
    def create_text(segments: list) -> str:
        return "\n".join(seg["text"].strip() for seg in segments)

    @staticmethod
    def create_timestamped_text(segments: list) -> str:
        return "\n".join(
            f"[{WhisperTranscriber.format_time(seg['start'])}] {seg['text'].strip()}"
            for seg in segments
        )

    def transcribe(self, audio_path: str, language: str | None = None) -> dict:
        if self.model is None:
            self.load_model()

        transcribe_opts = {"fp16": False}
        if language:
            transcribe_opts["language"] = language

        return self.model.transcribe(audio_path, **transcribe_opts)

    def transcribe_and_save(
        self,
        audio_path: str,
        output_dir: str,
        language: str | None = None,
    ) -> dict:
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"入力ファイルが見つかりません: {audio_path}")

        os.makedirs(output_dir, exist_ok=True)

        is_video = self.is_video(audio_path)
        extracted = None

        if is_video:
            extracted = self.extract_audio(audio_path, output_dir)
            transcribe_target = extracted
        else:
            transcribe_target = audio_path

        try:
            result = self.transcribe(transcribe_target, language=language)
        finally:
            if extracted and os.path.isfile(extracted):
                os.remove(extracted)

        segments = result["segments"]
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        detected_lang = result.get("language", "unknown")

        srt_content = self.create_srt(segments)
        text_content = self.create_text(segments)
        timestamped_content = self.create_timestamped_text(segments)

        srt_path = os.path.join(output_dir, f"{base_name}.srt")
        txt_path = os.path.join(output_dir, f"{base_name}.txt")
        ts_path = os.path.join(output_dir, f"{base_name}_with_timestamp.txt")

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text_content)
        with open(ts_path, "w", encoding="utf-8") as f:
            f.write(timestamped_content)

        return {
            "detected_language": detected_lang,
            "device": self.device,
            "model": self.model_name,
            "srt": srt_path,
            "txt": txt_path,
            "timestamped_txt": ts_path,
        }
