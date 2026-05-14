"""post_tool_batch hook — 도구 묶음 종료 후 trace.

핵심 role:
  - trace_log: batch 종료 기록

(metric_collect 는 정밀 측정 미구현)

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

HOOK_ID = "post_tool_batch"


def main() -> int:
    envelope = read_envelope()
    session_id = envelope.get("session_id") or "unknown"
    project_root = Path(envelope.get("project_root") or ".").resolve()

    ctx = load_context(project_root)
    if ctx is None:
        emit_decision("allow")
        return 0
    compose, _ = ctx
    roles = active_roles(compose, HOOK_ID)

    if "trace_log" in roles or "metric_collect" in roles:
        try:
            append_trace(project_root, session_id, {
                "hook": HOOK_ID,
                "batch_size": envelope.get("batch_size"),
            })
        except Exception:
            pass

    emit_decision("allow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
