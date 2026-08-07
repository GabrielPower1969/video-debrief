"""一条命令：视频链接 → output/<短标题>/（report.html + srt + audio.mp3）。

    ./handle "<YouTube 或 Bilibili 链接>"

流程：下载音频（+能拿到的原生字幕）→ 没字幕就 Whisper 转写 → 统一成 SRT
→ 原文非中文则逐行翻译 → LLM 摘要（章节/观点/金句）→ 渲染带播放器的 HTML 报告。

两个刻意的设计（与 video2doc 一脉相承）：
  1. LLM 凭证最先检查——ASR 可能跑几十分钟，不该烧完才发现没 key。
  2. 摘要失败就报错，绝不静默降级；但转写/SRT 在摘要前已落盘，可抢救。
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v2d import media, report
from v2d.srt import Line, clean_lines, fmt_mmss, is_chinese, parse_srt, write_srt


def _sanitize(name: str) -> str:
    for ch in '/\\:*?"<>|':
        name = name.replace(ch, "")
    return name.strip() or "未命名视频"


def _bi(bi) -> dict:
    return {"zh": bi.zh, "en": bi.en}


def _word_count(lines: list[Line], is_zh: bool) -> str:
    if is_zh:
        return f"{sum(len(l.text) for l in lines):,} 字"
    return f"{sum(len(l.text.split()) for l in lines):,} 词"


def run(url: str, *, output_root: str = "output", asr_model: str = "small",
        force_asr: bool = False, cookies_from_browser: str | None = None,
        cookies_file: str | None = None) -> Path:
    from v2d import llm

    # 0) 先检查 LLM 凭证
    if not llm.is_llm_available():
        raise SystemExit(
            "没有可用的 LLM 凭证，摘要无法进行。\n"
            "  请 export ANTHROPIC_API_KEY=...（或 `ant auth login`）。\n"
            "（提前检查是有意的：ASR 可能要跑几十分钟，不该等跑完才失败。）"
        )

    # 1) 下载
    print(f"[v2d] 下载音频/字幕: {url}")
    root = Path(output_root)
    workdir = root / "_work"
    if workdir.exists():
        shutil.rmtree(workdir)
    meta = media.download(url, workdir, cookies_from_browser=cookies_from_browser,
                          cookies_file=cookies_file)
    print(f"[v2d] 标题: {meta['title']}")

    # 2) 拿转写行：原生字幕优先，否则 Whisper
    lang = meta["language"]
    if meta["sub_path"] and not force_asr:
        lines = clean_lines(parse_srt(meta["sub_path"].read_text(encoding="utf-8", errors="ignore")))
        source_label = f"平台字幕（{meta['sub_path'].name.split('.')[-2]}）"
        print(f"[v2d] 使用平台字幕: {len(lines)} 行")
    else:
        from v2d.asr import transcribe
        print(f"[v2d] 无可用字幕，本地转写中（faster-whisper {asr_model}，可能需要几分钟）...")
        lines, lang = transcribe(meta["audio_path"], model_size=asr_model)
        lines = clean_lines(lines)
        source_label = f"Whisper {asr_model} 转写"
        print(f"[v2d] 转写完成: {len(lines)} 行，语言={lang}")
    if not lines:
        raise SystemExit("没有得到任何转写内容，无法继续。")

    sample = " ".join(l.text for l in lines[:80])
    is_zh = (lang or "").startswith("zh") or is_chinese(sample)
    lang = "zh" if is_zh else (lang or "en")

    # 3) 原文非中文 → 逐行翻译（先落盘原文 SRT，翻译/摘要失败也有东西可抢救）
    write_srt(lines, workdir / "transcript.srt")
    if not is_zh:
        from v2d.translate import translate_lines
        print(f"[v2d] 原文为 {lang}，逐行翻译中 ...")
        translate_lines(lines)
        write_srt(lines, workdir / "transcript.zh.srt", use_zh=True)

    # 4) 摘要
    print("[v2d] LLM 摘要 ...")
    from v2d.summarize import summarize
    core, chapters = summarize(lines, title=meta["title"], is_zh=is_zh)
    short = _sanitize(llm.short_title(meta["title"]))
    print(f"[v2d] 短标题: {short}")

    # 5) 组装报告数据 + 渲染
    duration = meta["duration"] or (lines[-1].end if lines else 0)
    data = {
        "meta": {
            "short_title": short,
            "title": meta["title"],
            "platform": meta["platform"],
            "uploader": meta["uploader"],
            "upload_date": meta["upload_date"],
            "url": meta["url"],
            "duration": duration,
            "lang": lang,
            "source_label": source_label,
            "generated_at": datetime.date.today().isoformat(),
        },
        "audio": "audio.mp3",
        "overview": _bi(core.overview),
        "topics": core.topics,
        "stats": [
            {"label": "时长", "value": fmt_mmss(duration)},
            {"label": "章节", "value": str(len(chapters))},
            {"label": "核心观点", "value": str(len(core.viewpoints))},
            {"label": "转写体量", "value": _word_count(lines, is_zh)},
        ],
        "viewpoints": [
            {"title": _bi(v.title), "detail": _bi(v.detail),
             "quote": v.quote, "quote_zh": v.quote_zh, "t": v.t}
            for v in core.viewpoints
        ],
        "chapters": [
            {"title": _bi(c.title), "summary": _bi(c.summary),
             "t_start": c.t_start, "t_end": c.t_end}
            for c in chapters
        ],
        "quotes": [{"text": q.text, "text_zh": q.text_zh, "t": q.t} for q in core.quotes],
        "transcript": [{"t0": l.start, "t1": l.end, "text": l.text, "zh": l.zh} for l in lines],
    }
    (workdir / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    report.render(data, workdir / "report.html")

    # 6) 清掉中间产物，目录改名为短标题
    for p in workdir.glob("media.*"):
        p.unlink()
    out_dir = root / short
    if out_dir.exists():
        shutil.rmtree(out_dir)
    workdir.rename(out_dir)
    return out_dir


# ---------------------------------------------------------------- demo --------

def demo(output_root: str = "output") -> Path:
    """离线渲染一份双语示例报告（不联网、不调 LLM），用于校验模板效果。"""
    out_dir = Path(output_root) / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    audio = _demo_audio(out_dir)

    tr = [
        (0, 6, "I spent eleven years at a big tech company, and last spring I walked away.",
         "我在一家大厂待了十一年，去年春天我离开了。"),
        (6, 14, "Everyone said I was crazy — the title, the salary, the stock refreshers.",
         "所有人都说我疯了——职级、薪水、股票续授。"),
        (14, 23, "But the calendar owned me. Thirty hours of meetings a week is not a career, it's a treadmill.",
         "但日历支配着我。一周三十小时的会议不是事业，是跑步机。"),
        (23, 33, "The turning point was my daughter asking why I only existed on weekends.",
         "转折点是我女儿问我，为什么我只在周末存在。"),
        (33, 44, "So we ran the numbers: our savings could buy us four years of ordinary life back home.",
         "于是我们算了笔账：积蓄够我们回老家过四年普通日子。"),
        (44, 55, "Quitting isn't the brave part. The brave part is admitting the ladder was leaning on the wrong wall.",
         "辞职不是勇敢的部分。勇敢的是承认梯子靠错了墙。"),
        (55, 66, "Now I code two hours a day on my own product, and it makes a tenth of my old salary.",
         "现在我每天为自己的产品写两小时代码，收入是过去的十分之一。"),
        (66, 78, "But I cook, I nap, I pick her up from school. Nobody pays you for that, and nothing pays more.",
         "但我做饭、午睡、接她放学。没人为此付你钱，却没有什么比这更值。"),
    ]
    data = {
        "meta": {
            "short_title": "离开大厂这一年",
            "title": "I Quit My $1M Big-Tech Job to Move Back Home — One Year Later",
            "platform": "Youtube", "uploader": "Demo Channel", "upload_date": "20260601",
            "url": "https://example.com/demo", "duration": 78, "lang": "en",
            "source_label": "示例数据（--demo）", "generated_at": datetime.date.today().isoformat(),
        },
        "audio": audio,
        "overview": {
            "zh": "讲述者回顾了从年薪百万的大厂管理岗辞职回老家的一年：促使他离开的不是倦怠本身，而是意识到时间被会议完全占有、家庭角色长期缺席。他用积蓄换出四年的缓冲期，把工作压缩成每天两小时的个人产品开发，收入骤降但可支配的生活大幅回归。",
            "en": "A former big-tech manager reflects on the year since quitting: it wasn't burnout but the realization that meetings owned his calendar and his family barely saw him. Savings bought a four-year buffer; work shrank to two focused hours a day on his own product — a tenth of the income, and most of his life back.",
        },
        "topics": ["职业选择", "大厂围城", "家庭与时间", "半退休实验"],
        "stats": [
            {"label": "时长", "value": "01:18"},
            {"label": "章节", "value": "3"},
            {"label": "核心观点", "value": "3"},
            {"label": "转写体量", "value": "128 词"},
        ],
        "viewpoints": [
            {"title": {"zh": "高薪的真实价格是日历的所有权", "en": "The real price of the salary is your calendar"},
             "detail": {"zh": "职级和股票是可见的收益，而不可见的成本是每周三十小时会议对时间的整体征用——他称之为跑步机而非事业。",
                        "en": "Title and stock are the visible upside; the invisible cost is thirty meeting-hours a week — a treadmill, not a career."},
             "quote": "Thirty hours of meetings a week is not a career, it's a treadmill.",
             "quote_zh": "一周三十小时的会议不是事业，是跑步机。", "t": 14},
            {"title": {"zh": "触发离开的是家庭角色的失位", "en": "The trigger was absence at home"},
             "detail": {"zh": "让他下决心的不是绩效或倦怠，而是女儿的一句『为什么你只在周末存在』——外部评价体系之外的信号。",
                        "en": "Not performance or burnout — his daughter asking why he only existed on weekends."},
             "quote": "The turning point was my daughter asking why I only existed on weekends.",
             "quote_zh": "转折点是我女儿问我，为什么我只在周末存在。", "t": 23},
            {"title": {"zh": "勇敢的不是辞职，而是承认方向错了", "en": "Courage is admitting the ladder was wrong"},
             "detail": {"zh": "他把叙事从『放弃高薪』改写为『纠正方向』：梯子爬得再高，靠错墙就是负资产。",
                        "en": "He reframes it: however high the ladder, leaning on the wrong wall makes climbing a liability."},
             "quote": "The brave part is admitting the ladder was leaning on the wrong wall.",
             "quote_zh": "勇敢的是承认梯子靠错了墙。", "t": 44},
        ],
        "chapters": [
            {"title": {"zh": "离开的决定", "en": "The Decision"},
             "summary": {"zh": "十一年大厂生涯与外界眼中『疯了』的辞职决定。",
                         "en": "Eleven years in, and a decision everyone called crazy."},
             "t_start": 0, "t_end": 23},
            {"title": {"zh": "账本与底气", "en": "Running the Numbers"},
             "summary": {"zh": "用积蓄换四年缓冲期，把风险变成一道算术题。",
                         "en": "Savings as a four-year buffer — risk reduced to arithmetic."},
             "t_start": 23, "t_end": 44},
            {"title": {"zh": "一年后的生活", "en": "One Year Later"},
             "summary": {"zh": "每天两小时的自有产品开发，十分之一的收入，成倍归还的生活。",
                         "en": "Two hours a day on his own product; a tenth of the pay, most of life back."},
             "t_start": 44, "t_end": 78},
        ],
        "quotes": [
            {"text": "Quitting isn't the brave part. The brave part is admitting the ladder was leaning on the wrong wall.",
             "text_zh": "辞职不是勇敢的部分。勇敢的是承认梯子靠错了墙。", "t": 44},
            {"text": "Nobody pays you for that, and nothing pays more.",
             "text_zh": "没人为此付你钱，却没有什么比这更值。", "t": 66},
        ],
        "transcript": [{"t0": a, "t1": b, "text": t, "zh": z} for a, b, t, z in tr],
    }
    report.render(data, out_dir / "report.html")
    print(f"[v2d] demo 报告 → {out_dir / 'report.html'}")
    return out_dir


def _demo_audio(out_dir: Path) -> str | None:
    """用 imageio-ffmpeg 生成 80 秒示例音频；生成失败就返回 None（播放器自动隐藏）。"""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        target = out_dir / "audio.mp3"
        subprocess.run(
            [get_ffmpeg_exe(), "-y", "-f", "lavfi", "-i",
             "sine=frequency=440:duration=80", "-af", "volume=0.12",
             "-q:a", "9", str(target)],
            check=True, capture_output=True,
        )
        return "audio.mp3"
    except Exception:
        return None


def main():
    p = argparse.ArgumentParser(description="视频链接 → 带播放器的 HTML 分析报告")
    p.add_argument("url", nargs="?", help="YouTube / Bilibili 视频链接")
    p.add_argument("--demo", action="store_true", help="离线渲染示例报告（校验模板）")
    p.add_argument("--asr-model", default="small",
                   help="faster-whisper 规格：tiny/base/small/medium/large-v3")
    p.add_argument("--force-asr", action="store_true", help="忽略平台字幕，强制 Whisper 转写")
    p.add_argument("--output-root", default="output")
    p.add_argument("--cookies-from-browser", metavar="BROWSER",
                   help="从本机浏览器读 cookie（chrome/edge/firefox/safari），用于需登录的视频")
    p.add_argument("--cookies", metavar="FILE", help="Netscape 格式 cookie 文件")
    a = p.parse_args()

    if a.demo:
        out = demo(a.output_root)
    elif not a.url:
        p.error("需要视频链接（或用 --demo）")
    else:
        out = run(a.url, output_root=a.output_root, asr_model=a.asr_model,
                  force_asr=a.force_asr, cookies_from_browser=a.cookies_from_browser,
                  cookies_file=a.cookies)
    print(f"\n完成 → {out.resolve()}")
    for f in sorted(out.iterdir()):
        print("  -", f.name)


if __name__ == "__main__":
    main()
