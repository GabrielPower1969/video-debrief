---
name: video-analysis-report
description: 生成带内嵌音频播放器的视频/访谈分析 HTML 报告。当需要把视频转写+摘要渲染成可交互报告（观点卡片、章节时间轴、逐段精读、金句、逐行转写，全部带 ▶ 跳转播放按钮，底部播放条 + 实时字幕）时使用本模板，不要从零手写 HTML。
---

# video-analysis-report

单文件 HTML 报告模板，深色专业版式：

- **左侧固定目录**（滚动高亮当前章节）+ 单栏正文，1200px 栅格，窄屏自动折叠
- **底部固定播放条**：毛玻璃，报告与 `audio.mp3` 同目录即可播放
- **实时字幕条**：播放时在播放条上方浮出当前这句（原文 + 中文译文），可一键开关，
  状态存 localStorage
- **全时间轴联动**：观点、章节、逐段精读、金句、转写行都带 `▶ mm:ss` 按钮，
  点击即跳转播放并变成 ⏸ 状态；转写自动高亮当前行 + 滚动跟随
- **双语规则**：原文中文 → 只显示中文；原文非中文 → 原文用衬线斜体在上、
  中文译文在下
- 无任何外部资源依赖，可离线打开/直接分发；带打印样式

## 用法

模板通过占位符注入数据，渲染只需一次字符串替换：

```python
html = TEMPLATE.read_text(encoding="utf-8")
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # 防 </script> 早闭合
html = html.replace("/*__REPORT_DATA__*/null", payload)
out_path.write_text(html, encoding="utf-8")
```

音频文件放在报告同目录，`data["audio"]` 填相对文件名（如 `"audio.mp3"`）；
填 `null` 则隐藏播放条与字幕条，`body.no-audio` 让时间戳降级为纯展示。

## 数据契约（REPORT_DATA）

BiText = `{"zh": str, "en": str|null}`；原文中文时 `en` 为 null。

| 字段 | 类型 | 说明 |
|---|---|---|
| `meta.short_title` | str | 大标题（5~10 字短标题） |
| `meta.title` | str | 原始视频标题（与短标题不同才显示） |
| `meta.platform / uploader / upload_date / url` | str | 头部 pill 与 footer 链接 |
| `meta.duration` | float | 秒 |
| `meta.lang` | str | `"zh"` 或原文语言码（非 zh 触发双语显示） |
| `meta.source_label` | str | 字幕来源（如 `平台字幕（en）` / `Whisper small 转写`） |
| `meta.generated_at` | str | 生成时间 |
| `audio` | str\|null | 音频相对路径 |
| `overview` | BiText | 全片概述（渲染成紫蓝渐变 callout） |
| `topics` | list[str] | 主题标签 |
| `stats` | list[{label, value}] | 数字瓦片（纯文本，正文墨色） |
| `viewpoints` | list | `{title: BiText, detail: BiText, quote: str, quote_zh: str|null, t: float}` |
| `chapters` | list | `{title: BiText, summary: BiText, t_start: float, t_end: float}` |
| `quotes` | list | `{text: str, text_zh: str|null, t: float}` |
| `transcript` | list | `{t0: float, t1: float, text: str, zh: str|null}` |

章节同时驱动「章节时间轴」（点状轴速览）和「逐段精读」（sticky 时间列 + 讲了什么
+ 落在本段区间的观点原话）。空列表的区块连同它的目录项一起隐藏，编号自动顺延。
所有文本经 `textContent` 注入，天然防 XSS，数据里不要再做 HTML 转义。

## 设计约定（改样式前先读）

- 双 accent：`--brand` 蓝用于交互（▶ 按钮、当前目录项、激活行、字幕条左边框），
  `--brand2` 紫用于引用/主题标签/概述 callout
- 数字瓦片与正文**不使用数据系列色**：数值用正文墨色，标签用弱化色（dataviz 规范）
- 非中文原文一律 `.en`（Georgia/宋体 斜体），中文译文 `.zh`（弱化、小一号）
- 页面不横向溢出；转写区自带纵向滚动；`body` 留 84px 给固定播放条

## 出处

视觉语言脱胎于 [GabrielPower1969/InterviewAnalysis](https://github.com/GabrielPower1969/InterviewAnalysis)
的 `interview-analysis` skill（MIT）——深色面板、侧栏目录、`.pb` 播放按钮、
底部播放条与实时字幕条。本模板按「视频分析」的内容模型重做了信息架构
（观点 / 章节 / 逐段 / 金句 / 转写），并改为由 `REPORT_DATA` 驱动 JS 渲染，
而非填 `{{PLACEHOLDER}}`。
