# video-to-doc-agent

把一个视频链接变成一份**可播放、可交互的 HTML 分析报告**。

给它一个 YouTube 或 Bilibili 链接，它会：

1. **下载**音频（和平台字幕，如果有）
2. 没字幕就用 **Whisper 本地转写**，统一产出 SRT
3. 原文非中文时，**逐行翻译**出中文对照 SRT
4. 用 Claude 做 **map-reduce 摘要**：概述 / 主题标签 / 核心观点 / 章节时间轴 / 金句
5. 渲染成单文件 `report.html`：**内嵌音频播放器**，观点引文、章节、金句、
   逐行转写全部带 `▶ mm:ss` 按钮，点击即跳到对应片段播放；播放时转写自动
   高亮当前行并滚动跟随

语言规则：**原文中文 → 纯中文报告；原文英文（或其他语言）→ 原文 + 中文双语报告**。

## 安装

需要 Python 3.10+。必须用 `.venv` 这个目录名——`./handle` 写死了用
`.venv/bin/python` 启动：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

ffmpeg 不用单独装（走 `imageio-ffmpeg` 自带的静态二进制）。

还需要 Anthropic 凭证（任一即可）：

- 环境变量 `ANTHROPIC_API_KEY`
- Claude Code 登录态（`~/.config/anthropic/` 下的凭证）

## 用法

```bash
# YouTube（有无字幕都行；有官方/自动字幕就直接用，没有就 Whisper 转写）
./handle "https://www.youtube.com/watch?v=xxxx"

# Bilibili（基本都没字幕，自动走 Whisper）
./handle "https://www.bilibili.com/video/BV1xxxx"

# 转写模型：tiny/base/small(默认)/medium/large-v3，越大越准越慢
./handle "https://..." --asr-model medium

# 平台字幕质量差，强制用 Whisper 重新转写
./handle "https://..." --force-asr

# 视频需要登录（如 B 站高清、会员视频）：借浏览器 cookie
./handle "https://..." --cookies-from-browser chrome
./handle "https://..." --cookies cookies.txt

# 离线示例（不下载、不调 LLM，看看报告长什么样）
./handle --demo
```

## 输出

每个视频一个目录，目录名是 LLM 起的 5~10 字短标题：

```
output/<短标题>/
├── report.html        # 分析报告（打开即用，音频在旁边就能播放）
├── audio.mp3          # 音频
├── transcript.srt     # 原文字幕/转写
├── transcript.zh.srt  # 中文对照（原文非中文时才有）
└── data.json          # 报告的结构化数据
```

`report.html` 无外部依赖，配上同目录的 `audio.mp3` 可以整目录拷走分发；
单发 HTML 也能打开，只是播放器会隐藏、时间戳降级为纯展示。

## 报告模板即 skill

报告的 HTML 模板沉淀在 `.claude/skills/video-analysis-report/`——
数据契约、注入方式、设计约定见其中的 `SKILL.md`。想改样式或在别的项目
复用这套“带播放器的访谈分析报告”，直接拿这个 skill。

## 已知边界

- 下载依赖 `yt-dlp`，受平台风控影响；B 站部分视频需要 `--cookies-from-browser`
- Whisper 在 CPU 上跑 `small` 模型大约是视频时长的 0.5~1 倍时间
- 摘要/翻译走 Claude API，会产生 token 消耗（长视频按 ~9000 字符分片）
