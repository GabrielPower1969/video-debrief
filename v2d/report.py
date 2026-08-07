"""报告渲染：数据 dict → 单文件 report.html。

模板是本仓库的 skill（.claude/skills/video-analysis-report/template.html），
渲染只做一次占位符替换，数据契约见该 skill 的 SKILL.md。
"""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "video-analysis-report" / "template.html"


def render(data: dict, out_path: Path) -> Path:
    html = TEMPLATE.read_text(encoding="utf-8")
    # 防止 JSON 里的 "</script>" 提前闭合 script 标签
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    marker = "/*__REPORT_DATA__*/null"
    if marker not in html:
        raise RuntimeError(f"模板缺少注入占位符：{TEMPLATE}")
    out_path.write_text(html.replace(marker, payload), encoding="utf-8")
    return out_path
