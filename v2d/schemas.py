"""LLM 结构化输出的数据契约。

双语约定：所有展示文本都是 BiText —— zh 必填；原文非中文时 en 存原文语言
版本（报告里原文在上、中文在下）。原文是中文时 en 一律为 null。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class BiText(BaseModel):
    zh: str = Field(description="中文版本（原文为中文时就是原文；否则为忠实翻译）")
    en: str | None = Field(default=None, description="原文非中文时的原文语言版本；原文为中文时为 null")


class Chapter(BaseModel):
    title: BiText = Field(description="章节标题，8 字以内")
    summary: BiText = Field(description="该章节讲了什么，2~3 句")
    t_start: float = Field(description="章节起始秒数，必须取自给定的 [Ns|mm:ss] 标记")
    t_end: float = Field(description="章节结束秒数")


class TQuote(BaseModel):
    text: str = Field(description="原文原句，逐字摘录，不许改写")
    text_zh: str | None = Field(default=None, description="原文非中文时给中文译文，否则 null")
    t: float = Field(description="这句话出现的秒数，必须取自给定标记")


class ChunkDigest(BaseModel):
    chapters: list[Chapter] = Field(description="本片段划出的 1~3 个章节")
    quotes: list[TQuote] = Field(description="本片段里 1~3 句最有信息量/最有态度的原话")
    digest: str = Field(description="本片段内容的中文纪要，供后续全局汇总使用，150 字以内")


class Viewpoint(BaseModel):
    title: BiText = Field(description="观点一句话标题")
    detail: BiText = Field(description="观点展开：讲话人的论证/例子/态度，2~4 句")
    quote: str = Field(description="支撑这个观点的原文原句，逐字摘录")
    quote_zh: str | None = Field(default=None, description="原文非中文时给译文")
    t: float = Field(description="该观点对应的时间点（秒），必须取自给定标记")


class ReportCore(BaseModel):
    overview: BiText = Field(description="全片概述，连贯段落，150~250 字，串起核心逻辑")
    topics: list[str] = Field(description="3~6 个中文主题标签")
    viewpoints: list[Viewpoint] = Field(description="4~8 个核心观点，按出现顺序")
    quotes: list[TQuote] = Field(description="3~6 句全片金句（从各片段候选里精选）")


class TranslationBatch(BaseModel):
    items: list[str] = Field(description="逐条对应输入行的中文译文，数量必须与输入一致")
