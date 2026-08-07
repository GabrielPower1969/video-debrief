#!/usr/bin/env python3
"""把 REPORT_DATA(JSON) 注入模板，产出单文件 HTML 报告。

    python3 render_report.py data.json report.html [--template path]

只依赖标准库。字段说明见 ../references/data-contract.md。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MARKER = "/*__REPORT_DATA__*/null"
DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "report_template.html"

REQUIRED = ("meta", "overview")


def render(data: dict, out_path: Path, template: Path = DEFAULT_TEMPLATE) -> Path:
    html = template.read_text(encoding="utf-8")
    if MARKER not in html:
        raise SystemExit(f"模板缺少注入占位符 {MARKER}：{template}")
    # "</" 转义掉，防止数据里的 </script> 提前闭合脚本标签
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html.replace(MARKER, payload), encoding="utf-8")
    return out_path


def check(data: dict) -> list[str]:
    """返回警告列表——只提醒，不阻断：报告缺几个区块照样有用。"""
    warn = []
    for k in REQUIRED:
        if not data.get(k):
            warn.append(f"缺少 {k}")
    if not data.get("transcript"):
        warn.append("没有 transcript：实时字幕和转写区会消失")
    if data.get("audio") is None:
        warn.append("audio 为 null：播放条隐藏，时间戳降级为纯展示")

    chs = data.get("chapters") or []
    for a, b in zip(chs, chs[1:]):
        if b.get("t_start", 0) < a.get("t_start", 0):
            warn.append("chapters 没有按 t_start 升序，逐段精读会乱序")
            break

    dur = float((data.get("meta") or {}).get("duration") or 0)
    lines = data.get("transcript") or []
    if dur and lines:
        end = float(lines[-1].get("t1") or lines[-1].get("t0") or 0)
        if end < dur * 0.9:
            warn.append(f"转写只覆盖到 {end:.0f}s / 全片 {dur:.0f}s（{end / dur:.0%}）"
                        "——字幕或下载可能被截断了")
    return warn


def main() -> None:
    ap = argparse.ArgumentParser(description="REPORT_DATA(JSON) → 单文件 HTML 报告")
    ap.add_argument("data", type=Path, help="REPORT_DATA 的 JSON 文件")
    ap.add_argument("out", type=Path, help="输出的 report.html")
    ap.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    a = ap.parse_args()

    data = json.loads(a.data.read_text(encoding="utf-8"))
    for w in check(data):
        print(f"[warn] {w}", file=sys.stderr)
    print(f"→ {render(data, a.out, a.template)}")


if __name__ == "__main__":
    main()
