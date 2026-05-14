"""post_tool_use hook — 도구 호출 후 status·trace 갱신.

핵심 role:
  - status_track: Read 호출이면 required-status.json 의 status 갱신 (unread → read)
  - edit_track:   변경 도구 (Edit/Write/...) 면 edit_history 에 path append
                  (cognitive_guard 의 per_session 누적 / loop_detection 의 입력)
  - trace_log:    이벤트 기록

stdout: {"decision": "allow"}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from lib.hooks._common import (
    active_roles,
    append_trace,
    emit_decision,
    load_context,
    read_envelope,
)

HOOK_ID = "post_tool_use"

MUTATING_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
MAX_HISTORY = 50


def track_edit(project_root: Path, session_id: str, tool_name: str, tool_args: dict) -> None:
    """cognitive-guard.json 의 edit_history 에 path append (변경 도구만)."""
    if tool_name not in MUTATING_TOOLS:
        return
    file_path = tool_args.get("file_path") or tool_args.get("notebook_path") or tool_args.get("path")
    if not file_path:
        return
    guard_file = project_root / ".harness" / "runtime" / "sessions" / session_id / "cognitive-guard.json"
    guard = {"changed_files": [], "diff_lines_total": 0, "new_files_total": 0, "edit_history": [], "bypass_used": False}
    if guard_file.exists():
        try:
            guard.update(json.loads(guard_file.read_text(encoding="utf-8")))
        except Exception:
            pass
    history = guard.get("edit_history", []) or []
    history.append(file_path)
    guard["edit_history"] = history[-MAX_HISTORY:]
    if file_path not in (guard.get("changed_files") or []):
        guard.setdefault("changed_files", []).append(file_path)
    try:
        guard_file.parent.mkdir(parents=True, exist_ok=True)
        guard_file.write_text(json.dumps(guard, indent=2, ensure_ascii=False))
    except Exception:
        pass


def track_read_status(project_root: Path, session_id: str, tool_name: str, tool_args: dict) -> None:
    """Read 도구 호출이면 required-status.json 의 해당 path 를 read 로 마킹."""
    if tool_name != "Read":
        return
    file_path = tool_args.get("file_path") or tool_args.get("path")
    if not file_path:
        return
    status_file = project_root / ".harness" / "runtime" / "sessions" / session_id / "required-status.json"
    if not status_file.exists():
        return
    try:
        status = json.loads(status_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return
    # 매칭 — basename 또는 path 그대로
    candidates = {file_path, Path(file_path).name}
    for key in list(status.keys()):
        if key in candidates or Path(key).name == Path(file_path).name:
            if isinstance(status[key], dict):
                status[key]["status"] = "read"
    try:
        status_file.write_text(json.dumps(status, indent=2, ensure_ascii=False))
    except Exception:
        pass


def main() -> int:
    envelope = read_envelope()
    session_id = envelope.get("session_id") or "unknown"
    project_root = Path(envelope.get("project_root") or ".").resolve()
    tool_name = envelope.get("tool_name", "")
    tool_args = envelope.get("tool_args") or {}

    ctx = load_context(project_root)
    if ctx is None:
        emit_decision("allow")
        return 0
    compose, _ = ctx
    roles = active_roles(compose, HOOK_ID)

    if "status_track" in roles:
        try:
            track_read_status(project_root, session_id, tool_name, tool_args)
        except Exception:
            pass

    if "edit_track" in roles:
        try:
            track_edit(project_root, session_id, tool_name, tool_args)
        except Exception:
            pass

    if "trace_log" in roles:
        try:
            append_trace(project_root, session_id, {
                "hook": HOOK_ID,
                "tool_name": tool_name,
                "file_path": tool_args.get("file_path") or tool_args.get("path"),
            })
        except Exception:
            pass

    emit_decision("allow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
