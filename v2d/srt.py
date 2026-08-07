"""SRT/VTT 解析与生成，以及贯穿全流程的字幕行数据结构。

Line 是整条流水线的通用货币：下载到的字幕、Whisper 转写、翻译结果
都归一成 Line 列表，后面摘要/报告只认它。
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Line:
    start: float          # 秒
    end: float            # 秒
    text: str             # 原文
    zh: str | None = None  # 原文非中文时的中文译文


# 同时接受 HH:MM:SS,mmm（SRT）与 [HH:]MM:SS.mmm（VTT，小时可省略）
_TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
_TAG = re.compile(r"<[^>]+>")


def ts_to_seconds(ts: str) -> float:
    m = _TS.fullmatch(ts.strip())
    if not m:
        raise ValueError(f"无法解析时间戳: {ts!r}")
    h, mi, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def seconds_to_ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    mi, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{mi:02d}:{s:02d},{ms:03d}"


def fmt_mmss(t: float) -> str:
    t = int(t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_srt(text: str) -> list[Line]:
    """解析 SRT/VTT 文本。对块结构宽容：序号行可有可无，VTT 头/NOTE 块自动跳过。"""
    lines: list[Line] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        rows = [r for r in block.split("\n") if r.strip()]
        if not rows:
            continue
        # 跳过可选的序号行 / VTT cue id 行
        if "-->" not in rows[0]:
            if len(rows) > 1 and "-->" in rows[1]:
                rows = rows[1:]
            else:
                continue  # WEBVTT 头、NOTE、STYLE 等
        a, b = rows[0].split("-->")
        content = _TAG.sub("", " ".join(rows[1:])).replace("&nbsp;", " ").strip()
        if not content:
            continue
        try:
            start = ts_to_seconds(a)
            end = ts_to_seconds(b.split()[0])  # 丢掉 VTT 的 cue 设置（position: 等）
        except ValueError:
            continue
        lines.append(Line(start, end, content))
    return lines


def clean_lines(lines: list[Line]) -> list[Line]:
    """清洗自动字幕的滚动重复：连续完全相同、或被前一行整句包含的行，丢弃。"""
    out: list[Line] = []
    for l in lines:
        t = re.sub(r"\s+", " ", l.text).strip()
        if not t:
            continue
        if out and (t == out[-1].text or t in out[-1].text):
            out[-1].end = max(out[-1].end, l.end)
            continue
        out.append(Line(l.start, l.end, t, l.zh))
    return out


def write_srt(lines: list[Line], path, *, use_zh: bool = False) -> None:
    blocks = []
    for i, l in enumerate(lines, 1):
        text = (l.zh if use_zh and l.zh else l.text)
        blocks.append(f"{i}\n{seconds_to_ts(l.start)} --> {seconds_to_ts(l.end)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def is_chinese(text_sample: str) -> bool:
    """CJK 字符占比 > 30% 视为中文内容（够用的启发式，只做兜底）。"""
    if not text_sample:
        return False
    cjk = sum(1 for ch in text_sample if "一" <= ch <= "鿿")
    return cjk / len(text_sample) > 0.30
