---
name: video-analysis-report
description: 生成带内嵌音频播放器的视频/访谈分析 HTML 报告。当需要把视频转写+摘要渲染成可交互报告（观点卡片、章节时间轴、金句、逐行转写，全部带 ▶ 跳转播放按钮）时使用本模板，不要从零手写 HTML。
---

# video-analysis-report

单文件 HTML 报告模板，效果对标 interview-analysis 一类的访谈分析报告：

- **内嵌播放器**（sticky 置顶）：报告与 `audio.mp3` 同目录即可播放
- **全时间轴联动**：观点引文、章节、金句、转写行都带 `▶ mm:ss` 按钮，点击即跳转播放；
  播放时转写自动高亮当前行 + 滚动跟随，播放器显示当前章节名
- **双语规则**：原文中文 → 只显示中文；原文非中文 → 原文在上、中文译文在下
- **明暗双主题**（跟随系统），无任何外部资源依赖，可离线打开/直接分发

## 用法

模板通过占位符注入数据，渲染只需一次字符串替换：

```python
html = TEMPLATE.read_text(encoding="utf-8")
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # 防 </script> 早闭合
html = html.replace("/*__REPORT_DATA__*/null", payload)
out_path.write_text(html, encoding="utf-8")
```

音频文件放在报告同目录，`data["audio"]` 填相对文件名（如 `"audio.mp3"`）；
填 `null` 则隐藏播放器、时间戳降级为纯展示。

## 数据契约（REPORT_DATA）

BiText = `{"zh": str, "en": str|null}`；原文中文时 `en` 为 null。

| 字段 | 类型 | 说明 |
|---|---|---|
| `meta.short_title` | str | 大标题（5~10 字短标题） |
| `meta.title` | str | 原始视频标题（与短标题不同才显示） |
| `meta.platform / uploader / upload_date / url` | str | 头部 kicker 与 footer 链接 |
| `meta.duration` | float | 秒 |
| `meta.lang` | str | `"zh"` 或原文语言码（非 zh 触发双语显示标签） |
| `meta.source_label` | str | 字幕来源说明（如 `官方字幕` / `Whisper small 转写`） |
| `meta.generated_at` | str | 生成时间 |
| `audio` | str\|null | 音频相对路径 |
| `overview` | BiText | 全片概述 |
| `topics` | list[str] | 主题标签 |
| `stats` | list[{label, value}] | 顶部数字瓦片（纯文本，已按规范用正文墨色） |
| `viewpoints` | list | `{title: BiText, detail: BiText, quote: str, quote_zh: str|null, t: float}` |
| `chapters` | list | `{title: BiText, summary: BiText, t_start: float, t_end: float}` |
| `quotes` | list | `{text: str, text_zh: str|null, t: float}` |
| `transcript` | list | `{t0: float, t1: float, text: str, zh: str|null}` |

空列表的区块会自动隐藏。所有文本经 `textContent` 注入，天然防 XSS，
数据里不要再做 HTML 转义。

## 设计约定（改样式前先读）

- 数字瓦片/正文**不使用数据系列色**：数值用正文墨色，标签用弱化色（dataviz 规范）
- accent 色只用于**交互元素**（▶ 按钮、当前章节、激活行）与主题标签
- 布局单栏 880px，窄屏自适应；宽内容自带滚动，页面不横向溢出
