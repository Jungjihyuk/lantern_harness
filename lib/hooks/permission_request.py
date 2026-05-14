"""permission_request hook — 도구 권한 요청.

핵심 role:
  - permission_gate: 단순 통과 (구체 정책은 미래)
  - trace_log:       기록

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

HOOK_ID = "permission_request"


def main() -> int:
    envelope = read_envelope()
    session_id = envelope.get("session_id") or "unknown"
    project_root = Path(envelope.get("project_root") or ".").resolve()
    tool_name = envelope.get("tool_name", "")
    permission = envelope.get("permission") or envelope.get("requested_permission", "")

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
                "permission": permission,
            })
        except Exception:
            pass

    # permission_gate — 현재는 단순 allow. 향후 정책 도입 시 deny 가능.
    emit_decision("allow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
