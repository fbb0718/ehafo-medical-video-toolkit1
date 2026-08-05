#!/bin/zsh

set -euo pipefail
cd -- "$(dirname -- "$0")"

python_command=".venv-fast/bin/python"
if [[ ! -x "$python_command" ]]; then
  python_command="$(command -v python3 || true)"
fi
if [[ -z "$python_command" ]]; then
  echo "未找到 Python 3，请先双击‘首次安装快速版.command’。"
  exit 1
fi

"$python_command" scripts/check_environment.py

variant="fast-hq-aligned-v5.3-$(date +%Y%m%d-%H%M%S)"
read "background?请选择背景 white/green [white]："
background="${background:-white}"
"$python_command" scripts/run_fast_question_project.py --variant "$variant" --background "$background"

echo
echo "生成完成，视频位于：$(pwd)/renders"
read "reply?按回车键关闭窗口。" || true
