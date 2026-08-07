"""转写行翻译：原文非中文时，逐行译出中文（报告里原文+译文双行显示）。

按批调用（每批 ~40 行）控制单次输入体量；译文数量与输入不一致时按序
对齐、缺的补空——宁可个别行缺译文，也不让错位毁掉整个时间轴。
"""
from __future__ import annotations

from . import llm
from .schemas import TranslationBatch
from .srt import Line

_BATCH = 40

_SYSTEM = (
    "你是字幕译者。把给定的每一行口语转写忠实译成简体中文：\n"
    "- 保持口语感，不书面化改写，不合并/拆分行\n"
    "- 专有名词、产品名保留原文\n"
    "- 输出条数必须与输入完全一致，一一对应"
)


def translate_lines(lines: list[Line]) -> None:
    """就地填充每行的 .zh 字段。"""
    for i in range(0, len(lines), _BATCH):
        batch = lines[i : i + _BATCH]
        numbered = "\n".join(f"{j + 1}. {l.text}" for j, l in enumerate(batch))
        out = llm.parse(_SYSTEM, f"逐行翻译（共 {len(batch)} 行）：\n{numbered}",
                        TranslationBatch, max_tokens=8000)
        items = out.items[: len(batch)] + [""] * max(0, len(batch) - len(out.items))
        for l, zh in zip(batch, items):
            l.zh = zh.strip() or None
