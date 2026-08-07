# Agent Instructions (Cursor / OpenAI Codex / 其他 AI 编码工具)

本仓库包含 **video-debrief**：把视频/播客/访谈变成一份自带播放器的 HTML
复盘报告的 skill。为 Claude Code 编写，但任何有文件读写和执行能力的 agent
都能用。

## 用户给了一个视频链接 / 音频 / 字幕，要总结、复盘、做文档时

按 **`skills/video-debrief/SKILL.md`** 执行。要点：

1. **拿到带时间戳的转写**。有 `.srt`/`.vtt` 直接用；只有链接就 `yt-dlp` 下音频
   （B 站只下音频，别要字幕）；只有媒体文件就本地 `whisper` / `faster-whisper`
   转成 SRT——**不要把媒体上传到任何外部服务**。
2. **判定原文语言**：中文出单语报告；非中文出「原文 + 中文译文」双语报告，
   逐行翻译时必须保证行数对齐。
3. **分片消化再全局汇总**：~9000 字符一片，每片划章节 / 摘原话 / 写纪要，
   再把纪要汇总成概述、主题、核心观点、金句。长稿一次性喂进去会丢中段。
4. **组装 `REPORT_DATA`**，字段见
   `skills/video-debrief/references/data-contract.md`。
5. **渲染**：
   ```bash
   python3 skills/video-debrief/scripts/render_report.py data.json report.html
   ```
   把音频放到 `report.html` 同目录，报告就能播。
6. 报告、音频、字幕放在同一个目录里交付。

辅助脚本：`skills/video-debrief/scripts/srt_to_transcript.py` 把 SRT
（可选加一份中文 SRT）转成 `transcript` 数组，顺带清理滚动式自动字幕的重复行。

## 硬规则

- **时间戳只能抄不能编**。喂给模型的转写每行前缀 `[123s|02:03]`，并明确要求
  时间戳取自这些标记。估算出来的时间戳会让报告里所有 ▶ 按钮失效。
- **引文逐字摘录**，汇总后再和候选金句做精确匹配把时间戳对回去。
- **覆盖率检查**：转写最后一句离片尾超过 10% 就告警——多半是下载或字幕被截断，
  这时候的报告看着完整、其实只讲了开头。
- 报告必须保持自包含：不引外部 CSS/JS/字体/图片，离线可开。

## 仓库里的另一半

`v2d/` 是把上面整条流程自动化的 Python 实现，`./handle <url>` 一条命令跑完。
只想要报告模板的话，`skills/` 目录可以单独拿走。
