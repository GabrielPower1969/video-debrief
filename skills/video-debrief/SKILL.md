---
name: video-debrief
description: >-
  把视频 / 播客 / 访谈的转写稿做成一份自带播放器的 HTML 复盘报告：概述、核心
  观点、章节时间轴、逐段精读、金句、逐行转写，每一个时间点都是 ▶ 按钮，点了
  就跳回原片那一刻；播放时浮出实时字幕并高亮当前转写行。重点句子标黄，
  报告自带夜间 / 白天两套配色。原文是中文就出中文报告，原文非中文就出
  「原文 + 中文译文」双语报告。
  Use this WHENEVER the user hands over a video/podcast/interview — a YouTube or
  Bilibili link, an audio/video file, or an .srt/.vtt/.txt transcript — and wants
  it summarized, 总结 / 归纳 / 复盘 / 拆解 / 分析, or turned into notes, a doc, or
  a report. Trigger even if they never say "HTML" or "报告". Trigger especially
  when they want the original timeline preserved (还原时间轴 / 带时间戳 / 能跳回去
  听), or want the summary clickable and playable instead of a wall of text.
  Do NOT use it for pure transcription with no analysis, or for text documents
  that have no timeline.
---

# Video Debrief

把「看完一个 46 分钟的视频」压缩成「5 分钟读完，想细看就点回去听」。

产物是**单个 HTML 文件**，和音频放同一目录就能播。报告里每个时间点都是按钮，
所以读者永远能一键回到原片求证——这是它和普通摘要的根本区别，也是下面所有
硬规则存在的理由。

## 输入

至少要有**带时间戳的转写**。没有就先做出来：

| 手上有什么 | 怎么办 |
|---|---|
| `.srt` / `.vtt` | 直接用，时间戳最准 |
| 视频链接 | `yt-dlp` 下音频；平台有字幕就用，没有就转写 |
| 音频/视频文件 | 本地 `whisper` / `faster-whisper` 转成 SRT（别上传到外部服务） |
| 只有纯文本 | 可以做，但要告诉用户没有时间轴，▶ 按钮会全部消失 |

音频是可选的。有音频报告才能播；没有就把 `data["audio"]` 填 `null`，
模板会自动隐藏播放条、时间戳降级成纯展示。

## 工作流

1. **通读转写，判定原文语言。** 中文 → 单语报告；非中文 → 双语报告。
   判定别只看语言码（平台经常标错），抽前 80 行看 CJK 字符占比更靠谱。

2. **非中文原文：逐行翻译。** 分批翻（40 行一批），并且**必须保证行数对齐**——
   翻译错位会让整条时间轴失去意义，宁可个别行留空也不能串行。

3. **分片消化。** 把转写切成 ~9000 字符的片段，每片让模型划 1~3 个章节、
   摘 1~3 句原话、写一段纪要。长稿一次性喂进去，模型会丢掉中段内容——
   这不是省 token 的问题，是覆盖率的问题。

4. **全局汇总。** 把各片纪要 + 候选金句喂回去，产出概述、主题标签、
   4~8 条核心观点（每条配逐字原话 + 时间点）、3~6 句精选金句。

5. **组装 `REPORT_DATA`，顺手把重点标黄。** 字段逐条说明见
   **`references/data-contract.md`**。概述、观点、章节纪要里用 `==这句话==`
   包住最吃重的那半句，渲染出来是荧光笔效果；**引文和转写不标**，它们必须逐字。
   一段黄一处就够——满屏黄和不标是一个效果。

6. **渲染。**
   ```bash
   python3 scripts/render_report.py data.json report.html
   ```
   把 `audio.mp3` 放到 `report.html` 旁边，报告就能播了。

## 硬规则

**时间戳只能抄，不能编。** 喂给模型的每一行都前缀成 `[123s|02:03] 原文…`，
并在 system prompt 里明说「时间戳必须取自行首标记里的整数秒，禁止估算」。
模型自己估的时间戳一定会偏，而偏掉的时间戳会让所有 ▶ 按钮变成噪音——
读者点两次跳错地方，就再也不会点第三次了。

**引文逐字摘录，不许润色。** 报告的信任感来自「点过去能对上」。改写过的
引文跳过去对不上原声，整份报告的可信度一起塌。汇总完再拿候选金句的文本
做一次精确匹配，把时间戳强制对回候选值，防止模型在汇总阶段偷偷改词。
这条也管标黄：`==…==` 只能加在自己写的话里，**引文一个字都不许动**。

**双语用 BiText 表达。** `{"zh": ..., "en": ...}`：原文中文时 `en` 一律为
`null`（模板会只渲染一行）；原文非中文时 `en` 放原文、`zh` 放译文，模板会把
原文用衬线斜体放上面、译文弱化放下面。

**覆盖率要检查。** 转写最后一句离片尾超过 10%，说明字幕或下载被截断了。
这时候产出的报告看起来完整、实际上只讲了开头——一定要告警而不是静默出报告。

## 目录

| 路径 | 什么时候读 |
|---|---|
| `references/data-contract.md` | 组装 `REPORT_DATA` 前 |
| `references/design.md` | 要改版式/配色/加区块前 |
| `assets/report_template.html` | 一般不用读，`render_report.py` 会处理 |
| `scripts/render_report.py` | 渲染：`data.json` + 模板 → 单文件 HTML |
| `scripts/srt_to_transcript.py` | 把 SRT（可选 + 中文 SRT）转成 `transcript` 数组 |
