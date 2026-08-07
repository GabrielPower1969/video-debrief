"""报告渲染：数据 dict → 单文件 report.html。

渲染逻辑本身住在 skill 里（skills/video-debrief/scripts/render_report.py），
这里只是把它接进流水线——这样 skill 目录单独拿走也是完整可用的，不会退化成
「必须配合 v2d 才能跑」的半成品。数据契约见
skills/video-debrief/references/data-contract.md。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "video-debrief"
TEMPLATE = SKILL / "assets" / "report_template.html"
_RENDERER = SKILL / "scripts" / "render_report.py"


def _load():
    spec = importlib.util.spec_from_file_location("v2d_render_report", _RENDERER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def render(data: dict, out_path: Path, *, progress=print) -> Path:
    mod = _load()
    for w in mod.check(data):
        progress(f"[v2d] ⚠ {w}")
    return mod.render(data, out_path, TEMPLATE)
