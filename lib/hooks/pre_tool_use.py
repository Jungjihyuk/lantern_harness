"""pre_tool_use hook — 도구 호출 직전 다중 가드.

처리 순서 (deny 우선):
  1. path_blocklist  — sensitive path (.env, secrets/ 등) 모든 도구 차단 (hard_stop)
  2. required_check  — Required Context 미읽음 → 변경 도구만 차단
  3. context_gating  — triggered 매칭 + 해당 doc 미읽음 → 차단
  4. cognitive_guard — per_call / per_session 초과 → 차단 (bypass marker 시 skip)
  5. loop_detection  — compose state.workflows 에 ralph 등록 시 자동 활성
  6. trace_log       — 결정과 무관하게 기록 (항상)

stdin envelope:
  {"hook_type": "pre_tool_use", "session_id": "...", "project_root": "...",
   "tool_name": "Edit", "tool_args": {...}}

stdout: {"decision": "allow|self_correct|hard_stop", "reason": "..."}
"""
from __future__ import annotations

import fnmatch
import json
import os
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

HOOK_ID = "pre_tool_use"

MUTATING_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit", "Bash"}


# ───────────────────── 추출 헬퍼 ─────────────────────

def get_file_path(tool_args: dict) -> str | None:
    """tool_args 에서 path 추출 (tool 별 키 다름)."""
    return (tool_args.get("file_path")
            or tool_args.get("notebook_path")
            or tool_args.get("path"))


def estimate_diff_lines(tool_name: str, tool_args: dict) -> int:
    """변경 line 수 추정 (대략)."""
    if tool_name == "Edit":
        new = tool_args.get("new_string", "") or ""
        old = tool_args.get("old_string", "") or ""
        return abs(new.count("\n") - old.count("\n")) + max(1, max(new.count("\n"), old.count("\n")))
    if tool_name == "Write":
        return (tool_args.get("content", "") or "").count("\n") + 1
    if tool_name == "NotebookEdit":
        return (tool_args.get("new_source", "") or "").count("\n") + 1
    if tool_name == "MultiEdit":
        edits = tool_args.get("edits", []) or []
        return sum(abs((e.get("new_string", "") or "").count("\n") -
                       (e.get("old_string", "") or "").count("\n"))
                   for e in edits)
    return 0


# ───────────────────── role 핸들러 ─────────────────────

def check_path_blocklist(file_path: str | None, compose) -> tuple[bool, str]:
    """sensitive path 면 (True, reason)."""
    if not file_path:
        return False, ""
    patterns = compose.policies.get("path_blocklist", {}).get("patterns", []) or []
    norm = file_path.replace("\\", "/").lstrip("./")
    for pat in patterns:
        if fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(file_path, pat):
            return True, f"path_blocklist 매칭: '{file_path}' (pattern: {pat})"
    return False, ""


def check_required_unread(project_root: Path, session_id: str) -> tuple[str, str]:
    """미읽음 required 있으면 (decision, reason). 없으면 ('', '')."""
    status_file = project_root / ".harness" / "runtime" / "sessions" / session_id / "required-status.json"
    if not status_file.exists():
        return "", ""
    try:
        status = json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return "", ""
    unread_hard = []
    unread_soft = []
    for path, info in (status or {}).items():
        if not isinstance(info, dict):
            continue
        if info.get("status") == "unread":
            if info.get("on_deny") == "hard_stop":
                unread_hard.append(path)
            else:
                unread_soft.append(path)
    if unread_hard:
        return "hard_stop", f"Required Context 미읽음 (hard_stop): {', '.join(unread_hard)}"
    if unread_soft:
        return "self_correct", f"Required Context 미읽음: {', '.join(unread_soft)}"
    return "", ""


def check_context_gating(file_path: str | None, compose, project_root: Path, session_id: str) -> tuple[str, str]:
    """triggered 패턴 매칭 + 해당 doc 미읽음 시 decision."""
    if not file_path:
        return "", ""
    triggered = [e for e in compose.entries
                 if e.domain == "cognition" and e.section == "context.triggered"]
    if not triggered:
        return "", ""
    norm = file_path.replace("\\", "/")
    status_file = project_root / ".harness" / "runtime" / "sessions" / session_id / "required-status.json"
    status = {}
    if status_file.exists():
        try:
            status = json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    for e in triggered:
        when = e.extras.get("when", "")
        if not when:
            continue
        if fnmatch.fnmatch(norm, when):
            src = e.extras.get("src_path")
            if src and status.get(src, {}).get("status") == "unread":
                on_deny = e.extras.get("on_deny", "self_correct")
                label = e.extras.get("label", "") or e.id
                return on_deny, f"trigger 매칭 ({when}) → {label} (`{src}`) 미읽음"
    return "", ""


def check_cognitive_guard(tool_name: str, tool_args: dict, compose, project_root: Path, session_id: str) -> tuple[str, str]:
    """diff lines / new files 누적 검사."""
    policies = compose.policies.get("cognitive_guard", {})
    if not policies:
        return "", ""
    guard_file = project_root / ".harness" / "runtime" / "sessions" / session_id / "cognitive-guard.json"
    guard = {"changed_files": [], "diff_lines_total": 0, "new_files_total": 0, "edit_history": [], "bypass_used": False}
    if guard_file.exists():
        try:
            guard.update(json.loads(guard_file.read_text(encoding="utf-8")))
        except Exception:
            pass

    # bypass marker 사용 가능 — 한 번 통과 후 reset
    if guard.get("bypass_used"):
        guard["bypass_used"] = False
        try:
            guard_file.write_text(json.dumps(guard, indent=2))
        except Exception:
            pass
        return "", ""

    per_call = policies.get("per_call", {}) or {}
    per_sess = policies.get("per_session", {}) or {}
    on_breach = policies.get("on_breach", "ask_human")
    bypass_marker = policies.get("bypass_marker", "@harness allow-large")

    diff = estimate_diff_lines(tool_name, tool_args)

    # per_call
    mdl = per_call.get("max_diff_lines")
    if mdl is not None and diff > mdl:
        decision = "self_correct" if on_breach == "self_correct" else "hard_stop"
        return decision, (f"per_call.max_diff_lines {mdl} 초과 (추정 {diff}). "
                          f"의도된 큰 변경이면 prompt 에 '{bypass_marker}' 마커 추가.")

    # per_session — 누적
    new_total = guard.get("diff_lines_total", 0) + diff
    msdl = per_sess.get("max_diff_lines")
    if msdl is not None and new_total > msdl:
        decision = "self_correct" if on_breach == "self_correct" else "hard_stop"
        return decision, f"per_session.max_diff_lines {msdl} 초과 (누적 {new_total})"

    return "", ""


def check_loop_detection(file_path: str | None, compose, project_root: Path, session_id: str) -> tuple[str, str]:
    """compose state.workflows 에 ralph 있으면 자동 활성. edit_history 같은 path N번이면 deny."""
    if not file_path:
        return "", ""
    # ralph workflow 활성 여부 — state.workflows entry 중 id == 'ralph' 있는지
    ralph_active = any(e.domain == "state" and e.section == "workflows" and e.id == "ralph"
                       for e in compose.entries)
    if not ralph_active:
        return "", ""
    policies = compose.policies.get("loop_detection", {}) or {}
    threshold = policies.get("consecutive_same_path", 3)
    on_loop = policies.get("on_loop", "self_correct")

    guard_file = project_root / ".harness" / "runtime" / "sessions" / session_id / "cognitive-guard.json"
    if not guard_file.exists():
        return "", ""
    try:
        guard = json.loads(guard_file.read_text(encoding="utf-8"))
    except Exception:
        return "", ""
    history = guard.get("edit_history", [])
    last = history[-(threshold - 1):] if threshold > 1 else []
    if len(last) >= threshold - 1 and all(p == file_path for p in last):
        return on_loop, f"loop_detection: 같은 path '{file_path}' {threshold}회 연속 수정 시도"
    return "", ""


# ───────────────────── 메인 ─────────────────────

def main() -> int:
    envelope = read_envelope()
    session_id = envelope.get("session_id") or "unknown"
    project_root = Path(envelope.get("project_root") or ".").resolve()
    tool_name = envelope.get("tool_name", "")
    tool_args = envelope.get("tool_args") or {}
    file_path = get_file_path(tool_args)

    ctx = load_context(project_root)
    if ctx is None:
        emit_decision("allow")
        return 0
    compose, _resolver = ctx
    roles = active_roles(compose, HOOK_ID)
    is_mutating = tool_name in MUTATING_TOOLS

    decision_result: tuple[str, str] = ("", "")

    # 1. path_blocklist — 모든 도구 (Read 포함)
    if "path_blocklist" in roles:
        deny, reason = check_path_blocklist(file_path, compose)
        if deny:
            decision_result = ("hard_stop", reason)

    # 2-4. 변경 도구만 — required / context / cognitive
    if not decision_result[0] and is_mutating:
        if "required_check" in roles:
            d, r = check_required_unread(project_root, session_id)
            if d:
                decision_result = (d, r)
        if not decision_result[0] and "context_gating" in roles:
            d, r = check_context_gating(file_path, compose, project_root, session_id)
            if d:
                decision_result = (d, r)
        if not decision_result[0] and "cognitive_guard" in roles:
            d, r = check_cognitive_guard(tool_name, tool_args, compose, project_root, session_id)
            if d:
                decision_result = (d, r)
        # 5. loop_detection 자동 — compose state.workflows 에 ralph 있을 때
        if not decision_result[0]:
            d, r = check_loop_detection(file_path, compose, project_root, session_id)
            if d:
                decision_result = (d, r)

    # 6. trace_log — 결정 무관 기록
    if "trace_log" in roles:
        try:
            append_trace(project_root, session_id, {
                "hook": HOOK_ID,
                "tool_name": tool_name,
                "file_path": file_path,
                "decision": decision_result[0] or "allow",
                "reason": decision_result[1] or None,
            })
        except Exception:
            pass

    # decision 응답
    if decision_result[0]:
        try:
            append_decision(project_root, session_id, {
                "hook": HOOK_ID,
                "tool_name": tool_name,
                "decision": decision_result[0],
                "reason": decision_result[1],
            })
        except Exception:
            pass
        emit_decision(decision_result[0], reason=decision_result[1])
    else:
        emit_decision("allow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
