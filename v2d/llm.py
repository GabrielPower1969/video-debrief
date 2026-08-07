"""统一的 LLM 入口（Anthropic Claude，结构化输出）。

原则：没有可用凭证就直接报错，绝不静默降级成低质量摘要。
模型默认 claude-fable-5，可用环境变量 V2D_MODEL 覆盖。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

MODEL = os.environ.get("V2D_MODEL", "claude-fable-5")


class LLMUnavailableError(RuntimeError):
    pass


def is_llm_available() -> bool:
    """直接检查凭证来源——Anthropic() 构造器不校验凭证，构造成功不代表能用。"""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    cfg = os.environ.get("ANTHROPIC_CONFIG_DIR")
    base = Path(cfg) if cfg else Path.home() / ".config" / "anthropic"
    creds = base / "credentials"
    return creds.is_dir() and any(creds.glob("*.json"))


@lru_cache(maxsize=1)
def _client():
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise LLMUnavailableError("未安装 anthropic SDK：pip install -r requirements.txt") from e
    return anthropic.Anthropic()


def parse(system: str, user: str, schema: type[BaseModel], *, max_tokens: int = 8000):
    """调用 Claude 并解析成 pydantic 对象。失败直接抛。"""
    resp = _client().messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"模型拒绝了该请求: {getattr(resp, 'stop_details', '')}")
    return resp.parsed_output


class _ShortTitle(BaseModel):
    short_title: str


def short_title(video_title: str) -> str:
    """压成 5~10 字短标题，用作产物目录名。语义取舍只能靠 LLM，正则硬截断做不到。"""
    out = parse(
        system=(
            "你负责把视频标题压缩成简短的文件夹名。规则：\n"
            "- 5~10 个字，抓住视频主旨\n"
            "- 原标题是中文就用中文，英文就用英文\n"
            "- 丢掉栏目名、话题标签、【】里的修饰、UP 主名等噪声\n"
            '- 不能含 / \\ : * ? " < > | 等文件名非法字符'
        ),
        user=f"视频标题：{video_title}",
        schema=_ShortTitle,
        max_tokens=2000,
    )
    return out.short_title.strip()
