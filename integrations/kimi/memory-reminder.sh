#!/usr/bin/env bash
# Kimi Code uses exit 2 and stderr to ask the assistant to continue after Stop.

omo_home="${OMO_HOME:-$HOME/.omo}"
hook_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd) || exit 0

if [[ -n "${OMO_PYTHON:-}" ]]; then
    python_exe="$OMO_PYTHON"
elif [[ -x "$omo_home/venv/Scripts/python.exe" ]]; then
    python_exe="$omo_home/venv/Scripts/python.exe"
elif [[ -x "$omo_home/venv/bin/python" ]]; then
    python_exe="$omo_home/venv/bin/python"
else
    exit 0
fi

memory_tool="${OMO_MEMORY_TOOL:-$omo_home/memory_tool.py}"
[[ -f "$memory_tool" ]] || exit 0
PYTHONIOENCODING=utf-8 "$python_exe" "$hook_dir/memory_reminder.py" "$omo_home" "$memory_tool"
[[ "$?" == 2 ]] && exit 2
exit 0
