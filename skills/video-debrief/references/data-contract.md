# REPORT_DATA 数据契约

`render_report.py` 接受一个 JSON 对象，注入模板的 `/*__REPORT_DATA__*/null`
占位符。所有文本在浏览器里经 `textContent` 写入，**天生防 XSS，不要再做 HTML
转义**（转义了反而会看到 `&amp;`）。

空列表的区块连同它的目录项一起隐藏，编号自动顺延——不需要的部分给 `[]` 就行。

## 重点标黄：`==这样==`

在文字里用 `==` 包住的部分会渲染成荧光笔划过的黄色重点。

**可以标黄的字段**（都是我们自己写的话）：

- `overview`
- `viewpoints[].title` / `viewpoints[].detail`
- `chapters[].title` / `chapters[].summary`

**不解析的字段**（必须逐字）：`viewpoints[].quote`、`quotes[].text`、
`transcript[].text` 及它们的 `_zh` / `zh` 对应项。原话里真出现 `==` 也会原样
显示——引文被吃掉几个字符就是篡改，报告的信任感全靠这个。

```json
{"zh": "核心判断是：==差距不在模型，在使用者==。", "en": null}
```

一段里最多黄一处，全黄等于没重点。中英双语时两边各自标，不要求位置对齐。

## BiText

双语的统一表达：

```json
{"zh": "中文", "en": "原文"}
```

- 原文**是中文**：`en` 一律 `null`，模板只渲染一行。
- 原文**非中文**：`en` 放原文（模板用衬线斜体显示在上），`zh` 放译文
  （弱化、小一号，显示在下）。

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|:--:|---|
| `meta` | object | ✓ | 见下 |
| `audio` | str \| null | ✓ | 音频**相对**路径，如 `"audio.mp3"`；`null` 则隐藏播放条 |
| `overview` | BiText | ✓ | 全片概述，150~250 字。渲染成紫蓝渐变 callout |
| `topics` | list[str] | | 主题标签，3~6 个 |
| `stats` | list[{label, value}] | | 顶部数字瓦片，建议 4 个；`value` 是已格式化的字符串 |
| `viewpoints` | list[Viewpoint] | | 核心观点，4~8 条 |
| `chapters` | list[Chapter] | | 章节；同时驱动「章节时间轴」和「逐段精读」两个区块 |
| `quotes` | list[Quote] | | 金句，3~6 句 |
| `transcript` | list[Line] | | 逐行转写；同时是实时字幕的数据源 |

### meta

| 字段 | 类型 | 说明 |
|---|---|---|
| `short_title` | str | 大标题。5~10 字的短标题，比原标题好读 |
| `title` | str | 原始视频标题；与 `short_title` 不同才显示在副标题位 |
| `platform` | str | 如 `Youtube` / `BiliBili` |
| `uploader` | str | UP主 / 频道 |
| `upload_date` | str | 发布日期 |
| `url` | str | 原视频链接，渲染在 footer |
| `duration` | float | 秒 |
| `lang` | str | `"zh"` 或原文语言码。非 `zh` 时头部显示「中英双语」 |
| `source_label` | str | 字幕来源，如 `平台字幕（en）` / `Whisper small 转写`。会写进 footer 的免责说明 |
| `generated_at` | str | 生成时间 |

### Viewpoint

```json
{
  "title":    {"zh": "高薪的真实价格是日历的所有权", "en": "The real price of the salary is your calendar"},
  "detail":   {"zh": "职级和股票是可见的收益……", "en": "Title and stock are the visible upside…"},
  "quote":    "Thirty hours of meetings a week is not a career, it's a treadmill.",
  "quote_zh": "一周三十小时的会议不是事业，是跑步机。",
  "t":        14.0
}
```

`quote` 是**逐字原话**（原文语言）；`quote_zh` 是它的中文译文，原文本就是中文时填
`null`。`t` 是这句话在原片中的秒数，必须来自转写行的时间戳。

`title` / `detail` 可以用 `==…==` 标黄；`quote` / `quote_zh` 不行。

### Chapter

```json
{
  "title":   {"zh": "离开的决定", "en": "The Decision"},
  "summary": {"zh": "十一年大厂生涯与外界眼中「疯了」的辞职决定。", "en": "Eleven years in, and a decision everyone called crazy."},
  "t_start": 0.0,
  "t_end":   23.0
}
```

章节要**按 `t_start` 升序**且首尾相接覆盖全片，否则「逐段精读」会漏掉内容。
落在 `[t_start, t_end)` 区间内的 `viewpoints[].quote` 会自动挂到这一段下面。

### Quote

```json
{"text": "Quitting isn't the brave part…", "text_zh": "辞职不是勇敢的部分……", "t": 44.0}
```

### Line（transcript）

```json
{"t0": 0.0, "t1": 6.0, "text": "I spent eleven years at a big tech company.", "zh": "我在一家大厂待了十一年。"}
```

`zh` 是译文，原文是中文时填 `null`。`t0`/`t1` 决定实时字幕在哪一秒显示哪一句，
所以**区间不要重叠**，滚动式自动字幕要先做去重合并再喂进来。

## 最小可用示例

```json
{
  "meta": {"short_title": "离开大厂这一年", "lang": "zh", "duration": 78,
           "source_label": "Whisper small 转写", "generated_at": "2026-08-07"},
  "audio": "audio.mp3",
  "overview": {"zh": "讲述者回顾了辞职回老家的一年……", "en": null},
  "topics": ["职业选择", "大厂围城"],
  "stats": [{"label": "时长", "value": "01:18"}, {"label": "核心观点", "value": "3"}],
  "viewpoints": [], "chapters": [], "quotes": [],
  "transcript": [{"t0": 0, "t1": 6, "text": "我在一家大厂待了十一年。", "zh": null}]
}
```
