"""本地语音识别：audio.mp3 → Line 列表（faster-whisper，CPU int8）。

没有官方字幕时的唯一来源。慢是它的本性——十几分钟的视频在普通 CPU 上
要几分钟到十几分钟，模型规格 tiny/base/small/medium/large-v3 自己权衡。
"""
from __future__ import annotations

from pathlib import Path

from .srt import Line


def transcribe(audio: Path, *, model_size: str = "small") -> tuple[list[Line], str]:
    """返回 (行列表, whisper 判定的语言代码，如 'zh' / 'en')。"""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio), vad_filter=True)
    lines = [
        Line(seg.start, seg.end, seg.text.strip())
        for seg in segments
        if seg.text.strip()
    ]
    return lines, (info.language or "unknown")
