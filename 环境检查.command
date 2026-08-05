#!/bin/zsh

set -euo pipefail
cd -- "$(dirname -- "$0")"

python_command=".venv-fast/bin/python"
if [[ ! -x "$python_command" ]]; then
  python_command="$(command -v python3 || true)"
fi
if [[ -z "$python_command" ]]; then
  echo "缺少 Python 3。建议执行：brew install python ffmpeg"
  exit 1
fi

"$python_command" scripts/check_environment.py

echo
echo "环境检查通过，可以生成快速视频。"
read "reply?按回车键关闭窗口。" || true
