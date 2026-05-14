"""post_tool_use hook — 도구 호출 후 status·trace 갱신.

핵심 role:
  - status_track: Read 호출이면 required-status.json 의 status 갱신 (unread → read)
  - trace_log:    이벤트 기록

(metric_collect 는 정밀 측정 미구현 — 미래에 trace 데이터로 후처리)

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
