#!/bin/zsh

set -euo pipefail
cd -- "$(dirname -- "$0")"

python_command="$(command -v python3.12 || command -v python3.11 || command -v python3 || true)"
if [[ -z "$python_command" ]]; then
  echo "缺少 Python 3.11/3.12。建议执行：brew install python@3.12 ffmpeg node@22"
  exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  echo "缺少 Node.js 22 或更高版本。"
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "缺少 FFmpeg。建议执行：brew install ffmpeg"
  exit 1
fi

"$python_command" scripts/check_environment.py --preinstall --include-high-quality
"$python_command" -m venv .venv
.venv/bin/python -m pip install -r requirements-fast.txt
if [[ "$(uname -m)" == "arm64" ]]; then
  .venv/bin/python -m pip install -r requirements-voice-apple-silicon.txt
fi
npm ci
check_arguments=("scripts/check_environment.py" "--include-high-quality")
if [[ "$(uname -m)" == "arm64" ]]; then
  check_arguments+=("--include-voice")
fi
.venv/bin/python "${check_arguments[@]}"

echo
echo "安装完成。"
read "reply?按回车键关闭窗口。" || true
