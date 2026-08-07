#!/usr/bin/env python3
"""SRT / VTT → REPORT_DATA 的 transcript 数组。

    python3 srt_to_transcript.py transcript.srt                  # 单语
    python3 srt_to_transcript.py transcript.srt --zh zh.srt      # 原文 + 中文译文

输出 [{"t0":…, "t1":…, "text":…, "zh":…}, …] 到 stdout。

顺带做了自动字幕的清理：滚动式字幕（每行都把上一行重复一遍再加几个词）
不去重的话，实时字幕会疯狂闪烁、转写区也会长出三倍。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 兼容 SRT（00:00:01,500）和 VTT（00:01.500，小时可省）
_TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
_ARROW = re.compile(r"-->")
_TAG = re.compile(r"<[^>]+>")


def _secs(m: re.Match) -> float:
    h, mi, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse(text: str) -> list[dict]:
    out: list[dict] = []
    cur: dict | None = None
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            cur = None
            continue
        if _ARROW.search(line):
            ts = list(_TS.finditer(line))
            if len(ts) >= 2:
                cur = {"t0": _secs(ts[0]), "t1": _secs(ts[1]), "text": ""}
                out.append(cur)
            continue
        if cur is None:
            continue  # 序号行 / WEBVTT 头 / cue setting，跳过
        piece = _TAG.sub("", line).strip()
        if piece:
            cur["text"] = (cur["text"] + " " + piece).strip()
    return [c for c in out if c["text"]]


def dedup(lines: list[dict]) -> list[dict]:
    """去掉滚动式自动字幕的重复：后一行完全包含前一行时，用后一行取代前一行。"""
    out: list[dict] = []
    for c in lines:
        if out:
            prev = out[-1]
            if c["text"] == prev["text"] or prev["text"] in c["text"]:
                prev["text"] = c["text"]
                prev["t1"] = c["t1"]
                continue
        out.append(dict(c))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="SRT/VTT → transcript 数组")
    ap.add_argument("srt", type=Path, help="原文字幕")
    ap.add_argument("--zh", type=Path, help="中文译文字幕（行数需与原文一致）")
    ap.add_argument("--no-dedup", action="store_true", help="保留滚动字幕的重复行")
    a = ap.parse_args()

    lines = parse(a.srt.read_text(encoding="utf-8", errors="ignore"))
    if not a.no_dedup:
        lines = dedup(lines)

    zh = None
    if a.zh:
        zh = parse(a.zh.read_text(encoding="utf-8", errors="ignore"))
        if not a.no_dedup:
            zh = dedup(zh)
        if len(zh) != len(lines):
            print(f"[warn] 译文 {len(zh)} 行 ≠ 原文 {len(lines)} 行，按位置对齐，"
                  "多余的丢弃、不足的留空", file=sys.stderr)

    for i, c in enumerate(lines):
        c["zh"] = zh[i]["text"] if zh and i < len(zh) else None

    json.dump(lines, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
