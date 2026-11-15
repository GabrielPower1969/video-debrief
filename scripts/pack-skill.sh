#!/usr/bin/env bash
# 把 skills/video-debrief 打成一个可上传的 skill 包：dist/video-debrief-skill.zip
#
# Claude.ai / Claude Desktop 的自定义 skill 上传要求 zip 的**根目录就是 skill 文件夹**
# （即解压后直接是 video-debrief/SKILL.md），所以这里从 skills/ 下打包而不是仓库根。
#
# 改过 SKILL.md / 模板 / 脚本之后记得重跑一次，再把 dist/ 一起提交——
# README 里给用户的下载链接直接指向仓库里的这个文件。
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="dist/video-debrief-skill.zip"
mkdir -p dist
rm -f "$OUT"

(cd skills && zip -r -q "../$OUT" video-debrief \
  -x '*/__pycache__/*' '*.pyc' '*.DS_Store')

echo "→ $OUT"
unzip -l "$OUT"
