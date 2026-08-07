"""下载：URL → audio.mp3 + （能拿到的话）原生字幕 SRT + 元信息。

统一走 yt-dlp（YouTube / Bilibili 都支持）。ffmpeg 用 imageio-ffmpeg 的
便携二进制，不要求系统安装。

字幕策略：
  - YouTube：优先人工字幕，其次自动字幕（writeautomaticsub）；转成 SRT。
  - Bilibili：**只下音频，完全不碰字幕**。B 站字幕接口既不可靠又容易串台
    （拿到的是别的分P/别的稿件的 CC 字幕），一律走 Whisper 转写更省心。
  - 需要登录的视频（B 站高清/部分内容）：--cookies-from-browser / --cookies 透传。

完整性是硬要求：
  下完必须用 ffmpeg 量一遍音频真实时长，和站点给的 duration 对不上就换 format
  重下，还不行就报错。绝不把 46 分钟的视频截成 1 分钟然后继续往下跑。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

# 字幕语言优先级：先中文后英文；命中哪个用哪个
_SUB_LANGS = ["zh-Hans", "zh-CN", "zh-Hant", "zh", "en", "en-US", "en-GB", "en-orig"]

# B 站 CDN 认 Referer，缺了会被掐断流（表现就是只下到开头一小段）
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_BILI_HEADERS = {"User-Agent": _UA, "Referer": "https://www.bilibili.com/"}

# 依次尝试的 format：先要真·纯音频流，再退到 yt-dlp 的默认挑法
_FORMATS = [
    "bestaudio[vcodec=none]/bestaudio",
    "bestaudio/best",
]

# 实测时长 / 站点标称时长 低于这个比例就认为下载被截断
_MIN_RATIO = 0.95


def is_bilibili(url: str) -> bool:
    return "bilibili.com" in url or "b23.tv" in url


def probe_duration(path: Path) -> float:
    """用 ffmpeg 读媒体文件的真实时长（秒）。读不出来返回 0。"""
    from imageio_ffmpeg import get_ffmpeg_exe

    out = subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)", out)
    if not m:
        return 0.0
    h, mi, s, frac = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + float(f"0.{frac}")


def download(url: str, workdir: Path, *, cookies_from_browser: str | None = None,
             cookies_file: str | None = None, progress=print) -> dict:
    """返回 meta dict：title/id/duration/uploader/platform/language/audio_path/sub_path。"""
    workdir.mkdir(parents=True, exist_ok=True)
    bili = is_bilibili(url)

    last_err: Exception | None = None
    for i, fmt in enumerate(_FORMATS, 1):
        _clean(workdir)
        try:
            info = _attempt(url, workdir, fmt, bili=bili,
                            cookies_from_browser=cookies_from_browser,
                            cookies_file=cookies_file)
        except Exception as e:  # 换个 format 再试一次，最后一轮才抛
            last_err = e
            progress(f"[v2d] 下载失败（format={fmt}）：{e}")
            continue

        audio = _finalize_audio(workdir)
        want = float(info.get("duration") or 0)
        got = probe_duration(audio)
        if not want:
            progress(f"[v2d] 音频时长 {_hms(got)}（站点未提供时长，跳过校验）")
            return _meta(info, url, audio, workdir, bili)
        progress(f"[v2d] 音频时长 {_hms(got)} / 站点标称 {_hms(want)}")
        if got >= want * _MIN_RATIO:
            return _meta(info, url, audio, workdir, bili)

        progress(f"[v2d] ⚠ 下载不完整（只有 {got / want:.0%}），换 format 重试 ...")
        last_err = RuntimeError(
            f"音频只下到 {_hms(got)}，站点标称 {_hms(want)}（{got / want:.0%}）")

    raise RuntimeError(
        f"音频下载不完整或失败：{last_err}\n"
        "  可能原因与对策：\n"
        "  1) 需要登录/大会员才能拿到完整流 → 加 --cookies-from-browser chrome\n"
        "  2) 网络被中途掐断 → 重跑一次；或先 `pip install -U yt-dlp` 再试\n"
        "  3) 多分P 稿件请用带 ?p=N 的完整链接"
    )


def _attempt(url: str, workdir: Path, fmt: str, *, bili: bool,
             cookies_from_browser: str | None, cookies_file: str | None) -> dict:
    import yt_dlp
    from imageio_ffmpeg import get_ffmpeg_exe

    opts = {
        "format": fmt,
        "outtmpl": str(workdir / "media.%(ext)s"),
        "ffmpeg_location": get_ffmpeg_exe(),
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"},
        ],
        "noplaylist": True,
        # —— 完整性相关：任何分片缺失都要炸，不许静默拼出个残片 ——
        "retries": 10,
        "fragment_retries": 10,
        "skip_unavailable_fragments": False,
        "concurrent_fragment_downloads": 4,
        "http_chunk_size": 10 * 1024 * 1024,
        "http_headers": dict(_BILI_HEADERS) if bili else {"User-Agent": _UA},
        # 保留 yt-dlp 自己的进度条和警告——之前 quiet 把截断警告一起吞了
        "quiet": False,
        "no_warnings": False,
        "noprogress": False,
    }
    if not bili:
        # B 站只下音频；YouTube 才去要字幕
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        opts["subtitleslangs"] = _SUB_LANGS
        opts["postprocessors"].append({"key": "FFmpegSubtitlesConvertor", "format": "srt"})
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if cookies_file:
        opts["cookiefile"] = cookies_file

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


def _clean(workdir: Path) -> None:
    for p in workdir.glob("media.*"):
        p.unlink(missing_ok=True)
    (workdir / "audio.mp3").unlink(missing_ok=True)


def _finalize_audio(workdir: Path) -> Path:
    audio = workdir / "audio.mp3"
    src = workdir / "media.mp3"
    if src.exists():
        src.replace(audio)
    if not audio.exists():
        raise RuntimeError("yt-dlp 下载完成但没有产出 media.mp3 —— 提取音频失败。")
    return audio


def _meta(info: dict, url: str, audio: Path, workdir: Path, bili: bool) -> dict:
    return {
        "title": info.get("title") or "未命名视频",
        "id": info.get("id", ""),
        "duration": float(info.get("duration") or probe_duration(audio)),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "upload_date": info.get("upload_date") or "",
        "url": info.get("webpage_url") or url,
        "platform": info.get("extractor_key") or "unknown",
        "language": info.get("language"),  # 可能为 None，最终以字幕/Whisper 判定为准
        "audio_path": audio,
        "sub_path": None if bili else _pick_subtitle(workdir, info.get("language")),
    }


def _hms(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:d}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 \
        else f"{sec // 60:02d}:{sec % 60:02d}"


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
