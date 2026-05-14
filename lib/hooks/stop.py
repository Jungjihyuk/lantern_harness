"""stop hook — 응답 종료 직전 검증.

핵심 role:
  - stop_validation: guard.policies.stop_validation.checks 실행. 실패 시 block 또는 warn
  - trace_log:       기록

stdout:
  {"decision": "allow"}                          — 통과
  {"decision": "block", "reason": "..."}         — 종료 차단 (on_fail: block)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from lib.hooks._common import (
    active_roles,
    append_decision,
    append_trace,
    emit_decision,
    load_context,
    read_envelope,
)

HOOK_ID = "stop"


def run_checks(checks: list, project_root: Path) -> list[tuple[str, bool, str]]:
    """각 check 실행. 결과 [(label, ok, output_tail)]."""
    results = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        cmd = check.get("command") or check.get("script")
        if not cmd:
            continue
        try:
            r = subprocess.run(
                cmd, shell=True, cwd=str(project_root),
                capture_output=True, text=True, timeout=120, check=False,
            )
            ok = r.returncode == 0
            tail = (r.stdout + r.stderr).strip().splitlines()
            tail_str = " | ".join(tail[-3:])
            results.append((cmd, ok, tail_str))
        except Exception as e:
            results.append((cmd, False, f"exec error: {e}"))
    return results


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

    decision_pair: tuple[str, str] = ("", "")

    # stop_validation
    if "stop_validation" in roles:
        policy = compose.policies.get("stop_validation", {}) or {}
        if policy.get("enabled"):
            checks = policy.get("checks", []) or []
            on_fail = policy.get("on_fail", "warn")
            results = run_checks(checks, project_root)
            failed = [(c, t) for c, ok, t in results if not ok]
            if failed:
                fails_str = "; ".join(f"{c}: {t}" for c, t in failed[:3])
                if on_fail == "block":
                    decision_pair = ("block", f"stop_validation 실패: {fails_str}")
                else:  # warn
                    # block 안 하고 trace 만 기록
                    try:
                        append_trace(project_root, session_id, {
                            "hook": HOOK_ID,
                            "stop_validation": "warn",
                            "failed": fails_str,
                        })
                    except Exception:
                        pass

    # trace_log
    if "trace_log" in roles:
        try:
            append_trace(project_root, session_id, {
                "hook": HOOK_ID,
                "decision": decision_pair[0] or "allow",
                "reason": decision_pair[1] or None,
            })
        except Exception:
            pass

    if decision_pair[0]:
        try:
            append_decision(project_root, session_id, {
                "hook": HOOK_ID,
                "decision": decision_pair[0],
                "reason": decision_pair[1],
            })
        except Exception:
            pass
        emit_decision(decision_pair[0], reason=decision_pair[1])
    else:
        emit_decision("allow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
