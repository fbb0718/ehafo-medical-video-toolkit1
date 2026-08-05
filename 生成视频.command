#!/bin/zsh

set -euo pipefail
cd -- "$(dirname -- "$0")"

python_command=".venv/bin/python"
if [[ ! -x "$python_command" ]]; then
  python_command="$(command -v python3 || true)"
fi
if [[ -z "$python_command" ]]; then
  echo "未找到 Python 3，请先双击‘首次安装.command’。"
  exit 1
fi

read "reuse_voice?是否使用已经审核的配音？[Y/n]："
arguments=("scripts/run_question_project.py" "--quality" "high")
read "voice?请选择音色 yhn/mcy [yhn]："
voice="${voice:-yhn}"
arguments+=("--voice" "$voice")
read "background?请选择背景 white/green [white]："
background="${background:-white}"
arguments+=("--background" "$background")
if [[ "$reuse_voice" != [nN] ]]; then
  arguments+=("--skip-voice")
  "$python_command" scripts/check_environment.py --include-high-quality
else
  "$python_command" scripts/check_environment.py --include-high-quality --include-voice
fi

"$python_command" "${arguments[@]}"

echo
echo "生成完成，视频位于：$(pwd)/renders"
read "reply?按回车键关闭窗口。" || true
