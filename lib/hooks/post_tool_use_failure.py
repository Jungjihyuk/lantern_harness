"""post_tool_use_failure hook — 도구 호출 실패 시 trace.

핵심 role:
  - trace_log: 실패 이벤트 기록

(eval_verdict 는 eval 시스템과 결합 — 미래 작업)

stdout: {"decision": "allow"}
"""
from __future__ import annotations

import sys
from pathlib import Path

from lib.hooks._common import (
    active_roles,
    append_trace,
    emit_decision,
    load_context,
    read_envelope,
)

HOOK_ID = "post_tool_use_failure"


def main() -> int:
    envelope = read_envelope()
    session_id = envelope.get("session_id") or "unknown"
    project_root = Path(envelope.get("project_root") or ".").resolve()
    tool_name = envelope.get("tool_name", "")
    error = envelope.get("error") or envelope.get("error_message", "")

    ctx = load_context(project_root)
    if ctx is None:
        emit_decision("allow")
        return 0
    compose, _ = ctx
    roles = active_roles(compose, HOOK_ID)

    if "trace_log" in roles:
        try:
            append_trace(project_root, session_id, {
                "hook": HOOK_ID,
                "tool_name": tool_name,
                "error": error,
            })
        except Exception:
            pass

    emit_decision("allow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
