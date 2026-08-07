"""下载：URL → audio.mp3 + （能拿到的话）原生字幕 SRT + 元信息。

统一走 yt-dlp（YouTube / Bilibili 都支持）。ffmpeg 用 imageio-ffmpeg 的
便携二进制，不要求系统安装。

字幕策略：
  - YouTube：优先人工字幕，其次自动字幕（writeautomaticsub）；转成 SRT。
  - Bilibili：绝大多数视频没有可下载字幕 → 上层落到 Whisper 转写。
  - 需要登录的视频（B 站高清/部分内容）：--cookies-from-browser / --cookies 透传。
"""
from __future__ import annotations

from pathlib import Path

# 字幕语言优先级：先中文后英文；命中哪个用哪个
_SUB_LANGS = ["zh-Hans", "zh-CN", "zh-Hant", "zh", "en", "en-US", "en-GB", "en-orig"]


def download(url: str, workdir: Path, *, cookies_from_browser: str | None = None,
             cookies_file: str | None = None) -> dict:
    """返回 meta dict：title/id/duration/uploader/platform/language/audio_path/sub_path。"""
    import yt_dlp
    from imageio_ffmpeg import get_ffmpeg_exe

    workdir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "media.%(ext)s"),
        "ffmpeg_location": get_ffmpeg_exe(),
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"},
            {"key": "FFmpegSubtitlesConvertor", "format": "srt"},
        ],
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": _SUB_LANGS,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if cookies_file:
        opts["cookiefile"] = cookies_file

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    audio = workdir / "audio.mp3"
    src = workdir / "media.mp3"
    if src.exists():
        src.replace(audio)
    if not audio.exists():
        raise RuntimeError("yt-dlp 下载完成但没有产出 media.mp3 —— 提取音频失败。")

    sub_path = _pick_subtitle(workdir, info.get("language"))

    return {
        "title": info.get("title") or "未命名视频",
        "id": info.get("id", ""),
        "duration": float(info.get("duration") or 0),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "upload_date": info.get("upload_date") or "",
        "url": info.get("webpage_url") or url,
        "platform": info.get("extractor_key") or "unknown",
        "language": info.get("language"),  # 可能为 None，最终以字幕/Whisper 判定为准
        "audio_path": audio,
        "sub_path": sub_path,
    }


def _pick_subtitle(workdir: Path, lang_hint: str | None) -> Path | None:
    """在下载目录里挑一份字幕：优先匹配视频语言前缀，其次任意 srt，最后 vtt。"""
    subs = sorted(workdir.glob("media.*.srt")) + sorted(workdir.glob("media.*.vtt"))
    if not subs:
        return None
    if lang_hint:
        for p in subs:
            # 文件名形如 media.zh-Hans.srt / media.en.vtt
            code = p.name.split(".")[-2].lower()
            if code.startswith(lang_hint.lower()[:2]):
                return p
    return subs[0]
