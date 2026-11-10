"""Handle a Kimi Code Stop hook using local state."""

import hashlib
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path


QUIET_SECONDS = 4 * 60 * 60
STATE_TTL_SECONDS = 7 * 24 * 60 * 60


def modified_at(path):
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0


def reminder_command(tool, session_id):
    arguments = [sys.executable, str(tool), "add", "要点内容", "--role", "assistant", "--session", session_id]
    if os.name == "nt":
        quoted = ("'" + argument.replace("'", "''") + "'" for argument in arguments)
        return "& " + " ".join(quoted)
    return shlex.join(arguments)


def run(home, tool):
    payload = json.load(sys.stdin)
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        return 0

    state_dir = home / "hook_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for stale_state in state_dir.glob("memory-reminder-*.stamp"):
        if modified_at(stale_state) < now - STATE_TTL_SECONDS:
            stale_state.unlink(missing_ok=True)

    database = home / "chroma" / "chroma.sqlite3"
    last_write = max(modified_at(database), modified_at(database.with_suffix(".sqlite3-wal")))
    session_key = hashlib.sha256(session_id.encode("ascii")).hexdigest()
    state = state_dir / f"memory-reminder-{session_key}.stamp"
    try:
        with state.open("x", encoding="ascii") as handle:
            handle.write(str(last_write))
    except FileExistsError:
        last_reminder_write = float(state.read_text(encoding="ascii"))
        if last_write <= last_reminder_write or now < last_write + QUIET_SECONDS:
            return 0
        state.write_text(str(last_write), encoding="ascii")

    print("请检查本会话是否有值得长期保存的决定或发现。", file=sys.stderr)
    print("需要补录时运行以下命令，并将示例内容替换成实际要点。", file=sys.stderr)
    print(reminder_command(tool, session_id), file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        result = run(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, ValueError):
        result = 0
    sys.exit(result)
