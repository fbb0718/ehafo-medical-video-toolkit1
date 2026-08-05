#!/bin/zsh

set -euo pipefail
cd -- "$(dirname -- "$0")"

for command_name in python3 ffmpeg ffprobe; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "缺少 $command_name。建议执行：brew install python ffmpeg"
    exit 1
  fi
done

python3 scripts/check_environment.py --preinstall

python3 -m venv .venv-fast
.venv-fast/bin/python -m pip install --upgrade pip
.venv-fast/bin/python -m pip install -r requirements-fast.txt
.venv-fast/bin/python scripts/check_environment.py

echo
echo "快速版安装完成。"
read "reply?按回车键关闭窗口。" || true
