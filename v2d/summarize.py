"""摘要：Line 列表 → 章节（带时间轴）+ 观点 + 金句 + 概述。

两段式（map-reduce）：
  1. 分片消化：转写按 ~9000 字符切片，每片让 LLM 划章节、摘金句、写纪要。
     时间戳只能取自我们标注的 [Ns|mm:ss]，模型不许自己编。
  2. 全局汇总：所有片段纪要 + 候选金句 → 概述 / 主题标签 / 核心观点 / 精选金句。

双语规则贯穿两段：原文中文 → 只填 zh；原文非中文 → en 存原文语言版本。
"""
from __future__ import annotations

from . import llm
from .schemas import Chapter, ChunkDigest, ReportCore, TQuote
from .srt import Line, fmt_mmss

_CHUNK_CHARS = 9000

_BILINGUAL_RULE = (
    "双语规则：本视频原文【不是中文】。所有 BiText 字段：en 填原文语言版本，"
    "zh 填忠实中文翻译；quote/text 逐字摘录原文，quote_zh/text_zh 给中文译文。"
)
_ZH_RULE = (
    "双语规则：本视频原文【是中文】。所有 BiText 的 en 一律为 null；"
    "quote_zh/text_zh 一律为 null（原文即中文）。"
)

_HL_RULE = (
    "重点标黄：在自己撰写的文字里，用 ==这样== 包住最吃重的半句，会渲染成荧光笔效果。\n"
    "适用于概述、观点标题与正文、章节标题与纪要；每段最多标一处，全标等于没标。\n"
    "禁止标在 quote / text 等逐字原话上——引文一个字符都不能动。\n"
)

_SYSTEM_CHUNK = (
    "你在分析一段视频转写。行首的 [Ns|mm:ss] 是该行的开始时间（N 为整数秒）。\n"
    "任务：1) 把这段内容划成 1~3 个章节；2) 摘 1~3 句最有信息量或最有态度的原话；\n"
    "3) 写一段 150 字以内的中文纪要供全局汇总用。\n"
    "硬性要求：所有时间戳必须取自行首标记里的整数秒 N，禁止编造或估算。\n"
    + _HL_RULE
)

_SYSTEM_FINAL = (
    "你在为一个视频写分析报告的全局部分。输入是各片段的纪要与候选金句（带秒数）。\n"
    "任务：1) 150~250 字概述，串起全片核心逻辑；2) 3~6 个中文主题标签；\n"
    "3) 4~8 个核心观点（每个都要有逐字原话支撑 + 时间点）；4) 精选 3~6 句金句。\n"
    "硬性要求：观点/金句的时间戳与原句只能来自输入提供的候选，不许编造。\n"
    + _HL_RULE
)


def _timed(lines: list[Line]) -> list[str]:
    return [f"[{int(l.start)}s|{fmt_mmss(l.start)}] {l.text}" for l in lines]


def _chunks(rows: list[str], budget: int = _CHUNK_CHARS) -> list[str]:
    out, cur, size = [], [], 0
    for r in rows:
        if cur and size + len(r) > budget:
            out.append("\n".join(cur))
            cur, size = [], 0
        cur.append(r)
        size += len(r) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def summarize(lines: list[Line], *, title: str, is_zh: bool,
              progress=print) -> tuple[ReportCore, list[Chapter]]:
    rule = _ZH_RULE if is_zh else _BILINGUAL_RULE
    chunks = _chunks(_timed(lines))

    digests: list[ChunkDigest] = []
    for i, chunk in enumerate(chunks, 1):
        progress(f"[v2d]   摘要片段 {i}/{len(chunks)} ...")
        d = llm.parse(_SYSTEM_CHUNK + rule,
                      f"视频标题：{title}\n\n转写片段：\n{chunk}",
                      ChunkDigest, max_tokens=8000)
        digests.append(d)

    chapters = sorted((c for d in digests for c in d.chapters), key=lambda c: c.t_start)
    candidate_quotes: list[TQuote] = [q for d in digests for q in d.quotes]

    digest_text = "\n\n".join(
        f"片段 {i + 1} 纪要：{d.digest}\n候选金句：\n"
        + "\n".join(f"  [{int(q.t)}s] {q.text}" + (f"（译：{q.text_zh}）" if q.text_zh else "")
                    for q in d.quotes)
        for i, d in enumerate(digests)
    )
    progress("[v2d]   全局汇总 ...")
    core = llm.parse(_SYSTEM_FINAL + rule,
                     f"视频标题：{title}\n\n{digest_text}",
                     ReportCore, max_tokens=10000)

    # 时间戳兜底：全局挑出来的金句若与候选文本相同，则强制对齐候选的时间戳
    by_text = {q.text: q.t for q in candidate_quotes}
    for q in core.quotes:
        if q.text in by_text:
            q.t = by_text[q.text]

    return core, chapters
